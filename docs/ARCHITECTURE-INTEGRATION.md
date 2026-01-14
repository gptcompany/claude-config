# Architecture Integration: SpecKit + ClaudeFlow + Backstage

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEVELOPMENT WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  Backstage   │───▶│   SpecKit    │───▶│  ClaudeFlow  │                   │
│  │  (Portal)    │    │  (Planning)  │    │ (Execution)  │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│         │                   │                   │                            │
│         ▼                   ▼                   ▼                            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Catalog    │    │   spec.md    │    │ Multi-Agent  │                   │
│  │  Templates   │    │   plan.md    │    │   Swarms     │                   │
│  │   Projects   │    │   tasks.md   │    │   Workers    │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Backstage (Developer Portal)
- **Software Catalog**: Inventory of all repos/services
- **Software Templates**: Scaffold new repos with standard structure
- **TechDocs**: Centralized documentation
- **Plugins**: GitHub Actions, Grafana dashboards

### SpecKit (Specification Framework)
- **Workflow Commands**:
  - `/speckit.specify` → Creates spec.md
  - `/speckit.plan` → Creates plan.md, research.md, contracts/
  - `/speckit.tasks` → Creates tasks.md
  - `/speckit.implement` → Executes tasks
  - `/speckit.analyze` → Validates consistency
- **Files Generated**:
  ```
  specs/{feature}/
  ├── spec.md           # Requirements, user stories
  ├── plan.md           # Architecture, tech decisions
  ├── tasks.md          # Actionable checklist
  ├── research.md       # Decisions log
  ├── data-model.md     # Entity definitions
  └── contracts/        # API schemas
  ```

### ClaudeFlow (Multi-Agent Orchestration)
- **Protocol**: MCP (Model Context Protocol)
- **Architecture**: Hive-Mind with Queen + Workers
- **Modes**:
  - `orchestrator` - Full autonomous execution
  - `on-demand` - Called for specific tasks
- **Integration**: Validates SpecKit checkpoints

## How They Work Together

### 1. New Feature Request

```
User Request → Backstage Template → New Repo with structure
                                          │
                                          ▼
                                    .claude/
                                    .specify/
                                    specs/
                                    catalog-info.yaml
```

### 2. Feature Development

```
/speckit.specify "Add user authentication"
        │
        ▼
    spec.md created
        │
        ▼
/speckit.plan
        │
        ▼
    plan.md + research.md + contracts/
        │
        ▼
/speckit.tasks
        │
        ▼
    tasks.md with T001, T002, ...
        │
        ▼
/speckit.taskstoissues --auto-project
        │
        ▼
    GitHub Issues → Project Board → Milestones
        │
        ▼
/speckit.implement (or ClaudeFlow swarm)
        │
        ▼
    Code written, tests pass
```

### 3. ClaudeFlow Integration Points

ClaudeFlow can be invoked at specific checkpoints:

```yaml
# canonical.yaml
claudeflow:
  speckit_integration:
    checkpoints:
      - phase: specify
        validator: truth_score      # Validate spec quality
        threshold: 0.7
      - phase: plan
        validator: feasibility_check # Check technical feasibility
      - phase: implement
        validator: tests_pass        # Run tests after each task
```

## Standard Repo Structure

Every repo should follow this structure for full integration:

```
{repo}/
├── .claude/                    # Claude Code config
│   ├── CLAUDE.md              # Project-specific instructions
│   ├── settings.local.json    # Local settings
│   ├── commands/              # Custom slash commands
│   ├── skills/                # Custom skills
│   └── validation/            # Validation config
│       └── config.json
├── .specify/                   # SpecKit templates
│   ├── memory/
│   │   └── constitution.md    # Project principles
│   ├── templates/
│   │   ├── spec-template.md
│   │   └── tasks-template.md
│   └── scripts/
│       └── bash/
├── specs/                      # Feature specifications
│   └── {feature}/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
├── tests/                      # Test suite
├── catalog-info.yaml           # Backstage catalog entry
└── README.md
```

## nautilus_dev Split Proposal

Current monolith should be split into:

| New Repo | Modules | Purpose |
|----------|---------|---------|
| `nautilus_core` | trading/, strategies/, risk/ | Trading engine |
| `nautilus_data` | data/, data_loaders/, feeds/, pipeline/ | Data + ML |
| `nautilus_ops` | monitoring/, dashboard/, security/, config/ | Operations |

Each repo gets:
- Own `.claude/` with context
- Own `.specify/` with constitution
- Own `specs/` for features
- Own `catalog-info.yaml` for Backstage
- Own GitHub Project board

## ClaudeFlow vs SpecKit

| Aspect | SpecKit | ClaudeFlow |
|--------|---------|------------|
| **Type** | Slash commands + templates | MCP server + agents |
| **Format** | Markdown (spec.md, tasks.md) | JSON + Hive-Mind protocol |
| **Execution** | Single Claude instance | Multi-agent swarms |
| **Use Case** | Planning, specification | Parallel execution |
| **Autonomy** | Human-in-loop | Can run autonomously |

**Best Practice**: Use SpecKit for planning → ClaudeFlow for execution

```bash
# Planning phase (SpecKit)
/speckit.specify → /speckit.plan → /speckit.tasks

# Execution phase (ClaudeFlow)
claude-flow swarm create --from-tasks specs/XXX/tasks.md
```

## Backstage Template Usage

1. **Create new repo via Backstage**:
   - Go to http://localhost:7007/create
   - Select "SpecKit-Ready Repository"
   - Fill in name, language, framework
   - Click Create

2. **Result**:
   - New GitHub repo with standard structure
   - Registered in Backstage catalog
   - GitHub labels created
   - Project board ready

## Sources

- [ClaudeFlow GitHub](https://github.com/ruvnet/claude-flow)
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/)
