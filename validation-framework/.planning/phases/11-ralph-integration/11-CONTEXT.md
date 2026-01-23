# Phase 11: Ralph Integration - Context

**Gathered:** 2026-01-23
**Status:** Ready for planning

<vision>
## How This Should Work

When code is committed, Ralph loop automatically triggers validation. The system runs two validation approaches in parallel:

1. **ECC verification** (quick feedback) - 6-phase sequential checks for immediate issues
2. **Our 14-dimension orchestrator** (deep analysis) - tiered parallel validation

The loop continues iterating until quality is sufficient. Failed Tier 1 (blockers) stops the loop and requires fixes. Results flow to Grafana dashboards for visibility, and validation context is injected into Sentry for debugging.

This is "full integration" - blocking on failures + metrics to dashboards + error context everywhere.

</vision>

<essential>
## What Must Be Nailed

- **Auto-blocking Tier 1** - Commit with Tier 1 failure = loop stops and requests fix
- **Metrics to Grafana** - Every validation run emits metrics visible in dashboard
- **Sentry context injection** - Validation errors injected into Sentry for debugging

All three are essential - none can be skipped.

</essential>

<specifics>
## Specific Ideas

- Parallel execution: ECC verification-loop for quick feedback, our orchestrator for comprehensive analysis
- Both systems complement each other rather than compete
- No specific UI preference - builder decides the best approach for communicating results

</specifics>

<notes>
## Additional Context

ECC has verification-loop skill but it's manual (`/verify`) and one-shot. Our Ralph loop is automatic and iterative. The integration should preserve both approaches:

- ECC: Quick, manual, 6-phase sequential
- Ours: Deep, automatic, 14-dimension parallel with tiered blocking

Key insight from discussion: ECC doesn't have automatic loops - this is our differentiator.

</notes>

---

*Phase: 11-ralph-integration*
*Context gathered: 2026-01-23*
