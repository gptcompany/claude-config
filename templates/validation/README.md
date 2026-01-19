# Universal Validation Framework

Production-grade validation pipeline templates for all projects.

## Quick Start

```bash
# Scaffold validation for your project
~/.claude/templates/validation/scaffold.sh /path/to/your/project [domain]

# Domains: trading, workflow, data, general (default)
```

## What It Creates

```
your-project/
├── .claude/validation/
│   └── config.json          # Validation configuration
└── tests/smoke/
    ├── conftest.py          # Shared fixtures
    ├── test_imports.py      # Critical import tests
    ├── test_config.py       # Config validation tests
    └── test_connectivity.py # Service connectivity tests
```

## Configuration

Edit `.claude/validation/config.json`:

```json
{
  "project_name": "my_project",
  "domain": "trading",
  "smoke_tests": {
    "critical_imports": [
      "strategies.common.risk",
      "risk.circuit_breaker"
    ],
    "config_files": [
      "config/canonical.yaml"
    ],
    "external_services": [
      "prometheus:9090",
      "redis:6379"
    ]
  },
  "k8s": {
    "enabled": true,
    "namespace": "trading",
    "rollout_strategy": "canary"
  },
  "rollback_triggers": [
    {"metric": "error_rate", "threshold": 0.05, "operator": ">"},
    {"metric": "var_pct", "threshold": 5, "operator": ">"}
  ]
}
```

### Config Fields

| Field | Description |
|-------|-------------|
| `project_name` | Used in generated test code |
| `domain` | `trading`, `workflow`, `data`, or `general` |
| `smoke_tests.critical_imports` | Python modules that must import successfully |
| `smoke_tests.config_files` | Config files to validate (YAML, JSON, TOML) |
| `smoke_tests.external_services` | Services to check (`host:port` format) |
| `k8s.enabled` | Generate K8s templates |
| `k8s.namespace` | Kubernetes namespace |
| `k8s.rollout_strategy` | `canary`, `blue-green`, or `rolling` |
| `rollback_triggers` | Metrics that trigger auto-rollback |

## Domain Extensions

### Trading (`domain: "trading"`)

Extra templates:
- `test_paper_trading.py` — Paper execution tests
- `test_risk_limits.py` — Risk enforcement tests
- `analysis-templates.yaml` — Argo Rollouts VaR/drawdown triggers

Default rollback triggers: error_rate, latency, VaR, drawdown

### Workflow (`domain: "workflow"`)

Extra templates:
- `test_workflow_execution.py` — Workflow execution tests
- `test_node_connections.py` — Node connectivity tests

Default rollback triggers: execution_time, failure_rate

### Data (`domain: "data"`)

Extra templates:
- `test_data_integrity.py` — Data integrity tests
- `test_api_endpoints.py` — API endpoint tests

Default rollback triggers: data_freshness, api_latency

## Running Tests

```bash
# Run smoke tests only (< 2 min)
pytest tests/smoke -v -m smoke --timeout=120

# With coverage
pytest tests/smoke -v -m smoke --cov=src --cov-report=term
```

## CI Integration

Copy workflow template to your project:

```bash
# Smoke tests workflow
cp ~/.claude/templates/validation/ci/smoke-tests.yml.j2 .github/workflows/
jinja2 .github/workflows/smoke-tests.yml.j2 .claude/validation/config.json \
  > .github/workflows/smoke-tests.yml
```

Or use directly with rendering disabled:

```yaml
# .github/workflows/smoke-tests.yml
name: Smoke Tests

on:
  push:
    branches: [main, develop]

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install uv && uv sync --frozen
      - run: uv run pytest tests/smoke -v -m smoke --timeout=120
```

## Local K8s Testing

For projects with `k8s.enabled: true`:

```bash
# Setup local cluster
~/.claude/templates/validation/k8s/setup-local-cluster.sh.j2

# Test canary rollout
~/.claude/templates/validation/k8s/test-rollout-local.sh.j2

# Cleanup
~/.claude/templates/validation/k8s/teardown.sh.j2
```

## Template Structure

```
~/.claude/templates/validation/
├── README.md                    # This file
├── config.schema.json           # JSON Schema for config validation
├── scaffold.sh                  # Project initialization script
│
├── smoke/                       # Smoke test templates
│   ├── conftest.py.j2
│   ├── test_imports.py.j2
│   ├── test_config.py.j2
│   └── test_connectivity.py.j2
│
├── ci/                          # CI workflow templates
│   ├── smoke-tests.yml.j2
│   ├── integration-tests.yml.j2
│   └── local-k8s-test.yml.j2
│
├── k8s/                         # Local K8s templates
│   ├── k3d-config.yaml.j2
│   ├── setup-local-cluster.sh.j2
│   ├── test-rollout-local.sh.j2
│   ├── teardown.sh.j2
│   └── mock-prometheus.yaml.j2
│
└── extensions/                  # Domain-specific
    ├── trading/
    ├── workflow/
    └── data/
```

## Jinja2 Template Variables

All templates receive the full config.json as context:

```jinja2
{# In any template #}
{{ project_name }}
{{ domain }}
{{ smoke_tests.critical_imports }}
{% for import in smoke_tests.critical_imports %}
import {{ import }}
{% endfor %}
```

Install jinja2-cli for rendering:

```bash
pip install jinja2-cli

# Render a template
jinja2 template.py.j2 config.json > output.py
```

## Requirements

- Python 3.12+
- pytest
- jinja2-cli (optional, for template rendering)
- k3d (optional, for local K8s)
- kubectl + argo rollouts plugin (optional, for K8s)
