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
        "--pdeathsig",
        "TERM",
        "/usr/local/bin/serena",
        "start-mcp-server",
        "--context",
        "claude-code",
    ]
    if command != "/usr/bin/setpriv" or args != expected_args:
        raise InstallError("Serena must use the canonical bounded launcher")
    for required in (command, expected_args[2]):
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


def _backup(path: Path, raw: bytes) -> Path:
    backup_dir = path.parent / ".claude/backups/claude-config"
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_dir / (
        f"claude-json-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
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


def install(
    template_path: Path,
    target: Path,
    *,
    legacy_paths: Sequence[Path],
    check: bool,
    executable: Callable[[str], bool] = lambda path: os.access(path, os.X_OK),
) -> tuple[bool, int]:
    template, _template_raw = _read_object(template_path)
    servers = _validate_template(template, executable)

    original_snapshot = _snapshot(target)
    if target.exists():
        active, original_raw = _read_object(target)
    else:
        active, original_raw = {}, b""
    merged = json.loads(json.dumps(active))
    merged["mcpServers"] = json.loads(json.dumps(servers))
    config_changed = merged != active

    if check:
        _legacy_drift(legacy_paths, check=True)
        if config_changed or (target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600):
            raise InstallError(
                "Claude MCP drift: "
                f"config={'yes' if config_changed else 'no'}, "
                f"mode={'yes' if target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600 else 'no'}"
            )
        return False, 0

    hardened = _legacy_drift(legacy_paths, check=False)
    if config_changed:
        if _snapshot(target) != original_snapshot:
            raise InstallError(f"Claude MCP config changed concurrently: {target}")
        if target.exists():
            _backup(target, original_raw)
        _atomic_json(target, merged)
    elif target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600:
        if _snapshot(target) != original_snapshot:
            raise InstallError(f"Claude MCP config changed concurrently: {target}")
        os.chmod(target, 0o600, follow_symlinks=False)
    return config_changed, hardened


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=ROOT / "templates/mcp-config.json")
    parser.add_argument("--target", type=Path, default=Path.home() / ".claude.json")
    parser.add_argument("--legacy", action="append", type=Path, default=[])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    legacy = args.legacy or list(DEFAULT_LEGACY_PATHS)
    try:
        config_changed, hardened = install(
            args.template.expanduser().resolve(),
            args.target.expanduser(),
            legacy_paths=[path.expanduser() for path in legacy],
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
            f"legacy_permissions_hardened={hardened}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
