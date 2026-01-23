#!/usr/bin/env python3
"""Unit tests for hooks/install.py - Hook Installation Helper."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hooks.install import (
    HOOK_IDENTIFIER,
    VALIDATION_HOOK_CONFIG,
    add_validation_hook,
    backup_settings,
    has_validation_hook,
    load_settings,
    remove_validation_hook,
    show_hook_config,
)


class TestLoadSettings:
    """Tests for load_settings() function."""

    def test_load_nonexistent_returns_empty(self):
        """Test loading from non-existent file returns empty dict."""
        with patch("hooks.install.SETTINGS_PATH", Path("/nonexistent/settings.json")):
            result = load_settings()
        assert result == {}

    def test_load_valid_json(self):
        """Test loading valid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value", "hooks": {}}, f)
            f.flush()
            with patch("hooks.install.SETTINGS_PATH", Path(f.name)):
                result = load_settings()
        assert result == {"key": "value", "hooks": {}}

    def test_load_invalid_json_exits(self):
        """Test loading invalid JSON exits with error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            with patch("hooks.install.SETTINGS_PATH", Path(f.name)):
                with pytest.raises(SystemExit) as exc_info:
                    load_settings()
                assert exc_info.value.code == 1

    def test_load_empty_file(self):
        """Test loading empty JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            f.flush()
            with patch("hooks.install.SETTINGS_PATH", Path(f.name)):
                result = load_settings()
        assert result == {}


class TestBackupSettings:
    """Tests for backup_settings() function."""

    def test_backup_nonexistent_returns_none(self):
        """Test backing up non-existent file returns None."""
        with patch("hooks.install.SETTINGS_PATH", Path("/nonexistent/settings.json")):
            result = backup_settings()
        assert result is None

    def test_backup_creates_copy(self):
        """Test backup creates a copy of the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            backup_dir = Path(tmpdir) / "backups"
            settings_path.write_text('{"test": "data"}')

            with patch("hooks.install.SETTINGS_PATH", settings_path):
                with patch("hooks.install.BACKUP_DIR", backup_dir):
                    result = backup_settings()

            assert result is not None
            assert result.exists()
            assert json.loads(result.read_text()) == {"test": "data"}


class TestHasValidationHook:
    """Tests for has_validation_hook() function."""

    def test_empty_settings(self):
        """Test empty settings has no hook."""
        assert has_validation_hook({}) is False

    def test_no_hooks_key(self):
        """Test settings without hooks key."""
        assert has_validation_hook({"other": "value"}) is False

    def test_empty_post_tool_use(self):
        """Test empty PostToolUse list."""
        settings = {"hooks": {"PostToolUse": []}}
        assert has_validation_hook(settings) is False

    def test_other_hooks_only(self):
        """Test with other hooks but not validation hook."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "echo test"}],
                    }
                ]
            }
        }
        assert has_validation_hook(settings) is False

    def test_validation_hook_present(self):
        """Test detection when validation hook is present."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python3 /path/to/{HOOK_IDENTIFIER}",
                            }
                        ],
                    }
                ]
            }
        }
        assert has_validation_hook(settings) is True


class TestAddValidationHook:
    """Tests for add_validation_hook() function."""

    def test_add_to_empty_settings(self):
        """Test adding hook to empty settings."""
        settings = {}
        result = add_validation_hook(settings)

        assert "hooks" in result
        assert "PostToolUse" in result["hooks"]
        assert len(result["hooks"]["PostToolUse"]) == 1

    def test_add_preserves_existing_hooks(self):
        """Test adding hook preserves existing hooks."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "echo test"}]}
                ],
                "PrePrompt": [{"type": "command"}],
            }
        }
        result = add_validation_hook(settings)

        # Should have 2 PostToolUse hooks now
        assert len(result["hooks"]["PostToolUse"]) == 2
        # PrePrompt should be preserved
        assert "PrePrompt" in result["hooks"]

    def test_no_duplicate_on_readd(self):
        """Test adding hook twice doesn't duplicate."""
        settings = {}
        result = add_validation_hook(settings)
        result = add_validation_hook(result)

        assert len(result["hooks"]["PostToolUse"]) == 1

    def test_hook_config_structure(self):
        """Test added hook has correct structure."""
        settings = {}
        result = add_validation_hook(settings)

        hook = result["hooks"]["PostToolUse"][0]
        assert "matcher" in hook
        assert "hooks" in hook
        assert hook["matcher"] == "Write|Edit|MultiEdit"


