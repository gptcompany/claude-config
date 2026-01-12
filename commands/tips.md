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

Read the tips file using the Read tool:

```
Read file: ~/.claude/metrics/last_session_tips.json
```

**Error handling:**
- File not found → Treat as "no tips"
- JSON parse error → Treat as "no tips", warn user
- Empty tips array → Treat as "no tips"

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

## User Interaction (REQUIRED)

After displaying the tips, you MUST use the `AskUserQuestion` tool.

**If tips exist (1 or more):**
```json
{
  "questions": [{
    "question": "How would you like to handle these tips?",
    "header": "Tips",
    "options": [
      {"label": "Show details for each", "description": "Explain what each tip means before I decide"},
      {"label": "Acknowledge and continue", "description": "I've noted the tips, proceed with my task"},
      {"label": "Skip", "description": "Ignore tips for now"}
    ],
    "multiSelect": false
  }]
}
```

**If NO tips exist:**
Do NOT use AskUserQuestion. Just display:
```
No optimization tips from previous session.
Ready to proceed with your task.
```

**IMPORTANT:**
- NEVER auto-execute commands from tips
- Tips are informational only - user decides what to do
- "Show details" = explain each tip's meaning and rationale
- "Acknowledge" = user has read them, continue normally

## Multi-Window Analysis (NEW)

When tips are available, also query QuestDB for multi-window trend analysis:

```python
from questdb_client import get_multi_window_stats
stats = get_multi_window_stats(project)
```

**Windows are dynamic percentages of total sessions:**
- all_time: 100% of sessions (baseline)
- recent: 80% of sessions
- trend: 50% of sessions

Display the trend analysis BEFORE the tips:

```markdown
## Session Trend Analysis

**Total**: {total_sessions} sessions | Source: {data_source}

| Window | Sessions | Error Rate | Rework Rate |
|--------|----------|------------|-------------|
| 100% (all) | {all_time.session_count} | {avg_error_rate}% ± {stddev}% | {avg_rework_rate}% ± {stddev}% |
| 80% (recent) | {recent.session_count} | {avg_error_rate}% ± {stddev}% | {avg_rework_rate}% ± {stddev}% |
| 50% (trend) | {trend.session_count} | {avg_error_rate}% ± {stddev}% | {avg_rework_rate}% ± {stddev}% |

**Trend**: Error rate {error_rate_trend} ({error_rate_delta:+.1%})
```

Trend indicators:
- ↓ improving (delta < -3%)
- → stable (-3% to +3%)
- ↑ degrading (delta > +3%)

## Example Output

```markdown
## Session Trend Analysis

**Total**: 400 sessions | Source: project

| Window | Sessions | Error Rate | Rework Rate |
|--------|----------|------------|-------------|
| 100% (all) | 400 | 32% ± 5% | 15% ± 8% |
| 80% (recent) | 320 | 28% ± 4% | 13% ± 6% |
| 50% (trend) | 200 | 22% ± 3% | 10% ± 4% |

**Trend**: Error rate improving ↓ (-10%)

---

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
