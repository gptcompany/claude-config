# GitHub Sync - GSD/Speckit ↔ GitHub Issues

## Overview

Automatic bidirectional sync between GSD/Speckit planning files and GitHub Issues/Projects.

## Architecture

```
┌─────────────────┐     push      ┌──────────────────────┐
│  .planning/     │ ───────────►  │  sync-planning.yml   │
│  ROADMAP.md     │               │  (caller workflow)   │
└─────────────────┘               └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ _reusable-sync-      │
                                  │ planning.yml         │
                                  │ (claude-config)      │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │  GitHub Issues       │
                                  │  GitHub Milestones   │
                                  │  GitHub Projects     │
                                  └──────────────────────┘
```

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Reusable workflow | `claude-config/.github/workflows/_reusable-sync-planning.yml` | Core sync logic |
| Caller workflow | `.github/workflows/sync-planning.yml` (each repo) | Triggers reusable |
| GSD parser | `claude-config/scripts/roadmaptoissues.py` | ROADMAP.md → Issues |
| Speckit parser | `claude-config/scripts/taskstoissues.py` | tasks.md → Issues |
| Core functions | `claude-config/scripts/github_sync_core.py` | Shared GitHub API functions |

## Trigger

Push to:
- `.planning/**` → GSD sync
- `tasks.md` → Speckit sync

## What Gets Synced

### GSD (ROADMAP.md)

| Source | Target |
|--------|--------|
| Phase | GitHub Milestone |
| Plan `- [ ] XX-YY: desc` | GitHub Issue with label `gsd-plan` |
| Plan `- [x]` completed | Issue closed |
| UAT issues | GitHub Issues with label `uat-issue` |

### Speckit (tasks.md)

| Source | Target |
|--------|--------|
| User Story | GitHub Milestone |
| Task `- [ ] TXXX` | GitHub Issue |
| Task `- [x]` completed | Issue closed |

## Required Format (GSD)

Plans MUST have checkbox format in Phase Details:

```markdown
### Phase 1: Name
**Goal**: ...
**Plans**: 2

Plans:
- [ ] 01-01: First plan description
- [ ] 01-02: Second plan description
```

## Setup for New Repos

The caller workflow is auto-deployed to all gptcompany repos.

For new repos, add:
```yaml
# .github/workflows/sync-planning.yml
name: Sync Planning
on:
  push:
    paths: ['.planning/**', 'tasks.md']
  workflow_dispatch:

jobs:
  sync:
    permissions:
      issues: write
      contents: read
    uses: gptcompany/claude-config/.github/workflows/_reusable-sync-planning.yml@main
    secrets: inherit
    with:
      framework: 'auto'
      create-project: true
      sync-todos: true
```

## Required Secrets

| Secret | Scope | Purpose |
|--------|-------|---------|
| `GH_PROJECT_PAT` | Org level | Create/manage ProjectsV2 boards |

## Manual Sync

```bash
# From any repo with GSD/Speckit
/github-sync                    # Create issues
/github-sync --bidirectional    # Sync both directions
/github-sync --dry-run          # Preview
```

## Troubleshooting

### "Found 0 plans"
- Check ROADMAP.md has `Plans:` section with checkbox format
- Plans must be `- [ ] XX-YY: description`

### Project board not created
- Verify `GH_PROJECT_PAT` secret exists with `project:write` scope
- Check workflow has `create-project: true`

### Issues not created
- Plans marked `[x]` won't create issues (already complete)
- Check workflow run logs: `gh run list --workflow=sync-planning.yml`
