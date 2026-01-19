#!/bin/bash
# Universal Validation Framework - Project Scaffold Script
# Usage: ./scaffold.sh /path/to/project [domain]
#
# Domains: trading, workflow, data, general (default)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="${1:?Usage: scaffold.sh /path/to/project [domain]}"
DOMAIN="${2:-general}"

# Validate domain
case "$DOMAIN" in
  trading|workflow|data|general) ;;
  *) echo "Error: Invalid domain '$DOMAIN'. Use: trading, workflow, data, general"; exit 1 ;;
esac

echo "Scaffolding validation pipeline for: $PROJECT_PATH"
echo "Domain: $DOMAIN"
echo ""

# Create directory structure
mkdir -p "$PROJECT_PATH/.claude/validation"
mkdir -p "$PROJECT_PATH/tests/smoke"

# Generate config.json with defaults based on domain
PROJECT_NAME="$(basename "$PROJECT_PATH")"

# Domain-specific defaults
case "$DOMAIN" in
  trading)
    IMPORTS='["strategies.common.risk", "strategies.common.recovery", "risk.circuit_breaker"]'
    CONFIGS='["config/canonical.yaml"]'
    SERVICES='[]'
    K8S_ENABLED='true'
    K8S_NS='"trading"'
    TRIGGERS='[
      {"metric": "error_rate", "threshold": 0.05, "operator": ">"},
      {"metric": "latency_p99_ms", "threshold": 100, "operator": ">"},
      {"metric": "var_pct", "threshold": 5, "operator": ">"},
      {"metric": "drawdown_pct", "threshold": 10, "operator": ">"}
    ]'
    ;;
  workflow)
    IMPORTS='["n8n_client", "workflow_engine"]'
    CONFIGS='["config/workflows.yaml"]'
    SERVICES='[]'
    K8S_ENABLED='false'
    K8S_NS='"workflows"'
    TRIGGERS='[
      {"metric": "execution_time_ms", "threshold": 30000, "operator": ">"},
      {"metric": "failure_rate", "threshold": 0.1, "operator": ">"}
    ]'
    ;;
  data)
    IMPORTS='["data_pipeline", "api_client"]'
    CONFIGS='["config/pipeline.yaml"]'
    SERVICES='[]'
    K8S_ENABLED='false'
    K8S_NS='"data"'
    TRIGGERS='[
      {"metric": "data_freshness_hours", "threshold": 24, "operator": ">"},
      {"metric": "api_latency_ms", "threshold": 500, "operator": ">"}
    ]'
    ;;
  general)
    IMPORTS='[]'
    CONFIGS='[]'
    SERVICES='[]'
    K8S_ENABLED='false'
    K8S_NS='"default"'
    TRIGGERS='[
      {"metric": "error_rate", "threshold": 0.05, "operator": ">"}
    ]'
    ;;
esac

cat > "$PROJECT_PATH/.claude/validation/config.json" << EOF
{
  "\$schema": "https://claude.ai/validation/config.schema.json",
  "project_name": "$PROJECT_NAME",
  "domain": "$DOMAIN",
  "smoke_tests": {
    "critical_imports": $IMPORTS,
    "config_files": $CONFIGS,
    "external_services": $SERVICES
  },
  "k8s": {
    "enabled": $K8S_ENABLED,
    "namespace": $K8S_NS,
    "rollout_strategy": "canary"
  },
  "rollback_triggers": $TRIGGERS,
  "ci": {
    "smoke_timeout_minutes": 5,
    "test_timeout_minutes": 10,
    "python_version": "3.12"
  }
}
EOF

echo "Created: .claude/validation/config.json"

# Copy smoke test templates
SMOKE_DIR="$SCRIPT_DIR/smoke"
if [[ -d "$SMOKE_DIR" ]]; then
  # Check if jinja2-cli is available
  if command -v jinja2 &>/dev/null; then
    echo "Rendering Jinja2 templates..."
    for tmpl in "$SMOKE_DIR"/*.j2; do
      [[ -f "$tmpl" ]] || continue
      output="$PROJECT_PATH/tests/smoke/$(basename "${tmpl%.j2}")"
      jinja2 "$tmpl" "$PROJECT_PATH/.claude/validation/config.json" > "$output"
      echo "Created: tests/smoke/$(basename "$output")"
    done
  else
    echo "Note: jinja2-cli not found. Copying raw templates."
    echo "Install with: pip install jinja2-cli"
    for tmpl in "$SMOKE_DIR"/*.j2; do
      [[ -f "$tmpl" ]] || continue
      cp "$tmpl" "$PROJECT_PATH/tests/smoke/"
      echo "Copied: tests/smoke/$(basename "$tmpl")"
    done
  fi
else
  echo "Warning: Smoke templates not found at $SMOKE_DIR"
fi

# Copy domain-specific extensions if exist
EXT_DIR="$SCRIPT_DIR/extensions/$DOMAIN"
if [[ -d "$EXT_DIR" ]] && [[ "$DOMAIN" != "general" ]]; then
  echo ""
  echo "Adding $DOMAIN domain extensions..."
  for tmpl in "$EXT_DIR"/*.j2; do
    [[ -f "$tmpl" ]] || continue
    if command -v jinja2 &>/dev/null; then
      output="$PROJECT_PATH/tests/smoke/$(basename "${tmpl%.j2}")"
      jinja2 "$tmpl" "$PROJECT_PATH/.claude/validation/config.json" > "$output"
      echo "Created: tests/smoke/$(basename "$output")"
    else
      cp "$tmpl" "$PROJECT_PATH/tests/smoke/"
      echo "Copied: tests/smoke/$(basename "$tmpl")"
    fi
  done
fi

# Create pytest marker configuration if not exists
if [[ ! -f "$PROJECT_PATH/pyproject.toml" ]]; then
  echo ""
  echo "Note: Add to pyproject.toml:"
  echo '  [tool.pytest.ini_options]'
  echo '  markers = ["smoke: quick validation tests"]'
else
  if ! grep -q 'markers.*=.*\[' "$PROJECT_PATH/pyproject.toml" 2>/dev/null; then
    echo ""
    echo "Note: Add pytest marker to pyproject.toml:"
    echo '  [tool.pytest.ini_options]'
    echo '  markers = ["smoke: quick validation tests"]'
  fi
fi

echo ""
echo "Done! Next steps:"
echo ""
echo "1. Edit .claude/validation/config.json to customize:"
echo "   - critical_imports: modules that must import"
echo "   - config_files: configs to validate"
echo "   - external_services: services to check (host:port)"
echo ""
echo "2. Run smoke tests:"
echo "   pytest tests/smoke -v -m smoke --timeout=120"
echo ""
echo "3. Add to CI (copy from ~/.claude/templates/validation/ci/):"
echo "   cp ~/.claude/templates/validation/ci/smoke-tests.yml.j2 .github/workflows/"
echo ""
