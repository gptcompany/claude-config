# Phase 10: Tier 3 Validators - Context

**Gathered:** 2026-01-22
**Status:** Ready for research

<vision>
## How This Should Work

Tier 3 validators act as **active guardrails** — not passive monitors, but proactive catchers that prevent issues before they compound.

Two validators:
1. **Mathematical validator** — Validates formulas from research papers AND inline code math. Leverages the existing CAS microservice at `localhost:8769` and N8N research pipeline. When CAS is unavailable, falls back to MCP Wolfram.

2. **API contract validator** — Detects breaking changes AND spec drift. Triggers on file changes to OpenAPI specs or route handlers. Auto-discovers specs (openapi.yaml, openapi.json, api/openapi.*) or uses config-driven paths. Supports FastAPI auto-generated endpoints.

Both produce JSON for automation + Markdown summaries for human review.

</vision>

<essential>
## What Must Be Nailed

- **CAS integration that works** — Connect to existing microservice, fallback to Wolfram MCP
- **API drift detection on file change** — Catch breaking changes before they reach consumers
- **Active not passive** — These should catch problems proactively, not just monitor

</essential>

<specifics>
## Specific Ideas

**Mathematical validator:**
- Uses existing CAS microservice (`localhost:8769/validate`)
- Supports SymPy, Wolfram, SageMath, MATLAB engines (already in microservice)
- Fallback to `mcp__wolframalpha__ask_llm` when local CAS unavailable
- Triggers: on-demand (Claude calls when sees formulas), integrates with /research pipeline
- Paper → code translation validation + inline formula sanity checks

**API contract validator:**
- Auto-discovery: `openapi.yaml`, `openapi.json`, `api/openapi.*`, FastAPI `/openapi.json`
- Config override for custom spec paths in validation-config.json
- Triggers on file change (spec files or route handlers)
- Breaking change classification (removed fields, type changes, etc.)
- Drift monitoring (code diverges from documented spec)

**Output format:**
- JSON for orchestrator/CI consumption
- Markdown summary for human review

</specifics>

<notes>
## Additional Context

Existing infrastructure to leverage:
- CAS microservice: `systemctl --user status cas-microservice` at port 8769
- N8N research pipeline already does formula validation
- MCP Wolfram available as fallback
- Orchestrator already has tiered execution (Tier1=blockers, Tier2=warnings, Tier3=monitors)

Tier 3 positioning: monitors → but user wants them as **active guardrails**, so they should be more proactive than typical Tier 3.

Phase 12 will handle visual validators (VisualTargetValidator, BehavioralValidator) — keeping Phase 10 focused on mathematical + api_contract.

</notes>

---

*Phase: 10-tier3-validators*
*Context gathered: 2026-01-22*
