#!/usr/bin/env python3
"""
Hook Installation Helper for Validation Orchestrator.

Installs PostToolUse hook configuration into ~/.claude/settings.json.

Usage:
    python3 install.py           # Install hooks
    python3 install.py --dry-run # Show what would be added
    python3 install.py --remove  # Remove validation hooks

Features:
    - Backs up existing settings before modifying
    - Merges with existing hooks (doesn't replace)
    - Creates settings.json if it doesn't exist
    - Validates JSON structure before writing
"""

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Configuration
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
BACKUP_DIR = Path.home() / ".claude" / "backups"
HOOK_SCRIPT = Path(__file__).parent / "post_tool_hook.py"

# Hook configuration to add
VALIDATION_HOOK_CONFIG = {
    "matcher": "Write|Edit|MultiEdit",
    "hooks": [
        {
            "type": "command",
            "command": f"python3 {HOOK_SCRIPT.resolve()}",
            "timeout": 30,
        }
    ],
}

# Identifier to find our hook in existing config
HOOK_IDENTIFIER = "validation/hooks/post_tool_hook.py"


def load_settings() -> dict:
    """Load existing settings.json or return empty structure."""
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {SETTINGS_PATH}: {e}")
            sys.exit(1)
    return {}


def backup_settings() -> Path | None:
    """Create backup of existing settings.json."""
    if not SETTINGS_PATH.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"settings_{timestamp}.json"
    shutil.copy2(SETTINGS_PATH, backup_path)
    return backup_path


def has_validation_hook(settings: dict) -> bool:
    """Check if validation hook is already installed."""
    hooks = settings.get("hooks", {})
    post_tool_hooks = hooks.get("PostToolUse", [])

    for hook_group in post_tool_hooks:
        for hook in hook_group.get("hooks", []):
            if HOOK_IDENTIFIER in hook.get("command", ""):
                return True
    return False


def add_validation_hook(settings: dict) -> dict:
    """Add validation hook to settings, preserving existing hooks."""
    if "hooks" not in settings:
        settings["hooks"] = {}

    if "PostToolUse" not in settings["hooks"]:
        settings["hooks"]["PostToolUse"] = []

    # Check if already installed
    if has_validation_hook(settings):
        return settings

    # Add our hook configuration
    settings["hooks"]["PostToolUse"].append(VALIDATION_HOOK_CONFIG)
    return settings


def remove_validation_hook(settings: dict) -> dict:
    """Remove validation hook from settings."""
    if "hooks" not in settings:
        return settings

    if "PostToolUse" not in settings["hooks"]:
        return settings

    # Filter out our hook
    settings["hooks"]["PostToolUse"] = [
        hook_group
        for hook_group in settings["hooks"]["PostToolUse"]
        if not any(
            HOOK_IDENTIFIER in h.get("command", "") for h in hook_group.get("hooks", [])
        )
    ]

    return settings


def show_hook_config():
    """Display the hook configuration that would be added."""
    print("\nValidation Hook Configuration:")
    print("-" * 50)
    print(json.dumps(VALIDATION_HOOK_CONFIG, indent=2))
    print("-" * 50)
    print(f"\nHook script: {HOOK_SCRIPT.resolve()}")
    print(f"Settings file: {SETTINGS_PATH}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install validation orchestrator hooks into Claude settings"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be added without making changes",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove validation hooks from settings",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall even if already installed",
    )
    args = parser.parse_args()

    # Load existing settings
    settings = load_settings()

    if args.dry_run:
        print("DRY RUN - No changes will be made\n")

        if has_validation_hook(settings):
            print("Status: Validation hook is ALREADY INSTALLED")
            show_hook_config()
            return

        print("Status: Validation hook NOT installed")
        print("\nWould add the following to PostToolUse hooks:")
        show_hook_config()

        # Show full result
        test_settings = add_validation_hook(settings.copy())
        print("\nResulting PostToolUse hooks:")
        print(
            json.dumps(test_settings.get("hooks", {}).get("PostToolUse", []), indent=2)
        )
        return

    if args.remove:
        if not has_validation_hook(settings):
            print("Validation hook is not installed. Nothing to remove.")
            return

        # Backup and remove
        backup_path = backup_settings()
        if backup_path:
            print(f"Backup created: {backup_path}")

        settings = remove_validation_hook(settings)
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
        print("Validation hook removed from settings.json")
        return

    # Install hook
    if has_validation_hook(settings) and not args.force:
        print("Validation hook is already installed.")
        print("Use --force to reinstall or --remove to uninstall.")
        return

    if args.force and has_validation_hook(settings):
        settings = remove_validation_hook(settings)

    # Backup existing settings
    backup_path = backup_settings()
    if backup_path:
        print(f"Backup created: {backup_path}")

    # Add hook
    settings = add_validation_hook(settings)

    # Validate JSON before writing
    try:
        json.dumps(settings)
    except (TypeError, ValueError) as e:
        print(f"Error: Invalid settings structure: {e}")
        sys.exit(1)

    # Write settings
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2))

    print(f"Validation hook installed to {SETTINGS_PATH}")
    show_hook_config()
    print("\nRestart Claude Code for changes to take effect.")


if __name__ == "__main__":
    main()
