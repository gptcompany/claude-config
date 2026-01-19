# Universal Validation Framework

## What This Is

A reusable validation pipeline framework that provides production-ready CI/CD templates, smoke tests, paper trading validation, and local Kubernetes simulation for all projects. It includes domain-specific extensions (trading, workflow, data) and a scaffold script for one-command project initialization.

## Core Value

**Every project gets production-grade validation with zero friction** — scaffold once, validate everywhere.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Jinja2 templates for smoke tests (imports, config, connectivity)
- [ ] Jinja2 templates for CI workflows (GitHub Actions)
- [ ] Jinja2 templates for local K8s simulation (k3d + Argo Rollouts)
- [ ] JSON Schema for project validation config
- [ ] Scaffold script for one-command project initialization
- [ ] Domain extension: trading (paper trading, risk limits, VaR triggers)
- [ ] Domain extension: workflow (execution tests, node connections)
- [ ] Domain extension: data (integrity tests, API endpoints)
- [ ] README documentation for usage guide

### Out of Scope

- Cloud deployment automation (EKS, GKE) — handled by individual projects
- Production secrets management — already solved with SOPS/age
- Monitoring/alerting setup — Grafana MCP handles this
- Project-specific business logic — only generic templates

## Context

**Motivation**: nautilus_dev has a broken nightly version detection (1.223 not notified), missing paper trading validation, and no smoke tests. Other projects (N8N_dev, UTXOracle, LiquidationHeatmap) have similar gaps. Instead of fixing each individually, create a universal framework.

**Technical Environment**:
- UV for Python dependency management
- GitHub Actions for CI/CD
- k3d for local Kubernetes simulation
- Argo Rollouts for canary deployments
- Prometheus metrics for auto-rollback triggers
- Jinja2 for template rendering

**Target Projects**:
- nautilus_dev (trading domain) — first implementation
- N8N_dev (workflow domain)
- UTXOracle (data domain)
- LiquidationHeatmap (data domain)

**Existing Infrastructure**:
- SOPS/age for secrets (`/media/sam/1TB/.env.enc`)
- Grafana MCP for monitoring
- Linear MCP for issue tracking
- GitHub workflows already exist in most projects

## Constraints

- **Tech Stack**: Python 3.12+, Jinja2, UV, GitHub Actions — consistent with existing projects
- **Location**: Templates in `~/.claude/templates/validation/` — accessible to all projects
- **Compatibility**: Must work with existing CI/CD pipelines without breaking changes
- **Simplicity**: No enterprise overhead — single scaffold script, minimal config

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Jinja2 for templates | Standard, well-supported, already used | — Pending |
| JSON Schema for config | Validation + IDE autocomplete | — Pending |
| Domain extensions pattern | Separates generic from domain-specific | — Pending |
| k3d over minikube/kind | Lighter weight, faster startup | — Pending |

---
*Last updated: 2026-01-19 after initialization*
