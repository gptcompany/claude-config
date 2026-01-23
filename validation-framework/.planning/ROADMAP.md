# Roadmap: Universal Validation Framework

## Overview

Build a reusable validation pipeline framework starting with core templates, then CI workflows, local K8s simulation, and domain-specific extensions. The framework ships in `~/.claude/templates/validation/` and is scaffolded to individual projects via a single command.

## Domain Expertise

- None (greenfield framework project)

## Milestones

- ✅ **Milestone 1** - Core Framework (Phases 1-5, shipped 2026-01-19)
- ✅ **Milestone 2** - Hybrid UAT & Validators (Phase 6, shipped 2026-01-20)
- 🚧 **Milestone 3** - Universal 14-Dimension Orchestrator (Phases 7-12, in progress)
- 🔮 **Milestone 4** - ECC Integration & Hooks Modernization (Phases 13-15, proposed)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ Milestone 1 & 2 (Phases 1-6) - SHIPPED 2026-01-20</summary>

- [x] **Phase 1: Core Framework** - Schema, scaffold script, base smoke tests
- [x] **Phase 2: CI Workflows** - GitHub Actions templates for smoke and integration
- [x] **Phase 3: Local K8s** - k3d cluster setup, Argo Rollouts, mock Prometheus
- [x] **Phase 4: Trading Extension** - Paper trading, risk limits, analysis templates
- [x] **Phase 5: Other Extensions** - Workflow and data domain templates
- [x] **Phase 6: Hybrid UAT & Validators** - Hybrid verify-work, accessibility, security, performance

### Phase 1: Core Framework
**Goal**: Create the foundational templates and scaffold script
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04
**Research**: Unlikely (established patterns - Jinja2, JSON Schema, pytest)
**Plans**: 2 plans

Plans:
- [x] 01-01: Create JSON Schema and scaffold script
- [x] 01-02: Create smoke test Jinja2 templates

### Phase 2: CI Workflows
**Goal**: Create GitHub Actions workflow templates
**Depends on**: Phase 1
**Requirements**: CI-01, CI-02
**Research**: Unlikely (standard GitHub Actions patterns)
**Plans**: 1 plan

Plans:
- [x] 02-01: Create CI workflow templates

### Phase 3: Local K8s
**Goal**: Create k3d cluster and Argo Rollouts templates
**Depends on**: Phase 2
**Requirements**: CI-03, K8S-01, K8S-02, K8S-03, K8S-04, K8S-05
**Research**: Likely (k3d configuration, Argo Rollouts analysis)
**Research topics**: k3d cluster config options, Argo Rollouts AnalysisTemplate syntax, mock Prometheus setup
**Plans**: 2 plans

Plans:
- [x] 03-01: Create k3d cluster templates
- [x] 03-02: Create Argo Rollouts and mock Prometheus templates

### Phase 4: Trading Extension
**Goal**: Create trading-specific validation templates
**Depends on**: Phase 1 (uses base smoke templates)
**Requirements**: EXT-TRADING-01, EXT-TRADING-02, EXT-TRADING-03
**Research**: Unlikely (patterns from nautilus_dev k8s/rollouts/)
**Plans**: 1 plan

Plans:
- [x] 04-01: Create trading domain templates

### Phase 5: Other Extensions
**Goal**: Create workflow and data domain templates
**Depends on**: Phase 1 (uses base smoke templates)
**Requirements**: EXT-WORKFLOW-01, EXT-WORKFLOW-02, EXT-DATA-01, EXT-DATA-02
**Research**: Unlikely (similar patterns to trading)
**Plans**: 1 plan

Plans:
- [x] 05-01: Create workflow and data domain templates

### Phase 6: Hybrid UAT & Validators
**Goal**: Create hybrid auto/manual UAT workflow with accessibility, security, and performance validators
**Depends on**: Phase 5 (uses existing templates), AI Validation Service
**Requirements**: HYBRID-01, A11Y-01, SEC-01, PERF-01
**Research**: Likely (axe-core integration, Trivy setup, Lighthouse CI)
**Research topics**: axe-core + Playwright integration, Trivy container scanning, Lighthouse CI configuration
**Plans**: 4 plans

Plans:
- [x] 06-01: Hybrid verify-work (auto-check + confidence + manual filter)
- [x] 06-02: Accessibility validation (axe-core + Playwright)
- [x] 06-03: Security scanning (Trivy container + dependency)
- [x] 06-04: Performance validation (Lighthouse CI + Core Web Vitals)

</details>

## Phase Details

### 🚧 Milestone 3: Universal 14-Dimension Orchestrator (In Progress)

