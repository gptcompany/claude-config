---
name: gsd:sync-github
description: Sync GSD project to GitHub Issues, Milestones, and Project Board
argument-hint: [--sync-todos] [--create-project] [--dry-run]
allowed-tools:
  - Read
  - Bash
  - AskUserQuestion
  - Glob
---

<objective>
Synchronize GSD project artifacts with GitHub:
- Phases → GitHub Milestones
- Plans → GitHub Issues (linked to phase milestones)
- Todos → GitHub Issues (with 'todo' label)

Supports bidirectional sync to keep ROADMAP.md in sync with GitHub issue states.
</objective>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/todos/pending/
</context>

<process>

<step name="validate">
```bash
# Verify we're in a git repo with GitHub remote
git remote -v 2>/dev/null | grep -q "github.com" || { echo "ERROR: Not a GitHub repository"; exit 1; }

# Verify ROADMAP exists
[ -f .planning/ROADMAP.md ] || { echo "ERROR: No ROADMAP.md found. Run /gsd:create-roadmap first."; exit 1; }

# Check gh CLI is available and authenticated
gh auth status 2>/dev/null || { echo "ERROR: gh CLI not authenticated. Run 'gh auth login'."; exit 1; }

echo "Validation passed"
```
</step>

<step name="check_arguments">
Parse arguments from `$ARGUMENTS`:

- `--sync-todos`: Also sync .planning/todos/ to GitHub Issues
- `--create-project`: Create GitHub Project board if it doesn't exist
- `--dry-run`: Preview changes without applying

Default: sync ROADMAP phases/plans only, link to existing project board (auto-detected)
</step>

<step name="determine_mode">
Use AskUserQuestion:
- header: "Sync mode"
- question: "What would you like to sync to GitHub?"
- options:
  - "Full sync (Recommended)" - Phases, plans, and todos
  - "Roadmap only" - Just phases and plans
  - "Bidirectional" - Update ROADMAP from closed issues
  - "Dry run" - Preview what would happen
</step>

<step name="execute_sync">
Based on selected mode, run the roadmaptoissues.py script:

**For Full sync:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --roadmap .planning/ROADMAP.md \
  --auto-project \
  --create-project \
  --sync-todos
```

**For Roadmap only:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --roadmap .planning/ROADMAP.md \
  --auto-project
```

**For Bidirectional:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --sync .planning
```

**For Dry run:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --roadmap .planning/ROADMAP.md \
  --auto-project \
  --sync-todos \
  --dry-run
```

If `--create-project` in arguments, add the flag.
If `--dry-run` in arguments, add the flag.
If `--sync-todos` in arguments, add the flag.
</step>

<step name="report_results">
Parse script output and present summary:

```
## GitHub Sync Complete

**Milestones:**
- Created: [N]
- Already existed: [N]

**Issues:**
- Created: [N]
- Already existed: [N]
- Closed (bidirectional): [N]

**Todos:**
- Synced: [N]

**Project Board:** [Name] ([URL])

---

### Next Steps

- View project board: `gh project view [N]`
- View issues: `gh issue list --label gsd-plan`
- Run bidirectional sync: `/gsd:sync-github --bidirectional`
```
</step>

<step name="update_state">
If not dry-run, update STATE.md with sync timestamp:

```bash
# Add sync record to STATE.md if it exists
if [ -f .planning/STATE.md ]; then
  timestamp=$(date "+%Y-%m-%d %H:%M")
  echo "" >> .planning/STATE.md
  echo "### GitHub Sync" >> .planning/STATE.md
  echo "Last synced: $timestamp" >> .planning/STATE.md
fi
```
</step>

</process>

<output>
- GitHub Milestones created for each phase
- GitHub Issues created for each plan
- GitHub Issues created for todos (if --sync-todos)
- Issues linked to auto-detected Project board
- STATE.md updated with sync timestamp
</output>

<success_criteria>
- [ ] ROADMAP.md validated
- [ ] gh CLI authenticated
- [ ] All phases synced as milestones
- [ ] All pending plans synced as issues
- [ ] Todos synced if requested
- [ ] Issues linked to project board
- [ ] STATE.md updated (if exists)
</success_criteria>
