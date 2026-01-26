# Phase 19: Production Hardening - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<vision>
## How This Should Work

The validation framework goes from "works in happy path" to "works in production." When validators fail, timeout, or misbehave, the system handles it gracefully instead of crashing or hanging. When files haven't changed, validation skips them intelligently. When everything's burning, the user still gets useful partial results.

The key feeling: **confidence**. After Phase 19, running validation on any project should feel reliable - like running `make` or `pytest`. No surprises, no hangs, predictable behavior.

</vision>

<essential>
## What Must Be Nailed

- **E2E test foundation** - Live `spawn_agent()` tests that validate the real claude-flow integration. Without this, we're hardening blind.
- **Caching that actually works** - Skip validation for unchanged files. Cache invalidation based on file hash + config changes. 5x minimum speedup.
- **Graceful failures** - When a validator dies, return partial results with clear indication of what failed. Never hang indefinitely.

</essential>

<specifics>
## Specific Ideas

**Expert Council PMW Analysis determined:**

1. **Order: 19-01 → 19-02 → 19-03 (merged)**
   - E2E tests first (can't harden what you can't test)
   - Caching second (accelerates everything, not premature)
   - Resilience last (circuit breaker + graceful degradation merged)

2. **Merge 19-03 + 19-04 into single "Resilience & Recovery" plan**
   - Circuit breaker and graceful degradation are the same pattern at different layers
   - Implementing together ensures consistency
   - Single plan easier to validate E2E

3. **Test distribution:**
   - 19-01: 10 tests (E2E foundation)
   - 19-02: 12 tests (caching layer)
   - 19-03: 18 tests (resilience merged)
   - Total: 40 tests (same as original scope)

**SWOT-validated decisions:**
- Caching is NOT premature optimization - it's baseline expectation
- E2E tests MUST be designed for stability (no flaky tests)
- Circuit breaker config needs sensible defaults

</specifics>

<notes>
## Additional Context

**PMW (Prove Me Wrong) findings:**
- Q1: "Circuit breaker first" - PARTIALLY DISPROVEN (caching reduces need)
- Q2: "E2E is heavy" - HOLDS (design for stability)
- Q3: "Caching is premature" - DISPROVEN (accelerates development)
- Q4: "19-03 vs 19-04 separate" - QUESTIONABLE (merged is better)

**Execution flow:**
```
19-01: E2E Foundation          [10 tests] → Validates spawn_agent() works
  ↓
19-02: Caching Layer           [12 tests] → 5x speedup, reduces load
  ↓
19-03: Resilience & Recovery   [18 tests] → Circuit breaker + graceful degradation
```

**Dependencies:**
- Phase 18 complete (Visual + Behavioral validators integrated)
- claude-flow MCP available for E2E tests
- QuestDB running for metrics during E2E

</notes>

---

*Phase: 19-production-hardening*
*Context gathered: 2026-01-26*
*Strategy: Expert Council PMW Analysis*
