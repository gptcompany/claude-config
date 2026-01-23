# Phase 12: Confidence-Based Loop Extension - Context

**Gathered:** 2026-01-23
**Status:** Ready for research

<vision>
## How This Should Work

The validation loop becomes intelligent — instead of running a fixed number of iterations, it uses multi-dimensional confidence scoring to know when work is "done enough."

Multiple validators (visual similarity, DOM structure, accessibility, performance) each contribute to a fused confidence score. The loop continues refining until the combined confidence crosses a threshold, then terminates dynamically.

This transforms Tier 3 validators from passive monitors that just report into active loop drivers that guide the refinement process.

</vision>

<essential>
## What Must Be Nailed

- **Dynamic termination** - Loop knows when to stop based on confidence, not fixed iterations
- **Progressive refinement** - Three-stage approach: layout → style → polish
- **Unified scoring** - Single confidence number from multiple validators (visual + DOM + a11y + perf)

These are interconnected as a system — can't nail one without the others.

</essential>

<specifics>
## Specific Ideas

- **Dual observability**:
  - Grafana dashboard for real-time confidence metrics monitoring
  - Terminal feedback for immediate progress indicators during Claude's refinement
- Phase 12 is confidence loop only — ECC integration stays in Milestone 4 (Phases 13-15)

</specifics>

<notes>
## Additional Context

Phase 12 completes Milestone 3 (Universal 14-Dimension Orchestrator). After this, the framework has:
- Tiered execution (Tier 1 blockers, Tier 2 warnings, Tier 3 monitors)
- 14 validation dimensions
- Confidence-driven loop termination
- Full observability (Prometheus/Grafana + terminal)

ECC patterns (verification loop, TDD workflow, hooks port) are intentionally deferred to M4.

</notes>

---

*Phase: 12-confidence-loop*
*Context gathered: 2026-01-23*
