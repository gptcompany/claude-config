---
status: testing
phase: 17-observability-dashboards
source: 17-01-SUMMARY.md, 17-02-SUMMARY.md, 17-03-SUMMARY.md, 17-04-SUMMARY.md
started: 2026-01-26T15:00:00Z
updated: 2026-01-26T15:00:00Z
---

## Current Test

number: 1
name: CLI Summary Command
expected: |
  Run `vr summary` or `validation-report summary`.
  Shows validation summary with total runs, pass rate, and breakdown by dimension.
  Output is colorized (green for good, red for bad).
awaiting: user response

## Tests

### 1. CLI Summary Command
expected: Run `vr summary` shows validation summary with total runs, pass rate, dimension breakdown, colorized output
result: [pending]

### 2. CLI Failures Command
expected: Run `vr failures --days 14` shows validators sorted by pass rate (worst first)
result: [pending]

### 3. CLI Trend Command
expected: Run `vr trend accessibility --days 7` shows ASCII bar chart with daily pass rates
result: [pending]

### 4. CLI Projects Command
expected: Run `vr projects` shows cross-project quality scores comparison
result: [pending]

### 5. Grafana Overview Dashboard
expected: Open http://localhost:3000/d/validation-overview - shows 8 panels: stat panels (runs, pass rate, failures, duration), time series, tables
result: [pending]

### 6. Grafana Drilldown Dashboard
expected: Open http://localhost:3000/d/validator-drilldown - has dimension dropdown, shows per-validator metrics when selected
result: [pending]

### 7. Grafana Project Comparison Dashboard
expected: Open http://localhost:3000/d/project-comparison - shows quality scores by project, bar charts, trend lines
result: [pending]

### 8. Query Library Functions
expected: Run `node -e "require('/home/sam/.claude/scripts/lib/validation-queries.js').getValidationSummary(7).then(console.log)"` returns JSON with totals and byDimension
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0

## Issues for /gsd:plan-fix

[none yet]
