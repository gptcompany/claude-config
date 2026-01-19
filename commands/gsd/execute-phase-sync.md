---
name: gsd:execute-phase-sync
description: Execute phase with automatic claude-flow state sync (crash recovery enabled)
argument-hint: "<phase-number>"
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

<objective>
Wrapper for /gsd:execute-phase with automatic claude-flow state sync.
Provides crash recovery and cross-session state persistence.
</objective>

<process>
## 1. BEFORE: Check for previous state and save checkpoint

```
# Get project name from current directory
project = basename(cwd)
phase = $ARGUMENTS

# Check for previous incomplete state
mcp__claude-flow__memory_retrieve key="gsd:{project}:{phase}"

# If found incomplete state:
#   - Show to user: "Found incomplete state from previous session"
#   - Ask: "Continue from where we left off?"
#   - If yes: mcp__claude-flow__session_restore sessionId="gsd-{project}-{phase}"
#   - If no: proceed fresh

# Save starting checkpoint
mcp__claude-flow__session_save sessionId="gsd-{project}-{phase}-start"
mcp__claude-flow__memory_store key="gsd:{project}:{phase}" value={
  "status": "in_progress",
  "phase": phase,
  "started_at": now(),
  "plans": []
}
```

## 2. EXECUTE: Run the original command

Use Skill tool to invoke the original execute-phase:
```
Skill(skill="gsd:execute-phase", args="{phase}")
```

## 3. AFTER: Save completion state

```
# Update state with results
mcp__claude-flow__memory_store key="gsd:{project}:{phase}" value={
  "status": "completed",
  "phase": phase,
  "completed_at": now(),
  "results": "success"
}

# Save completion checkpoint
mcp__claude-flow__session_save sessionId="gsd-{project}-{phase}-done"
```

## 4. ON ERROR: Save error state for recovery

If any error during execution:
```
mcp__claude-flow__memory_store key="gsd:{project}:{phase}" value={
  "status": "failed",
  "phase": phase,
  "error": error_message,
  "failed_at": now()
}
mcp__claude-flow__session_save sessionId="gsd-{project}-{phase}-error"
```
</process>

<output>
After completion, confirm:
- State saved to claude-flow memory
- Session checkpoint created
- Ready for crash recovery if needed
</output>
