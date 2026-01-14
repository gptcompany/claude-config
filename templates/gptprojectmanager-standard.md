# gptprojectmanager Standard Repository Structure

## Directory Layout

```
{repo}/
├── .claude/                    # Claude Code configuration
│   ├── CLAUDE.md              # Project-specific instructions
│   ├── settings.local.json    # Environment settings
│   ├── commands/              # Custom slash commands
│   ├── skills/                # Custom skills
│   └── validation/
│       └── config.json        # Spec-pipeline validation
│
├── .specify/                   # SpecKit framework
│   ├── memory/
│   │   └── constitution.md    # Project principles (SSOT)
│   ├── templates/
│   │   ├── spec-template.md
│   │   ├── plan-template.md
│   │   └── tasks-template.md
│   └── scripts/
│       └── bash/
│           └── check-prerequisites.sh
│
├── specs/                      # Feature specifications
│   └── {NNN}-{feature-name}/
│       ├── spec.md
│       ├── plan.md
│       ├── tasks.md
│       └── research.md
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md        # System architecture (auto-validated)
│   └── README.md              # Quick start
│
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── catalog-info.yaml           # Backstage catalog entry
├── pyproject.toml             # Python dependencies
└── README.md                  # Project overview
```

## Required Files

### 1. CLAUDE.md (minimum)
```markdown
# CLAUDE.md

## Project Overview
**{repo_name}** - {description}

## Key Principles
- KISS + YAGNI
- {project-specific principles}

## Commands
| Command | Purpose |
|---------|---------|
| `/health` | System health check |
| `/spec-pipeline` | Full SpecKit workflow |
```

### 2. constitution.md (minimum)
```markdown
# Project Constitution

## Core Principles
1. **KISS** - Keep It Simple
2. **YAGNI** - Don't over-engineer
3. **TDD** - Test-driven for core logic

## Quality Gates
- Tests must pass before merge
- No secrets in code
```

### 3. catalog-info.yaml
```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: {repo_name}
  annotations:
    github.com/project-slug: gptprojectmanager/{repo_name}
spec:
  type: service
  lifecycle: production
  owner: gptprojectmanager
```

### 4. validation/config.json
```json
{
  "domain": "{domain}",
  "anti_patterns": [],
  "research_keywords": {
    "trigger": [],
    "skip": []
  }
}
```

## GitHub Labels (Auto-created by /new-project)

| Label | Color | Purpose |
|-------|-------|---------|
| auto-generated | #0E8A16 | SpecKit-generated issues |
| priority-p1 | #B60205 | Critical |
| priority-p2 | #FBCA04 | Normal |
| priority-p3 | #0E8A16 | Low |
| parallelizable | #1D76DB | Can be parallel |
| evolve | #5319E7 | Evolving requirement |

## GitHub Project Board

Name pattern: `{repo_name} Development`

Created automatically with `--auto-project` flag:
```bash
python taskstoissues.py --tasks-file specs/XXX/tasks.md --auto-project
```

## Compliance Checklist

- [ ] .claude/CLAUDE.md exists
- [ ] .specify/memory/constitution.md exists
- [ ] .claude/validation/config.json exists
- [ ] catalog-info.yaml exists
- [ ] GitHub labels created
- [ ] GitHub Project board created
- [ ] Registered in canonical.yaml
