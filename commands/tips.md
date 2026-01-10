# Previous Session Tips

Inject optimization tips from the previous session into context.

## Usage
```
/tips
```

## What It Does

Reads `~/.claude/metrics/last_session_tips.json` (saved by session-summary.py at stop) and displays:
- Session analysis summary (data source, sessions analyzed)
- Evidence-based optimization tips with confidence scores
- Suggested commands for each tip

User can then use the suggested commands or ignore if not applicable.

## Execution

Read the tips file:

```bash
cat ~/.claude/metrics/last_session_tips.json 2>/dev/null || echo '{"error": "No tips from previous session"}'
```

## Format Output

### Tips Engine v2 Format (with confidence and evidence)

For tips with `confidence` field, format as:

```markdown
## Previous Session Tips

**Analysis**: {sessions_analyzed} sessions | Data source: {data_source}

### 1. [{confidence}%] {message}
**Command**: `{command}`
**Evidence**: {evidence}
**Category**: {category}
{rationale if present}

### 2. [{confidence}%] {message}
...

---
*Use the suggested commands, or ignore if not applicable.*
```

### Legacy Format (with priority)

For tips with `priority` field (legacy format), format as:

```markdown
## Previous Session Tips

**Duration**: {duration_min}min | **Tool calls**: {tool_calls} | **Errors**: {errors}

### Critical (Priority 1):
- {tip}

### Medium (Priority 2):
- {tip}

### Low (Priority 3):
- {tip}

---
*Consider using suggested commands in your next task.*
```

## Staleness Check

If the tips are older than 24 hours, warn the user:

```
Note: These tips are from {timestamp}, which is more than 24 hours ago.
They may not be relevant to your current session.
```

## No Tips Available

If no tips file exists or file is empty:

```
No optimization tips from previous session.
This happens when:
- Previous session was too short (<5 tool calls)
- No patterns triggered tips
- Session ended abnormally
```

## Example Output

```markdown
## Previous Session Tips

**Analysis**: 10 sessions | Data source: project

### 1. [92%] Error rate 37% (z=2.8, elite <15%)
**Command**: `/undo:checkpoint`
**Evidence**: DORA Change Failure Rate threshold + statistical anomaly
**Category**: safety

### 2. [85%] Stuck in loop: 19 iterations on same task
**Command**: `/speckit.plan`
**Evidence**: Pattern analysis: >5 iterations = same approach failing
**Category**: planning

### 3. [78%] File settings.json edited 19 times
**Command**: `/undo:checkpoint`
**Evidence**: Microsoft Research: file churn predicts defects
**Category**: safety

---
*Use the suggested commands, or ignore if not applicable.*
```
