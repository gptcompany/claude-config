#!/usr/bin/env python3
"""Install the minimal user-scoped Claude MCP allowlist."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVERS = {"context7", "serena"}
DEFAULT_LEGACY_PATHS = (Path.home() / ".mcp.json", Path.home() / ".claude/.mcp.json")
POLICY_BEGIN = "<!-- >>> claude-config-mcp-policy >>>"
POLICY_END = "<!-- <<< claude-config-mcp-policy <<<"


class InstallError(RuntimeError):
    pass


def _read_object(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked JSON file: {path}")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"expected a JSON object: {path}")
    return value, raw


def _validate_owned_regular_file(path: Path) -> None:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked file: {path}")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise InstallError(f"unable to inspect {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise InstallError(f"expected a regular file: {path}")
    if metadata.st_uid != os.geteuid():
        raise InstallError(f"file is not owned by the current user: {path}")


def _validate_template(
    template: dict[str, Any],
    executable: Callable[[str], bool],
) -> dict[str, dict[str, Any]]:
    servers = template.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != EXPECTED_SERVERS:
        raise InstallError("MCP template must contain exactly context7 and serena")

    context7 = servers.get("context7")
    if context7 != {"type": "http", "url": "https://mcp.context7.com/mcp"}:
        raise InstallError("Context7 must use the canonical secret-free HTTPS endpoint")

    serena = servers.get("serena")
    if not isinstance(serena, dict):
        raise InstallError("Serena MCP definition must be an object")
    if serena.get("type") != "stdio":
        raise InstallError("Serena must use stdio transport")
    command = str(serena.get("command") or "")
    args = serena.get("args")
    expected_args = [
        "serena",
        "start-mcp-server",
        "--context",
        "claude-code",
    ]
    if command != "/usr/bin/env" or args != expected_args:
        raise InstallError("Serena must use the canonical portable launcher")
    for required in (command, expected_args[0]):
        if not executable(required):
            raise InstallError(f"required MCP executable is unavailable: {required}")
    return servers


def _snapshot(path: Path) -> tuple[int, int, int, int] | None:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked file: {path}")
    if not path.exists():
        return None
    _validate_owned_regular_file(path)
    metadata = path.stat()
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _policy_target(path: Path) -> tuple[Path, tuple[int, int, str] | None]:
    if not path.is_symlink():
        return path, None
    try:
        link_metadata = path.lstat()
        link_value = os.readlink(path)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise InstallError(f"unable to resolve active CLAUDE.md symlink: {path}: {exc}") from exc
    _validate_owned_regular_file(resolved)
    return resolved, (link_metadata.st_dev, link_metadata.st_ino, link_value)


def _verify_policy_link(
    path: Path,
    resolved: Path,
    expected: tuple[int, int, str] | None,
) -> None:
    current_resolved, current = _policy_target(path)
    if current != expected or current_resolved != resolved:
        raise InstallError(f"active CLAUDE.md symlink changed concurrently: {path}")


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _backup(path: Path, raw: bytes, *, prefix: str, backup_dir: Path) -> Path:
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_dir / (
        f"{prefix}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        f"-{time.time_ns()}.json"
    )
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    return backup


def _managed_policy(active: str, policy: str) -> str:
    begin_count = active.count(POLICY_BEGIN)
    end_count = active.count(POLICY_END)
    if begin_count != end_count or begin_count > 1:
        raise InstallError("active CLAUDE.md has malformed MCP policy markers")
    block = f"{POLICY_BEGIN}\n{policy.strip()}\n{POLICY_END}"
    if begin_count == 0:
        separator = "\n\n" if active.strip() else ""
        return f"{active.rstrip()}{separator}{block}\n"
    start = active.index(POLICY_BEGIN)
    end = active.index(POLICY_END, start) + len(POLICY_END)
    return f"{active[:start]}{block}{active[end:]}"


def _legacy_drift(paths: Sequence[Path], *, check: bool) -> int:
    hardened = 0
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        _validate_owned_regular_file(path)
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            if check:
                raise InstallError(f"legacy MCP file has unsafe permissions: {path}")
            os.chmod(path, 0o600)
            hardened += 1
    return hardened


def _validate_legacy_paths(paths: Sequence[Path]) -> None:
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        _validate_owned_regular_file(path)


def install(
    template_path: Path,
    target: Path,
    *,
    legacy_paths: Sequence[Path],
    policy_template: Path | None = None,
    policy_target: Path | None = None,
    check: bool,
    executable: Callable[[str], bool] = lambda command: (
        os.access(command, os.X_OK) if "/" in command else shutil.which(command) is not None
    ),
) -> tuple[bool, bool, int]:
    template, _template_raw = _read_object(template_path)
    servers = _validate_template(template, executable)
    _validate_legacy_paths(legacy_paths)

    original_snapshot = _snapshot(target)
    if target.exists():
        active, original_raw = _read_object(target)
    else:
        active, original_raw = {}, b""
    merged = json.loads(json.dumps(active))
    merged["mcpServers"] = json.loads(json.dumps(servers))
    config_changed = merged != active

    policy_changed = False
    policy_snapshot: tuple[int, int, int, int] | None = None
    resolved_policy_target: Path | None = None
    policy_link: tuple[int, int, str] | None = None
    policy_raw = b""
    managed_policy = ""
    if (policy_template is None) != (policy_target is None):
        raise InstallError("MCP policy template and target must be provided together")
    if policy_template is not None and policy_target is not None:
        if policy_template.is_symlink():
            raise InstallError(f"refusing symlinked policy template: {policy_template}")
        try:
            policy = policy_template.read_text(encoding="utf-8")
        except OSError as exc:
            raise InstallError(f"unable to read MCP policy template: {exc}") from exc
        resolved_policy_target, policy_link = _policy_target(policy_target)
        policy_snapshot = _snapshot(resolved_policy_target)
        if resolved_policy_target.exists():
            try:
                policy_raw = resolved_policy_target.read_bytes()
                active_policy = policy_raw.decode("utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise InstallError(f"unable to read active CLAUDE.md: {exc}") from exc
        else:
            active_policy = ""
        managed_policy = _managed_policy(active_policy, policy)
        policy_changed = managed_policy != active_policy

    if check:
        _legacy_drift(legacy_paths, check=True)
        target_mode_drift = target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600
        policy_mode_drift = bool(
            resolved_policy_target
            and resolved_policy_target.exists()
            and stat.S_IMODE(resolved_policy_target.stat().st_mode) != 0o600
        )
        if config_changed or policy_changed or target_mode_drift or policy_mode_drift:
            raise InstallError(
                "Claude MCP drift: "
                f"config={'yes' if config_changed else 'no'}, "
                f"policy={'yes' if policy_changed else 'no'}, "
                f"mode={'yes' if target_mode_drift or policy_mode_drift else 'no'}"
            )
        return False, False, 0

    target_mode_drift = target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600
    policy_mode_drift = bool(
        resolved_policy_target
        and resolved_policy_target.exists()
        and stat.S_IMODE(resolved_policy_target.stat().st_mode) != 0o600
    )
    if (config_changed or target_mode_drift) and _snapshot(target) != original_snapshot:
        raise InstallError(f"Claude MCP config changed concurrently: {target}")
    if (
        policy_target is not None
        and resolved_policy_target is not None
        and (policy_changed or policy_mode_drift)
        and _snapshot(resolved_policy_target) != policy_snapshot
    ):
        raise InstallError(f"active CLAUDE.md changed concurrently: {policy_target}")
    if policy_target is not None and resolved_policy_target is not None:
        _verify_policy_link(policy_target, resolved_policy_target, policy_link)

    backup_dir = target.parent / ".claude/backups/claude-config"
    if resolved_policy_target is not None and policy_changed:
        if resolved_policy_target.exists():
            _backup(
                resolved_policy_target,
                policy_raw,
                prefix="claude-md",
                backup_dir=backup_dir,
            )
        _atomic_text(resolved_policy_target, managed_policy)
    elif resolved_policy_target is not None and resolved_policy_target.exists():
        if policy_mode_drift:
            os.chmod(resolved_policy_target, 0o600, follow_symlinks=False)
    if config_changed:
        if target.exists():
            _backup(
                target,
                original_raw,
                prefix="claude-json",
                backup_dir=backup_dir,
            )
        _atomic_json(target, merged)
    elif target.exists() and target_mode_drift:
        os.chmod(target, 0o600, follow_symlinks=False)
    hardened = _legacy_drift(legacy_paths, check=False)
    return config_changed, policy_changed, hardened


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=ROOT / "templates/mcp-config.json")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude.json")
    parser.add_argument(
        "--policy-template",
        type=Path,
        default=ROOT / "templates/global-mcp-policy.md",
    )
    parser.add_argument(
        "--policy-target",
        type=Path,
        default=Path.home() / ".claude/CLAUDE.md",
    )
    parser.add_argument("--legacy", action="append", type=Path, default=[])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    legacy = args.legacy or list(DEFAULT_LEGACY_PATHS)
    try:
        config_changed, policy_changed, hardened = install(
            args.template.expanduser().resolve(),
            args.target.expanduser(),
            legacy_paths=[path.expanduser() for path in legacy],
            policy_template=args.policy_template.expanduser().resolve(),
            policy_target=args.policy_target.expanduser(),
            check=args.check,
        )
    except InstallError as exc:
        parser.error(str(exc))
    if args.check:
        print("Claude MCP: aligned (context7, serena)")
    else:
        print(
            "Claude MCP: "
            f"config_updated={'yes' if config_changed else 'no'} "
            f"policy_updated={'yes' if policy_changed else 'no'} "
            f"legacy_permissions_hardened={hardened}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
