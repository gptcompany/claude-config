# Universal Validation Framework

## What This Is

A production-ready 14-dimension validation framework with tiered execution, confidence-based progressive refinement, and visual/behavioral validators for screenshot-driven development. Provides reusable CI/CD templates, smoke tests, and domain-specific extensions for all projects.

## Core Value

**Every project gets production-grade validation with zero friction** — scaffold once, validate everywhere, with confidence-based iterative refinement.

## Current State (v3.0 shipped 2026-01-24)

**Tech stack:** Python 3.12+, Jinja2, pytest, asyncio
**Location:** `~/.claude/templates/validation/`
**Size:** 68 Python files, 19,004 LOC, 367+ tests

**Key components:**
- ValidationOrchestrator (14-dimension tiered execution)
- Visual/Behavioral/MultiModal validators
- ProgressiveRefinementLoop (confidence-based)
- TerminalReporter + GrafanaReporter

## Requirements

### Validated

- ✓ Jinja2 templates for smoke tests (imports, config, connectivity) — v1.0
- ✓ Jinja2 templates for CI workflows (GitHub Actions) — v1.0
- ✓ Jinja2 templates for local K8s simulation (k3d + Argo Rollouts) — v1.0
- ✓ JSON Schema for project validation config — v1.0
- ✓ Scaffold script for one-command project initialization — v1.0
- ✓ Domain extension: trading (paper trading, risk limits, VaR triggers) — v1.0
- ✓ Domain extension: workflow (execution tests, node connections) — v1.0
- ✓ Domain extension: data (integrity tests, API endpoints) — v1.0
- ✓ Hybrid UAT workflow (auto-check + confidence + manual filter) — v2.0
- ✓ Accessibility validator (axe-core + Playwright) — v2.0
- ✓ Security validator (Trivy container + dependency) — v2.0
- ✓ Performance validator (Lighthouse CI + Core Web Vitals) — v2.0
- ✓ ValidationOrchestrator with 14-dimension tiered execution — v3.0
- ✓ Config Schema v2 with domain presets — v3.0
- ✓ DesignPrinciplesValidator (KISS/YAGNI/DRY with radon) — v3.0
- ✓ OSSReuseValidator (pattern detection, package suggestions) — v3.0
- ✓ MathematicalValidator (CAS microservice integration) — v3.0
- ✓ APIContractValidator (OpenAPI diff with oasdiff) — v3.0
- ✓ Ralph loop integration (PostToolUse hooks, backpressure) — v3.0
- ✓ Prometheus metrics + Sentry context integration — v3.0
- ✓ Visual validators (ODiff pixel + SSIM perceptual) — v3.0
- ✓ Behavioral validator (Zhang-Shasha DOM tree diff) — v3.0
- ✓ MultiModalValidator (weighted score fusion) — v3.0
- ✓ ProgressiveRefinementLoop (three-stage: LAYOUT→STYLE→POLISH) — v3.0
- ✓ TerminationEvaluator (threshold/stall/max termination) — v3.0
- ✓ TerminalReporter + GrafanaReporter (dual output) — v3.0

### Active (v4.0)

- [ ] ECC 6-phase verification loop integration
- [ ] Unified `/validate` skill
- [ ] Node.js hooks with utils.js shared library
- [ ] hooks.json declarative config
- [ ] Cross-platform hooks (Linux/macOS/Windows)
- [ ] TDD workflow skill (enforced, not just docs)
- [ ] Coding standards skill
- [ ] Eval harness skill (pass@k metrics)

### Out of Scope

- Cloud deployment automation (EKS, GKE) — handled by individual projects
- Production secrets management — already solved with SOPS/age
- Monitoring/alerting setup — Grafana MCP handles this
- Project-specific business logic — only generic templates
- Mobile app validation — web-first approach
- Offline mode — real-time metrics is core value

## Context

**Motivation**: nautilus_dev had broken nightly version detection, missing paper trading validation, and no smoke tests. Other projects (N8N_dev, UTXOracle, LiquidationHeatmap) had similar gaps. Instead of fixing each individually, created a universal framework.

**Target Projects:**
- nautilus_dev (trading domain) — first implementation
- N8N_dev (workflow domain)
- UTXOracle (data domain)
- LiquidationHeatmap (data domain)

**Existing Infrastructure:**
- SOPS/age for secrets (`/media/sam/1TB/.env.enc`)
- Grafana MCP for monitoring
- Linear MCP for issue tracking
- GitHub workflows already exist in most projects

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Jinja2 for templates | Standard, well-supported, already used | ✓ Good |
| JSON Schema for config | Validation + IDE autocomplete | ✓ Good |
| Domain extensions pattern | Separates generic from domain-specific | ✓ Good |
| k3d over minikube/kind | Lighter weight, faster startup | ✓ Good |
| Three-tier validation | Tier 1 blocks, Tier 2 warns, Tier 3 monitors | ✓ Good |
| 14 dimensions | Comprehensive coverage without overhead | ✓ Good |
| ODiff + SSIM fusion | Fast pixel + perceptual similarity | ✓ Good |
| Zhang-Shasha for DOM | Optimal O(n²) tree edit distance | ✓ Good |
| Three-stage refinement | LAYOUT→STYLE→POLISH progression | ✓ Good |
| Dual reporting | Terminal for humans, Grafana for dashboards | ✓ Good |
| Rich library optional | Graceful fallback to plain text | ✓ Good |

## Constraints

- **Tech Stack**: Python 3.12+, Jinja2, UV, GitHub Actions — consistent with existing projects
- **Location**: Templates in `~/.claude/templates/validation/` — accessible to all projects
- **Compatibility**: Must work with existing CI/CD pipelines without breaking changes
- **Simplicity**: No enterprise overhead — single scaffold script, minimal config

---
*Last updated: 2026-01-24 after v3.0 milestone*
