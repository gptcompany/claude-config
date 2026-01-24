# Roadmap: Universal Validation Framework

## Overview

Build a reusable validation pipeline framework starting with core templates, then CI workflows, local K8s simulation, and domain-specific extensions. The framework ships in `~/.claude/templates/validation/` and is scaffolded to individual projects via a single command.

## Domain Expertise

- None (greenfield framework project)

## Milestones

- ✅ [**v1.0 Core Framework**](milestones/v1.0-ROADMAP.md) (Phases 1-5) — SHIPPED 2026-01-19
- ✅ [**v2.0 Hybrid UAT**](milestones/v2.0-ROADMAP.md) (Phase 6) — SHIPPED 2026-01-20
- ✅ [**v3.0 14-Dimension Orchestrator**](milestones/v3.0-ROADMAP.md) (Phases 7-12) — SHIPPED 2026-01-24
- 🚧 **v4.0 ECC Integration & Hooks Modernization** (Phases 13-15) — In Progress

## Completed Milestones

<details>
<summary>✅ v1.0 & v2.0 (Phases 1-6) - SHIPPED 2026-01-20</summary>

- [x] **Phase 1: Core Framework** - Schema, scaffold script, base smoke tests
- [x] **Phase 2: CI Workflows** - GitHub Actions templates for smoke and integration
- [x] **Phase 3: Local K8s** - k3d cluster setup, Argo Rollouts, mock Prometheus
- [x] **Phase 4: Trading Extension** - Paper trading, risk limits, analysis templates
- [x] **Phase 5: Other Extensions** - Workflow and data domain templates
- [x] **Phase 6: Hybrid UAT & Validators** - Hybrid verify-work, accessibility, security, performance

</details>

<details>
<summary>✅ v3.0 Universal 14-Dimension Orchestrator (Phases 7-12) - SHIPPED 2026-01-24</summary>

- [x] **Phase 7: Orchestrator Core** - ValidationOrchestrator with tiered execution
- [x] **Phase 8: Config Schema v2** - Config generation CLI with domain presets
- [x] **Phase 9: Tier 2 Validators** - design_principles + oss_reuse validators
- [x] **Phase 10: Tier 3 Validators** - mathematical + api_contract validators
- [x] **Phase 11: Ralph Integration** - PostToolUse hooks, Prometheus, Sentry, Grafana
- [x] **Phase 12: Confidence Loop** - Visual/behavioral validators, score fusion, progressive refinement

**Delivered:**
- ValidationOrchestrator (1,093 LOC) with 14-dimension tiered execution
- VisualTargetValidator: ODiff + SSIM screenshot comparison
- BehavioralValidator: Zhang-Shasha DOM tree comparison
- MultiModalValidator: Weighted quasi-arithmetic mean fusion
- ProgressiveRefinementLoop: Three-stage refinement (LAYOUT → STYLE → POLISH)
- TerminationEvaluator: Dynamic termination (threshold, stall, max iterations)
- TerminalReporter + GrafanaReporter for dual output
- 367+ tests passing, 19,004 LOC total

</details>

---

## 🚧 v4.0 ECC Integration & Hooks Modernization (In Progress)

**Milestone Goal:** Port ECC best practices (Node.js hooks, skills, verification loop) and integrate with existing GSD/claude-flow infrastructure.

**Reference:** `/media/sam/1TB/everything-claude-code/`

### Phase 13: ECC Full Integration

**Goal**: Integrate ECC architecture patterns with our GSD/claude-flow system
**Depends on**: Phase 12 (confidence loop complete)
**Research**: Likely (new integration patterns)
**Research topics**: ECC architecture patterns, hybrid validation strategy
**Plans**: 3 plans

Plans:
- [x] 13-01: Create hybrid validation workflow (ECC 6-phase → our 14-dim)
- [x] 13-02: Port ECC agents (e2e-runner, security-reviewer) to our system
- [x] 13-03: Create unified `/validate` skill

### Phase 14: Hooks Node.js Port (ECC Base)

**Goal**: Port ECC base hooks and utils library to Node.js
**Depends on**: Phase 13
**Status**: ✅ Complete
**Plans**: 5 plans

Plans:
- [x] 14-01: Create utils.js and package-manager.js libraries from ECC
- [x] 14-02: Port ECC session hooks (session-start, session-end, pre-compact)
- [x] 14-03: Port ECC workflow hooks (suggest-compact, evaluate-session)
- [x] 14-04: Create hooks.json declarative config (14 bindings)
- [x] 14-05: Test suite (80 tests) + CI workflow

### Phase 14.5: claude-hooks-shared Port

**Goal**: Port our advanced hooks from claude-hooks-shared to Node.js
**Depends on**: Phase 14
**Research**: Complete (cross-check analysis done)
**Source**: `/media/sam/1TB/claude-hooks-shared/`
**Plans**: 7 plans

Plans:
- [ ] 14.5-01: Core libs (mcp-client, git-utils, metrics, tips-engine)
- [ ] 14.5-02: Safety hooks (git-safety, smart-safety, port-conflict, ci-batch)
- [ ] 14.5-03: Intelligence hooks (session-start-tracker, session-analyzer, meta-learning, lesson-injector)
- [ ] 14.5-04: Quality hooks (ci-autofix, plan-validator, pr-readiness, architecture-validator, readme-generator)
- [ ] 14.5-05: Productivity hooks (auto-format, tdd-guard, task-checkpoint, auto-simplify)
- [ ] 14.5-06: Metrics & Coordination (dora-tracker, quality-score, claudeflow-sync, file/task coordination)
- [ ] 14.5-07: UX & Control (tips-injector, ralph-loop, hive-manager, session-insights)

### Phase 15: Skills Port

**Goal**: Port ECC skills we don't have (tdd-workflow, verification-loop, coding-standards)
**Depends on**: Phase 14
**Research**: Unlikely (port existing code)
**Plans**: 5 plans

Plans:
- [ ] 15-01: Port tdd-workflow skill (enforced TDD, not just docs)
- [ ] 15-02: Port verification-loop skill (6-phase sequential)
- [ ] 15-03: Port coding-standards skill
- [ ] 15-04: Port eval-harness skill (pass@k metrics)
- [ ] 15-05: Integrate skills with GSD workflow triggers

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1-5 | v1.0 | 7/7 | ✅ Complete | 2026-01-19 |
| 6 | v2.0 | 4/4 | ✅ Complete | 2026-01-20 |
| 7-12 | v3.0 | 14/14 | ✅ Complete | 2026-01-24 |
| 13. ECC Full Integration | v4.0 | 3/3 | ✅ Complete | 2026-01-24 |
| 14. Hooks Node.js Port (ECC) | v4.0 | 5/5 | ✅ Complete | 2026-01-24 |
| 14.5. claude-hooks-shared Port | v4.0 | 0/7 | Not started | - |
| 15. Skills Port | v4.0 | 0/5 | Not started | - |

**Total:** 33 plans shipped, 12 remaining for v4.0
