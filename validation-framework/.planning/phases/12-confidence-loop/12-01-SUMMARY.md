---
phase: 12-confidence-loop
plan: 01
subsystem: validation
tags: [visual, odiff, ssim, image-comparison, scikit-image, playwright]

# Dependency graph
requires:
  - phase: 11-ralph-integration
    provides: ValidationOrchestrator, tiered execution, Prometheus metrics
provides:
  - VisualTargetValidator with combined ODiff + SSIM scoring
  - ODiffRunner pixel-level comparison wrapper
  - PerceptualComparator SSIM perceptual comparison
  - Fused confidence scoring system (60% pixel, 40% SSIM)
affects: [12-02, 12-03, confidence-loop]

# Tech tracking
tech-stack:
  added: [odiff-bin, scikit-image, pillow]
  patterns: [graceful-degradation, fused-scoring, async-validation]

key-files:
  created:
    - validators/visual/pixel_diff.py
    - validators/visual/perceptual.py
    - validators/visual/validator.py
    - validators/visual/__init__.py
  modified: []

key-decisions:
  - "Use ODiff CLI via subprocess for fast SIMD pixel comparison"
  - "Use SSIM from scikit-image for perceptual similarity"
  - "Fused scoring: 60% pixel + 40% SSIM (configurable weights)"
  - "Graceful degradation when tools unavailable"

patterns-established:
  - "Visual validator pattern: combine fast pixel diff with perceptual similarity"
  - "Center crop for dimension mismatch handling"
  - "Parsable stdout format for CLI tool integration"

# Metrics
duration: 42min
completed: 2026-01-23
---

# Plan 12-01: Visual Comparison Foundation Summary

**ODiff pixel + SSIM perceptual comparison with fused confidence scoring for visual validation**

## Performance

- **Duration:** 42 min
- **Started:** 2026-01-23T19:29:33Z
- **Completed:** 2026-01-23T20:11:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- ODiffRunner wrapping odiff-bin CLI with parsable stdout parsing
- PerceptualComparator using scikit-image SSIM with grayscale conversion
- VisualTargetValidator combining both methods with fused confidence
- 80 tests passing across all visual validator modules
- Graceful degradation when tools unavailable (uses available one)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pixel_diff.py with ODiff wrapper** - `d0f2d07` (feat)
2. **Task 2: Create perceptual.py with SSIM scoring** - `177a4c5` (feat)
3. **Task 3: Create VisualTargetValidator with combined scoring** - `c95b46b` (feat)

## Files Created/Modified
- `validators/visual/pixel_diff.py` - ODiff CLI wrapper for pixel comparison
- `validators/visual/perceptual.py` - SSIM-based perceptual comparison
- `validators/visual/validator.py` - Combined validator with fused scoring
- `validators/visual/__init__.py` - Module exports
- `validators/visual/tests/test_pixel_diff.py` - 29 tests for ODiff wrapper
- `validators/visual/tests/test_perceptual.py` - 26 tests for SSIM comparator
- `validators/visual/tests/test_validator.py` - 25 tests for combined validator

## Decisions Made
- Used `--parsable-stdout` flag for odiff instead of `--json` (which doesn't exist)
- Used center crop for dimension mismatch instead of resize (preserves pixel ratio)
- Default weights: 60% pixel, 40% SSIM (pixel catches exact differences, SSIM catches perceptual ones)
- Both tools optional - falls back to single available tool when one missing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed odiff CLI options**
- **Found during:** Task 1 (ODiff wrapper implementation)
- **Issue:** Plan assumed `--json` flag which doesn't exist in odiff
- **Fix:** Used `--parsable-stdout` flag and parsed semicolon-separated output
- **Files modified:** validators/visual/pixel_diff.py
- **Verification:** Integration tests pass with real odiff
- **Committed in:** d0f2d07 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Fixed incorrect CLI flag assumption. No scope creep.

## Issues Encountered
None - plan executed smoothly after CLI flag correction.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Visual comparison foundation complete
- Ready for behavioral (DOM diff) validators in Plan 02
- Ready for MultiModalValidator fusion in Plan 03

---
*Phase: 12-confidence-loop*
*Plan: 01*
*Completed: 2026-01-23*
