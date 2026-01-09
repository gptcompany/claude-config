---
name: metrics-insight
description: Analyze Claude Code metrics from QuestDB and generate actionable insights. Daily/weekly/monthly reports with SPACE-based analysis. 90% less time vs manual review.
version: "1.0"
category: [analysis, productivity]
---

# Metrics Insight

Automated analysis of Claude Code usage metrics with actionable recommendations.

Based on:
- [Anthropic Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Google Developer Intelligence](https://newsletter.pragmaticengineer.com/p/measuring-developer-productivity-bae) (Speed, Ease, Quality)
- [SPACE Framework](https://blog.codacy.com/space-framework) (Satisfaction, Performance, Activity, Collaboration, Efficiency)

## Quick Start

```bash
/insight              # Weekly summary (default)
/insight daily        # Last 24h
/insight monthly      # Last 30 days
/insight compare      # This week vs last week
/insight agents       # Agent ROI analysis
/insight hooks        # Hook performance
```

## SPACE-Based Analysis

### S - Satisfaction
- Session completion rate
- Error frequency trends
- Tool reliability scores

### P - Performance
- Tokens per task (efficiency)
- Agent success rates
- Time to completion

### A - Activity
- Tool usage distribution
- Peak productivity hours
- Task completion volume

### C - Collaboration (Agent)
- Agent spawn patterns
- Agent ROI (tokens vs value)
- Agent failure analysis

### E - Efficiency
- Hook latency impact
- Context utilization
- Cache hit rates

## Report Templates

### Daily Report (5 min read)
```markdown
# Daily Insight - {date}

## Quick Stats
- Sessions: {count}
- Tokens: {total} (~${cost})
- Errors: {count} ({trend})

## Top Issue
{critical_issue_if_any}

## Action Required
- [ ] {single_most_important_action}
```

### Weekly Report (10 min read)
```markdown
# Weekly Insight - {week}

## Executive Summary
| Metric | Value | vs Last Week |
|--------|-------|--------------|
| Sessions | {n} | {trend}% |
| Tokens | {n} | {trend}% |
| Cost | ${n} | {trend}% |
| Efficiency | {n}/task | {trend}% |

## SPACE Analysis

### Performance (Speed)
- Avg task duration: {n} min
- Agent success rate: {n}%
- Hook latency: {n}ms avg

### Efficiency (Quality)
- Tokens per completed task: {n}
- Context resets: {n} (target: <3/day)
- Cache utilization: {n}%

## Top 3 Insights
1. {insight_1}
2. {insight_2}
3. {insight_3}

## Agent ROI Analysis
| Agent | Spawns | Tokens | Success | ROI |
|-------|--------|--------|---------|-----|
| {agent} | {n} | {n} | {%} | {rating} |

## Hook Health
| Hook | Avg Latency | Max | Issues |
|------|-------------|-----|--------|
| {hook} | {n}ms | {n}ms | {count} |

## Recommendations
Priority actions for next week:
1. [ ] {action_1} - Impact: {high/medium/low}
2. [ ] {action_2} - Impact: {high/medium/low}
3. [ ] {action_3} - Impact: {high/medium/low}

## Trends
{7_day_trend_visualization}
```

### Monthly Report (20 min read)
```markdown
# Monthly Insight - {month}

## Financial Summary
| Category | Amount | Budget | Variance |
|----------|--------|--------|----------|
| Total Cost | ${n} | ${n} | {%} |
| Cost/Session | ${n} | ${n} | {%} |
| Cost/Task | ${n} | ${n} | {%} |

## Productivity Gains
- Tasks completed: {n}
- Estimated manual hours saved: {n}h
- ROI: {n}x

## Strategic Insights
{detailed_analysis}

## System Health Score
Overall: {score}/100

Components:
- Hooks: {score}/100
- Agents: {score}/100
- Metrics: {score}/100
- Config: {score}/100

## Next Month Recommendations
{strategic_recommendations}
```

## Data Sources

### QuestDB Queries
```sql
-- Daily efficiency
SELECT
  date_trunc('day', timestamp) as day,
  count(*) as tool_calls,
  avg(duration_ms) as avg_duration,
  sum(case when success then 1 else 0 end)::float / count(*) as success_rate
FROM claude_tool_usage
WHERE timestamp > dateadd('d', -1, now())
GROUP BY day

-- Agent ROI
SELECT
  agent_type,
  count(*) as spawns,
  sum(tokens_used) as total_tokens,
  avg(case when success then 1.0 else 0.0 end) as success_rate,
  sum(tokens_used) / nullif(sum(case when success then 1 else 0 end), 0) as tokens_per_success
FROM claude_agents
WHERE timestamp > dateadd('d', -7, now())
GROUP BY agent_type
ORDER BY total_tokens DESC

-- Hook latency
SELECT
  hook_name,
  avg(duration_ms) as avg_latency,
  percentile_cont(0.95) within group (order by duration_ms) as p95_latency,
  count(*) filter (where not success) as failures
FROM claude_hooks
WHERE timestamp > dateadd('d', -7, now())
GROUP BY hook_name
HAVING avg_latency > 100
ORDER BY avg_latency DESC
```

### JSONL Sources
```yaml
files:
  - ~/.claude/metrics/task_classifier.jsonl
  - ~/.claude/metrics/dora_metrics.jsonl
  - .claude/stats/agent_spawns.jsonl
```

## Insight Categories

### 1. Cost Optimization
```
INSIGHT: Agent 'Explore' used 45% of tokens but completed 12% of tasks
SEVERITY: Medium
ACTION: Use targeted Grep/Glob instead of Explore for simple searches
IMPACT: ~30% token reduction, ~$15/week savings
```

### 2. Performance Issues
```
INSIGHT: Hook 'ssot_check.py' P95 latency is 1.2s (target: <500ms)
SEVERITY: High
ACTION: Add caching or reduce file scanning scope
IMPACT: 2s faster prompt processing
```

### 3. Reliability Concerns
```
INSIGHT: Agent 'Plan' failed 4 times this week (timeout)
SEVERITY: Medium
ACTION: Increase timeout or add checkpoints
IMPACT: Fewer interrupted planning sessions
```

### 4. Unused Resources
```
INSIGHT: Skill 'pinescript-converter' not invoked in 30 days
SEVERITY: Low
ACTION: Archive or improve trigger keywords
IMPACT: Cleaner skill discovery
```

## Elite Engineer Pattern

> **Google DevInt approach**: No single metric captures productivity.
> Analyze through **Speed** (latency), **Ease** (friction), **Quality** (success rate).

> **LinkedIn DevInsights**: Focus on reducing "friction from key developer activities."
> Track P50/P90 for critical paths.

### Weekly Ritual (5 minutes Monday)
```
1. Run: /insight weekly
2. Review: Top 3 insights
3. Fix: Most impactful issue
4. Ignore: Everything else
5. Result: System stays healthy with minimal effort
```

### Monthly Review (30 minutes)
```
1. Run: /insight monthly
2. Analyze: Cost trends, ROI
3. Archive: Unused skills/agents
4. Optimize: Slow hooks
5. Plan: Next month improvements
```

## Output Formats

### Terminal (default)
```
📊 Weekly Insight (Jan 6-12, 2026)

Sessions: 47 (+12% vs last week)
Tokens: 2.3M (~$28)
Efficiency: 1,180 tokens/task (↓8% 👍)

🎯 SPACE Score: 82/100
├── Satisfaction: 88 (low errors)
├── Performance: 79 (agent success rate)
├── Activity: 85 (steady usage)
├── Collaboration: 78 (agent ROI)
└── Efficiency: 80 (token optimization)

🔍 Top Insights:
1. ⚠️ Hook latency up 40% - check ssot_check.py
2. ✅ Agent success rate 96% (best month)
3. 💡 'Explore' agent overused - try targeted search

📋 Priority Actions:
- [ ] Profile ssot_check.py (High impact)
- [ ] Archive pinescript skill (Low effort)
```

### Markdown File
Saved to: `~/.claude/reports/insight-{date}.md`

### JSON (automation)
```json
{
  "period": "weekly",
  "dates": {"start": "2026-01-06", "end": "2026-01-12"},
  "summary": {
    "sessions": 47,
    "tokens": 2300000,
    "cost_usd": 28.00,
    "efficiency": 1180
  },
  "space_score": {
    "overall": 82,
    "satisfaction": 88,
    "performance": 79,
    "activity": 85,
    "collaboration": 78,
    "efficiency": 80
  },
  "insights": [...],
  "recommendations": [...]
}
```

## Token Economics

| Task | Manual Analysis | With Skill | Savings |
|------|-----------------|------------|---------|
| Daily review | ~15 min | ~2 min | 87% |
| Weekly report | ~45 min | ~5 min | 89% |
| Monthly analysis | ~2 hours | ~15 min | 88% |

**Skill overhead**: ~500 tokens (query + format)

## Automatic Invocation

**Triggers**:
- "show metrics"
- "analyze usage"
- "insight report"
- "weekly summary"
- "how am I doing"

**Does NOT trigger**:
- Specific debugging questions
- Code-related queries
- File operations

## Integration

**Hooks called**:
- None (read-only analysis)

**Chains to**:
- `claude-audit` (if issues detected)
- `github-workflow` (for issue creation)

**Metrics logged**:
```yaml
table: claude_skills
fields:
  skill_name: metrics-insight
  period: daily|weekly|monthly
  duration_ms: {measured}
  insights_generated: {count}
```

---

Sources:
- [Anthropic Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Pragmatic Engineer: Measuring Developer Productivity](https://newsletter.pragmaticengineer.com/p/measuring-developer-productivity-bae)
- [SPACE Framework](https://blog.codacy.com/space-framework)
- [Google Developer Intelligence](https://newsletter.pragmaticengineer.com/p/engineering-productivity)
