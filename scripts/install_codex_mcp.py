#!/usr/bin/env python3
"""Install the minimal global Codex MCP profile without replacing user settings."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import time
import tomllib
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVERS = {"context7", "serena"}
SECTION_HEADER = re.compile(r"^\s*\[([^\]]+)]\s*(?:#.*)?$")


class InstallError(RuntimeError):
    pass


def _validate_owned_regular_file(path: Path) -> None:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked Codex config: {path}")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise InstallError(f"unable to inspect {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise InstallError(f"expected a regular file: {path}")
    if metadata.st_uid != os.geteuid():
        raise InstallError(f"file is not owned by the current user: {path}")


def _read_toml(path: Path) -> tuple[dict, bytes]:
    if path.is_symlink():
        raise InstallError(f"refusing symlinked TOML file: {path}")
    try:
        raw = path.read_bytes()
        value = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InstallError(f"unable to read TOML {path}: {exc}") from exc
    return value, raw


def _snapshot(path: Path) -> tuple[int, int, int, int] | None:
    if not path.exists() and not path.is_symlink():
        return None
    _validate_owned_regular_file(path)
    metadata = path.stat()
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _validate_template(
    path: Path,
    executable: Callable[[str], bool],
) -> str:
    template, raw = _read_toml(path)
    servers = template.get("mcp_servers")
    if not isinstance(servers, dict) or set(servers) != EXPECTED_SERVERS:
        raise InstallError("Codex MCP template must contain exactly context7 and serena")
    context7 = servers.get("context7")
    if context7 != {
        "url": "https://mcp.context7.com/mcp",
        "startup_timeout_sec": 30.0,
    }:
        raise InstallError("Context7 must use the canonical HTTPS endpoint and 30s timeout")
    serena = servers.get("serena")
    expected_args = [
        "serena",
        "start-mcp-server",
        "--context",
        "ide-assistant",
    ]
    if not isinstance(serena, dict) or serena != {
        "command": "/usr/bin/env",
        "args": expected_args,
        "startup_timeout_sec": 30.0,
    }:
        raise InstallError("Serena must use the canonical portable Codex launcher")
    for required in ("/usr/bin/env", "serena"):
        if not executable(required):
            raise InstallError(f"required MCP executable is unavailable: {required}")
    return raw.decode("utf-8").strip()


def _section_chunks(text: str) -> tuple[str, list[tuple[str, str]]]:
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in text.splitlines(keepends=True):
        match = SECTION_HEADER.match(line.rstrip("\n"))
        if match:
            current = (match.group(1).strip(), [line])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    return "".join(preamble), [(name, "".join(lines)) for name, lines in sections]


def _managed_config(active: str, template: str) -> str:
    preamble, sections = _section_chunks(active)
    output: list[str] = [preamble.rstrip()]
    inserted = False
    preserved_serena_tools: list[str] = []
    for name, chunk in sections:
        if name.startswith("mcp_servers."):
            if name.startswith("mcp_servers.serena.tools."):
                preserved_serena_tools.append(chunk.strip())
            if not inserted:
                output.append(template)
                inserted = True
            continue
        output.append(chunk.strip())
    if not inserted:
        output.append(template)
    output.extend(preserved_serena_tools)
    rendered = "\n\n".join(part for part in output if part).rstrip() + "\n"
    try:
        parsed = tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"managed Codex config would be invalid TOML: {exc}") from exc
    servers = parsed.get("mcp_servers")
    if not isinstance(servers, dict) or set(servers) != EXPECTED_SERVERS:
        raise InstallError("managed Codex config did not produce the exact MCP allowlist")
    return rendered


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


def _backup(path: Path, raw: bytes) -> Path:
    backup_dir = path.parent / "backups/claude-config"
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_dir / (
        f"codex-config-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        f"-{time.time_ns()}.toml"
    )
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return backup


def install(
    template_path: Path,
    target: Path,
    *,
    check: bool,
    executable: Callable[[str], bool] = lambda command: (
        os.access(command, os.X_OK) if "/" in command else shutil.which(command) is not None
    ),
) -> bool:
    template = _validate_template(template_path, executable)
    original_snapshot = _snapshot(target)
    if target.exists():
        _active, original_raw = _read_toml(target)
        active = original_raw.decode("utf-8")
    else:
        original_raw = b""
        active = ""
    managed = _managed_config(active, template)
    changed = managed != active
    mode_drift = target.exists() and stat.S_IMODE(target.stat().st_mode) != 0o600
    if check:
        if changed or mode_drift:
            raise InstallError(
                f"Codex MCP drift: config={'yes' if changed else 'no'}, "
                f"mode={'yes' if mode_drift else 'no'}"
            )
        return False
    if (changed or mode_drift) and _snapshot(target) != original_snapshot:
        raise InstallError(f"Codex MCP config changed concurrently: {target}")
    if changed:
        if target.exists():
            _backup(target, original_raw)
        _atomic_text(target, managed)
    elif mode_drift:
        os.chmod(target, 0o600, follow_symlinks=False)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=ROOT / "templates/codex-mcp.toml")
    parser.add_argument("--target", type=Path, default=Path.home() / ".codex/config.toml")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        changed = install(
            args.template.expanduser().resolve(),
            args.target.expanduser(),
            check=args.check,
        )
    except InstallError as exc:
        parser.error(str(exc))
    if args.check:
        print("Codex MCP: aligned (context7, serena; startup timeout 30s)")
    else:
        print(f"Codex MCP: config_updated={'yes' if changed else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
