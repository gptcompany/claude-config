---
phase: 15-skills-port
plan: 03
subsystem: quality
tags: [coding-standards, eslint, patterns, hooks, pre-tool-use]

# Dependency graph
requires:
  - phase: 15-01
    provides: Node.js hook infrastructure and test patterns
provides:
  - Pattern-based anti-pattern detection library
  - PreToolUse coding standards hook
  - /standards:check and /standards:config commands
affects: [15-05-gsd-integration, future-quality-hooks]

# Tech tracking
tech-stack:
  added: []
  patterns: [pattern-based-detection, configurable-enforcement, glob-matching]

key-files:
  created:
    - ~/.claude/scripts/hooks/skills/standards/patterns.js
    - ~/.claude/scripts/hooks/skills/standards/coding-standards.js
    - ~/.claude/scripts/hooks/skills/standards/check-file.js
    - ~/.claude/scripts/hooks/skills/standards/standards.test.js
    - ~/.claude/commands/standards/check.md
    - ~/.claude/commands/standards/config.md
  modified:
    - ~/.claude/hooks/hooks.json

key-decisions:
  - "Warn mode default - allow writes with warnings, block only when explicitly configured"
  - "Fail-open error handling - any hook error allows the operation to proceed"
  - "Custom minimatch implementation - avoid external dependency while supporting common patterns"

patterns-established:
  - "Pattern library separation: patterns.js exports detection logic, hook script uses it"
  - "Config-driven enforcement: ~/.claude/standards-config.json controls behavior"
  - "Severity levels: error (blocks), warn (logs), info (suggestions)"

# Metrics
duration: 25min
completed: 2026-01-25
---

# Phase 15 Plan 03: Coding Standards Skill Summary

**Pattern-based coding standards enforcement with warn/block modes for JS/TS and Python anti-patterns**

## Performance

- **Duration:** 25 min
- **Started:** 2026-01-25T12:50:00Z
- **Completed:** 2026-01-25T13:15:00Z
- **Tasks:** 5 (1 partial from previous session)
- **Files modified:** 7

## Accomplishments

- Anti-pattern detection library with 13 patterns (7 JS, 6 Python)
- PreToolUse hook with configurable warn/block/off enforcement modes
- CLI check-file.js for manual directory/file scanning
- 34 tests with 100% pass rate

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Patterns Library** - `ebb2848` (feat) - *from previous session*
2. **Task 2: Create Standards Enforcer Hook** - `8bff5ff` (feat)
3. **Task 3: Create Standards Commands** - `8f6da0f` (feat)
4. **Task 4: Add Hook Binding** - `b899e95` (feat)
5. **Task 5: Create Tests** - `fe7e153` (test)

## Files Created/Modified

- `~/.claude/scripts/hooks/skills/standards/patterns.js` (287 LOC) - Anti-pattern definitions and detection
- `~/.claude/scripts/hooks/skills/standards/coding-standards.js` (252 LOC) - PreToolUse hook
- `~/.claude/scripts/hooks/skills/standards/check-file.js` (190 LOC) - CLI checking tool
- `~/.claude/scripts/hooks/skills/standards/standards.test.js` (670 LOC) - Test suite
- `~/.claude/commands/standards/check.md` - Manual check command
- `~/.claude/commands/standards/config.md` - Configuration command
- `~/.claude/hooks/hooks.json` - Added coding-standards hook binding

## Pattern Coverage

### JavaScript/TypeScript (7 patterns)
| Pattern | Severity | Description |
|---------|----------|-------------|
| console-log-in-prod | warn | console.log in production code |
| any-type | warn | `: any` type annotation |
| hardcoded-secret | error | Credentials in code |
| todo-without-issue | info | TODO without issue link |
| debugger-statement | error | debugger left in code |
| alert-in-code | warn | alert() usage |
| process-exit-in-lib | warn | process.exit() in libraries |

### Python (6 patterns)
| Pattern | Severity | Description |
|---------|----------|-------------|
| print-in-prod | warn | print() in production |
| bare-except | error | except: without type |
| star-import | warn | from x import * |
| hardcoded-secret-py | error | Credentials in code |
| mutable-default-arg | warn | def fn(x=[]) |
| pass-only-except | warn | except: pass |

## Decisions Made

1. **Warn mode as default** - Most users want feedback without blocking writes during development
2. **Fail-open error handling** - Hook errors should never break the user's workflow
3. **Custom minimatch** - Implemented glob matching without external deps (supports *.ext, test_*.py, dir/*, **/)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed minimatch for glob patterns**
- **Found during:** Task 5 (test execution)
- **Issue:** test_*.py and **/__tests__/* patterns not matching correctly
- **Fix:** Rewrote minimatch with proper pattern ordering and regex conversion
- **Files modified:** patterns.js
- **Verification:** All 34 tests pass
- **Committed in:** fe7e153 (part of test commit)

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** Fix was essential for pattern exclusion to work. No scope creep.

## Issues Encountered

None - aside from the minimatch fix documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Coding standards hook is active and working
- Ready for 15-04 (eval-harness) and 15-05 (GSD integration)
- Standards can be configured via ~/.claude/standards-config.json

---
*Phase: 15-skills-port*
*Plan: 03*
*Completed: 2026-01-25*
