# Health Check Command

Run cross-repo drift detection and system health analysis.

## Command
`/health`

## What It Does

1. Runs `~/.claude/scripts/drift-detector.py`
2. Reports health score (0-100)
3. Lists issues by severity
4. Suggests fixes

## Usage

```bash
# Quick check
/health

# With auto-fix
/health --fix

# Generate report
/health --report
```

## Execution

Run the drift detector script:

```bash
python3 ~/.claude/scripts/drift-detector.py $ARGS
```

Where `$ARGS` are any arguments passed to the command.

## Expected Output

```
Health Score: 100/100
No drift detected. All systems healthy.
```

Or if issues found:

```
Health Score: 75/100

MEDIUM: 3 issues
  - [repo_name] Issue description [fixable]

Run with --fix to apply fixes.
```

## When to Use

- **Weekly**: Monday morning quick check
- **After changes**: When modifying hooks/skills/commands
- **Before commits**: Verify consistency
- **New repo setup**: After running /new-project
