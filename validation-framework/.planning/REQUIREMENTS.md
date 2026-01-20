# Requirements: Universal Validation Framework

## Overview

Production-ready validation pipeline framework with domain-specific extensions.

## v1 Requirements

### CORE: Core Framework

| ID | Requirement | Priority |
|----|-------------|----------|
| CORE-01 | JSON Schema for validation config (`config.schema.json`) | P0 |
| CORE-02 | Scaffold script (`scaffold.sh`) for project initialization | P0 |
| CORE-03 | README.md with usage documentation | P0 |

### SMOKE: Smoke Test Templates

| ID | Requirement | Priority |
|----|-------------|----------|
| SMOKE-01 | `test_imports.py.j2` — Critical imports validation | P0 |
| SMOKE-02 | `test_config.py.j2` — Config file validation | P0 |
| SMOKE-03 | `test_connectivity.py.j2` — External service connectivity | P0 |
| SMOKE-04 | `conftest.py.j2` — Shared pytest fixtures | P0 |

### CI: CI/CD Workflow Templates

| ID | Requirement | Priority |
|----|-------------|----------|
| CI-01 | `smoke-tests.yml.j2` — GitHub Actions smoke stage | P0 |
| CI-02 | `integration-tests.yml.j2` — Integration test stage | P1 |
| CI-03 | `local-k8s-test.yml.j2` — Local K8s validation (manual trigger) | P1 |

### K8S: Local Kubernetes Templates

| ID | Requirement | Priority |
|----|-------------|----------|
| K8S-01 | `k3d-config.yaml.j2` — Cluster configuration | P1 |
| K8S-02 | `setup-local-cluster.sh.j2` — Cluster setup script | P1 |
| K8S-03 | `test-rollout-local.sh.j2` — Canary test script | P1 |
| K8S-04 | `teardown.sh.j2` — Cleanup script | P1 |
| K8S-05 | `mock-prometheus.yaml.j2` — Mock metrics for analysis | P1 |

### EXT-TRADING: Trading Domain Extension

| ID | Requirement | Priority |
|----|-------------|----------|
| EXT-TRADING-01 | `test_paper_trading.py.j2` — Paper trading execution tests | P1 |
| EXT-TRADING-02 | `test_risk_limits.py.j2` — Risk enforcement tests | P1 |
| EXT-TRADING-03 | `analysis-templates.yaml.j2` — Argo Rollouts analysis (VaR, drawdown) | P1 |

### EXT-WORKFLOW: Workflow Domain Extension

| ID | Requirement | Priority |
|----|-------------|----------|
| EXT-WORKFLOW-01 | `test_workflow_execution.py.j2` — Workflow execution tests | P2 |
| EXT-WORKFLOW-02 | `test_node_connections.py.j2` — Node connectivity tests | P2 |

### EXT-DATA: Data Domain Extension

| ID | Requirement | Priority |
|----|-------------|----------|
| EXT-DATA-01 | `test_data_integrity.py.j2` — Data integrity validation | P2 |
| EXT-DATA-02 | `test_api_endpoints.py.j2` — API endpoint tests | P2 |

### HYBRID: Hybrid UAT Framework

| ID | Requirement | Priority |
|----|-------------|----------|
| HYBRID-01 | Hybrid verify-work workflow with auto-check + confidence scoring + human filter | P1 |
| HYBRID-02 | Multi-mode dashboard (live monitor, review station, report viewer) | P1 |
| HYBRID-03 | Four-round UAT workflow (Auto → Human-All → Fix → Edge+Regression) | P1 |

### A11Y: Accessibility Validation

| ID | Requirement | Priority |
|----|-------------|----------|
| A11Y-01 | `accessibility.yml.j2` — GitHub Actions workflow for axe-core + Playwright | P1 |
| A11Y-02 | `axe.config.js.j2` — axe-core configuration template | P1 |
| A11Y-03 | `test_a11y.spec.ts.j2` — Playwright accessibility test template | P1 |

### SEC: Security Scanning

