# Claude Code Infrastructure

Enterprise-grade Claude Code configuration hub serving multiple repositories.

## Architecture Overview

```
~/.claude/                          # Global Claude Code configuration
├── canonical.yaml                  # SSOT - Single Source of Truth
├── CLAUDE.md                       # Global instructions for all projects
├── settings.json                   # Claude Code settings
│
├── schemas/                        # Validation schemas
│   ├── metrics.yaml               # QuestDB metrics schema (7 tables)
│   └── skill.yaml                 # Skill definition template
│
├── scripts/                        # Automation scripts
│   ├── drift-detector.py          # Cross-repo consistency validator
│   └── new-project.py             # New project skeleton generator
│
├── commands/                       # Global slash commands
│   ├── tdd/                       # TDD workflow commands
│   ├── undo/                      # Checkpoint/rollback commands
│   ├── health.md                  # /health - System health check
│   ├── audit.md                   # /audit - Full system audit
│   └── new-project.md             # /new-project - Scaffold new repos
│
├── skills/                         # Global reusable skills
│   ├── pytest-test-generator/     # Generate pytest tests from code
│   ├── pydantic-model-generator/  # Generate Pydantic models
│   ├── github-workflow/           # GitHub Actions workflow generator
│   └── metrics-insight/           # Metrics analysis and reporting
│
└── projects/                       # Project-specific sessions (gitignored)
```

## Single Source of Truth (SSOT)

All configuration lives in `canonical.yaml`:

```yaml
infrastructure:
  questdb:                    # Shared metrics database
    host: localhost
    ilp_port: 9009           # InfluxDB Line Protocol
    pg_port: 8812            # PostgreSQL wire protocol
  redis:                     # Session caching
    host: localhost
    port: 6379
  monitoring:                # Grafana dashboards (in nautilus_dev)
    path: /media/sam/1TB/nautilus_dev/monitoring
    grafana_port: 3000

repositories:                # All managed projects
  nautilus_dev:
    path: /media/sam/1TB/nautilus_dev
    language: python
    test_command: uv run pytest tests/ -x
  n8n_dev:
    path: /media/sam/1TB/N8N_dev
    language: typescript
  utxoracle:
    path: /media/sam/1TB/UTXOracle
    language: python
  liquidation_heatmap:
    path: /media/sam/1TB/LiquidationHeatmap
    language: python

global:
  commands: [tdd/, undo/, speckit.*]
  skills: [pytest-test-generator, pydantic-model-generator, ...]
  hooks:
    pre_tool_use: [context_bundle_builder.py, smart-safety-check.py, ...]
    post_tool_use: [dora-tracker.py, auto-format.py, ...]
    stop: [context-preservation.py, session-summary.py, ...]
```

## Shared Infrastructure

### Hooks (`/media/sam/1TB/claude-hooks-shared/`)

All repositories share the same hooks infrastructure:

| Hook | Type | Purpose |
|------|------|---------|
| context_bundle_builder.py | PreToolUse | Build context bundles |
| smart-safety-check.py | PreToolUse (Bash) | Prevent dangerous commands |
| git-safety-check.py | PreToolUse (Bash) | Git operation safety |
| tdd-guard-check.py | PreToolUse (Write\|Edit) | Enforce TDD discipline |
| dora-tracker.py | PostToolUse | DORA metrics collection |
| auto-format.py | PostToolUse (Write\|Edit) | Auto-format on save |
| context-preservation.py | Stop | Save context on exit |
| session-summary.py | Stop | Generate session summaries |

### Metrics (QuestDB)

7 tables for comprehensive observability:

| Table | Purpose |
|-------|---------|
| claude_tool_usage | Tool calls, latency, success rates |
| claude_events | Errors, warnings, anomalies |
| claude_sessions | Session duration, token usage, cost |
| claude_agents | Agent performance, ROI analysis |
| claude_hooks | Hook latency, block rates |
| claude_tasks | Task completion, duration |
| claude_context | Context utilization tracking |

### Monitoring (Grafana)

Location: `/media/sam/1TB/nautilus_dev/monitoring/`

- **Dashboard**: `grafana/dashboards/claude_metrics.json`
- **Alerts**: `grafana/provisioning/alerting/claude-alert-rules.yaml`

Alerts configured:
- High error rate (>10/hour)
- Hook latency (>500ms avg)
- Agent success rate (<80%)
- Daily cost spike (>$50)
- Tool failure rate (>20%)

## Commands Reference

| Command | Description |
|---------|-------------|
| `/health` | Quick system health check |
| `/audit` | Full audit with metrics analysis |
| `/audit --report` | Generate markdown report |
| `/new-project <path>` | Scaffold new project with Claude Code |
| `/tdd:cycle` | Full TDD Red-Green-Refactor cycle |
| `/undo:checkpoint` | Create safe rollback point |

## Scripts

### drift-detector.py

Validates cross-repo consistency:

```bash
# Check for drift
python3 ~/.claude/scripts/drift-detector.py

# Auto-fix issues
python3 ~/.claude/scripts/drift-detector.py --fix

# JSON output for automation
python3 ~/.claude/scripts/drift-detector.py --json
```

Checks for:
- Duplicate skills/commands across repos
- Settings.json consistency
- Obsolete artifacts
- Config drift from canonical.yaml

### new-project.py

Scaffolds new projects:

```bash
python3 ~/.claude/scripts/new-project.py /path/to/new-project

# With explicit language
python3 ~/.claude/scripts/new-project.py /path/to/project --language rust
```

Creates:
- `.claude/` directory structure
- `CLAUDE.md` with project-specific instructions
- `settings.local.json` linking to shared hooks
- Entry in `canonical.yaml`

## Metrics Schema (SPACE Framework)

Based on Google's Developer Intelligence and SPACE Framework:

- **S**atisfaction: Developer experience metrics
- **P**erformance: Code quality, test coverage
- **A**ctivity: Tool usage, session counts
- **C**ollaboration: PR cycle time, review turnaround
- **E**fficiency: Context utilization, token optimization

## Token Economics

| Component | Tokens | Loaded |
|-----------|--------|--------|
| Global CLAUDE.md | ~500 | Always |
| Project CLAUDE.md | ~2,800 | Per project |
| canonical.yaml | 0 | Never (reference only) |
| schemas/*.yaml | 0 | Never (reference only) |
| skills/ | ~200/skill | On invocation |

## Adding a New Repository

1. Run `/new-project /path/to/repo`
2. Customize generated `CLAUDE.md`
3. Add project-specific skills to `.claude/skills/`
4. Run `/health` to verify setup

## Thresholds

Configured in `canonical.yaml`:

| Metric | Warning | Critical |
|--------|---------|----------|
| Hook latency | 100ms | 500ms |
| Agent success rate | <80% | - |
| Daily cost | $30 | $50 |
| Context utilization | 80% | - |

## Contributing

1. All changes to shared infrastructure go through this repo
2. Run `drift-detector.py` before committing
3. Update `canonical.yaml` for any config changes
4. Test hooks locally before pushing

## License

Private repository. Internal use only.
