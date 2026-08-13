from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts" / "install_claude_hooks.py"
    spec = importlib.util.spec_from_file_location("install_claude_hooks", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _active_settings() -> dict:
    return {
        "model": "opus",
        "theme": "dark",
        "enableAllProjectMcpServers": True,
        "permissions": {
            "allow": ["Edit(//home/sam/**)", "MultiEdit(//home/sam/**)"],
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "npx @claude-flow/cli@latest hooks pre-command --cmd x || true",
                        },
                        {
                            "type": "command",
                            "command": "node \"/home/sam/.claude/scripts/hooks/safety/git-safety-check.js\"",
                            "timeout": 1,
                        },
                    ],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "node \"$HOME/.claude/hooks/gsd-context-monitor.js\"",
                        }
                    ],
                }
            ],
        },
    }


def test_install_merges_hooks_preserves_preferences_and_is_idempotent(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text("// local hook\n", encoding="utf-8")
    (target / "settings.json").write_text(json.dumps(_active_settings()), encoding="utf-8")

    assets, settings_changed = module.install(ROOT, target, check=False)
    installed = json.loads((target / "settings.json").read_text(encoding="utf-8"))

    assert assets > 0
    assert settings_changed
    assert installed["model"] == "opus"
    assert installed["theme"] == "dark"
    assert installed["enableAllProjectMcpServers"] is False
    assert installed["permissions"]["allow"] == ["Edit(//home/sam/**)"]
    commands = [
        hook["command"]
        for groups in installed["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]
    assert not any(module.LEGACY_CLAUDE_FLOW in command for command in commands)
    assert any("gsd-context-monitor.js" in command for command in commands)
    git_safety = next(command for command in commands if "git-safety-check.js" in command)
    assert git_safety == 'node "$HOME/.claude/scripts/hooks/safety/git-safety-check.js"'
    assert (target / "scripts/hooks/safety/git-safety-check.js").exists()
    assert (target / "scripts/lib/utils.js").exists()
    assert (target / "hooks/gsd-check-update.js").exists()
    assert not (target / "scripts/lib/utils.test.js").exists()
    assert len(list((target / "backups/claude-config").glob("settings-*.json"))) == 1

    assert module.install(ROOT, target, check=True) == (0, False)
    assert module.install(ROOT, target, check=False) == (0, False)
    assert len(list((target / "backups/claude-config").glob("settings-*.json"))) == 1


def test_check_detects_asset_drift(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "settings.json").write_text("{}\n", encoding="utf-8")
    module.install(ROOT, target, check=False)
    (target / "scripts/lib/utils.js").write_text("drift\n", encoding="utf-8")

    with pytest.raises(module.InstallError, match="assets=1"):
        module.install(ROOT, target, check=True)


def test_install_rejects_missing_extra_registered_hook(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    active = _active_settings()
    active["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = (
        'node "$HOME/.claude/hooks/missing-extra.js"'
    )
    (target / "settings.json").write_text(json.dumps(active), encoding="utf-8")

    with pytest.raises(module.InstallError, match="missing-extra.js"):
        module.install(ROOT, target, check=False)


def test_install_rejects_symlinked_asset_before_reading_it(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "settings.json").write_text("{}\n", encoding="utf-8")
    linked = target / "scripts/lib/utils.js"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(ROOT / "scripts/lib/utils.js")

    with pytest.raises(module.InstallError, match="symlinked asset"):
        module.install(ROOT, target, check=False)
