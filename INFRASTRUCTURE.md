# Infrastructure Map - SSOT

**Ultimo aggiornamento:** 2026-01-15

## Quick Reference

| Cosa | Dove | SSOT |
|------|------|------|
| **Config principale** | `~/.claude/canonical.yaml` | ✓ |
| **API Keys** | `~/.claude/.env` | ✓ |
| **MCP Profiles** | `~/.claude/mcp-profiles/` | ✓ |
| **Hooks** | `/media/sam/1TB/claude-hooks-shared/` | ✓ |
| **Scripts** | `~/.claude/scripts/` | ✓ |
| **Commands** | `~/.claude/commands/` | ✓ |
| **Skills** | `~/.claude/skills/` | ✓ |
| **Monitoring** | `/media/sam/1TB/nautilus_dev/monitoring/` | ✓ |

---

## 1. Directory Structure

```
~/.claude/                              # GLOBAL CONFIG
├── canonical.yaml                      # SSOT principale
├── .env                                # API keys (SSOT secrets)
├── settings.json                       # Claude Code settings
├── INFRASTRUCTURE.md                   # Questo file
│
├── mcp-profiles/                       # MCP configs globali
│   ├── base.json                       # Minimal (context7)
│   └── live.json                       # Full (sentry, linear, claude-flow)
│
├── scripts/                            # Utility scripts
│   ├── drift-detector.py               # Health check
│   ├── taskstoissues.py                # Tasks → GitHub Issues
│   └── trigger-n8n-research.sh         # N8N integration
│
├── commands/                           # Slash commands (GLOBAL)
│   ├── speckit.*.md                    # SpecKit workflow
│   ├── tdd/*.md                        # TDD commands
│   └── undo/*.md                       # Undo system
│
├── skills/                             # Skills (GLOBAL)
│   ├── pytest-test-generator/
│   ├── pydantic-model-generator/
│   └── github-workflow/
│
├── specs/                              # SpecKit specs
│   └── backstage-idp/
│       └── spec.md
│
├── plans/                              # Plan mode files
├── metrics/                            # Session metrics
└── templates/                          # Project templates

/media/sam/1TB/claude-hooks-shared/     # HOOKS (SSOT)
├── hooks/
│   ├── core/                           # Essential hooks
│   ├── safety/                         # Security checks
│   ├── productivity/                   # Auto-format, TDD guard
│   ├── metrics/                        # DORA, token tracking
│   ├── intelligence/                   # Tips, session analyzer
│   ├── quality/                        # Sentry, PR readiness
│   └── ux/                             # Notifications
└── scripts/
    └── context-monitor.py              # Status line

/media/sam/1TB/nautilus_dev/monitoring/ # MONITORING (shared)
├── grafana/
│   ├── dashboards/                     # JSON dashboards
│   └── provisioning/
├── prometheus/
└── docker-compose.yml
```

---

## 2. Repositories

| Repo | Path | Purpose |
|------|------|---------|
| **nautilus_dev** | `/media/sam/1TB/nautilus_dev` | Trading platform |
| **N8N_dev** | `/media/sam/1TB/N8N_dev` | Workflow automation |
| **UTXOracle** | `/media/sam/1TB/UTXOracle` | Bitcoin analytics |
| **LiquidHeatmap** | `/media/sam/1TB/LiquidHeatmap` | Visualization |

Ogni repo ha:
```
{repo}/
├── CLAUDE.md                           # At ROOT (not .claude/)
├── .claude/
│   ├── settings.local.json             # Local overrides
│   └── agents/                         # Project-specific agents
├── .mcp.json                           # Base MCP config
└── .mcp.live.json                      # Extended MCP (optional)
```

---

## 3. Environment Variables

### SSOT: `~/.claude/.env`
```
LINEAR_API_KEY=...          # Linear issue tracking
DISCORD_WEBHOOK_URL=...     # Notifications
N8N_AUTH_TOKEN=...          # N8N automation
N8N_AUTH_HEADER=...         # N8N auth
```

### Infra: `/media/sam/1TB/nautilus_dev/.env`
```
QUESTDB_HOST=localhost
QUESTDB_ILP_PORT=9009
SENTRY_DSN=...
SENTRY_ORG=...
```

### AI Tools: `/media/sam/1TB/N8N_dev/.env`
```
GOOGLE_CLOUD_PROJECT=...
LANGSMITH_API_KEY=...
BRAVE_API_KEY=...
```

**REGOLA:** Ogni variabile in UN SOLO file. `drift-detector.py` verifica duplicati.

---

## 4. MCP Profiles

### Globali (`~/.claude/mcp-profiles/`)

