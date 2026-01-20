---
status: complete
phase: full-milestone
source: 02-01-SUMMARY.md, 03-01-SUMMARY.md, 03-02-SUMMARY.md, 04-01-SUMMARY.md, 05-01-SUMMARY.md, STATE.md
started: 2026-01-20T12:30:00Z
updated: 2026-01-20T12:35:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Config Schema Exists
expected: File exists at ~/.claude/templates/validation/config.schema.json with JSON Schema defining project_name, domain, ci, k8s, rollback_triggers
result: pass

### 2. Scaffold Script Runs
expected: ~/.claude/templates/validation/scaffold.sh exists and when run with a config.json, renders Jinja2 templates to target directory
result: pass

### 3. Smoke Test Templates Exist
expected: 4 Jinja2 templates in ~/.claude/templates/validation/smoke/ for base pytest smoke tests
result: pass

### 4. CI Smoke Tests Workflow
expected: smoke-tests.yml.j2 in ci/ renders to GitHub Actions workflow that runs pytest with smoke markers
result: pass

### 5. CI Integration Tests Workflow
expected: integration-tests.yml.j2 renders workflow with domain-specific services (Redis for trading, PostgreSQL for data)
result: pass

### 6. k3d Cluster Config Template
expected: k3d-config.yaml.j2 in k8s/ creates k3d cluster config with configurable workers, port mappings (80/443/9090), local registry
result: pass

### 7. Cluster Setup Script
expected: setup-local-cluster.sh.j2 creates k3d cluster and installs Argo Rollouts controller automatically
result: pass

### 8. Cluster Teardown Script
expected: teardown.sh.j2 provides idempotent cluster removal (safe to run multiple times)
result: pass

### 9. Mock Prometheus Deployment
expected: mock-prometheus.yaml.j2 deploys Prometheus with nginx sidecar serving static metrics from rollback_triggers config
result: pass

### 10. Canary Rollout Test Script
expected: test-rollout-local.sh.j2 validates 5% -> 25% -> 100% canary progression with Argo Rollouts
result: pass

### 11. Local K8s CI Workflow
expected: local-k8s-test.yml.j2 creates manual-trigger workflow for local K8s validation
result: pass

### 12. Trading Paper Trading Tests
expected: test_paper_trading.py.j2 in extensions/trading/ generates pytest tests for order submission, fills, positions
result: pass

### 13. Trading Risk Limits Tests
expected: test_risk_limits.py.j2 generates tests for position size, VaR, drawdown, circuit breaker
result: pass

### 14. Trading Analysis Templates
expected: analysis-templates.yaml.j2 generates Argo AnalysisTemplates for trading metrics (success-rate, latency, var, drawdown)
result: pass

### 15. Workflow Execution Tests
expected: test_workflow_execution.py.j2 in extensions/workflow/ generates tests for trigger, completion, timeout handling
result: pass

### 16. Workflow Node Connection Tests
expected: test_node_connections.py.j2 generates tests for node reachability, credentials, API versions
result: pass

### 17. Data Integrity Tests
expected: test_data_integrity.py.j2 in extensions/data/ generates tests for schema validation, type consistency
result: pass

### 18. Data API Endpoints Tests
expected: test_api_endpoints.py.j2 generates tests for health, auth, CRUD, error handling
result: pass

## Summary

total: 18
passed: 18
issues: 0
pending: 0
skipped: 0

## Issues for /gsd:plan-fix

[none]
