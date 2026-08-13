from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts/install_claude_mcp.py"
    spec = importlib.util.spec_from_file_location("install_claude_mcp", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _install(module, target: Path, legacy: Path, *, check: bool = False):
    return module.install(
        ROOT / "templates/mcp-config.json",
        target,
        legacy_paths=[legacy],
        check=check,
        executable=lambda path: path in {"/usr/bin/setpriv", "/usr/local/bin/serena"},
    )


def test_install_keeps_profile_data_and_replaces_only_user_mcp_allowlist(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    active = {
        "projects": {"/repo": {"allowedTools": ["Bash"]}},
        "oauthAccount": {"accountUuid": "preserved"},
        "mcpServers": {
            "linear": {"command": "linear", "env": {"TOKEN": "not-copied"}},
        },
    }
    target.write_text(json.dumps(active), encoding="utf-8")
    target.chmod(0o600)
    legacy.write_text('{"mcpServers":{"sentry":{"env":{"TOKEN":"secret"}}}}\n')
    legacy.chmod(0o664)

    changed, hardened = _install(module, target, legacy)
    installed = json.loads(target.read_text(encoding="utf-8"))

    assert changed is True
    assert hardened == 1
    assert installed["projects"] == active["projects"]
    assert installed["oauthAccount"] == active["oauthAccount"]
    assert set(installed["mcpServers"]) == {"context7", "serena"}
    assert installed["mcpServers"]["context7"] == {
        "type": "http",
        "url": "https://mcp.context7.com/mcp",
    }
    assert "project-from-cwd" not in installed["mcpServers"]["serena"]["args"]
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(legacy.stat().st_mode) == 0o600
    backups = list((tmp_path / ".claude/backups/claude-config").glob("claude-json-*.json"))
    assert len(backups) == 1
    assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600
    assert json.loads(backups[0].read_text(encoding="utf-8")) == active

    assert _install(module, target, legacy, check=True) == (False, 0)
    assert _install(module, target, legacy) == (False, 0)
    assert len(list((tmp_path / ".claude/backups/claude-config").glob("*.json"))) == 1


def test_check_detects_config_and_legacy_permission_drift(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    target.write_text("{}\n", encoding="utf-8")
    target.chmod(0o600)
    legacy.write_text("{}\n", encoding="utf-8")
    legacy.chmod(0o600)

    with pytest.raises(module.InstallError, match="config=yes"):
        _install(module, target, legacy, check=True)

    _install(module, target, legacy)
    legacy.chmod(0o644)
    with pytest.raises(module.InstallError, match="unsafe permissions"):
        _install(module, target, legacy, check=True)


def test_install_rejects_missing_launcher_before_writing(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    original = {"model": "opus"}
    target.write_text(json.dumps(original), encoding="utf-8")
    target.chmod(0o600)

    with pytest.raises(module.InstallError, match="unavailable"):
        module.install(
            ROOT / "templates/mcp-config.json",
            target,
            legacy_paths=[legacy],
            check=False,
            executable=lambda _path: False,
        )

    assert json.loads(target.read_text(encoding="utf-8")) == original


def test_install_rejects_symlinked_target_and_legacy(tmp_path: Path) -> None:
    module = _load_module()
    real = tmp_path / "real.json"
    real.write_text("{}\n", encoding="utf-8")
    target = tmp_path / ".claude.json"
    target.symlink_to(real)

    with pytest.raises(module.InstallError, match="symlinked"):
        _install(module, target, tmp_path / ".mcp.json")

    target.unlink()
    target.write_text("{}\n", encoding="utf-8")
    legacy = tmp_path / ".mcp.json"
    legacy.symlink_to(real)
    with pytest.raises(module.InstallError, match="symlinked"):
        _install(module, target, legacy)

    target.unlink()
    target.symlink_to(tmp_path / "missing.json")
    legacy.unlink()
    with pytest.raises(module.InstallError, match="symlinked"):
        _install(module, target, legacy)


def test_install_detects_concurrent_target_change(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    target.write_text('{"model":"opus"}\n', encoding="utf-8")
    target.chmod(0o600)
    real_snapshot = module._snapshot
    calls = 0

    def changed_snapshot(path: Path):
        nonlocal calls
        calls += 1
        value = real_snapshot(path)
        if calls == 2 and value is not None:
            return (*value[:-1], value[-1] + 1)
        return value

    monkeypatch.setattr(module, "_snapshot", changed_snapshot)

    with pytest.raises(module.InstallError, match="changed concurrently"):
        _install(module, target, legacy)
    assert json.loads(target.read_text(encoding="utf-8")) == {"model": "opus"}
