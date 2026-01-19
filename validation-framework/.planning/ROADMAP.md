# Roadmap: Universal Validation Framework

## Overview

Build a reusable validation pipeline framework starting with core templates, then CI workflows, local K8s simulation, and domain-specific extensions. The framework ships in `~/.claude/templates/validation/` and is scaffolded to individual projects via a single command.

## Domain Expertise

- None (greenfield framework project)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Core Framework** - Schema, scaffold script, base smoke tests
- [ ] **Phase 2: CI Workflows** - GitHub Actions templates for smoke and integration
- [ ] **Phase 3: Local K8s** - k3d cluster setup, Argo Rollouts, mock Prometheus
- [ ] **Phase 4: Trading Extension** - Paper trading, risk limits, analysis templates
- [ ] **Phase 5: Other Extensions** - Workflow and data domain templates

## Phase Details

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
- [ ] 02-01: Create CI workflow templates

### Phase 3: Local K8s
**Goal**: Create k3d cluster and Argo Rollouts templates
**Depends on**: Phase 2
**Requirements**: CI-03, K8S-01, K8S-02, K8S-03, K8S-04, K8S-05
**Research**: Likely (k3d configuration, Argo Rollouts analysis)
**Research topics**: k3d cluster config options, Argo Rollouts AnalysisTemplate syntax, mock Prometheus setup
**Plans**: 2 plans

Plans:
- [ ] 03-01: Create k3d cluster templates
- [ ] 03-02: Create Argo Rollouts and mock Prometheus templates

### Phase 4: Trading Extension
**Goal**: Create trading-specific validation templates
**Depends on**: Phase 1 (uses base smoke templates)
**Requirements**: EXT-TRADING-01, EXT-TRADING-02, EXT-TRADING-03
**Research**: Unlikely (patterns from nautilus_dev k8s/rollouts/)
**Plans**: 1 plan

Plans:
- [ ] 04-01: Create trading domain templates

### Phase 5: Other Extensions
**Goal**: Create workflow and data domain templates
**Depends on**: Phase 1 (uses base smoke templates)
**Requirements**: EXT-WORKFLOW-01, EXT-WORKFLOW-02, EXT-DATA-01, EXT-DATA-02
**Research**: Unlikely (similar patterns to trading)
**Plans**: 1 plan

Plans:
- [ ] 05-01: Create workflow and data domain templates

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Framework | 2/2 | Complete | 2026-01-19 |
| 2. CI Workflows | 0/1 | Not started | - |
| 3. Local K8s | 0/2 | Not started | - |
| 4. Trading Extension | 0/1 | Not started | - |
| 5. Other Extensions | 0/1 | Not started | - |
