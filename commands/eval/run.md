# Run Eval

Execute test suite and track pass@k metrics.

## On Invocation

```bash
node ~/.claude/scripts/hooks/skills/eval/eval-harness.js --attempt=$ATTEMPT
```

## Options

- `--suite=<name>` - Name this test suite (e.g., unit, integration, e2e)
- `--attempt=<n>` - Which attempt this is (default: 1)
- `--command=<cmd>` - Override test command (auto-detected by default)
- `--timeout=<ms>` - Test timeout in milliseconds (default: 300000)

## Metrics Tracked

- **pass@1**: First-attempt success rate
- **pass@2**: Success by second attempt
- **pass@k**: Success by attempt k

## Why Track Attempts

When fixing bugs or implementing features, track attempts to measure:

1. **First attempt (pass@1)** - Initial code quality
2. **Second attempt (pass@2)** - Quick-fix capability
3. **Later attempts** - Iteration efficiency

Higher pass@1 indicates better initial implementation quality.
pass@2 vs pass@1 gap shows quick-fix effectiveness.

## Example Workflow

```bash
# First attempt at implementing feature
/eval:run --attempt=1

# Tests failed, made changes
/eval:run --attempt=2

# Still failing, debug more
/eval:run --attempt=3

# Check overall metrics
/eval:report
```

## Test Command Detection

Auto-detects based on project type:

| Project Type | Command |
|-------------|---------|
| Node.js | `npm test` |
| Python | `pytest -v` |
| Go | `go test ./...` |
| Rust | `cargo test` |
| Ruby | `bundle exec rspec` |
| Java (Maven) | `mvn test` |
| Java (Gradle) | `./gradlew test` |

## QuestDB Integration

Metrics are exported to QuestDB for Grafana visualization:

- Table: `claude_eval_runs`
- Fields: passed, total, attempt, duration_ms
- Tags: project, test_suite

## Data Location

- Local: `~/.claude/evals/results.json`
- QuestDB: `claude_eval_runs` table
