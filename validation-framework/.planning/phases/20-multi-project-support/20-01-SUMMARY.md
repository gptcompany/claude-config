---
phase: 20-multi-project-support
plan: 01
status: completed
duration_minutes: 25
files_changed:
  - ~/.claude/templates/validation/config_loader.py
  - ~/.claude/templates/validation/orchestrator.py
  - ~/.claude/templates/validation/tests/test_config_loader.py
  - ~/.claude/templates/validation/tests/test_orchestrator.py
tests_passed: 117
tests_added: 14
---

# Plan 20-01: Config Inheritance Implementation

## Summary

Implemented config inheritance with RFC 7396 JSON Merge Patch semantics for the validation framework. This enables global defaults at `~/.claude/validation/global-config.json` to cascade to project configs, enabling zero-config validation for any project.

## Changes Made

### 1. config_loader.py - New Global Config Functions

Added new module-level constant and 5 new functions:

```python
GLOBAL_CONFIG_PATH = Path.home() / ".claude" / "validation" / "global-config.json"

def load_global_config() -> dict:
    """Load global config if exists, return empty dict otherwise."""

def load_project_config(path: Path | None = None) -> dict:
    """Load project-specific config with directory/file path support."""

def merge_configs_rfc7396(global_config: dict, project_config: dict) -> dict:
    """RFC 7396 merge patch semantics - project overrides global."""

def load_config(project_path: Path | None = None) -> dict:
    """Compose full config with inheritance chain + _config_source metadata."""
```

### 2. orchestrator.py - Integration

Updated `_load_config()` method to use `load_config()` from config_loader:

- Falls back to legacy loading if import fails
- Maintains backward compatibility with explicit config paths
- Adds `_config_source` metadata to config for debugging

### 3. Tests Added (14 new tests in 4 test classes)

| Test Class | Tests | Description |
|------------|-------|-------------|
| `TestLoadGlobalConfig` | 3 | Global config loading (exists, missing, invalid JSON) |
| `TestLoadProjectConfig` | 4 | Project config loading (exists, missing, explicit file, invalid JSON) |
| `TestMergeConfigsRfc7396` | 3 | RFC 7396 semantics (simple override, deep merge, array replacement) |
| `TestLoadConfigIntegration` | 4 | Full inheritance chain (global+project, global only, project only, defaults only) |

### 4. Test Fixes

Updated 3 existing tests in `test_orchestrator.py` that were affected by the global config loading:
- `test_init_without_config` - Patched global config path
- `test_visual_in_enabled_config` - Renamed and updated to use explicit config
- `test_behavioral_in_enabled_config` - Renamed and updated to use explicit config

## Config Inheritance Chain

```
1. Template defaults (DEFAULT_CONFIG, DEFAULT_DIMENSIONS)
       |
       v
2. Global config (~/.claude/validation/global-config.json)
       |
       v
3. Project config (.claude/validation/config.json)
       |
       v
4. Final config with _config_source metadata
```

## RFC 7396 Merge Rules

- Project values override global at same path
- Nested dicts are recursively merged
- Arrays are replaced entirely (not merged element-by-element)

## Verification

```bash
# Config loader tests (56 tests including 14 new)
pytest ~/.claude/templates/validation/tests/test_config_loader.py -v
# Result: 56 passed

# Orchestrator tests (61 tests - no regressions)
pytest ~/.claude/templates/validation/tests/test_orchestrator.py -v
# Result: 61 passed

# Combined
pytest ~/.claude/templates/validation/tests/test_config_loader.py \
       ~/.claude/templates/validation/tests/test_orchestrator.py -v
# Result: 117 passed
```

## Usage Example

```python
from config_loader import load_config

# Auto-discovers project config, merges with global
config = load_config()

# Check config sources
print(config["_config_source"])
# {'global': True, 'project': True, 'global_path': '...', 'project_path': '...'}

# Project overrides global coverage threshold
print(config["dimensions"]["coverage"]["min_percent"])
# 90 (from project, global had 70)
```

## Backward Compatibility

- Existing code using explicit config paths continues to work
- Projects without global config use template defaults
- `load_config_with_defaults()` remains available for legacy use
