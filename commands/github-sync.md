---
name: github-sync
description: Unified GitHub sync for both Speckit and GSD frameworks - auto-detects and syncs
argument-hint: [--dry-run] [--create-project] [--sync-todos] [--bidirectional]
allowed-tools:
  - Read
  - Bash
  - AskUserQuestion
  - Glob
---

<objective>
Unified GitHub synchronization that automatically detects whether the project uses Speckit or GSD (or both) and syncs to GitHub Issues, Milestones, and Project Boards.

Handles:
- **Speckit**: .specify/tasks.md → GitHub Issues
- **GSD**: .planning/ROADMAP.md → GitHub Issues/Milestones
- **Both**: Syncs both frameworks, using different labels to distinguish
</objective>

<context>
# Auto-detect project structure
@.specify/tasks.md (if exists - Speckit)
@.planning/ROADMAP.md (if exists - GSD)
@.planning/todos/pending/ (if exists - GSD todos)
</context>

<process>

<step name="validate">
```bash
# Verify we're in a git repo with GitHub remote
git remote -v 2>/dev/null | grep -q "github.com" || { echo "ERROR: Not a GitHub repository"; exit 1; }

# Check gh CLI is available and authenticated
gh auth status 2>/dev/null || { echo "ERROR: gh CLI not authenticated. Run 'gh auth login'."; exit 1; }

echo "Validation passed"
```
</step>

<step name="detect_framework">
Detect which framework(s) are present:

```bash
SPECKIT=false
GSD=false

# Check for Speckit
if [ -f ".specify/tasks.md" ]; then
  SPECKIT=true
  echo "Detected: Speckit (.specify/tasks.md)"
fi

# Check for GSD
if [ -f ".planning/ROADMAP.md" ]; then
  GSD=true
  echo "Detected: GSD (.planning/ROADMAP.md)"
fi

# Check for neither
if [ "$SPECKIT" = "false" ] && [ "$GSD" = "false" ]; then
  echo "ERROR: No framework detected."
  echo "Expected: .specify/tasks.md (Speckit) or .planning/ROADMAP.md (GSD)"
  exit 1
fi
```
</step>

<step name="parse_arguments">
Parse arguments from `$ARGUMENTS`:

| Argument | Effect |
|----------|--------|
| `--dry-run` | Preview changes without applying |
| `--create-project` | Create GitHub Project board if missing |
| `--sync-todos` | (GSD) Also sync .planning/todos/ |
| `--bidirectional` | Sync closed issues back to tasks/roadmap |
| `--speckit-only` | Only sync Speckit (if both present) |
| `--gsd-only` | Only sync GSD (if both present) |
</step>

<step name="confirm_sync">
If no --dry-run and both frameworks detected, use AskUserQuestion:
- header: "Multiple frameworks"
- question: "Both Speckit and GSD detected. What would you like to sync?"
- options:
  - "Both (Recommended)" - Sync Speckit and GSD
  - "Speckit only" - Just .specify/tasks.md
  - "GSD only" - Just .planning/ROADMAP.md
  - "Dry run first" - Preview what would happen
</step>

<step name="sync_speckit">
If Speckit detected and not skipped:

**For issue creation:**
```bash
# Find tasks.md path
TASKS_PATH=$(find .specify -name "tasks.md" -type f | head -1)

python ~/.claude/scripts/taskstoissues.py \
  --tasks-file "$TASKS_PATH" \
  --auto-project \
  ${CREATE_PROJECT:+--create-project} \
  ${DRY_RUN:+--dry-run}
```

**For bidirectional sync:**
```bash
SPEC_DIR=$(dirname "$TASKS_PATH")
python ~/.claude/scripts/taskstoissues.py \
  --sync "$SPEC_DIR" \
  ${DRY_RUN:+--dry-run}
```
</step>

<step name="sync_gsd">
If GSD detected and not skipped:

**For issue creation:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --roadmap .planning/ROADMAP.md \
  --auto-project \
  ${CREATE_PROJECT:+--create-project} \
  ${SYNC_TODOS:+--sync-todos} \
  ${DRY_RUN:+--dry-run}
```

**For bidirectional sync:**
```bash
python ~/.claude/scripts/roadmaptoissues.py \
  --sync .planning \
  ${DRY_RUN:+--dry-run}
```
</step>

<step name="report_summary">
Combine results from both syncs if applicable:

```
## GitHub Sync Complete

### Speckit Results (if synced)
- Milestones: [created/existing]
- Issues: [created/existing/closed]

### GSD Results (if synced)
- Phases → Milestones: [created/existing]
- Plans → Issues: [created/existing/closed]
- Todos: [synced] (if --sync-todos)

### Project Board
- Name: {repo_name} Development
- URL: [link]

---

### Commands

View all synced issues:
\`\`\`bash
gh issue list --label auto-generated
\`\`\`

Run bidirectional sync:
\`\`\`bash
/github-sync --bidirectional
\`\`\`
```
</step>

</process>

<output>
- GitHub Milestones for user stories (Speckit) / phases (GSD)
- GitHub Issues for tasks (Speckit) / plans (GSD)
- GitHub Issues for todos (GSD, if --sync-todos)
- Issues linked to auto-detected Project board
- Bidirectional sync keeps files in sync with issue states
</output>

<cross_framework_handling>
When both frameworks are present:

1. **Labels distinguish source:**
   - Speckit: `spec-NNN`, `auto-generated`
   - GSD: `gsd-plan`, `phase-N`, `todo`

2. **Milestones:**
   - Speckit: `US1: [User Story Title]`
   - GSD: `Phase 1: [Phase Name]`

3. **Project Board:**
   - Both use same board: `{repo_name} Development`
   - Issues distinguished by labels

4. **Bidirectional sync:**
   - Run separately for each framework
   - Won't interfere with each other due to different label prefixes
</cross_framework_handling>

<success_criteria>
- [ ] Framework(s) detected
- [ ] gh CLI authenticated
- [ ] Speckit sync completed (if present)
- [ ] GSD sync completed (if present)
- [ ] Issues linked to project board
- [ ] Summary reported to user
</success_criteria>