| ID | Requirement | Priority |
|----|-------------|----------|
| SEC-01 | `security.yml.j2` — GitHub Actions workflow for Trivy scanning | P1 |
| SEC-02 | `trivy.yaml.j2` — Trivy configuration template | P1 |
| SEC-03 | `.trivyignore.j2` — Known issues exclusion template | P1 |

### PERF: Performance Validation

| ID | Requirement | Priority |
|----|-------------|----------|
| PERF-01 | `performance.yml.j2` — GitHub Actions workflow for Lighthouse CI | P1 |
| PERF-02 | `lighthouserc.js.j2` — Lighthouse CI configuration template | P1 |
| PERF-03 | `budgets.json.j2` — Performance budgets template | P1 |

## v2 Requirements (Future)

| ID | Requirement | Notes |
|----|-------------|-------|
| V2-01 | Cloud deployment templates (EKS, GKE) | After v1 validates locally |
| V2-02 | Multi-repo orchestration | Coordinate validation across repos |
| V2-03 | Validation dashboard | Grafana dashboard for all projects |

## Acceptance Criteria

### CORE-01: JSON Schema
- [ ] Schema validates all required fields
- [ ] Schema provides enum for domain types
- [ ] IDE autocomplete works with schema

### CORE-02: Scaffold Script
- [ ] `scaffold.sh /path/to/project [domain]` creates complete structure
- [ ] Supports all domain types: trading, workflow, data, general
- [ ] Generates valid config.json with defaults
- [ ] Renders Jinja2 templates if jinja2-cli available
- [ ] Fallback to raw template copy if jinja2 unavailable

### SMOKE-01 through SMOKE-04: Smoke Tests
- [ ] Generated tests pass ruff lint
- [ ] Generated tests pass mypy type check
- [ ] Tests complete in < 2 minutes
- [ ] Tests correctly import from config.json critical_imports

### CI-01: Smoke Tests Workflow
- [ ] Valid GitHub Actions YAML
- [ ] Runs on push to main/develop
- [ ] Uses UV for dependency management
- [ ] Uploads test results as artifact

### K8S-01 through K8S-05: Local K8s
- [ ] k3d cluster starts in < 2 minutes
- [ ] Argo Rollouts installs correctly
- [ ] Mock Prometheus serves metrics
- [ ] Canary rollout 5%→25%→100% completes
- [ ] Auto-rollback triggers on metric failure

### EXT-TRADING-01 through EXT-TRADING-03: Trading
- [ ] Paper trading tests validate order execution
- [ ] Risk limit tests enforce configured thresholds
- [ ] Analysis templates query Prometheus correctly

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| SMOKE-01 | Phase 1 | Complete |
| SMOKE-02 | Phase 1 | Complete |
| SMOKE-03 | Phase 1 | Complete |
| SMOKE-04 | Phase 1 | Complete |
| CI-01 | Phase 2 | Complete |
| CI-02 | Phase 2 | Complete |
| CI-03 | Phase 3 | Complete |
| K8S-01 | Phase 3 | Complete |
| K8S-02 | Phase 3 | Complete |
| K8S-03 | Phase 3 | Complete |
| K8S-04 | Phase 3 | Complete |
| K8S-05 | Phase 3 | Complete |
| EXT-TRADING-01 | Phase 4 | Complete |
| EXT-TRADING-02 | Phase 4 | Complete |
| EXT-TRADING-03 | Phase 4 | Complete |
| EXT-WORKFLOW-01 | Phase 5 | Complete |
| EXT-WORKFLOW-02 | Phase 5 | Complete |
| EXT-DATA-01 | Phase 5 | Complete |
| EXT-DATA-02 | Phase 5 | Complete |
| HYBRID-01 | Phase 6 | Pending |
| HYBRID-02 | Phase 6 | Pending |
| HYBRID-03 | Phase 6 | Pending |
| A11Y-01 | Phase 6 | Pending |
| A11Y-02 | Phase 6 | Pending |
| A11Y-03 | Phase 6 | Pending |
| SEC-01 | Phase 6 | Pending |
| SEC-02 | Phase 6 | Pending |
| SEC-03 | Phase 6 | Pending |
| PERF-01 | Phase 6 | Pending |
| PERF-02 | Phase 6 | Pending |
| PERF-03 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓
