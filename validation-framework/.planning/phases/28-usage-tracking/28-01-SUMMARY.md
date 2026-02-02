# Phase 28: Usage Tracking & Budget - Summary

**Completed:** 2026-02-02
**Plan:** 28-01

## What Was Done

### Task 1: OTEL Diagnostics in OpenClaw Config ✅
- Added `diagnostics-otel` to `plugins.allow` and `plugins.entries` in `openclaw.json`
- Added `/app/extensions/diagnostics-otel` to `plugins.load.paths`
- Configured `diagnostics.otel` with endpoint, protocol, service name, metrics-only
- Set `diagnostics.enabled: true` (required by plugin startup guard)
- Installed OTEL SDK v1.x dependencies in extension directory (v2.x incompatible with plugin code)
- Created symlink `/app/node_modules/@opentelemetry` → extension's `node_modules/@opentelemetry` (pnpm strict mode workaround)
- **Note:** Plugin loads without errors but does NOT emit metrics in embedded agent CLI mode. Diagnostic events (`model.usage`) are only emitted during interactive Matrix sessions, not `agent --message` CLI runs. This is a known limitation.

### Task 2: Metrics Pipeline ✅
- Deployed OTEL Collector (`otel/opentelemetry-collector-contrib:latest`) on Workstation
  - OTLP HTTP receiver on port 4318
  - Prometheus scrape exporter on port 8889
  - Docker compose at `/media/sam/1TB/moltbot-iac/workstation/otel/docker-compose.yml`
- Added `otel-collector` scrape job to Prometheus config (`/etc/prometheus/prometheus.yml`)
- Enabled `--web.enable-otlp-receiver` in Prometheus systemd service (native OTLP support for future use)
- **Pivot:** Since OTEL plugin doesn't emit in CLI mode, implemented log-based metrics exporter:
  - Budget enforcer script reads JSONL logs from gateway container via SSH
  - Parses `agentMeta.usage` from completed runs
  - Calculates cost per model using cost table
  - Writes Prometheus-format metrics to `/media/sam/1TB/moltbot-iac/workstation/node_exporter_textfile/openclaw.prom`

### Task 3: Budget Enforcer ✅
- Created `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.sh`
  - Reads today's OpenClaw JSONL logs from gateway container
  - Calculates daily cost using Python inline parser (handles nested JSON reliably)
  - Cost table covers: claude-opus-4-5, claude-sonnet-4, gemini-2.5-flash/pro, kimi-k2.5, gpt-5.2
  - Compares against `MAX_DAILY_USD` (default $5.00, configurable via env)
  - On overspend: creates `/tmp/openclaw-budget-exceeded` flag + sends Matrix alert to bambam room
  - On recovery: removes flag automatically
  - Logs to `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.log`
- Created systemd service + timer files (in `/media/sam/1TB/moltbot-iac/workstation/`)
  - `budget-enforcer.service`: Type=oneshot, runs as sam
  - `budget-enforcer.timer`: Every 5 minutes, persistent

## Metrics Exposed

| Metric | Type | Description |
|--------|------|-------------|
| `openclaw_daily_cost_usd` | gauge | Estimated daily cost in USD |
| `openclaw_budget_max_usd` | gauge | Daily budget cap |
| `openclaw_budget_exceeded` | gauge | 1 if over budget, 0 otherwise |

## Current Values (at deploy)

- Daily cost: **$0.17** (8 agent runs, mostly claude-opus-4-5 cache reads)
- Budget cap: **$5.00/day**
- Budget exceeded: **No**

## Files Modified/Created

| File | Action |
|------|--------|
| `192.168.1.100:/home/sam/moltbot-infra/clawdbot-config/openclaw.json` | Modified (OTEL config, plugin paths) |
| `/etc/prometheus/prometheus.yml` | Modified (added otel-collector scrape job) |
| `/etc/systemd/system/prometheus.service` | Modified (added --web.enable-otlp-receiver) |
| `/media/sam/1TB/moltbot-iac/workstation/otel/docker-compose.yml` | Created |
| `/media/sam/1TB/moltbot-iac/workstation/otel/otel-collector.yaml` | Created |
| `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.sh` | Created |
| `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.service` | Created |
| `/media/sam/1TB/moltbot-iac/workstation/budget-enforcer.timer` | Created |

## Manual Steps Required

The following require manual execution (blocked by safety hooks):

```bash
# 1. Install systemd timer
sudo cp /media/sam/1TB/moltbot-iac/workstation/budget-enforcer.service \
        /media/sam/1TB/moltbot-iac/workstation/budget-enforcer.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now budget-enforcer.timer

# 2. Enable node_exporter textfile collector (optional, for Prometheus metrics)
sudo sed -i 's|ExecStart=/usr/local/bin/node_exporter.*|ExecStart=/usr/local/bin/node_exporter --collector.systemd --collector.processes --collector.textfile.directory=/media/sam/1TB/moltbot-iac/workstation/node_exporter_textfile|' /etc/systemd/system/node_exporter.service
sudo systemctl daemon-reload
sudo systemctl restart node_exporter
```

## Known Limitations

1. **OTEL plugin doesn't emit in CLI mode**: The `diagnostics-otel` plugin only emits `model.usage` events during interactive Matrix sessions, not embedded agent CLI runs (`agent --message`). This is an OpenClaw upstream limitation.
2. **Log-based metrics are point-in-time**: The budget enforcer calculates from today's log file. Historical data requires log retention.
3. **Cost table is static**: Model pricing changes require updating the COST_TABLE in the script.
4. **Google OAuth models show $0**: By design, Google OAuth tokens don't report cost in OpenClaw.

## Verification Checklist

- [x] Budget enforcer calculates cost correctly ($0.17 from 8 runs)
- [x] Prometheus metrics file written correctly
- [x] Flag file mechanism works (tested: creates on overspend, removes on recovery)
- [x] OTEL Collector running and healthy
- [x] No errors in OpenClaw gateway logs
- [ ] Systemd timer active (requires manual install)
- [ ] Node_exporter textfile collector enabled (requires manual config)
