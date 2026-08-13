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
        policy_template=ROOT / "templates/global-mcp-policy.md",
        policy_target=target.parent / ".claude/CLAUDE.md",
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

    policy_target = tmp_path / ".claude/CLAUDE.md"
    policy_target.parent.mkdir()
    policy_target.write_text("# Existing profile instructions\n", encoding="utf-8")
    policy_target.chmod(0o600)

    changed, policy_changed, hardened = _install(module, target, legacy)
    installed = json.loads(target.read_text(encoding="utf-8"))

    assert changed is True
    assert policy_changed is True
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
    policy = policy_target.read_text(encoding="utf-8")
    assert policy.startswith("# Existing profile instructions\n")
    assert policy.count(module.POLICY_BEGIN) == 1
    assert "activate the exact authorized Git root" in policy
    backups = list((tmp_path / ".claude/backups/claude-config").glob("*.json"))
    assert len(backups) == 2
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in backups)
    config_backup = next(path for path in backups if path.name.startswith("claude-json-"))
    policy_backup = next(path for path in backups if path.name.startswith("claude-md-"))
    assert json.loads(config_backup.read_text(encoding="utf-8")) == active
    assert policy_backup.read_text(encoding="utf-8") == "# Existing profile instructions\n"

    assert _install(module, target, legacy, check=True) == (False, False, 0)
    assert _install(module, target, legacy) == (False, False, 0)
    assert len(list((tmp_path / ".claude/backups/claude-config").glob("*.json"))) == 2


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


def test_legacy_symlink_fails_before_active_files_are_changed(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    original_config = '{"model":"opus"}\n'
    target.write_text(original_config, encoding="utf-8")
    target.chmod(0o600)
    policy_target = tmp_path / ".claude/CLAUDE.md"
    policy_target.parent.mkdir()
    original_policy = "# Existing policy\n"
    policy_target.write_text(original_policy, encoding="utf-8")
    legacy_real = tmp_path / "legacy-real.json"
    legacy_real.write_text("{}\n", encoding="utf-8")
    legacy = tmp_path / ".mcp.json"
    legacy.symlink_to(legacy_real)

    with pytest.raises(module.InstallError, match="symlinked"):
        _install(module, target, legacy)

    assert target.read_text(encoding="utf-8") == original_config
    assert policy_target.read_text(encoding="utf-8") == original_policy
    assert not (tmp_path / ".claude/backups").exists()

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
    target_calls = 0

    def changed_snapshot(path: Path):
        nonlocal target_calls
        value = real_snapshot(path)
        if path == target:
            target_calls += 1
        if path == target and target_calls == 2 and value is not None:
            return (*value[:-1], value[-1] + 1)
        return value

    monkeypatch.setattr(module, "_snapshot", changed_snapshot)

    with pytest.raises(module.InstallError, match="changed concurrently"):
        _install(module, target, legacy)
    assert json.loads(target.read_text(encoding="utf-8")) == {"model": "opus"}


def test_policy_update_preserves_surrounding_text_and_rejects_bad_markers(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    policy_target = tmp_path / ".claude/CLAUDE.md"
    policy_target.parent.mkdir()
    old = (
        "before\n\n"
        f"{module.POLICY_BEGIN}\nold policy\n{module.POLICY_END}\n\nafter\n"
    )
    policy_target.write_text(old, encoding="utf-8")
    policy_target.chmod(0o600)

    _install(module, target, legacy)
    installed = policy_target.read_text(encoding="utf-8")
    assert installed.startswith("before\n\n")
    assert installed.endswith("\n\nafter\n")
    assert "old policy" not in installed
    assert installed.count(module.POLICY_BEGIN) == 1

    policy_target.write_text(f"{module.POLICY_BEGIN}\nbroken\n", encoding="utf-8")
    with pytest.raises(module.InstallError, match="malformed"):
        _install(module, target, legacy)


def test_policy_update_preserves_owned_symlink(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    policy_link = tmp_path / ".claude/CLAUDE.md"
    policy_link.parent.mkdir()
    policy_real = tmp_path / "dotfiles/CLAUDE.md"
    policy_real.parent.mkdir()
    policy_real.write_text("# Dotfiles policy\n", encoding="utf-8")
    policy_real.chmod(0o664)
    policy_link.symlink_to(policy_real)

    config_changed, policy_changed, hardened = _install(module, target, legacy)

    assert (config_changed, policy_changed, hardened) == (True, True, 0)
    assert policy_link.is_symlink()
    assert policy_link.resolve() == policy_real
    assert policy_real.read_text(encoding="utf-8").startswith("# Dotfiles policy\n")
    assert policy_real.read_text(encoding="utf-8").count(module.POLICY_BEGIN) == 1
    assert stat.S_IMODE(policy_real.stat().st_mode) == 0o600


def test_policy_symlink_change_is_detected_before_write(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    target = tmp_path / ".claude.json"
    legacy = tmp_path / ".mcp.json"
    policy_link = tmp_path / ".claude/CLAUDE.md"
    policy_link.parent.mkdir()
    policy_real = tmp_path / "first.md"
    policy_other = tmp_path / "second.md"
    policy_real.write_text("first\n", encoding="utf-8")
    policy_other.write_text("second\n", encoding="utf-8")
    policy_link.symlink_to(policy_real)
    real_verify = module._verify_policy_link

    def changed_link(path: Path, resolved: Path, expected):
        path.unlink()
        path.symlink_to(policy_other)
        real_verify(path, resolved, expected)

    monkeypatch.setattr(module, "_verify_policy_link", changed_link)

    with pytest.raises(module.InstallError, match="symlink changed concurrently"):
        _install(module, target, legacy)
    assert policy_real.read_text(encoding="utf-8") == "first\n"
    assert policy_other.read_text(encoding="utf-8") == "second\n"
    assert not target.exists()
