---
phase: 12-confidence-loop
plan: 02
subsystem: validators
tags: [dom-diff, tree-edit-distance, zss, behavioral, html-comparison]

# Dependency graph
requires:
  - phase: 10
    provides: Validator patterns from MathematicalValidator and APIContractValidator
provides:
  - BehavioralValidator for DOM structure comparison
  - DOMComparator using Zhang-Shasha tree edit distance
  - Graceful degradation when zss not installed
affects: [12-confidence-loop, multimodal-scoring]

# Tech tracking
tech-stack:
  added: [zss (zhang-shasha)]
  patterns: [tree-edit-distance, html-parsing, structural-similarity]

key-files:
  created:
    - validators/behavioral/dom_diff.py
    - validators/behavioral/validator.py
    - validators/behavioral/__init__.py
    - validators/behavioral/tests/__init__.py
    - validators/behavioral/tests/test_dom_diff.py
    - validators/behavioral/tests/test_validator.py

key-decisions:
  - "Used zss (Zhang-Shasha) library for tree edit distance - O(n^2) optimal algorithm"
  - "Filter non-meaningful elements (script, style, meta, head) for cleaner comparison"
  - "ZSS compares tags only, not attributes - simpler but effective for structure"

patterns-established:
  - "Graceful degradation pattern: fallback when optional dependency unavailable"
  - "Similarity score pattern: edit_distance / max(tree_size) for 0-1 confidence"

# Metrics
duration: 7min
completed: 2026-01-23
---

# Phase 12 Plan 02: BehavioralValidator Summary

**DOM structure comparison using Zhang-Shasha tree edit distance with zss library, returning 0-1 confidence score**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-23T19:29:02Z
- **Completed:** 2026-01-23T19:35:37Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- DOMComparator with parse_html() for HTML to tree conversion
- Tree edit distance via zss (Zhang-Shasha) algorithm
- Filtered elements: script, style, meta, head, noscript, template, link
- BehavioralValidator (Tier 3 MONITOR) with configurable threshold
- Graceful fallback when zss not installed (Jaccard similarity heuristic)
- 74 tests passing (45 dom_diff + 29 validator)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create dom_diff.py with tree edit distance + tests** - `6e67b42` (feat)
2. **Task 2: Create BehavioralValidator with structural scoring + tests** - `3787f50` (feat)

## Files Created/Modified

- `validators/behavioral/dom_diff.py` - DOMComparator with Zhang-Shasha algorithm
- `validators/behavioral/validator.py` - BehavioralValidator extending BaseValidator
- `validators/behavioral/__init__.py` - Package exports
- `validators/behavioral/tests/__init__.py` - Test package
- `validators/behavioral/tests/test_dom_diff.py` - 45 tests for DOM comparison
- `validators/behavioral/tests/test_validator.py` - 29 tests for validator

## Decisions Made

1. **Zhang-Shasha algorithm via zss**: Optimal O(n^2) tree edit distance, well-tested library
2. **Tag-only comparison**: ZSS compares labels (tags), not attributes - simpler and sufficient for structural similarity
3. **Filtered elements**: Exclude script, style, meta, head, noscript, template, link - not meaningful for structure
4. **Fallback heuristic**: Jaccard similarity of tag sets when zss unavailable

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- pytest-cov had module import caching issues in this repo, but all tests pass independently

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BehavioralValidator ready for orchestrator integration
- Can be added to Tier 3 validators in Phase 12-03 or later
- ZSS library added as optional dependency (graceful degradation works)

---
*Phase: 12-confidence-loop*
*Completed: 2026-01-23*