| Profile | File | MCP Servers |
|---------|------|-------------|
| **base** | `base.json` | context7 |
| **live** | `live.json` | context7, sentry, linear, claude-flow |

### Per-progetto

| Repo | Config | Additional MCPs |
|------|--------|-----------------|
| nautilus_dev | `.mcp.live.json` | serena, wolframalpha, matlab |
| N8N_dev | `.mcp.json` | n8n-mcp |
| N8N_dev | `.mcp.browser.json` | puppeteer |

### Aliases (in `~/.bashrc`)

```bash
# Globali (profili SSOT)
alias ccbase="claude --mcp-config ~/.claude/mcp-profiles/base.json"
alias ccfull="claude --mcp-config ~/.claude/mcp-profiles/live.json"

# Per-progetto (nel repo)
alias cclive="claude --mcp-config .mcp.live.json"
alias ccbrowser="claude --mcp-config .mcp.browser.json"
```

---

## 5. Services

### Monitoring Stack

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| Grafana | 3000 | Dashboards | `systemctl status grafana-server` |
| Prometheus | 9090 | Metrics scraping | `systemctl status prometheus` |
| Alertmanager | 9093 | Alert routing → Discord | `systemctl status alertmanager` |
| Loki | 3100 | Log aggregation | Docker |
| Promtail | - | Log collector | Docker |
| Auto-remediation | 9095 | Webhook auto-fix | `systemctl status auto-remediation` |

### Data Storage

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| QuestDB | 9000/9009 | Time-series (Claude metrics) | Docker |
| InfluxDB | 8086 | Bitcoin historical data | Docker |
| PostgreSQL | 5433 | N8N + Backstage DB | Docker |
| Redis | 6379 | Cache | Docker |

### Platform Services

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| Backstage | 7007 | Developer Portal | Docker |
| N8N | 5678 | Workflow Automation | Docker |
| Phoenix | 6006 | LLM Observability | Docker |

### Production Apps (2TB-NVMe)

| App | Path | Docker Container |
|-----|------|------------------|
| QuestDB | `/media/sam/2TB-NVMe/prod/apps/questdb` | nautilus-questdb |
| Nautilus | `/media/sam/2TB-NVMe/prod/apps/nautilus` | - |
| Mempool | `/media/sam/2TB-NVMe/prod/apps/mempool-stack` | mempool-* |
| InfluxDB | `/media/sam/2TB-NVMe/prod/services/influxdb` | influxdb-production |

---

## 6. Hooks Flow

```
User Input
    │
    ▼
UserPromptSubmit
├── session_start_tracker.py    # Tips injection
├── ci_status_injector.py       # CI status
├── task-classifier-v2.py       # Task type
└── ralph-resume.py             # Resume sessions

    │
    ▼
PreToolUse
├── context_bundle_builder.py   # Context injection
├── smart-safety-check.py       # Security (Bash)
├── git-safety-check.py         # Git protection
└── tdd-guard-check.py          # TDD enforcement (Edit)

    │
    ▼
[Tool Execution]
    │
    ▼
PostToolUse
├── post-tool-use.py            # Metrics
├── dora-tracker.py             # DORA metrics
├── auto-format.py              # Code formatting
├── architecture-validator.py   # ARCHITECTURE.md
└── sentry-error-context.py     # Error suggestions

    │
    ▼
Stop
├── context-preservation.py     # Save context
├── session_analyzer.py         # Generate tips
├── session_insights_writer.py  # Write SSOT
└── auto-ralph.py               # Pipeline automation
```

---

## 7. Commands Quick Reference

| Command | Purpose |
|---------|---------|
| `/health` | System health check |
| `/tips` | Show optimization tips |
| `/speckit.specify` | Create feature spec |
| `/speckit.plan` | Plan implementation |
| `/speckit.tasks` | Generate tasks |
| `/speckit.implement` | Execute tasks |
| `/tdd:cycle` | TDD workflow |
| `/undo:checkpoint` | Create checkpoint |
| `/undo:rollback` | Rollback changes |

---

## 8. Scheduled Automation (Cron)

| Schedule | Script | Purpose |
|----------|--------|---------|
| `*/30 * * * *` | drift-to-questdb.py | Save drift metrics |
| `0 * * * *` | drift-detector.py | Hourly drift detection |
| `0 4 * * 0` | repo-cleanup.py --all | Weekly repo cleanup |
| `0 6 * * *` | repo-compliance.py --all | Daily compliance check |
| `0 */2 * * *` | sync-to-backstage.py | Sync catalog to Backstage |
| `0 8 * * 1` | weekly-health-report.sh | Monday Discord report |

**Logs:** `/tmp/{script-name}.log`

---

## 9. Health Checks

