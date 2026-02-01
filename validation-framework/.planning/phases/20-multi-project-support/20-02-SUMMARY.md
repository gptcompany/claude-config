---
phase: 20-multi-project-support
plan: 02
status: complete
completed: 2026-01-26
---

# Plan 02 Summary: Monorepo Package Discovery

## Objective
Implement monorepo package discovery via directory convention to auto-detect packages with validation configs.

## Deliverables

### 1. `monorepo.py` Module
**Location:** `~/.claude/templates/validation/monorepo.py`

**Components:**
- `IGNORE_DIRS` - Set of directories to skip during discovery
- `PackageInfo` - Dataclass with name, path, config_path, and merged config
- `is_ignored(path)` - Check if path should be skipped
- `discover_packages(root, max_depth=3)` - Find all packages with configs
- `is_monorepo(root)` - Return True if >1 package found
- CLI entry point for `python monorepo.py [path]`

**IGNORE_DIRS includes:**
```python
{'.git', 'node_modules', '__pycache__', '.venv', 'venv',
 'dist', 'build', '.next', '.nuxt', '.tox', '.pytest_cache',
 '.mypy_cache', '.ruff_cache', 'htmlcov', 'coverage',
 '.eggs', '*.egg-info', '.nox', '.cache'}
```

### 2. Unit Tests
**Location:** `~/.claude/templates/validation/tests/test_monorepo.py`

**20 tests covering:**
1. `test_discover_single_project` - Single package at root
2. `test_discover_monorepo` - Multiple packages found
3. `test_ignore_node_modules` - node_modules skipped
4. `test_ignore_pycache` - __pycache__ skipped
5. `test_ignore_git` - .git skipped
6. `test_max_depth_respected` - Deep packages filtered
7. `test_is_monorepo_true` - Multi-package returns True
8. `test_is_monorepo_false` - Single package returns False
9. `test_package_info_has_merged_config` - Config merged with defaults
10. `test_empty_directory` - Empty dir returns []
11-20. Additional edge cases (glob patterns, hidden dirs, sorting, etc.)

### 3. CLI Entry Point
```bash
# Discover packages in current directory
python monorepo.py .

# Discover packages in specific path
python monorepo.py /path/to/monorepo
```

**Output:**
```
Found 2 package(s):
  - backend: /path/to/monorepo/packages/backend
  - frontend: /path/to/monorepo/packages/frontend
```

## Verification

```bash
# Run tests (20 passed)
pytest ~/.claude/templates/validation/tests/test_monorepo.py -v

# Test CLI
python ~/.claude/templates/validation/monorepo.py /tmp/test-monorepo
# Output: Found 2 package(s): backend, frontend
```

## Integration Points

- Uses `load_config()` from `config_loader.py` (20-01) for merged configs
- Provides foundation for `multi_validate.py` (20-03)
- Enables validation commands to auto-detect monorepo structure

## Files Modified
- `~/.claude/templates/validation/monorepo.py` (NEW)
- `~/.claude/templates/validation/tests/test_monorepo.py` (NEW)

## Next Steps
Plan 20-03: Implement `multi_validate.py` to orchestrate validation across discovered packages.
