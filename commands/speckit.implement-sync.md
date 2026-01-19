---
description: Execute implementation with automatic claude-flow state sync (crash recovery enabled)
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Task
  - TodoWrite
  - AskUserQuestion
  - Skill
  - mcp__claude-flow__memory_store
  - mcp__claude-flow__memory_retrieve
  - mcp__claude-flow__session_save
  - mcp__claude-flow__session_restore
---

## Objective

Wrapper for /speckit.implement with automatic claude-flow state sync.
Provides crash recovery and cross-session state persistence.

## User Input

```text
$ARGUMENTS
```

## Process

### 1. BEFORE: Check for previous state and save checkpoint

```python
# Get project and feature context
project = basename(cwd)
feature = detect_from_specify_dir()  # from .specify/

# Check for previous incomplete state
mcp__claude-flow__memory_retrieve(key=f"speckit:{project}:{feature}")

# If found incomplete state:
#   - Show: "Found incomplete implementation from previous session"
#   - Ask: "Continue from where we left off?"
#   - If yes: mcp__claude-flow__session_restore(sessionId=f"speckit-{project}-{feature}")

# Save starting checkpoint
mcp__claude-flow__session_save(sessionId=f"speckit-{project}-{feature}-start")
mcp__claude-flow__memory_store(key=f"speckit:{project}:{feature}", value={
    "status": "in_progress",
    "feature": feature,
    "started_at": "now()",
    "tasks_total": 0,
    "tasks_done": 0
})
```

### 2. EXECUTE: Run the original command

Use Skill tool to invoke the original implement:
```
Skill(skill="speckit.implement", args="$ARGUMENTS")
```

### 3. AFTER: Save completion state

```python
# Update state with results
mcp__claude-flow__memory_store(key=f"speckit:{project}:{feature}", value={
    "status": "completed",
    "feature": feature,
    "completed_at": "now()",
    "tasks_done": "all"
})

# Save completion checkpoint
mcp__claude-flow__session_save(sessionId=f"speckit-{project}-{feature}-done")
```

### 4. ON ERROR: Save error state for recovery

If any error during execution:
```python
mcp__claude-flow__memory_store(key=f"speckit:{project}:{feature}", value={
    "status": "failed",
    "feature": feature,
    "error": "error_message",
    "failed_at": "now()",
    "last_task": "task_id"
})
mcp__claude-flow__session_save(sessionId=f"speckit-{project}-{feature}-error")
```

## Output

After completion, confirm:
- State saved to claude-flow memory
- Session checkpoint created
- Ready for crash recovery if needed
