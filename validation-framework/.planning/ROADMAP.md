# Roadmap: Universal Validation Framework

## Overview

Build a reusable validation pipeline framework starting with core templates, then CI workflows, local K8s simulation, and domain-specific extensions. The framework ships in `~/.claude/templates/validation/` and is scaffolded to individual projects via a single command.

## Domain Expertise

- None (greenfield framework project)

## Milestones

- ✅ [**v1.0 Core Framework**](milestones/v1.0-ROADMAP.md) (Phases 1-5) — SHIPPED 2026-01-19
- ✅ [**v2.0 Hybrid UAT**](milestones/v2.0-ROADMAP.md) (Phase 6) — SHIPPED 2026-01-20
- ✅ [**v3.0 14-Dimension Orchestrator**](milestones/v3.0-ROADMAP.md) (Phases 7-12) — SHIPPED 2026-01-24
- ✅ [**v4.0 ECC Integration & Hooks Modernization**](milestones/v4.0-ROADMAP.md) (Phases 13-15) — SHIPPED 2026-01-25

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

<details>
<summary>✅ v4.0 ECC Integration & Hooks Modernization (Phases 13-15) - SHIPPED 2026-01-25</summary>

- [x] **Phase 13: ECC Full Integration** (3/3 plans) — Hybrid validation workflow, ECC agents, /validate skill
- [x] **Phase 14: Hooks Node.js Port** (5/5 plans) — Utils, session hooks, workflow hooks, hooks.json config
- [x] **Phase 14.5: claude-hooks-shared Port** (8/8 plans) — 40+ hooks, QuestDB metrics, debug system
- [x] **Phase 14.6: Hooks Integration & Validation** (4/4 plans) — 224 tests, 99.6% pass rate, documentation
- [x] **Phase 15: Skills Port** (5/5 plans) — tdd-guard, verification-loop, coding-standards, eval-harness, GSD triggers

**Delivered:**
- Node.js hooks system (40+ hooks) with declarative hooks.json config
- QuestDB dual-write (local JSON + async export) for metrics observability
- Debug system: hook-debugger, hook-tracer, hook-health CLI
- Skills: /verify:loop, /verify:quick, /standards:check, /eval:run, /eval:report
- 645+ tests (497 hooks + 148 skills), 99%+ pass rate

See [v4.0 Archive](milestones/v4.0-ROADMAP.md) for full details.

</details>

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1-5 | v1.0 | 7/7 | ✅ Complete | 2026-01-19 |
| 6 | v2.0 | 4/4 | ✅ Complete | 2026-01-20 |
| 7-12 | v3.0 | 14/14 | ✅ Complete | 2026-01-24 |
| 13. ECC Full Integration | v4.0 | 3/3 | ✅ Complete | 2026-01-24 |
| 14. Hooks Node.js Port (ECC) | v4.0 | 5/5 | ✅ Complete | 2026-01-24 |
| 14.5. claude-hooks-shared Port | v4.0 | 8/8 | ✅ Complete | 2026-01-24 |
| 14.6. Hooks Integration & Validation | v4.0 | 4/4 | ✅ Complete | 2026-01-24 |
| 15. Skills Port | v4.0 | 5/5 | ✅ Complete | 2026-01-25 |

**Total:** 50 plans shipped, v4.0 milestone complete

**Test Coverage Achieved:**
- Phase 14.5-14.6: 497 tests
- Phase 15 Skills: 148 tests (33 + 29 + 34 + 28 + 24)
- **Total:** 645+ tests
