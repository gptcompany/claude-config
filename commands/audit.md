# Claude Code Audit Command

Comprehensive system audit combining health check and metrics analysis.

## Command
`/audit`

## What It Does

1. **Health Check**: Runs drift-detector for cross-repo consistency
2. **Metrics Analysis**: Queries QuestDB for usage patterns
3. **Recommendations**: Generates actionable insights

## Usage

```bash
# Full audit
/audit

# Quick health only
/audit health

# Metrics only
/audit metrics

# Generate report
/audit --report
```

## Audit Components

### 1. Health Check
- Cross-repo drift detection
- Duplicate skill/command identification
- Settings consistency verification
- Obsolete artifact detection

### 2. Metrics Analysis (if QuestDB available)
- Tool usage patterns
- Agent ROI analysis
- Hook latency profiling
- Error frequency trends

### 3. Recommendations
- Priority-ranked action items
- Auto-fix suggestions
- Performance optimization tips

## Output Format

```
Claude Code Audit
=================
Date: 2026-01-09

HEALTH CHECK
------------
Score: 100/100
Status: All systems healthy

METRICS SUMMARY (last 7 days)
-----------------------------
Sessions: 47
Tokens: 2.3M (~$28)
Agent Success: 94%
Hook Latency: 45ms avg

TOP INSIGHTS
------------
1. Agent 'Explore' overused (40% tokens, 12% tasks)
2. Hook latency improved 15% this week
3. No errors in 48h

RECOMMENDATIONS
---------------
[ ] Consider targeted Grep/Glob vs Explore
[ ] Archive unused 'pinescript' skill
```

## Execution

The audit combines multiple scripts:

```bash
# Health check
python3 ~/.claude/scripts/drift-detector.py --json

# Metrics (if QuestDB available)
# Query claude_tool_usage, claude_agents, claude_hooks

# Generate combined report
```

## When to Use

| Scenario | Command |
|----------|---------|
| Monday morning review | `/audit` |
| After config changes | `/audit health` |
| Performance debugging | `/audit metrics` |
| Monthly planning | `/audit --report` |

## Integration

Works with:
- `~/.claude/canonical.yaml` - SSOT configuration
- `~/.claude/schemas/metrics.yaml` - Metrics schema
- QuestDB - Metrics storage