**Milestone Goal:** Integrate existing validation components into a unified 14-dimension orchestrator with tiered execution and Ralph loop backpressure.

**Reference Plan:** `/home/sam/.claude/plans/calm-wobbling-ripple.md`

#### Phase 7: Orchestrator Core
**Goal**: Create ValidationOrchestrator with tiered execution (Tier1=blockers, Tier2=warnings, Tier3=monitors)
**Depends on**: Phase 6 (uses existing validators)
**Research**: Unlikely (internal async Python patterns)
**Plans**: TBD

Plans:
- [ ] 07-01: Create ValidationOrchestrator template + wire into Ralph loop

#### Phase 8: Config Schema v2 (COMPLETE)
**Goal**: Extend config generation tooling to expose all 14 dimensions with sensible defaults
**Depends on**: Phase 7
**Research**: Unlikely (JSON Schema extension)
**Plans**: 1 plan

Plans:
- [x] 08-01: Config generation CLI with domain presets

#### Phase 9: Tier 2 Validators (COMPLETE)
**Goal**: Create design_principles (KISS/YAGNI/DRY) and oss_reuse (package suggestions) validators
**Depends on**: Phase 8
**Research**: Completed (radon complexity metrics)
**Plans**: 2 plans

Plans:
- [x] 09-01: Create design_principles validator with radon + AST analysis
- [x] 09-02: Create oss_reuse validator with pattern detection

#### Phase 10: Tier 3 Validators (COMPLETE)
**Goal**: Create mathematical (CAS microservice) and api_contract (OpenAPI diff) validators
**Depends on**: Phase 8
**Research**: Completed (CAS microservice protocol, oasdiff CLI)
**Plans**: 2 plans

Plans:
- [x] 10-01: Create MathematicalValidator with CAS client and formula extractor
- [x] 10-02: Create APIContractValidator with spec discovery and oasdiff runner

#### Phase 11: Ralph Integration
**Goal**: Wire orchestrator into Ralph loop hook + MCP integration (Playwright, Sentry, Grafana)
**Depends on**: Phases 9, 10
**Research**: Unlikely (existing hook patterns)
**Plans**: TBD

Plans:
- [ ] 11-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Framework | M1 | 2/2 | Complete | 2026-01-19 |
| 2. CI Workflows | M1 | 1/1 | Complete | 2026-01-19 |
| 3. Local K8s | M1 | 2/2 | Complete | 2026-01-19 |
| 4. Trading Extension | M1 | 1/1 | Complete | 2026-01-19 |
| 5. Other Extensions | M1 | 1/1 | Complete | 2026-01-19 |
| 6. Hybrid UAT & Validators | M2 | 4/4 | Complete | 2026-01-20 |
| 7. Orchestrator Core | M3 | 1/1 | Complete | 2026-01-22 |
| 8. Config Schema v2 | M3 | 1/1 | Complete | 2026-01-22 |
| 9. Tier 2 Validators | M3 | 2/2 | Complete | 2026-01-22 |
| 10. Tier 3 Validators | M3 | 2/2 | Complete | 2026-01-22 |
| 11. Ralph Integration | M3 | 0/? | Not started | - |
| 12. Confidence Loop | M3 | 0/? | Not started | - |
| 13. ECC Full Integration | M4 | 0/? | Not started | - |
| 14. Hooks Node.js Port | M4 | 0/? | Not started | - |
| 15. Skills Port | M4 | 0/? | Not started | - |

#### Phase 12: Confidence-Based Loop Extension
**Goal**: Transform Tier 3 from passive monitors to active loop drivers with visual-driven development
**Depends on**: Phase 11
**Research**: Likely (visual comparison libraries, behavioral testing frameworks)
**Research topics**: Playwright visual comparison, image similarity algorithms, DOM diffing, golden file testing
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

**Scope:**
- VisualTargetValidator: Screenshot-driven development loop
- BehavioralValidator: Functional equivalence testing
- MultiModalValidator: Fused confidence scoring (visual + DOM + behavior + a11y + perf)
- ProgressiveRefinementLoop: Three-stage refinement (layout → style → polish)
- Ralph loop integration with dynamic termination conditions

---

### 🔮 Milestone 4: ECC Integration & Hooks Modernization (Proposed)

**Milestone Goal:** Port ECC best practices (Node.js hooks, skills, verification loop) and integrate with existing GSD/claude-flow infrastructure.

**Reference:** `/media/sam/1TB/everything-claude-code/`

#### Phase 13: ECC Full Integration
**Goal**: Integrate ECC architecture patterns with our GSD/claude-flow system
**Depends on**: Phase 11 (Ralph integration complete)
**Research**: Completed (ECC analysis done 2026-01-23)
**Effort estimate**: 30-40h

