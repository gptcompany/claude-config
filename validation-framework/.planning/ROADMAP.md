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
- ✅ [**v5.0 GSD + Validation + Claude-Flow Integration**](milestones/v5.0-ROADMAP.md) (Phase 16) — SHIPPED 2026-01-26
- 🚧 **v6.0 Full-Stack Validation Platform** (Phases 17-20) — IN PROGRESS

---

## v6.0: Full-Stack Validation Platform

**Goal:** Transform the framework from MVP to production-grade platform with full observability, deep validators, hardened runtime, and multi-project support.

### Phase 17: Observability & Dashboards (COMPLETE)

| Plan | Description | Tests | Status |
|------|-------------|-------|--------|
| 17-01 | Discord alerts via Grafana | 3 YAMLs | ✅ Complete |
| 17-02 | QuestDB query library + views | 26 | ✅ Complete |
| 17-03 | Grafana Dashboard Pack (3 dashboards) | JSON | ✅ Complete |
| 17-04 | CLI reporting tool | 29 | ✅ Complete |

**Deliverables:**
- Alert rules: `~/.claude/grafana/alerting/` (contact points, rules, policies)
- Dashboards: `/var/lib/grafana/dashboards/validation/` (overview, drilldown, comparison)
- Query lib: `~/.claude/scripts/lib/validation-queries.js` (5 functions, 26 tests)
- CLI: `~/.claude/scripts/bin/validation-report` (5 commands, 29 tests)

### Phase 18: Validator Depth

| Plan | Description | Tests | Status |
|------|-------------|-------|--------|
| 18-01 | Visual validator (ODiff + SSIM) | 15 | ⏳ Pending |
| 18-02 | Behavioral validator (DOM diff) | 12 | ⏳ Pending |
| 18-03 | Performance validator (Lighthouse) | 10 | ⏳ Pending |
| 18-04 | Mathematical validator (CAS) | 12 | ⏳ Pending |

### Phase 19: Production Hardening

| Plan | Description | Tests | Status |
|------|-------------|-------|--------|
| 19-01 | Live spawn_agent() + E2E tests | 10 | ⏳ Pending |
| 19-02 | Incremental validation (caching) | 12 | ⏳ Pending |
| 19-03 | Timeout/retry + circuit breaker | 8 | ⏳ Pending |
| 19-04 | Error recovery + graceful degradation | 10 | ⏳ Pending |

### Phase 20: Multi-Project Support

| Plan | Description | Tests | Status |
|------|-------------|-------|--------|
| 20-01 | Global config inheritance | 8 | ⏳ Pending |
| 20-02 | Monorepo per-package configs | 10 | ⏳ Pending |
| 20-03 | Shared validator plugins | 12 | ⏳ Pending |
| 20-04 | Cross-project metrics aggregation | 8 | ⏳ Pending |

**Total:** 4 phases, 16 plans, ~149 tests planned

### Execution Priority

```
Phase 17 (Observability) → Quick wins, immediate visibility
     ↓
Phase 19 (Hardening) → Stability before expanding
     ↓
Phase 18 (Validators) → Functional depth
     ↓
Phase 20 (Multi-Project) → Scalability
```

---

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

| 16. GSD-Validation Integration | v5.0 | 4/4 | ✅ Complete | 2026-01-26 |
| 17. Observability & Dashboards | v6.0 | 4/4 | ✅ Complete | 2026-01-26 |
| 18. Validator Depth | v6.0 | 0/4 | ⏳ Pending | - |
| 19. Production Hardening | v6.0 | 0/4 | ⏳ Pending | - |
| 20. Multi-Project Support | v6.0 | 0/4 | ⏳ Pending | - |

**Total:** 58 plans shipped (v1.0-v5.0 + Phase 17), 12 plans planned (v6.0 remaining)

**Test Coverage:**
- v1.0-v5.0: 521 tests
- Phase 17: 55 tests (26 query + 29 CLI)
- v6.0 remaining: ~94 tests
- **Target:** 670+ tests
