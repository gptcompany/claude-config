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

## 3. SIMPLIFY: Auto-simplify modified code (MANDATORY if threshold exceeded)

**MANDATORY STEP** - After execution completes, MUST check for complex code and simplify.

```bash
# Get modified/new files from this session (both committed and untracked)
MODIFIED_FILES=$(git status --porcelain | grep -E '\.(py|ts|js|tsx|jsx)$' | awk '{print $2}' || true)

NEEDS_SIMPLIFY=false
COMPLEX_FILES=""

if [ -n "$MODIFIED_FILES" ]; then
    # Check complexity with quick heuristics
    for file in $MODIFIED_FILES; do
        if [ -f "$file" ]; then
            LINES=$(wc -l < "$file")
            FUNCS=$(grep -cE '^\s*(def |async def |function |const .* = |class )' "$file" || echo 0)

            # Threshold: file > 200 lines OR > 10 functions
            if [ "$LINES" -gt 200 ] || [ "$FUNCS" -gt 10 ]; then
                echo "Complex code detected in $file (lines: $LINES, functions: $FUNCS)"
                NEEDS_SIMPLIFY=true
                COMPLEX_FILES="$COMPLEX_FILES $file"
            fi
        fi
    done
fi
```

**If NEEDS_SIMPLIFY is true, MUST spawn code-simplifier:**
```
Task(
    subagent_type="code-simplifier:code-simplifier",  # NOTE: Full name required!
    prompt="Simplify the recently modified code in: $COMPLEX_FILES. Focus on reducing complexity while preserving functionality.",
    model="sonnet"
)
```

**DO NOT skip this step** - code complexity compounds over time.

## 3.5. DEBUG: Fix static errors with Ralph (if Pyright/lint errors exist)

**After simplification (or if skipped), check for static analysis errors.**

```bash
# Check for Pyright errors in modified files
HAS_ERRORS=false
for file in $MODIFIED_FILES; do
    if [ -f "$file" ] && [[ "$file" == *.py ]]; then
        # Quick pyright check (suppress output, just check exit code)
        if ! python3 -m pyright "$file" --outputjson 2>/dev/null | grep -q '"generalDiagnostics": \[\]'; then
            HAS_ERRORS=true
            break
        fi
    fi
done
```

**If HAS_ERRORS is true, run Ralph debug loop:**
```
Use ralph mode to fix errors:
"fix all Pyright type errors in: $MODIFIED_FILES"

Ralph will iterate until 0 errors or max iterations reached.
```

This step is **MANDATORY if errors detected**. Ralph excels at mechanical fixes like:
- Type annotation errors
- Missing imports
- Unused variables
- Argument type mismatches

## 3.6. VERIFY: Run tests (if test suite exists)

**After debug fixes, verify behavior with tests.**

```bash
# Detect test framework and run
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ] || [ -d "tests" ]; then
    pytest --tb=short -q 2>&1 || TEST_FAILED=true
elif [ -f "package.json" ]; then
    npm test 2>&1 || TEST_FAILED=true
fi
```

**If TEST_FAILED is true:**
- CI-autofix hook will handle retries automatically (PostToolUse on Bash)
- If retries exhausted, manual intervention needed

## 4. AFTER: Save completion state

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
