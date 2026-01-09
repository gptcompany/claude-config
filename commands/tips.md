# Previous Session Tips

Show optimization tips from the previous session.

## Usage
```
/tips
```

## What It Does

Reads `~/.claude/metrics/last_session_tips.json` (saved by session-summary.py at stop) and displays:
- Session summary (duration, tool calls, errors)
- Prioritized optimization tips

User can then decide to copy relevant tips into their prompt.

## Execution

Read the tips file and format for display:

```bash
cat ~/.claude/metrics/last_session_tips.json 2>/dev/null || echo '{"error": "No tips from previous session"}'
```

Format the output as:

```
PREVIOUS SESSION TIPS
=====================
Duration: Xmin | Tool calls: Y | Errors: Z

Priority 1 (Critical):
! <tip>

Priority 2 (Medium):
> <tip>

Priority 3 (Low):
- <tip>
```

If no tips file exists, inform the user that no previous session data is available.
