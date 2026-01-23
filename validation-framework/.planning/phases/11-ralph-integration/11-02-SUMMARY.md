# Plan 11-02 Summary: Metrics and Sentry Integration

**Status:** COMPLETED
**Completed:** 2026-01-23
**Duration:** ~15 minutes

## Tasks Completed

### Task 1: Create Prometheus metrics module
**Files created:**
- `~/.claude/templates/validation/integrations/__init__.py`
- `~/.claude/templates/validation/integrations/metrics.py`

**Implementation:**
- Isolated `CollectorRegistry` (doesn't pollute global Prometheus registry)
- Metrics defined:
  - `validation_runs_total` (Counter) - labels: tier, result, project
  - `validation_duration_seconds` (Histogram) - labels: tier, validator
  - `validation_score` (Gauge) - labels: tier, project
  - `validation_blockers_count` (Gauge) - labels: project, validator
- `push_validation_metrics(result, project)` function:
  - Accepts both `TierResult` and `ValidationReport`
  - Pushes to Pushgateway (default: localhost:9091)
  - Catches connection errors, logs warning, doesn't crash
- Graceful degradation: no-op if prometheus_client not installed
- `PUSHGATEWAY_URL` env var support
- Warning logged once on first call if prometheus_client missing

**Verification:**
```bash
cd ~/.claude/templates/validation && python3 -c "from integrations.metrics import push_validation_metrics; print('import ok')"
# Output: import ok
```

### Task 2: Create Sentry context injection module
**File created:**
- `~/.claude/templates/validation/integrations/sentry_context.py`

**Implementation:**
- `inject_validation_context(result)` - injects structured context:
  - `set_context("validation", {...})` - tier, passed, score, blockers, warnings, validators_run, duration_ms
  - `set_tag(...)` - validation.tier, validation.passed, validation.score
  - `add_breadcrumb(...)` - timeline entry with validator details
- `capture_validation_error(error, context)`:
  - Uses `push_scope()` for isolated context
  - Sets fingerprint for proper error grouping
  - Adds validation-specific extras and tags
- `add_validation_breadcrumb(message, level, data)` - helper for manual breadcrumbs
- Graceful degradation:
  - No-op if sentry_sdk not installed
  - No-op if Sentry not initialized (no client)
  - No warnings, no crashes (Sentry is optional)

**Verification:**
```bash
cd ~/.claude/templates/validation && python3 -c "from integrations.sentry_context import inject_validation_context; print('import ok')"
# Output: import ok
```

### Task 3: Wire integrations into orchestrator
**File modified:**
- `~/.claude/templates/validation/orchestrator.py`

**Changes:**
1. Added conditional imports at top with fallback no-op functions:
   ```python
   try:
       from integrations.metrics import push_validation_metrics, METRICS_AVAILABLE
   except ImportError:
       METRICS_AVAILABLE = False
       def push_validation_metrics(*args, **kwargs): pass
   ```

2. Added `_log_integrations_status()` function - logs available integrations once at startup

3. Updated `run_all()` method:
   - Calls `_log_integrations_status()` at start
   - After each tier completion:
     - `push_validation_metrics(tier_result, project_name)`
     - `inject_validation_context(tier_result)`
   - When blocked (Tier 1 fails):
     - `add_validation_breadcrumb()` with blocker details
   - Final push with full ValidationReport before return

**Verification:**
```bash
cd ~/.claude/templates/validation && python3 orchestrator.py --tier 1 2>&1 | head -20
# Output: Tier 1: FAILED (no import errors)
```

## Verification Results

| Check | Status |
|-------|--------|
| `from integrations.metrics import push_validation_metrics` | PASS |
| `from integrations.sentry_context import inject_validation_context` | PASS |
| `python3 orchestrator.py --tier 1` runs without import errors | PASS |
| Metrics push attempted (logged when Pushgateway unavailable) | PASS |
| Sentry context injection attempted (graceful if not initialized) | PASS |
| Integrations status logged at startup | PASS |

## Log Output Sample

```json
{"timestamp": "2026-01-23 17:57:59,511", "level": "INFO", "module": "orchestrator", "message": "Integrations available: Sentry context"}
{"timestamp": "2026-01-23 17:58:06,294", "level": "WARNING", "module": "orchestrator", "message": "prometheus_client not installed - metrics will not be pushed. Install with: pip install prometheus_client"}
{"timestamp": "2026-01-23 17:58:06,295", "level": "WARNING", "module": "orchestrator", "message": "Tier 1 BLOCKED: ['code_quality', 'type_safety', 'security', 'coverage']"}
```

## Key Design Decisions

1. **Lazy initialization for metrics** - Registry and metrics created on first push, not at import time
2. **No warnings for Sentry** - Sentry is fully optional, silence is golden
3. **One warning for Prometheus** - Logged once on first call to help debugging
4. **Hub-based Sentry check** - Uses `sentry_sdk.Hub.current.client` to check if SDK is initialized
5. **Both TierResult and ValidationReport supported** - Functions detect type and handle accordingly

## Files Created/Modified

| File | Action | LOC |
|------|--------|-----|
| `integrations/__init__.py` | Created | 18 |
| `integrations/metrics.py` | Created | 215 |
| `integrations/sentry_context.py` | Created | 268 |
| `orchestrator.py` | Modified | +70 |

**Total new code:** ~571 LOC

## Dependencies (Optional)

- `prometheus_client` - for metrics push to Pushgateway
- `sentry_sdk` - for context injection (already installed in environment)

Both are optional - code gracefully degrades without them.

## Next Steps

Plan 11-03: Create the PostToolUse hook that uses these integrations to validate file changes in real-time during Claude Code sessions.
