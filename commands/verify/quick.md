# Quick Verification

Run fast verification loop, skipping slow phases like security scanning.

## On Invocation

```bash
node ~/.claude/scripts/hooks/skills/verification/verification-runner.js --skip=security
```

## Phases Run

1. **Build** - Compile/transpile code (fail-fast)
2. **Type Check** - Static type analysis (fail-fast)
3. **Lint** - Code quality checks
4. **Tests** - Run test suite (fail-fast)
5. ~~Security~~ (skipped)
6. **Diff** - Show pending git changes

## When to Use

- During development iteration (fast feedback loop)
- Before quick commits
- When security scan is slow or rate-limited
- When iterating on failing tests

## Behavior

Same as `/verify:loop` but skips the security phase:
- Sequential execution
- Fail-fast on build, typecheck, test
- Shows diff at end
- Auto-detects project type

## Example

```
$ /verify:quick

==================================================
   VERIFICATION LOOP (node+ts)
==================================================

[checkmark] Build (1234ms)
[checkmark] Type Check (567ms)
[checkmark] Lint (234ms)
[checkmark] Tests (2345ms)
[circle] Security (skipped)
[checkmark] Changes (12ms)

--------------------------------------------------
Summary: 5 passed, 0 failed, 1 skipped
Duration: 4392ms

[checkmark] READY for commit
```

## Comparison

| Command | Phases | Speed | When to Use |
|---------|--------|-------|-------------|
| `/verify:quick` | 5 | ~5s | During development |
| `/verify:loop` | 6 | ~10s | Before PR, important commits |

## See Also

- `/verify:loop` - Full verification with security
