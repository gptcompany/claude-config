---
description: Convert existing tasks into actionable, dependency-ordered GitHub issues for the feature based on available design artifacts.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. From the executed script, extract the path to **tasks.md**.

3. Get the Git remote by running:

```bash
git config --get remote.origin.url
```

> [!CAUTION]
> ONLY PROCEED TO NEXT STEPS IF THE REMOTE IS A GITHUB URL

4. Run the global taskstoissues script:

```bash
python ~/.claude/scripts/taskstoissues.py \
  --tasks-file "$TASKS_PATH" \
  --spec-dir "$FEATURE_DIR"
```

For dry-run preview first:
```bash
python ~/.claude/scripts/taskstoissues.py \
  --tasks-file "$TASKS_PATH" \
  --spec-dir "$FEATURE_DIR" \
  --dry-run
```

5. Report summary to user:
   - Milestones created/existing
   - Issues created/existing
   - Any errors

> [!CAUTION]
> UNDER NO CIRCUMSTANCES EVER CREATE ISSUES IN REPOSITORIES THAT DO NOT MATCH THE REMOTE URL

## Features

The script automatically:
- Creates GitHub milestones for each User Story
- Creates issues with proper labels (priority, parallelizable, evolve)
- Links issues to milestones
- Skips already-existing issues (idempotent)
- Supports dry-run mode for preview

## Manual Fallback

If script fails, fall back to manual `gh issue create` commands as before.
