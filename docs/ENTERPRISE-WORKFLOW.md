# Enterprise Development Workflow

## Overview

Integrated workflow using SpecKit, ClaudeFlow, and GitHub for enterprise-grade development.

## Workflow Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ENTERPRISE WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. SPECIFICATION                                                        │
│     └── /speckit.specify "feature description"                           │
│         → Creates: specs/{feature}/spec.md                               │
│                                                                          │
│  2. PLANNING                                                             │
│     └── /speckit.plan                                                    │
│         → Creates: specs/{feature}/plan.md, research.md                  │
│         → Creates: data-model.md, contracts/                             │
│                                                                          │
│  3. TASK GENERATION                                                      │
│     └── /speckit.tasks                                                   │
│         → Creates: specs/{feature}/tasks.md                              │
│         → Tasks organized by user story (P1, P2, P3...)                  │
│                                                                          │
│  4. GITHUB ISSUES                                                        │
│     └── /speckit.taskstoissues                                           │
│         → Creates: GitHub Issues from pending tasks                      │
│         → Creates: Milestones from phases/user stories                   │
│         → Links: Issues to Project Board                                 │
│                                                                          │
│  5. IMPLEMENTATION                                                       │
│     └── /speckit.implement                                               │
│         → Executes tasks in order                                        │
│         → Marks [X] completed tasks                                      │
│         → Auto-closes GitHub Issues via sync                             │
│                                                                          │
│  6. ANALYSIS                                                             │
│     └── /speckit.analyze                                                 │
│         → Validates spec/plan/tasks consistency                          │
│         → Reports coverage gaps                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## GitHub Project Structure

### Recommended: One Project per Repository

```
Repository: nautilus_dev
└── GitHub Project: "nautilus_dev Development"
    ├── View: Board (Kanban)
    │   ├── Todo
    │   ├── In Progress
    │   └── Done
    ├── View: Table
    └── Milestones:
        ├── 044-lob-deep-learning
        ├── 045-next-feature
        └── ...
```

### Alternative: One Project per Feature

```
Repository: nautilus_dev
├── GitHub Project: "044-lob-deep-learning"
│   └── Issues from tasks.md
├── GitHub Project: "045-next-feature"
│   └── Issues from tasks.md
└── ...
```

## Commands Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `/speckit.specify` | Create feature specification | spec.md |
| `/speckit.plan` | Plan implementation | plan.md, research.md, contracts/ |
| `/speckit.tasks` | Generate actionable tasks | tasks.md |
| `/speckit.taskstoissues` | Create GitHub Issues | Issues + Milestones |
| `/speckit.implement` | Execute tasks | Code changes |
| `/speckit.analyze` | Validate consistency | Analysis report |
| `/speckit.clarify` | Ask clarifying questions | Updated spec.md |
| `/speckit.checklist` | Generate custom checklist | Checklist |

## GitHub Integration

### Token Scopes Required

```bash
# Add project scope to GitHub CLI
gh auth refresh -s read:project -s project
```

### Creating a Project Board

```bash
# Create repo-level project
gh project create --owner gptprojectmanager --title "nautilus_dev Development"

# Link issues to project
gh issue edit ISSUE_NUMBER --add-project "nautilus_dev Development"
```

### taskstoissues.py Features

```bash
# Create issues from tasks.md
python taskstoissues.py --tasks-file specs/034/tasks.md

# Bidirectional sync (completed tasks <-> closed issues)
python taskstoissues.py --sync specs/034-kelly-criterion

# Sync all specs
python taskstoissues.py --sync-all

# Preview changes
python taskstoissues.py --tasks-file specs/034/tasks.md --dry-run
```

## ClaudeFlow Integration

### Orchestration Mode

```yaml
# canonical.yaml
claudeflow:
  enabled: true
  mode: orchestrator
  speckit_integration:
    checkpoints:
      - phase: specify
        validator: truth_score
        threshold: 0.7
      - phase: plan
        validator: feasibility_check
        threshold: 0.7
      - phase: implement
        validator: tests_pass
```

### Worktrees for Parallel Development

```bash
# Create worktree for feature
git worktree add /tmp/claude-worktrees/044-lob-deep-learning 044-lob-deep-learning

# ClaudeFlow auto-manages worktrees when enabled
```

## Automation Hooks

### Post-Tasks Hook (Recommended)

Add to hooks-shared to auto-prompt for issue creation:

```python
# hooks/productivity/post-tasks-prompt.py
# Triggers after /speckit.tasks completes
# Asks: "Create GitHub Issues from tasks.md?"
```

### Bidirectional Sync Cron

```bash
# Sync GitHub Issues ↔ tasks.md every hour
0 * * * * python3 ~/.claude/scripts/taskstoissues.py --sync-all >> /tmp/taskstoissues.log 2>&1
```

## Backstage Integration

### View in Backstage

- **Catalog**: All repos visible at http://localhost:7007/catalog
- **GitHub PRs**: Per-entity PR status
- **GitHub Actions**: CI/CD status
- **Grafana**: Embedded dashboards

### catalog-info.yaml Annotations

```yaml
metadata:
  annotations:
    github.com/project-slug: gptprojectmanager/nautilus_dev
    grafana/dashboard-selector: "uid in (nautilus-health)"
```

## Quality Gates

### Pre-Implementation Checklist

- [ ] spec.md reviewed and approved
- [ ] plan.md feasibility confirmed
- [ ] tasks.md coverage verified with /speckit.analyze
- [ ] GitHub Issues created
- [ ] Project board set up

### Post-Implementation Checklist

- [ ] All tasks marked [X]
- [ ] All GitHub Issues closed
- [ ] Tests passing
- [ ] Documentation updated
- [ ] PR merged
