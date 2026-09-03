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
            "allow": [
                "Edit(//home/sam/**)",
                "MultiEdit(//home/sam/**)",
                "mcp__context7__get-library-docs",
            ],
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
                            "command": "npx ruflo hooks pre-command --cmd x || true",
                        },
                        {
                            "type": "command",
                            "command": "npx Claude-Flow@v3alpha hooks pre-command || true",
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
                        },
                        {
                            "type": "command",
                            "command": "node \"$HOME/.claude/scripts/hooks/metrics/claudeflow-sync.js\"",
                        },
                    ],
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "node \"$HOME/.claude/scripts/hooks/intelligence/cf-session-workers.js\"",
                        }
                    ]
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
    for relative in module.RETIRED_ASSETS:
        retired = target / relative
        retired.parent.mkdir(parents=True, exist_ok=True)
        retired.write_text("retired\n", encoding="utf-8")
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
    assert not any(
        marker in command.lower()
        for command in commands
        for marker in module.LEGACY_CLAUDE_FLOW_MARKERS
    )
    assert not any("gsd-context-monitor.js" in command for command in commands)
    git_safety = next(command for command in commands if "git-safety-check.js" in command)
    assert git_safety == 'node "$HOME/.claude/scripts/hooks/safety/git-safety-check.js"'
    assert (target / "scripts/hooks/safety/git-safety-check.js").exists()
    assert (target / "scripts/lib/utils.js").exists()
    assert (target / "scripts/statusline/context-monitor.js").exists()
    assert (target / "scripts/statusline/ui-components.js").exists()
    assert (target / "skills/swarm/SKILL.md").exists()
    assert (target / "commands/pipeline.speckit.md").exists()
    assert (target / "hooks/gsd-check-update.js").exists()
    assert all(not (target / relative).exists() for relative in module.RETIRED_ASSETS)
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
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text(
        "// local hook\n", encoding="utf-8"
    )
    active = _active_settings()
    active["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = (
        'node "$HOME/.claude/hooks/missing-extra.js"'
    )
    (target / "settings.json").write_text(json.dumps(active), encoding="utf-8")

    with pytest.raises(module.InstallError, match="missing-extra.js"):
        module.install(ROOT, target, check=False)


def test_install_allows_registered_commands_without_managed_asset_paths(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text(
        "// local hook\n", encoding="utf-8"
    )
    active = _active_settings()
    active["hooks"]["PostToolUse"][0]["hooks"].append(
        {"type": "command", "command": "printf ok"}
    )
    (target / "settings.json").write_text(json.dumps(active), encoding="utf-8")

    module.install(ROOT, target, check=False)

    installed = json.loads((target / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for groups in installed["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]
    assert "printf ok" in commands


def test_install_rejects_symlinked_asset_before_reading_it(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "settings.json").write_text("{}\n", encoding="utf-8")
    linked = target / "scripts/lib/utils.js"
    linked.parent.mkdir(parents=True)
    outside = tmp_path / "outside.js"
    outside.write_text("drift\n", encoding="utf-8")
    linked.symlink_to(outside)

    with pytest.raises(module.InstallError, match="symlinked asset"):
        module.install(ROOT, target, check=False)


def test_install_allows_matching_assets_through_symlinked_managed_root(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "settings.json").write_text("{}\n", encoding="utf-8")
    (target / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)

    module.install(ROOT, target, check=False)

    assert (target / "scripts/lib/utils.js").samefile(ROOT / "scripts/lib/utils.js")


def test_install_rejects_matching_asset_through_noncanonical_symlink(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    (target / "settings.json").write_text("{}\n", encoding="utf-8")
    linked = target / "scripts/lib/utils.js"
    linked.parent.mkdir(parents=True)
    outside = tmp_path / "outside.js"
    outside.write_bytes((ROOT / "scripts/lib/utils.js").read_bytes())
    linked.symlink_to(outside)

    with pytest.raises(module.InstallError, match="non-canonical symlinked asset"):
        module.install(ROOT, target, check=False)


def test_install_rejects_symlinked_profile_root(tmp_path: Path) -> None:
    module = _load_module()
    real_target = tmp_path / "real-profile"
    real_target.mkdir()
    target = tmp_path / "linked-profile"
    target.symlink_to(real_target, target_is_directory=True)

    with pytest.raises(module.InstallError, match="symlinked settings path"):
        module.install(ROOT, target, check=False)

    assert list(real_target.iterdir()) == []


def test_install_rejects_unsafe_retired_asset_before_writes(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    settings = target / "settings.json"
    settings.write_text(json.dumps(_active_settings()), encoding="utf-8")
    original = settings.read_bytes()
    retired = target / module.RETIRED_ASSETS[0]
    retired.parent.mkdir(parents=True)
    retired.symlink_to(tmp_path / "outside")

    with pytest.raises(module.InstallError, match="retired asset"):
        module.install(ROOT, target, check=False)

    assert settings.read_bytes() == original
    assert not (target / "scripts/lib/utils.js").exists()


def test_install_rejects_symlinked_retired_parent_before_writes(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    settings = target / "settings.json"
    settings.write_text(json.dumps(_active_settings()), encoding="utf-8")
    original = settings.read_bytes()
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text(
        "// local hook\n", encoding="utf-8"
    )
    outside = tmp_path / "outside"
    retired = outside / "hooks/metrics/claudeflow-sync.js"
    retired.parent.mkdir(parents=True)
    retired.write_text("must survive\n", encoding="utf-8")
    (target / "scripts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(module.InstallError, match="symlinked .* path"):
        module.install(ROOT, target, check=False)

    assert settings.read_bytes() == original
    assert retired.read_text(encoding="utf-8") == "must survive\n"


def test_install_rolls_back_assets_and_retired_files_on_settings_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    settings = target / "settings.json"
    settings.write_text(json.dumps(_active_settings()), encoding="utf-8")
    original_settings = settings.read_bytes()
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text(
        "// local hook\n", encoding="utf-8"
    )
    managed = target / "scripts/lib/utils.js"
    managed.parent.mkdir(parents=True)
    managed.write_text("old asset\n", encoding="utf-8")
    retired = target / module.RETIRED_ASSETS[0]
    retired.parent.mkdir(parents=True, exist_ok=True)
    retired.write_text("retired\n", encoding="utf-8")

    def fail_settings(*_args, **_kwargs) -> None:
        raise OSError("injected settings failure")

    monkeypatch.setattr(module, "_atomic_json", fail_settings)

    with pytest.raises(module.InstallError, match="rolled back"):
        module.install(ROOT, target, check=False)

    assert settings.read_bytes() == original_settings
    assert managed.read_text(encoding="utf-8") == "old asset\n"
    assert retired.read_text(encoding="utf-8") == "retired\n"
    assert not list((target / "backups/claude-config").glob("settings-*.json"))
    assert not (target / "commands").exists()
    assert not (target / "skills").exists()
    assert not (target / "backups").exists()


def test_install_rejects_symlinked_backup_parent_before_writes(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / ".claude"
    target.mkdir()
    settings = target / "settings.json"
    settings.write_text(json.dumps(_active_settings()), encoding="utf-8")
    original = settings.read_bytes()
    (target / "hooks").mkdir()
    (target / "hooks/gsd-context-monitor.js").write_text(
        "// local hook\n", encoding="utf-8"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "backups").symlink_to(outside, target_is_directory=True)

    with pytest.raises(module.InstallError, match="symlinked backup path"):
        module.install(ROOT, target, check=False)

    assert settings.read_bytes() == original
    assert list(outside.iterdir()) == []
