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
- ✅ [**v6.0 Full-Stack Validation Platform**](milestones/v6.0-ROADMAP.md) (Phases 17-20) — SHIPPED 2026-01-26
- 🚧 **v7.0 OpenClaw Full Autonomy** - Phases 21-29 (in progress)

---

<details>
<summary>✅ v6.0 Full-Stack Validation Platform (Phases 17-20) — SHIPPED 2026-01-26</summary>

- [x] Phase 17: Observability & Dashboards (4/4 plans) — Discord alerts, Grafana dashboards, CLI
- [x] Phase 18: Validator Depth (1/1 plans) — Visual + Behavioral integration
- [x] Phase 19: Production Hardening (3/3 plans) — E2E tests, caching, resilience
- [x] Phase 20: Multi-Project Support (4/4 plans) — Config inheritance, monorepo, plugins

**Total:** 12 plans, 203 tests

</details>

---

### 🚧 v7.0 OpenClaw Full Autonomy (In Progress)

**Milestone Goal:** Configure OpenClaw al 100% delle capacità e abilitare loop di coding autonomo 24/7 con quality gates, cross-model review (Gemini), validation framework integrato, e monitoring.

#### Phase 21: Models & Providers
**Goal**: Multi-model setup — Gemini 2.5 Pro via OAuth (gratis 1000 req/day), OpenAI fallback, failover chain
**Depends on**: Previous milestone complete
**Research**: Likely (Gemini CLI headless OAuth, OpenClaw provider config, model failover docs)
**Research topics**: Gemini CLI token caching headless, OpenClaw models.providers config, failover chain syntax
**Plans**: TBD

Plans:
- [x] 21-01: Multi-model provider config (4 providers, fallback chain, LLM Task plugin)

#### Phase 22: Agent Config & System Prompts
**Goal**: System prompt per-agent con istruzioni TDD/quality, sandbox mode, thinking levels, sub-agent config
**Depends on**: Phase 21
**Research**: Likely (OpenClaw agent runtime docs, system prompt config, sandbox modes, sub-agents)
**Research topics**: agents.defaults.systemPrompt, sandbox scoped mode, thinking budget config
**Plans**: TBD

Plans:
- [ ] 22-01: TBD

#### Phase 23: Hooks & Webhooks
**Goal**: Hook custom pre/post exec per validation, webhooks GitHub→agent action, escalation su Matrix
**Depends on**: Phase 22
**Research**: Likely (OpenClaw hooks API, webhook config, SOUL hook, custom hook format)
**Research topics**: hooks.custom entries, webhook endpoint config, GitHub webhook→agent trigger
**Plans**: TBD

Plans:
- [ ] 23-01: TBD

#### Phase 24: Skills & LLM Task
**Goal**: Skill nativa TDD cycle, LLM Task tool per cross-model review, Lobster typed workflows
**Depends on**: Phase 23
**Research**: Likely (OpenClaw skills format, LLM Task tool config, Lobster runtime docs)
**Research topics**: skills gating config, llm_task provider routing, lobster workflow definition
**Plans**: TBD

Plans:
- [ ] 24-01: TBD

#### Phase 25: Gemini Cross-Review
**Goal**: Setup Gemini OAuth headless nel gateway Docker, receipt system, cross-model validation pipeline
**Depends on**: Phase 21 (provider config), Phase 24 (LLM Task)
**Research**: Likely (Gemini CLI headless auth in Docker, token persistence, NO_BROWSER flow)
**Research topics**: Gemini OAuth token caching path, Docker volume persistence, receipt JSON format
**Plans**: TBD

Plans:
- [ ] 25-01: TBD

#### Phase 26: Quality Gates Integration
**Goal**: Git hooks pre-commit/pre-push con validation framework, branch strategy feature→main, exec-approvals audit
**Depends on**: Phase 22 (agent config)
**Research**: Unlikely (nostro codice esistente, pattern stabiliti)
**Plans**: TBD

Plans:
- [ ] 26-01: TBD

#### Phase 27: Autonomous Loop (Piano C)
**Goal**: Spec-first workflow completo, state persistence su disco, iteration loop con max rounds, escalation policy, progressive-deploy integration come gate finale
**Depends on**: Phase 25 (cross-review), Phase 26 (quality gates)
**Research**: Unlikely (internal patterns, MEMORY.md design, progressive-deploy già esistente)
**Plans**: TBD

Plans:
- [ ] 27-01: TBD

#### Phase 28: Usage Tracking & Budget
**Goal**: Token tracking per-agent/per-task, cost monitoring, budget cap con hard stop, rate limiting
**Depends on**: Phase 21 (providers configurati)
**Research**: Likely (OpenClaw usage tracking docs, cost API, budget config)
**Research topics**: usage.tracking config, per-task token accounting, budget.maxTokensPerTask
**Plans**: TBD

Plans:
- [ ] 28-01: TBD

#### Phase 29: Monitoring & Dashboards
**Goal**: Grafana dashboard OpenClaw (task success rate, token usage, quality scores), alerting Discord/Matrix
**Depends on**: Phase 28 (usage tracking), Phase 27 (autonomous loop)
**Research**: Unlikely (infra Grafana esistente, pattern dashboard stabiliti)
**Plans**: TBD

Plans:
- [ ] 29-01: TBD

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
| 18. Validator Depth | v6.0 | 1/1 | ✅ Complete | 2026-01-26 |
| 19. Production Hardening | v6.0 | 3/3 | ✅ Complete | 2026-01-26 |
| 20. Multi-Project Support | v6.0 | 4/4 | ✅ Complete | 2026-01-26 |

| 21. Models & Providers | v7.0 | 1/1 | ✅ Complete | 2026-02-01 |
| 22. Agent Config & System Prompts | v7.0 | 0/? | Not started | - |
| 23. Hooks & Webhooks | v7.0 | 0/? | Not started | - |
| 24. Skills & LLM Task | v7.0 | 0/? | Not started | - |
| 25. Gemini Cross-Review | v7.0 | 0/? | Not started | - |
| 26. Quality Gates Integration | v7.0 | 0/? | Not started | - |
| 27. Autonomous Loop (Piano C) | v7.0 | 0/? | Not started | - |
| 28. Usage Tracking & Budget | v7.0 | 0/? | Not started | - |
| 29. Monitoring & Dashboards | v7.0 | 0/? | Not started | - |

**Total:** 66 plans shipped (v1.0-v6.0), 9 phases planned (v7.0)

**Test Coverage:**
- v1.0-v5.0: 521 tests
- v6.0: 203 tests (56 config + 20 monorepo + 19 plugins + 32 queries + 61 orchestrator + 15 E2E)
- **Total:** 724+ tests
