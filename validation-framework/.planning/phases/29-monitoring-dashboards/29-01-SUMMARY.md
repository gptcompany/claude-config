---
phase: 29-monitoring-dashboards
plan: 01
status: completed
date: 2026-02-02
---

# Phase 29-01 Summary: OpenClaw Monitoring Dashboards

## What was built

### 1. Extended budget-enforcer.sh (+6 metrics)
- **File**: `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.sh`
- Python parser now outputs JSON with all metrics (cost + tasks + tokens + timestamp)
- Bash parses JSON and writes to `.prom` file
- Existing budget enforcement logic unchanged
- New metrics: `openclaw_tasks_total`, `openclaw_tasks_success`, `openclaw_task_success_rate`, `openclaw_tokens_input_total`, `openclaw_tokens_output_total`, `openclaw_last_update_timestamp`

### 2. Grafana Dashboard JSON (8 panels)
- **File**: `/home/sam/.claude/grafana/dashboards/openclaw-overview.json`
- UID: `openclaw-overview`, refresh 5m, Prometheus datasource variable
- Row 1: Daily Cost (gauge), Budget Remaining (gauge), Tasks Today (stat), Success Rate (stat)
- Row 2: Cost Trend (timeseries + budget threshold line), Token Usage (timeseries)
- Row 3: Task Success/Fail (stacked bars), Budget Status (state-timeline)

### 3. Alert Rules (3 rules)
- **File**: `/home/sam/.claude/grafana/alerting/openclaw-alert-rules.yaml`
- `openclaw-budget-exceeded` (critical, 2m for)
- `openclaw-low-success-rate` (warning, 10m for, threshold 70%)
- `openclaw-stale-metrics` (warning, 5m for, threshold 600s)

### 4. Contact Points (2 entries)
- **File**: `/home/sam/.claude/grafana/alerting/openclaw-contact-points.yaml`
- `discord-openclaw-critical` — Discord webhook
- `matrix-openclaw-ops` — Webhook placeholder for Matrix bridge

## Validation Results

| Tier | Check | Result |
|------|-------|--------|
| Tier 1 | .prom file written | PASS (9 metrics) |
| Tier 1 | Dashboard JSON valid | PASS (8 panels) |
| Tier 1 | Alert YAML valid | PASS (3 rules) |
| Tier 1 | Contact points YAML valid | PASS (2 entries) |
| Tier 1 | Metrics in Prometheus | PASS (9/9 queried via Grafana MCP) |
| Tier 2 | Dashboard import | MANUAL (MCP lacks write perms) |

## Metrics snapshot (2026-02-02)

```
openclaw_daily_cost_usd = 0.168924
openclaw_budget_max_usd = 5.00
openclaw_budget_exceeded = 0
openclaw_tasks_total = 8
openclaw_tasks_success = 0
openclaw_task_success_rate = 0.0
openclaw_tokens_input_total = 19
openclaw_tokens_output_total = 93
openclaw_last_update_timestamp = 1770055581
```

## Manual step required

Import dashboard to Grafana:
1. Visit http://192.168.1.111:3000
2. Dashboards → Import → Upload `openclaw-overview.json`
3. Select Prometheus datasource
