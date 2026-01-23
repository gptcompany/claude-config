---
status: testing
phase: 11-ralph-integration
source: 11-01-SUMMARY.md, 11-02-SUMMARY.md, 11-03-SUMMARY.md
started: 2026-01-23T19:05:00Z
updated: 2026-01-23T19:05:00Z
---

## Current Test

number: 1
name: Hook imports successfully
expected: |
  Run: `cd ~/.claude/templates/validation && python3 -c "from hooks.post_tool_hook import main; print('ok')"`
  Output: "ok" (no import errors)
awaiting: user response

## Tests

### 1. Hook imports successfully
expected: `python3 -c "from hooks.post_tool_hook import main"` returns "ok"
result: [pending]

### 2. Read tool gets immediate approve
expected: `echo '{"tool_name": "Read", "tool_input": {}}' | python3 hooks/post_tool_hook.py` returns `{"decision": "approve"}`
result: [pending]

### 3. Metrics module graceful degradation
expected: `python3 -c "from integrations.metrics import push_validation_metrics; print('ok')"` imports without error
result: [pending]

### 4. Sentry module graceful degradation
expected: `python3 -c "from integrations.sentry_context import inject_validation_context; print('ok')"` imports without error
result: [pending]

### 5. Ralph Loop CLI help
expected: `python3 ralph_loop.py --help` shows usage with --files, --project, --json options
result: [pending]

### 6. Ralph Loop JSON output
expected: `python3 ralph_loop.py --files test.py --project test --json` returns valid JSON with state, score, blockers fields
result: [pending]

### 7. Grafana dashboard valid JSON
expected: `python3 -c "import json; json.load(open('dashboards/validation-dashboard.json'))"` parses without error
result: [pending]

### 8. Install helper dry-run
expected: `python3 hooks/install.py --dry-run` shows hook configuration preview
result: [pending]

### 9. Unit tests pass
expected: `pytest tests/ -v` shows 177+ tests passing, 71%+ coverage
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0

## Issues for /gsd:plan-fix

[none yet]
