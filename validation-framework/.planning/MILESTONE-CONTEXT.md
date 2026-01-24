# Milestone Context

**Generated:** 2026-01-24
**Status:** Ready for /gsd:new-milestone

<features>
## Features to Build

- **ECC Full Integration**: Unify ECC 6-phase verification loop with our 14-dimension orchestrator. Port ECC agents (e2e-runner, security-reviewer, code-reviewer). Create unified `/validate` skill.

- **Node.js Hooks Migration**: Port critical hooks from Bash/Python to Node.js for cross-platform reliability. Create utils.js shared library (from ECC patterns). Implement hooks.json declarative config. Test on Linux + macOS CI.

- **Skills Port**: Port ECC skills we lack - tdd-workflow (enforced TDD, not just docs), verification-loop (6-phase sequential), coding-standards, eval-harness (pass@k metrics). Integrate with GSD workflow triggers.

</features>

<scope>
## Scope

**Suggested name:** v4.0 ECC Integration & Hooks Modernization
**Estimated phases:** 3 (Phases 13-15)
**Estimated effort:** 90-115h
**Focus:** Port ECC best practices and modernize hooks infrastructure for cross-platform reliability

</scope>

<phase_mapping>
## Phase Mapping

- Phase 13: ECC Full Integration (30-40h)
  - 13-01: Create hybrid validation workflow (ECC 6-phase → our 14-dim)
  - 13-02: Port ECC agents (e2e-runner, security-reviewer) to our system
  - 13-03: Create unified `/validate` skill

- Phase 14: Hooks Node.js Port (40-50h)
  - 14-01: Create utils.js shared library
  - 14-02: Port critical hooks (context_bundle, post-tool-use, safety checks)
  - 14-03: Port high-priority hooks (architecture, readme, ci-autofix)
  - 14-04: Create hooks.json declarative config
  - 14-05: Test cross-platform (Linux + macOS CI)

- Phase 15: Skills Port (20-25h)
  - 15-01: Port tdd-workflow skill
  - 15-02: Port verification-loop skill
  - 15-03: Port coding-standards skill
  - 15-04: Port eval-harness skill
  - 15-05: Integrate skills with GSD workflow triggers

</phase_mapping>

<constraints>
## Constraints

- Must maintain backward compatibility with existing Python hooks during migration
- Node.js hooks must work on Linux, macOS, and Windows
- Skills must integrate with existing GSD workflow triggers
- ECC patterns should be adapted to our architecture, not copied verbatim

</constraints>

<notes>
## Additional Context

**Reference:** `/media/sam/1TB/everything-claude-code/`

**Migration priority for hooks:**
1. Critical: context_bundle_builder, post-tool-use, safety checks
2. High: architecture-validator, readme-generator, ci-autofix
3. Medium: metrics, intelligence hooks

**Skills gap analysis:**
- tdd-workflow: ECC has 409 LOC, we have 51 LOC doc-only version
- verification-loop: ECC has 120 LOC sequential gates, we have parallel tiers
- coding-standards: ECC has 520 LOC, we have nothing
- eval-harness: ECC has 221 LOC pass@k metrics, we have nothing

</notes>

---

*This file is temporary. It will be deleted after /gsd:new-milestone creates the milestone.*
