# Plan 11-03 Summary: Ralph Loop and Grafana Dashboard

**Phase:** 11-ralph-integration
**Plan:** 03
**Status:** COMPLETED
**Completed:** 2026-01-23

## Objective

Create Ralph Loop iterative validation state machine with CLI interface and Grafana dashboard for observability.

## Tasks Completed

### Task 1: Create Ralph Loop state machine
**File created:**
- `~/.claude/templates/validation/ralph_loop.py`

**Implementation:**

1. **LoopState enum** with states:
   - `IDLE` - Initial state
   - `VALIDATING` - Running validation
   - `BLOCKED` - Tier 1 failed (cannot proceed)
   - `FIX_REQUESTED` - Waiting for fixes
   - `COMPLETE` - Validation finished

2. **RalphLoopConfig dataclass**:
   ```python
   max_iterations: int = 5
   min_score_threshold: float = 70.0
   tier1_timeout_seconds: float = 30.0
   tier2_timeout_seconds: float = 120.0
   ```
   - Supports loading from JSON file
   - Supports CLI overrides

3. **LoopResult dataclass**:
   - state, iteration, score, blockers, message
   - history: list of IterationHistory
   - execution_time_ms
   - to_dict() for JSON serialization

4. **RalphLoop class**:
   - State machine: IDLE -> VALIDATING -> (BLOCKED | COMPLETE)
   - Tier 1 blocks immediately on failure
   - Tier 2+3 run in parallel after Tier 1 passes
   - Score calculation with weighted average (T1: 50%, T2: 30%, T3: 20%)
   - Loop continues until score >= threshold or max iterations

5. **Integration calls**:
   - `push_validation_metrics()` after each tier
   - `inject_validation_context()` after each tier
   - `add_validation_breadcrumb()` for timeline events

6. **CLI interface**:
   - `--files`: comma-separated or stdin
   - `--project`: project name (auto-detect from git)
   - `--config`: optional config file path
   - `--json`: output as JSON
   - `--max-iterations`: override config
   - `--threshold`: override config

**Verification:**
```bash
python3 ralph_loop.py --help
# Shows usage with all options

python3 ralph_loop.py --files test.py --project test --json
# Returns structured JSON result
```

### Task 2: Create Grafana dashboard template
**Files created:**
- `~/.claude/templates/validation/dashboards/__init__.py`
- `~/.claude/templates/validation/dashboards/validation-dashboard.json`

**Dashboard specifications:**
- uid: `validation-orchestrator`
- title: `Validation Orchestrator`
- tags: `["validation", "ci", "quality"]`

**Panels (10 total):**

| Row | Panel | Type | Query |
|-----|-------|------|-------|
| Overview | Validation Pass Rate | stat | `rate(validation_runs_total{result='pass'}[1h])` |
| Overview | Current Score | stat | `avg(validation_score)` |
| Overview | Active Blockers | stat | `sum(validation_blockers_count)` |
| Trends | Validation Runs | timeseries | `rate(validation_runs_total[5m])` |
| Trends | Duration Heatmap | heatmap | `validation_duration_seconds_bucket` |
| Breakdown | Blockers by Validator | timeseries | `validation_blockers_count by validator` |
| Breakdown | Tier Results | bargauge | `validation_runs_total by tier` |

**Variables:**
- `project`: label_values(validation_runs_total, project)
- `tier`: 1, 2, 3 (custom)

**Settings:**
- Default time range: Last 6 hours
- Auto-refresh: 30 seconds
- Datasource: `${DS_PROMETHEUS}`

**Verification:**
```bash
python3 -c "import json; d = json.load(open('dashboards/validation-dashboard.json')); print('panels:', len(d.get('panels', [])))"
# panels: 10
```

### Task 3: Add git post-commit hook template
**File created:**
- `~/.claude/templates/validation/hooks/post-commit.sh`

**Implementation:**
- Non-blocking (runs in background)
- Extracts changed files from `git diff-tree`
- Auto-detects project name from git root
- Saves JSON output to `/tmp/ralph_result.json`
- Optional desktop notifications (`RALPH_LOOP_NOTIFY=1`)
- Logs to `~/.claude/logs/ralph-hook.log`

**Configuration via environment:**
- `RALPH_LOOP_SCRIPT`: path to ralph_loop.py
- `RALPH_LOOP_CONFIG`: path to config.json
- `RALPH_LOOP_JSON`: enable JSON output (default: 1)
- `RALPH_LOOP_NOTIFY`: enable desktop notifications

**Installation:**
```bash
cp ~/.claude/templates/validation/hooks/post-commit.sh .git/hooks/post-commit
chmod +x .git/hooks/post-commit
```

**Verification:**
```bash
bash -n ~/.claude/templates/validation/hooks/post-commit.sh && echo "syntax ok"
# syntax ok
```

## Verification Results

| Check | Status |
|-------|--------|
| `python3 ralph_loop.py --help` shows usage | PASS |
| `python3 ralph_loop.py --files test.py --project test --json` runs | PASS |
| Dashboard JSON is valid | PASS |
| Dashboard has 10 panels (>= 6 required) | PASS |
| post-commit.sh passes bash -n syntax check | PASS |
| Integration with metrics/sentry from Plan 11-02 works | PASS |

## Success Criteria Met

- [x] All tasks completed
- [x] Ralph loop runs iteratively with state machine
- [x] Tier 1 blocks, Tier 2+3 run in parallel
- [x] Metrics pushed after each tier
- [x] Dashboard ready for Grafana import (10 panels)
- [x] Git hook template ready for installation

## Files Created/Modified

| File | Action | LOC |
|------|--------|-----|
| `~/.claude/templates/validation/ralph_loop.py` | Created | ~520 |
| `~/.claude/templates/validation/dashboards/__init__.py` | Created | 25 |
| `~/.claude/templates/validation/dashboards/validation-dashboard.json` | Created | ~700 |
| `~/.claude/templates/validation/hooks/post-commit.sh` | Created | 95 |

**Total new code:** ~1340 lines

## Integration Summary

Ralph Loop now integrates with:

1. **Prometheus (via Plan 11-02)**
   - Pushes metrics after each tier completion
   - Enables real-time Grafana visualization

2. **Sentry (via Plan 11-02)**
   - Injects context for debugging
   - Adds breadcrumbs for timeline tracking

3. **Git (via post-commit hook)**
   - Triggers validation automatically on commit
   - Non-blocking execution

## Usage Examples

### CLI Validation
```bash
# Run validation on specific files
python3 ralph_loop.py --files "src/main.py,src/utils.py" --project myapp --json

# Pipe files from git
git diff --name-only HEAD~1 | python3 ralph_loop.py --project myapp
```

### Git Hook Setup
```bash
# Install hook
cp ~/.claude/templates/validation/hooks/post-commit.sh .git/hooks/post-commit
chmod +x .git/hooks/post-commit

# Enable notifications
export RALPH_LOOP_NOTIFY=1
```

### Grafana Dashboard Import
1. Open Grafana
2. Go to Dashboards > Import
3. Upload `validation-dashboard.json`
4. Select Prometheus datasource
5. Click Import

## Next Steps

Phase 11 (Ralph Integration) is now complete:
- Plan 11-01: PostToolUse hook infrastructure
- Plan 11-02: Metrics and Sentry integration
- Plan 11-03: Ralph Loop and Grafana dashboard (this plan)

Ready to proceed to Phase 12 if defined in ROADMAP.md.
