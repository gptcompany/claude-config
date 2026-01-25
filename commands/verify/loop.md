# Full Verification Loop

Run complete 6-phase verification pipeline before commits or PRs.

## On Invocation

```bash
node ~/.claude/scripts/hooks/skills/verification/verification-runner.js
```

## Phases

1. **Build** - Compile/transpile code (fail-fast)
2. **Type Check** - Static type analysis (fail-fast)
3. **Lint** - Code quality checks
4. **Tests** - Run test suite (fail-fast)
5. **Security** - Vulnerability scanning
6. **Diff** - Show pending git changes

## Behavior

- Runs phases sequentially
- **Fail-fast** on critical phases (build, typecheck, test)
- Reports all issues for non-fail-fast phases (lint, security)
- Shows git diff summary at end
- Auto-detects project type (npm, python, go, rust, etc.)

## Options

```
--skip=<phase>      Skip a specific phase
--skip-security     Shortcut for --skip=security
--verbose           Show full command output
--quiet             Suppress output except errors
--json              Output results as JSON
```

## Output

Returns structured result:
- **READY**: All phases passed, code is ready for commit
- **BLOCKED**: Failed at fail-fast phase, fix needed before continuing
- **ISSUES**: Non-critical issues found, review recommended

## When to Use

- Before creating a PR: `/verify:loop`
- Before important commits
- After significant refactoring
- When CI keeps failing locally

## Example

```
$ /verify:loop

==================================================
   VERIFICATION LOOP (node+ts)
==================================================

[checkmark] Build (1234ms)
[checkmark] Type Check (567ms)
[checkmark] Lint (234ms)
[checkmark] Tests (2345ms)
[checkmark] Security (456ms)
[checkmark] Changes (12ms)

--------------------------------------------------
Summary: 6 passed, 0 failed, 0 skipped
Duration: 4848ms

[checkmark] READY for commit
```

## See Also

- `/verify:quick` - Fast verification (skips security)