class TestRemoveValidationHook:
    """Tests for remove_validation_hook() function."""

    def test_remove_from_empty(self):
        """Test removing from empty settings is safe."""
        settings = {}
        result = remove_validation_hook(settings)
        assert result == {}

    def test_remove_no_hooks_key(self):
        """Test removing when no hooks key."""
        settings = {"other": "value"}
        result = remove_validation_hook(settings)
        assert result == {"other": "value"}

    def test_remove_preserves_other_hooks(self):
        """Test removing validation hook preserves other hooks."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "echo test"}]},
                    {
                        "matcher": "Write",
                        "hooks": [{"command": f"python3 /path/{HOOK_IDENTIFIER}"}],
                    },
                ]
            }
        }
        result = remove_validation_hook(settings)

        # Should only have 1 hook left
        assert len(result["hooks"]["PostToolUse"]) == 1
        # The Bash hook should be preserved
        assert result["hooks"]["PostToolUse"][0]["matcher"] == "Bash"

    def test_remove_nonexistent_is_safe(self):
        """Test removing when hook not present is safe."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Bash", "hooks": [{"command": "echo test"}]}
                ]
            }
        }
        result = remove_validation_hook(settings)

        # Should still have the Bash hook
        assert len(result["hooks"]["PostToolUse"]) == 1


class TestShowHookConfig:
    """Tests for show_hook_config() function."""

    def test_show_prints_output(self, capsys):
        """Test show_hook_config prints something."""
        show_hook_config()

        captured = capsys.readouterr()
        assert "Validation Hook Configuration" in captured.out
        assert "matcher" in captured.out

    def test_show_includes_script_path(self, capsys):
        """Test show_hook_config includes script path."""
        show_hook_config()

        captured = capsys.readouterr()
        assert "Hook script" in captured.out


class TestValidationHookConfig:
    """Tests for VALIDATION_HOOK_CONFIG constant."""

    def test_config_has_matcher(self):
        """Test config has matcher field."""
        assert "matcher" in VALIDATION_HOOK_CONFIG
        assert "Write" in VALIDATION_HOOK_CONFIG["matcher"]
        assert "Edit" in VALIDATION_HOOK_CONFIG["matcher"]

    def test_config_has_hooks_list(self):
        """Test config has hooks list."""
        assert "hooks" in VALIDATION_HOOK_CONFIG
        assert isinstance(VALIDATION_HOOK_CONFIG["hooks"], list)
        assert len(VALIDATION_HOOK_CONFIG["hooks"]) > 0

    def test_config_hook_has_timeout(self):
        """Test hook config has timeout."""
        hook = VALIDATION_HOOK_CONFIG["hooks"][0]
        assert "timeout" in hook
        assert hook["timeout"] == 30


class TestMainFunction:
    """Tests for main() function via argument parsing."""

    def test_dry_run_no_changes(self, capsys):
        """Test --dry-run doesn't modify anything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text("{}")

            with patch("hooks.install.SETTINGS_PATH", settings_path):
                with patch("sys.argv", ["install.py", "--dry-run"]):
                    from hooks.install import main

                    main()

            # Settings should be unchanged
            assert json.loads(settings_path.read_text()) == {}

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    def test_remove_already_absent(self, capsys):
        """Test --remove when hook not installed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            settings_path.write_text("{}")

            with patch("hooks.install.SETTINGS_PATH", settings_path):
                with patch("sys.argv", ["install.py", "--remove"]):
                    from hooks.install import main

                    main()

        captured = capsys.readouterr()
        assert "not installed" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
