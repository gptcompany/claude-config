# PLAN 10-02: APIContractValidator Summary

**Status:** COMPLETE
**Date:** 2026-01-22

## Objective

Create APIContractValidator that detects OpenAPI spec breaking changes via oasdiff CLI.

## What Was Built

### 1. SpecDiscovery (`validators/api_contract/spec_discovery.py`)
- Auto-discovers OpenAPI specs in standard locations
- Standard paths checked:
  - `openapi.yaml`, `openapi.json`, `openapi.yml`
  - `api/openapi.*`, `docs/openapi.*`, `spec/openapi.*`
  - `swagger.yaml`, `swagger.json`
- Glob patterns: `**/openapi*.yaml`, `**/openapi*.json`, etc.
- Config override for custom paths
- Methods:
  - `find_specs(project_root)`: Find all specs
  - `find_baseline(project_root, config)`: Find baseline spec for comparison

### 2. OasdiffRunner (`validators/api_contract/oasdiff_runner.py`)
- Wrapper for oasdiff CLI tool
- Methods:
  - `is_available()`: Check if oasdiff binary exists
  - `breaking_changes(base_spec, revision_spec)`: Detect breaking changes
  - `diff(base_spec, revision_spec)`: Full diff between specs
- Parses JSON output for breaking changes (level, code, path, message)
- Graceful handling:
  - FileNotFoundError when oasdiff not installed
  - Timeout handling (30s default)
  - Various oasdiff JSON output formats

### 3. APIContractValidator (`validators/api_contract/validator.py`)
- Tier 3 (MONITOR) validator
- No auto-fix agent (contract changes need human review)
- Integrates SpecDiscovery and OasdiffRunner
- Graceful degradation:
  - oasdiff not installed: passes with warning
  - No specs found: passes (nothing to validate)
  - No baseline configured: passes (no comparison possible)

### 4. Orchestrator Integration
- Added import with fallback in `orchestrator.py`
- Created wrapper class with stub fallback
- Updated `VALIDATOR_REGISTRY` to use real implementation
- Updated `orchestrator.py.j2` template

## Verification Results

```
APIContractValidator result: No OpenAPI specs found
Details: {'specs_found': 0, 'oasdiff_available': False}
```

oasdiff not installed on this system - validator gracefully degraded.

## Files Modified

- `~/.claude/templates/validation/validators/api_contract/__init__.py` (new)
- `~/.claude/templates/validation/validators/api_contract/spec_discovery.py` (new)
- `~/.claude/templates/validation/validators/api_contract/oasdiff_runner.py` (new)
- `~/.claude/templates/validation/validators/api_contract/validator.py` (new)
- `~/.claude/templates/validation/orchestrator.py` (updated)
- `~/.claude/templates/validation/orchestrator.py.j2` (updated)

## Notes

- oasdiff can be installed via: `go install github.com/oasdiff/oasdiff@latest`
- Breaking change detection requires baseline spec path in config
- Tier 3 validators never block the pipeline (graceful degradation by design)
- Future enhancement: git-based baseline tracking (Phase 11)
