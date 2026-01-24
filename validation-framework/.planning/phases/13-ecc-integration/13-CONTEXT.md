# Phase 13: ECC Full Integration - Context

**Gathered:** 2026-01-24
**Status:** Ready for research

<vision>
## How This Should Work

Take the best of ECC (everything-claude-code) and merge it into our existing validation orchestrator. This is a best-of-both approach — cherry-pick ECC's verification agents and slot them into our 14-dimension tiered system.

The architecture should be layered: our ValidationOrchestrator coordinates, ECC agents execute specific checks. Users interact with one system, but under the hood it's orchestrating specialized agents from both origins.

Need to first audit which ECC agents are available and assess what we can integrate vs what duplicates existing functionality.

</vision>

<essential>
## What Must Be Nailed

- **Complete agent coverage** — All validation dimensions should be handled by proper agents, not just heuristics. If there's a validation dimension, there should be an agent responsible for it.
- **Clear layered separation** — Our orchestrator coordinates, ECC agents execute. No blurred responsibilities.
- **All verification agents integrated** — e2e-runner, security-reviewer, code-reviewer, test-runner, plus any others that fill gaps.

</essential>

<specifics>
## Specific Ideas

- Audit ECC agents first to determine what's available
- Integrate all verification agents, plus additional ones if they fill coverage gaps
- Maintain backward compatibility with existing orchestrator API
- ECC agents should feel native to the system (seamless integration under the hood)

</specifics>

<notes>
## Additional Context

Reference path: `/media/sam/1TB/everything-claude-code/`

The goal is complete coverage, not minimal viable. If ECC has agents that improve our coverage, they come in. The layered approach means clear ownership — orchestrator owns coordination, agents own execution.

</notes>

---

*Phase: 13-ecc-integration*
*Context gathered: 2026-01-24*
