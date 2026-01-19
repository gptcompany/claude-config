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
| CI-01 | Phase 2 | Pending |
| CI-02 | Phase 2 | Pending |
| CI-03 | Phase 3 | Pending |
| K8S-01 | Phase 3 | Pending |
| K8S-02 | Phase 3 | Pending |
| K8S-03 | Phase 3 | Pending |
| K8S-04 | Phase 3 | Pending |
| K8S-05 | Phase 3 | Pending |
| EXT-TRADING-01 | Phase 4 | Pending |
| EXT-TRADING-02 | Phase 4 | Pending |
| EXT-TRADING-03 | Phase 4 | Pending |
| EXT-WORKFLOW-01 | Phase 5 | Pending |
| EXT-WORKFLOW-02 | Phase 5 | Pending |
| EXT-DATA-01 | Phase 5 | Pending |
| EXT-DATA-02 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓
