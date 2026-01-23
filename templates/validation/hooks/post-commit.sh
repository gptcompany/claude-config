#!/bin/bash
# Git post-commit hook for Ralph Loop validation
#
# Triggers validation asynchronously after each commit.
# Does NOT block the commit - runs in background.
#
# Installation:
#   cp ~/.claude/templates/validation/hooks/post-commit.sh .git/hooks/post-commit
#   chmod +x .git/hooks/post-commit
#
# Or use install.py:
#   python3 ~/.claude/templates/validation/hooks/install.py --git-hook
#
# Configuration:
#   Set RALPH_LOOP_CONFIG to path of config.json (optional)
#   Set RALPH_LOOP_JSON=1 to save JSON output
#   Set RALPH_LOOP_NOTIFY=1 to show desktop notification on completion
#
# Output:
#   /tmp/ralph_result.json (if RALPH_LOOP_JSON=1)
#   ~/.claude/logs/ralph-loop.log (always)

set -e

# Configuration
RALPH_LOOP_SCRIPT="${RALPH_LOOP_SCRIPT:-$HOME/.claude/templates/validation/ralph_loop.py}"
RALPH_LOOP_CONFIG="${RALPH_LOOP_CONFIG:-}"
RALPH_LOOP_JSON="${RALPH_LOOP_JSON:-1}"
RALPH_LOOP_NOTIFY="${RALPH_LOOP_NOTIFY:-0}"

# Get changed files in this commit
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | tr '\n' ',' | sed 's/,$//')

# Exit if no files changed
if [ -z "$CHANGED_FILES" ]; then
    exit 0
fi

# Get project name from git root
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo "unknown")

# Get commit info for logging
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
COMMIT_MSG=$(git log -1 --pretty=%s 2>/dev/null | head -c 50 || echo "unknown")

# Check if ralph_loop.py exists
if [ ! -f "$RALPH_LOOP_SCRIPT" ]; then
    echo "Ralph Loop: Script not found at $RALPH_LOOP_SCRIPT"
    exit 0
fi

# Build command arguments
RALPH_ARGS="--files \"$CHANGED_FILES\" --project \"$PROJECT\""

if [ -n "$RALPH_LOOP_CONFIG" ] && [ -f "$RALPH_LOOP_CONFIG" ]; then
    RALPH_ARGS="$RALPH_ARGS --config \"$RALPH_LOOP_CONFIG\""
fi

if [ "$RALPH_LOOP_JSON" = "1" ]; then
    RALPH_ARGS="$RALPH_ARGS --json"
fi

# Run Ralph loop in background (non-blocking)
# Output to temp file for later inspection
(
    # Create a subshell to avoid affecting the main shell
    cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0

    # Run validation
    if [ "$RALPH_LOOP_JSON" = "1" ]; then
        eval "python3 \"$RALPH_LOOP_SCRIPT\" $RALPH_ARGS" > /tmp/ralph_result.json 2>&1
        EXIT_CODE=$?
    else
        eval "python3 \"$RALPH_LOOP_SCRIPT\" $RALPH_ARGS" > /tmp/ralph_output.txt 2>&1
        EXIT_CODE=$?
    fi

    # Optional: Desktop notification on completion
    if [ "$RALPH_LOOP_NOTIFY" = "1" ]; then
        if command -v notify-send >/dev/null 2>&1; then
            if [ $EXIT_CODE -eq 0 ]; then
                notify-send "Ralph Loop" "Validation passed for $PROJECT" --icon=dialog-ok
            elif [ $EXIT_CODE -eq 1 ]; then
                notify-send "Ralph Loop" "Validation BLOCKED for $PROJECT" --icon=dialog-error --urgency=critical
            else
                notify-send "Ralph Loop" "Validation completed with warnings for $PROJECT" --icon=dialog-warning
            fi
        fi
    fi

    # Log completion
    echo "[$(date -Iseconds)] Commit $COMMIT_SHA: exit=$EXIT_CODE, project=$PROJECT, files=$CHANGED_FILES" >> ~/.claude/logs/ralph-hook.log
) &

# Show quick status message (non-blocking)
echo "Ralph validation triggered for $PROJECT ($COMMIT_SHA: $COMMIT_MSG)"

# Exit immediately - don't wait for background process
exit 0
