# Roadmap: Universal Validation Framework

## Overview

Build a reusable validation pipeline framework starting with core templates, then CI workflows, local K8s simulation, and domain-specific extensions. The framework ships in `~/.claude/templates/validation/` and is scaffolded to individual projects via a single command.

## Domain Expertise

- None (greenfield framework project)

## Milestones

- ✅ **Milestone 1** - Core Framework (Phases 1-5, shipped 2026-01-19)
- ✅ **Milestone 2** - Hybrid UAT & Validators (Phase 6, shipped 2026-01-20)
- 🚧 **Milestone 3** - Universal 14-Dimension Orchestrator (Phases 7-11, in progress)

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
- [ ] 07-01: TBD (run /gsd:plan-phase 7 to break down)

#### Phase 8: Config Schema v2
**Goal**: Extend config.schema.json with 14 dimensions, tier classification, and enabled flags
**Depends on**: Phase 7
**Research**: Unlikely (JSON Schema extension)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD

#### Phase 9: Tier 2 Validators
**Goal**: Create design_principles (KISS/YAGNI/DRY) and oss_reuse (package suggestions) validators
**Depends on**: Phase 8
**Research**: Likely (pypi/npm API, radon complexity metrics)
**Research topics**: radon for Python complexity, npm registry API, pypi JSON API
**Plans**: TBD

Plans:
- [ ] 09-01: TBD

#### Phase 10: Tier 3 Validators
**Goal**: Create mathematical (CAS microservice) and api_contract (OpenAPI diff) validators
**Depends on**: Phase 8
**Research**: Likely (CAS microservice protocol, openapi-diff libraries)
**Research topics**: localhost:8769/validate protocol, openapi-diff Python packages
**Plans**: TBD

Plans:
- [ ] 10-01: TBD

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
| 7. Orchestrator Core | M3 | 0/? | Not started | - |
| 8. Config Schema v2 | M3 | 0/? | Not started | - |
| 9. Tier 2 Validators | M3 | 0/? | Not started | - |
| 10. Tier 3 Validators | M3 | 0/? | Not started | - |
| 11. Ralph Integration | M3 | 0/? | Not started | - |
