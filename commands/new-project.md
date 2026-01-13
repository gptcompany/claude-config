# New Project Setup Command

Initialize a new repository with Claude Code skeleton based on canonical.yaml.

## Command
`/new-project`

## What It Does

1. Creates `.claude/` directory structure
2. Generates `CLAUDE.md` from template
3. Creates `settings.local.json` with correct env vars
4. Links to global hooks via settings
5. Optionally copies project-specific skills

## Usage

```bash
# In the new repo directory
/new-project

# With language hint
/new-project python

# With framework
/new-project python fastapi
```

## Directory Structure Created

```
.claude/
├── CLAUDE.md                 # Project instructions
├── settings.local.json       # Local settings (inherits global hooks)
├── agents/                   # Project-specific agents (empty)
├── commands/                 # Project-specific commands (empty)
├── skills/                   # Project-specific skills (empty)
└── validation/
    └── config.json           # Project validation config (for /spec-pipeline)
```

## CLAUDE.md Template

The generated CLAUDE.md includes:

```markdown
# CLAUDE.md

## Project Overview
**{project_name}** - {description}

## Tech Stack
- Language: {language}
- Framework: {framework}
- Test Command: {test_command}
- Lint Command: {lint_command}

## Development Rules
- Follow project conventions in existing code
- Run tests before committing
- Use native tools, avoid reimplementing

## Quick Commands
- `/health` - Check system health
- `/tdd:cycle` - TDD workflow
- `/undo:checkpoint` - Create rollback point
- `/speckit:taskstoissues` - Create GitHub Issues from tasks.md
```

## settings.local.json Template

```json
{
  "env": {
    "QUESTDB_HOST": "localhost",
    "QUESTDB_ILP_PORT": "9009"
  }
}
```

Note: Hooks are inherited from `~/.claude/settings.json` (global).

## Execution Steps

1. **Detect project info**:
   - Project name from directory
   - Language from files (pyproject.toml → Python, package.json → TypeScript)
   - Framework from dependencies

2. **Create structure**:
   ```bash
   mkdir -p .claude/{agents,commands,skills,validation}
   ```

3. **Generate CLAUDE.md**:
   - Use template with detected values
   - Include project-specific rules based on language

4. **Create settings.local.json**:
   - Copy env vars from canonical.yaml
   - No hooks (inherited from global)

5. **Create validation/config.json**:
   ```bash
   cp ~/.claude/templates/validation-config.json .claude/validation/config.json
   ```
   - Update `domain` field based on project type
   - Add language-specific anti-patterns (Python: iterrows, requests.get)
   - Add framework-specific keywords

6. **Update canonical.yaml**:
   - Add new repo to repositories section
   - Run drift-detector to verify

## Post-Setup

After running `/new-project`:

1. Review generated `CLAUDE.md`
2. Add project-specific rules
3. Run `/health` to verify integration
4. Commit `.claude/` directory

## Global Scripts Available

Projects automatically have access to these global scripts via `/spec-pipeline`:

| Script | Purpose |
|--------|---------|
| `~/.claude/scripts/taskstoissues.py` | Create GitHub Issues from tasks.md with milestones |
| `~/.claude/scripts/spec_pipeline.py` | Full SpecKit pipeline orchestrator |
| `~/.claude/scripts/trigger-n8n-research.sh` | Trigger academic research pipeline |

**Tasks ↔ Issues Sync**:
```bash
# Create issues from tasks.md
python ~/.claude/scripts/taskstoissues.py --tasks-file specs/XXX/tasks.md --spec-dir specs/XXX

# Bidirectional sync (closed issues ↔ [X] tasks)
python ~/.claude/scripts/taskstoissues.py --sync specs/XXX

# Sync all specs
python ~/.claude/scripts/taskstoissues.py --sync-all
```

## Integration with Canonical

The command reads from `~/.claude/canonical.yaml`:
- Infrastructure settings (QuestDB host/port)
- Global skills/commands list
- Default test/lint commands per language