**Scope:**
- Unify ECC 6-phase verification loop with our 14-dimension orchestrator
- Sequential gates (ECC) + parallel tiers (ours) = hybrid workflow
- ECC agents integration (e2e-runner, security-reviewer, code-reviewer)
- Unified `/validate` skill that runs both systems

Plans:
- [ ] 13-01: Create hybrid validation workflow (ECC 6-phase → our 14-dim)
- [ ] 13-02: Port ECC agents (e2e-runner, security-reviewer) to our system
- [ ] 13-03: Create unified `/validate` skill

#### Phase 14: Hooks Node.js Port
**Goal**: Migrate critical hooks from Bash/Python to Node.js for cross-platform reliability
**Depends on**: Phase 13
**Research**: Completed (ECC utils.js analyzed)
**Effort estimate**: 40-50h

**Current state (claude-hooks-shared):**
- 50+ hooks in Python/Bash
- Silent failures, no error handling
- Platform-specific (Linux only)
- 13,952 LOC total

**Target state (ECC pattern):**
- Node.js with utils.js shared library
- try-catch everywhere, visible error messages
- Cross-platform (Linux/macOS/Windows)
- hooks.json declarative config

**Migration priority (by impact):**
1. **Critical** (port first):
   - `hooks/core/context_bundle_builder.py` → Node.js
   - `hooks/core/post-tool-use.py` → Node.js
   - `hooks/safety/smart-safety-check.py` → Node.js
   - `hooks/safety/git-safety-check.py` → Node.js

2. **High** (port second):
   - `hooks/productivity/architecture-validator.py` → Node.js
   - `hooks/productivity/readme-generator.py` → Node.js
   - `hooks/quality/ci-autofix.py` → Node.js

3. **Medium** (port if time):
   - `hooks/metrics/*` → Node.js
   - `hooks/intelligence/*` → Node.js

Plans:
- [ ] 14-01: Create utils.js shared library (port from ECC + our additions)
- [ ] 14-02: Port critical hooks (context_bundle, post-tool-use, safety checks)
- [ ] 14-03: Port high-priority hooks (architecture, readme, ci-autofix)
- [ ] 14-04: Create hooks.json declarative config
- [ ] 14-05: Test cross-platform (Linux + macOS CI)

**Deliverables:**
- `~/.claude/hooks/lib/utils.js` - shared utilities
- `~/.claude/hooks/hooks.json` - declarative config
- `~/.claude/hooks/*.js` - ported hooks
- GitHub Actions CI testing Linux + macOS

#### Phase 15: Skills Port
**Goal**: Port ECC skills we don't have (tdd-workflow, verification-loop, coding-standards)
**Depends on**: Phase 14
**Research**: Completed (ECC skills analyzed)
**Effort estimate**: 20-25h

**Gap analysis:**

| ECC Skill | LOC | Our equivalent | Action |
|-----------|-----|----------------|--------|
| tdd-workflow | 409 | tdd-guard (51 LOC, doc-only) | **PORT** |
| verification-loop | 120 | orchestrator (different) | **PORT** |
| coding-standards | 520 | - | **PORT** |
| eval-harness | 221 | - | **PORT** |
| security-review | 494 | security validator | MERGE |
| frontend-patterns | 631 | - | SKIP (domain-specific) |
| backend-patterns | 582 | - | SKIP (domain-specific) |
| continuous-learning | 80 | - | DEFER |
| strategic-compact | 63 | - | DEFER |

Plans:
- [ ] 15-01: Port tdd-workflow skill (enforced TDD, not just docs)
- [ ] 15-02: Port verification-loop skill (6-phase sequential)
- [ ] 15-03: Port coding-standards skill
- [ ] 15-04: Port eval-harness skill (pass@k metrics)
- [ ] 15-05: Integrate skills with GSD workflow triggers

**Integration points:**
- `/gsd:execute-plan` triggers tdd-workflow for `tdd=true` tasks
- `/gsd:execute-phase` triggers verification-loop at end
- Pre-commit hook triggers coding-standards check

---

## Milestone Summary

| Milestone | Phases | Status | Est. Effort |
|-----------|--------|--------|-------------|
| M1: Core Framework | 1-5 | ✅ Complete | - |
| M2: Hybrid UAT | 6 | ✅ Complete | - |
| M3: 14-Dim Orchestrator | 7-12 | 🚧 In progress | 60-90h remaining |
| M4: ECC Integration | 13-15 | 🔮 Proposed | 90-115h |

**Total remaining effort:** 150-205h