```bash
# Full drift check
python3 ~/.claude/scripts/drift-detector.py

# Quick service check
systemctl status grafana-server prometheus alertmanager auto-remediation

# Docker services
docker ps --format "table {{.Names}}\t{{.Status}}"

# Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'

# Loki health
curl -s http://localhost:3100/ready

# QuestDB tables
curl -s "http://localhost:9000/exec?query=SHOW%20TABLES" | jq '.dataset[][0]'
```

---

## 10. Alerting & Auto-Remediation

### Alertmanager Configuration
- **Config:** `/etc/alertmanager/alertmanager.yml`
- **Discord Webhook:** Alerts sent to Discord channel
- **Auto-fix:** Critical alerts trigger auto-remediation

### Prometheus Alert Rules
- **Location:** `/etc/prometheus/rules/`
- **Files:** `backstage.yml`, `system-alerts.yml`

### Auto-Remediation Actions
| Alert | Action |
|-------|--------|
| BackstageDown | `docker restart backstage-portal` |
| N8NDown | `docker restart n8n-n8n-1` |
| LokiDown | `docker restart loki` |
| QuestDBDown | `docker restart nautilus-questdb` |

### Runbooks
- **Location:** `~/.claude/runbooks/`
- grafana-down.md
- backstage-down.md
- questdb-issues.md
- disk-space-low.md

---

## 11. Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| Tips non appaiono | Check `~/.claude/metrics/session_insights.json` |
| MCP non carica | Verifica path in `--mcp-config` |
| Env var mancante | Check `~/.claude/.env` + `source ~/.bashrc` |
| Hook fallisce | Check timeout in `settings.json` |
| Grafana down | `sudo systemctl restart grafana-server` |

---

## 12. Backstage Developer Portal

**URL**: http://localhost:3002 (frontend) | http://localhost:7007 (backend API)
**Location**: `/media/sam/1TB/backstage-portal/`

### Quick Start

```bash
# Option 1: Systemd service (enterprise - auto-start on boot)
sudo /media/sam/1TB/backstage-portal/install-service.sh
systemctl status backstage

# Option 2: Development mode with GSM
backstage-start  # alias for ./start-with-gsm.sh

# Option 3: Simple mode (no GSM)
backstage-start-simple

# Open in browser
ccbackstage  # alias for xdg-open http://localhost:3002
```

### Features

| Feature | Status | Notes |
|---------|--------|-------|
| Software Catalog | ✅ Active | All 4 repos registered |
| Grafana Integration | ✅ Configured | Requires Grafana on :3000 |
| GitHub Actions | ✅ Configured | Token from GSM |
| GitHub PRs | ✅ Configured | Token from GSM |
| MCP Profiles | ✅ Active | base & live profiles |
| GSM Integration | ✅ Active | start-with-gsm.sh |
| Systemd Service | ✅ Ready | install-service.sh |
| PostgreSQL | ✅ Connected | n8n PostgreSQL :5433 |

### Catalog Locations

- Repos: `{repo}/catalog-info.yaml` in each repository
- System: `/media/sam/1TB/backstage-portal/catalog/system.yaml`
- MCP: `/media/sam/1TB/backstage-portal/catalog/mcp/`

### Aliases

```bash
alias ccbackstage='xdg-open http://localhost:3002'
alias backstage-start='cd /media/sam/1TB/backstage-portal && ./start-with-gsm.sh'
alias backstage-start-simple='cd /media/sam/1TB/backstage-portal && source .env && yarn start'
```

---

## 13. Google Secret Manager (GSM)

**Project**: `$GOOGLE_CLOUD_PROJECT` (from N8N_dev/.env)

### Available Secrets

| Secret | Usage |
|--------|-------|
| GITHUB_TOKEN | GitHub API / Backstage integration |
| LINEAR_API_KEY | Linear issue tracking |
| SENTRY_AUTH_TOKEN | Sentry error tracking |
| DISCORD_WEBHOOK_URL | Discord notifications |

### Access Commands

```bash
# Get secret value
gcloud secrets versions access latest --secret=GITHUB_TOKEN

# List all secrets
gcloud secrets list

# Export for Backstage
export GITHUB_TOKEN=$(gcloud secrets versions access latest --secret=GITHUB_TOKEN)
```

---

## 14. Next Steps (Roadmap)

- [x] Backstage IDP deployment
- [x] Grafana integration configured
- [x] GitHub token from GSM → Backstage (start-with-gsm.sh)
- [x] PostgreSQL connection verified (n8n-postgres-1:5432 via Docker network)
- [x] Systemd service ready (install-service.sh)
- [x] Production Docker deployment (backstage-portal running on :7007)
- [x] Config drift dashboard in Grafana (config-drift.json, cron ogni 30min)
