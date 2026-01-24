---
phase: 13-ecc-integration
plan: 03
subsystem: validation
tags: [skill, cli, orchestrator, ecc-integration]

# Dependency graph
requires:
  - phase: 13-01
    provides: ECCValidatorBase, validators/ecc/ module structure
provides:
  - /validate skill for unified validation command
  - run_from_cli method for tier-filtered execution
  - ECC validator registration pattern with graceful fallback
affects: [14-hooks-modernization, 15-skills-port]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Skill Pattern: markdown skill definition at ~/.claude/skills/"
    - "CLI Pattern: positional tier argument for orchestrator"
    - "Graceful Import: ECC_VALIDATORS_AVAILABLE flag"

key-files:
  created:
    - ~/.claude/skills/validate.md
  modified:
    - ~/.claude/templates/validation/orchestrator.py

key-decisions:
  - "Positional tier argument instead of --tier flag for simpler CLI"
  - "Exit codes: 0=pass, 1=Tier1 fail, 2=error"
  - "ECC validators registered conditionally with ECC_VALIDATORS_AVAILABLE"

patterns-established:
  - "Skill Definition Pattern: markdown docs at ~/.claude/skills/"
  - "Graceful Degradation: try/except with _AVAILABLE flag for optional validators"

# Metrics
duration: 2min
completed: 2026-01-24
---

# Phase 13 Plan 03: Unified /validate Skill Summary

**/validate skill with tier filtering and ECC validators registered in orchestrator (graceful fallback)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-24T09:34:12Z
- **Completed:** 2026-01-24T09:36:35Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Created `/validate` skill definition with tier filtering docs (1/quick, 2, 3, all)
- Added `run_from_cli(tier)` method to ValidationOrchestrator for skill invocation
- Registered ECC validators in VALIDATOR_REGISTRY with graceful degradation
- Updated orchestrator docstring to document core + ECC dimensions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create /validate skill definition** - `9eba42e` (feat)
2. **Task 2: Add run_from_cli method to orchestrator** - `1321755` (feat)
3. **Task 3: Register ECC validators in VALIDATOR_REGISTRY** - `35ddfec` (feat)

## Files Created/Modified

- `~/.claude/skills/validate.md` - Skill definition with usage, tier summary, exit codes (31 lines)
- `~/.claude/templates/validation/orchestrator.py` - Added run_from_cli, ECC imports, registry update (+114 lines)

## Decisions Made

1. **Positional tier argument** - Simpler CLI: `python orchestrator.py 1` vs `python orchestrator.py --tier 1`
2. **Exit code convention** - 0=pass, 1=Tier1 blockers failed, 2=validation error
3. **Graceful ECC import** - `ECC_VALIDATORS_AVAILABLE` flag enables conditional registry update
4. **ASCII output** - Used `[PASS]/[FAIL]/[+]/[-]` instead of emoji for terminal compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 13-02 (ECC validators implementation) can proceed independently
- Once 13-02 completes, ECC validators will auto-register via conditional import
- Phase 13 complete after 13-02 finishes
- Ready for Phase 14: Hooks Node.js Port

---
*Phase: 13-ecc-integration*
*Completed: 2026-01-24*
