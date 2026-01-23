#!/usr/bin/env python3
"""
Config Loader for Validation Framework v2

Provides:
- validate_config(): Validate config against schema, return clear errors
- load_config_with_defaults(): Load config with defaults applied
- merge_configs(): Merge project config with template defaults

Usage:
    from config_loader import load_config_with_defaults, validate_config

    # Validate first
    errors = validate_config(Path("config.json"))
    if errors:
        print("Config invalid:", errors)
        sys.exit(1)

    # Load with defaults
    config = load_config_with_defaults(Path("config.json"))
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema  # noqa: F401
    from jsonschema import Draft202012Validator, ValidationError  # noqa: F401

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    Draft202012Validator = None  # type: ignore
    ValidationError = None  # type: ignore


# =============================================================================
# Schema Location
# =============================================================================

SCHEMA_PATH = Path(__file__).parent / "config.schema.json"


# =============================================================================
# Default Dimension Configs
# =============================================================================

DEFAULT_DIMENSIONS = {
    # Tier 1 - Blockers
    "code_quality": {
        "enabled": True,
        "tier": 1,
        "max_complexity": 10,
        "max_lines_per_file": 500,
        "linter": "ruff",
    },
    "type_safety": {"enabled": True, "tier": 1, "checker": "pyright", "strict": False},
    "security": {
        "enabled": True,
        "tier": 1,
        "fail_on": ["HIGH", "CRITICAL"],
        "scanners": ["bandit", "gitleaks"],
    },
    "coverage": {
        "enabled": True,
        "tier": 1,
        "min_percent": 70,
        "fail_under": 70,
        "exclude_patterns": ["tests/*", "*_test.py", "conftest.py"],
    },
    # Tier 2 - Warnings
    "design_principles": {
        "enabled": True,
        "tier": 2,
        "agent": "code-simplifier",
        "max_function_lines": 50,
        "max_parameters": 5,
        "max_nesting_depth": 4,
    },
    "oss_reuse": {
        "enabled": False,
        "tier": 2,
        "min_lines_to_suggest": 20,
        "registries": ["pypi"],
    },
    "architecture": {
        "enabled": True,
        "tier": 2,
        "agent": "architecture-validator",
        "require_file": False,
    },
    "documentation": {
        "enabled": True,
        "tier": 2,
        "agent": "readme-generator",
        "required_sections": ["Installation", "Usage"],
    },
    # Tier 3 - Monitors
    "performance": {
        "enabled": True,
        "tier": 3,
        "budgets": {"lcp_ms": 2500, "fid_ms": 100, "cls": 0.1, "ttfb_ms": 800},
    },
    "accessibility": {
        "enabled": True,
        "tier": 3,
        "standard": "WCAG21AA",
        "fail_on": ["critical", "serious"],
    },
    "visual": {
        "enabled": False,
        "tier": 3,
        "threshold_percent": 1.0,
        "golden_dir": ".golden",
    },
    "mathematical": {
        "enabled": False,
        "tier": 3,
        "cas_endpoint": "http://localhost:8769/validate",
        "min_confidence": "HIGH",
    },
    "data_integrity": {"enabled": False, "tier": 3, "schemas_dir": "schemas/"},
    "api_contract": {
        "enabled": False,
        "tier": 3,
        "spec_path": "openapi.yaml",
        "fail_on_breaking": True,
    },
}

DEFAULT_CONFIG = {
    "smoke_tests": {
        "critical_imports": [],
        "config_files": [],
        "external_services": [],
    },
    "k8s": {"enabled": False, "namespace": "default", "rollout_strategy": "canary"},
    "rollback_triggers": [],
    "ci": {
        "smoke_timeout_minutes": 5,
        "test_timeout_minutes": 10,
        "python_version": "3.12",
    },
    "dimensions": DEFAULT_DIMENSIONS,
    "backpressure": {
        "max_iterations": 15,
        "max_budget_usd": 20.0,
        "tier1_max_failures": 3,
        "min_interval_seconds": 10,
    },
}


# =============================================================================
# Domain Presets
# =============================================================================

DOMAIN_PRESETS = {
    "trading": {
        "smoke_tests": {
            "critical_imports": [
                "strategies.common.risk",
                "strategies.common.recovery",
                "risk.circuit_breaker",
            ],
            "config_files": ["config/canonical.yaml"],
            "external_services": [],
        },
        "k8s": {"enabled": True, "namespace": "trading", "rollout_strategy": "canary"},
        "rollback_triggers": [
            {"metric": "error_rate", "threshold": 0.05, "operator": ">"},
            {"metric": "latency_p99_ms", "threshold": 100, "operator": ">"},
            {"metric": "var_pct", "threshold": 5, "operator": ">"},
            {"metric": "drawdown_pct", "threshold": 10, "operator": ">"},
        ],
        "dimensions": {
            "coverage": {"min_percent": 80, "fail_under": 80},
            "security": {"fail_on": ["MEDIUM", "HIGH", "CRITICAL"]},
        },
    },
    "workflow": {
        "smoke_tests": {
            "critical_imports": ["n8n_client", "workflow_engine"],
            "config_files": ["config/workflows.yaml"],
            "external_services": [],
        },
        "k8s": {
            "enabled": False,
            "namespace": "workflows",
            "rollout_strategy": "canary",
        },
        "rollback_triggers": [
            {"metric": "execution_time_ms", "threshold": 30000, "operator": ">"},
            {"metric": "failure_rate", "threshold": 0.1, "operator": ">"},
        ],
        "dimensions": {
            "coverage": {"min_percent": 60, "fail_under": 60},
            "performance": {
                "budgets": {"lcp_ms": 3000, "fid_ms": 150, "cls": 0.15, "ttfb_ms": 1000}
            },
        },
    },
    "data": {
        "smoke_tests": {
            "critical_imports": ["data_pipeline", "api_client"],
            "config_files": ["config/pipeline.yaml"],
            "external_services": [],
        },
        "k8s": {"enabled": False, "namespace": "data", "rollout_strategy": "canary"},
        "rollback_triggers": [
            {"metric": "data_freshness_hours", "threshold": 24, "operator": ">"},
            {"metric": "api_latency_ms", "threshold": 500, "operator": ">"},
        ],
        "dimensions": {
            "data_integrity": {"enabled": True},
            "api_contract": {"enabled": True},
        },
    },
    "general": {
        "smoke_tests": {
            "critical_imports": [],
            "config_files": [],
            "external_services": [],
        },
        "rollback_triggers": [
            {"metric": "error_rate", "threshold": 0.05, "operator": ">"}
        ],
    },
}


# =============================================================================
# Validation
# =============================================================================


def validate_config(config_path: Path) -> list[str]:
    """
    Validate config file against schema.

    Returns:
        List of error messages. Empty list = valid config.
    """
    errors = []

    # Check file exists
    if not config_path.exists():
        return [f"Config file not found: {config_path}"]

    # Check schema exists
    if not SCHEMA_PATH.exists():
        return [f"Schema file not found: {SCHEMA_PATH}"]

    # Load config
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in config: {e}"]

    # Load schema
    try:
        schema = json.loads(SCHEMA_PATH.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in schema: {e}"]

    # Validate with jsonschema if available
    if HAS_JSONSCHEMA and Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        for error in validator.iter_errors(config):
            path = " -> ".join(str(p) for p in error.absolute_path) or "root"
            errors.append(f"[{path}] {error.message}")
    else:
        # Basic validation without jsonschema
        if "project_name" not in config:
            errors.append("[root] 'project_name' is required")
        if "domain" not in config:
            errors.append("[root] 'domain' is required")
        elif config.get("domain") not in ["trading", "workflow", "data", "general"]:
            errors.append("[domain] must be one of: trading, workflow, data, general")

    return errors


def validate_config_dict(config: dict) -> list[str]:
    """
    Validate config dict against schema.

    Returns:
        List of error messages. Empty list = valid config.
    """
    errors = []

    # Check schema exists
    if not SCHEMA_PATH.exists():
        return [f"Schema file not found: {SCHEMA_PATH}"]

    # Load schema
    try:
        schema = json.loads(SCHEMA_PATH.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in schema: {e}"]

    # Validate with jsonschema if available
    if HAS_JSONSCHEMA and Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        for error in validator.iter_errors(config):
            path = " -> ".join(str(p) for p in error.absolute_path) or "root"
            errors.append(f"[{path}] {error.message}")
    else:
        # Basic validation without jsonschema
        if "project_name" not in config:
            errors.append("[root] 'project_name' is required")
        if "domain" not in config:
            errors.append("[root] 'domain' is required")
        elif config.get("domain") not in ["trading", "workflow", "data", "general"]:
            errors.append("[domain] must be one of: trading, workflow, data, general")

    return errors


# =============================================================================
# Merge Logic
# =============================================================================


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge override into base.

    - Dicts are recursively merged
    - Lists and scalars from override replace base
    - Keys in override take precedence
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def merge_configs(project_config: dict) -> dict:
    """
    Merge project config with defaults.

    - Starts with DEFAULT_CONFIG
    - Deep merges project_config on top
    - For dimensions: each dimension gets its defaults, then project overrides
    """
    # Start with defaults
    result = deep_merge({}, DEFAULT_CONFIG)

    # Merge project config
    result = deep_merge(result, project_config)

    # Special handling for dimensions: ensure all dimensions have defaults
    if "dimensions" in result:
        merged_dims = {}
        for dim_name, default_dim in DEFAULT_DIMENSIONS.items():
            if dim_name in result["dimensions"]:
                merged_dims[dim_name] = deep_merge(
                    default_dim, result["dimensions"][dim_name]
                )
            else:
                merged_dims[dim_name] = default_dim.copy()
        result["dimensions"] = merged_dims

    return result


# =============================================================================
# Loading
# =============================================================================


def load_config_with_defaults(config_path: Path) -> dict:
    """
    Load and validate config, applying defaults.

    Raises:
        ValueError: If config is invalid
        FileNotFoundError: If config file doesn't exist
    """
    # Validate first
    errors = validate_config(config_path)
    if errors:
        raise ValueError("Invalid config:\n" + "\n".join(f"  - {e}" for e in errors))

    # Load and merge
    config = json.loads(config_path.read_text())
    return merge_configs(config)


def find_validation_config(start_dir: Path | None = None) -> Path | None:
    """
    Find validation config by searching upward from start_dir.

    Searches for:
    - .claude/validation/config.json
    - .claude/config.json
    - validation/config.json
    """
    if start_dir is None:
        start_dir = Path.cwd()

    search_paths = [
        ".claude/validation/config.json",
        ".claude/config.json",
        "validation/config.json",
    ]

    current = start_dir.resolve()

    while current != current.parent:
        for rel_path in search_paths:
            candidate = current / rel_path
            if candidate.exists():
                return candidate
        current = current.parent

    return None


# =============================================================================
# Config Generation
# =============================================================================


def generate_config(project_name: str, domain: str = "general") -> dict:
    """
    Generate a full config with all 14 dimensions and domain-specific overrides.

    Args:
        project_name: Name of the project
        domain: One of 'trading', 'workflow', 'data', 'general'

    Returns:
        Complete config dict with $schema reference and all dimensions
    """
    if domain not in DOMAIN_PRESETS:
        raise ValueError(
            f"Unknown domain: {domain}. Use: {list(DOMAIN_PRESETS.keys())}"
        )

    # Start with defaults
    config = deep_merge({}, DEFAULT_CONFIG)

    # Apply domain preset
    domain_preset = DOMAIN_PRESETS[domain]
    config = deep_merge(config, domain_preset)

    # Set project metadata
    config["$schema"] = "https://claude.ai/validation/config.schema.json"
    config["project_name"] = project_name
    config["domain"] = domain

    # Ensure all 14 dimensions are present with full defaults merged
    merged_dims = {}
    for dim_name, default_dim in DEFAULT_DIMENSIONS.items():
        if "dimensions" in config and dim_name in config["dimensions"]:
            merged_dims[dim_name] = deep_merge(
                default_dim, config["dimensions"][dim_name]
            )
        else:
            merged_dims[dim_name] = default_dim.copy()
    config["dimensions"] = merged_dims

    return config


# =============================================================================
# CLI
# =============================================================================


def main():
    """CLI for config validation and inspection."""
    import argparse

    parser = argparse.ArgumentParser(description="Validation config loader")
    parser.add_argument("config", nargs="?", help="Path to config file")
    parser.add_argument("--validate", action="store_true", help="Validate config")
    parser.add_argument(
        "--show-defaults", action="store_true", help="Show default config"
    )
    parser.add_argument(
        "--show-merged", action="store_true", help="Show config with defaults applied"
    )
    parser.add_argument(
        "--find", action="store_true", help="Find config in current directory tree"
    )
    # New generation flags
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate new config with all dimensions",
    )
    parser.add_argument(
        "--domain",
        choices=["trading", "workflow", "data", "general"],
        default="general",
        help="Domain preset (default: general)",
    )
    parser.add_argument(
        "--project-name",
        dest="project_name",
        help="Project name (required with --generate)",
    )
    parser.add_argument("--output", "-o", help="Write to file instead of stdout")

    args = parser.parse_args()

    # Handle --generate
    if args.generate:
        if not args.project_name:
            print("Error: --project-name is required with --generate", file=sys.stderr)
            sys.exit(1)
        try:
            config = generate_config(args.project_name, args.domain)
            output = json.dumps(config, indent=2)
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(output)
                print(f"Generated: {args.output}")
            else:
                print(output)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.show_defaults:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return

    if args.find:
        config_path = find_validation_config()
        if config_path:
            print(f"Found: {config_path}")
        else:
            print("No validation config found")
            sys.exit(1)
        return

    if not args.config:
        parser.print_help()
        sys.exit(1)

    config_path = Path(args.config)

    if args.validate:
        errors = validate_config(config_path)
        if errors:
            print("Validation FAILED:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print("Validation OK")
        return

    if args.show_merged:
        try:
            config = load_config_with_defaults(config_path)
            print(json.dumps(config, indent=2))
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Default: validate
    errors = validate_config(config_path)
    if errors:
        print("Validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("Validation OK")


if __name__ == "__main__":
    main()
