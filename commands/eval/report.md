# Eval Report

View pass@k metrics summary.

## On Invocation

```bash
node ~/.claude/scripts/hooks/skills/eval/eval-harness.js --summary
```

## Output

Shows pass@k percentages calculated from recent runs:

```
{
  "totalRuns": 42,
  "passAt": {
    "pass@1": "65.0%",
    "pass@2": "85.0%",
    "pass@3": "95.0%"
  },
  "overallPassRate": "78.5%",
  "lastUpdated": "2026-01-25T13:00:00.000Z"
}
```

## Interpretation

- **pass@1: 65%** - 65% of tests pass on first attempt
- **pass@2: 85%** - 85% pass by second attempt (20% needed one fix)
- **pass@3: 95%** - 95% pass by third attempt

## Recent Runs

View individual run history:

```bash
node ~/.claude/scripts/hooks/skills/eval/eval-harness.js --recent
node ~/.claude/scripts/hooks/skills/eval/eval-harness.js --recent --count=20
```

## Data Location

- Local: `~/.claude/evals/results.json`
- QuestDB: `claude_eval_runs` table

## Grafana Dashboard

View trends in Grafana:

- Panel: "Eval Pass@K Trends"
- Query: `SELECT * FROM claude_eval_runs WHERE project = 'your-project'`

## Benchmarks

Typical healthy metrics:

| Metric | Good | Warning | Action Needed |
|--------|------|---------|---------------|
| pass@1 | >70% | 50-70% | <50% |
| pass@2 | >90% | 80-90% | <80% |
| pass@3 | >95% | 90-95% | <90% |

## Improving Pass@1

To improve first-attempt success:

1. Write tests before implementation (TDD)
2. Use type checking
3. Review similar code before writing
4. Break complex tasks into smaller steps

## Clear Metrics

To reset metrics (start fresh):

```bash
rm ~/.claude/evals/results.json
```
