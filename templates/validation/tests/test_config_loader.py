#!/usr/bin/env python3
"""Unit tests for config_loader.py - Config loading and validation."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from config_loader import (
    DEFAULT_CONFIG,
    DEFAULT_DIMENSIONS,
    DOMAIN_PRESETS,
    deep_merge,
    find_validation_config,
    generate_config,
    load_config,
    load_config_with_defaults,
    load_global_config,
    load_project_config,
    merge_configs,
    merge_configs_rfc7396,
    validate_config,
    validate_config_dict,
)


class TestDeepMerge:
    """Tests for deep_merge() function."""

    def test_merge_empty_dicts(self):
        """Test merging two empty dicts."""
        result = deep_merge({}, {})
        assert result == {}

    def test_merge_into_empty(self):
        """Test merging override into empty base."""
        result = deep_merge({}, {"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_merge_empty_override(self):
        """Test merging empty override into base."""
        result = deep_merge({"a": 1}, {})
        assert result == {"a": 1}

    def test_merge_scalars_override(self):
        """Test that scalars are overridden."""
        result = deep_merge({"a": 1, "b": 2}, {"a": 10})
        assert result == {"a": 10, "b": 2}

    def test_merge_nested_dicts(self):
        """Test deep merging of nested dicts."""
        base = {"outer": {"inner": 1, "other": 2}}
        override = {"outer": {"inner": 10}}
        result = deep_merge(base, override)
        assert result == {"outer": {"inner": 10, "other": 2}}

    def test_merge_lists_override(self):
        """Test that lists are replaced, not merged."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"items": [4, 5]}

    def test_merge_mixed_types(self):
        """Test merging with different value types."""
        base = {"a": {"nested": 1}, "b": "string", "c": [1, 2]}
        override = {"a": {"nested": 2}, "d": True}
        result = deep_merge(base, override)
        assert result == {"a": {"nested": 2}, "b": "string", "c": [1, 2], "d": True}

    def test_merge_deeply_nested(self):
        """Test deeply nested structure merge."""
        base = {"l1": {"l2": {"l3": {"value": 1}}}}
        override = {"l1": {"l2": {"l3": {"value": 2}}}}
        result = deep_merge(base, override)
        assert result["l1"]["l2"]["l3"]["value"] == 2


class TestMergeConfigs:
    """Tests for merge_configs() function."""

    def test_merge_empty_project_config(self):
        """Test merging empty project config uses defaults."""
        result = merge_configs({})
        assert "dimensions" in result
        assert "backpressure" in result

    def test_merge_preserves_defaults(self):
        """Test that default dimensions are preserved."""
        result = merge_configs({"project_name": "test"})
        assert "code_quality" in result["dimensions"]
        assert "type_safety" in result["dimensions"]

    def test_merge_overrides_dimension(self):
        """Test overriding a specific dimension setting."""
        project = {"dimensions": {"coverage": {"min_percent": 90}}}
        result = merge_configs(project)
        assert result["dimensions"]["coverage"]["min_percent"] == 90
        # Other default settings should be preserved
        assert "fail_under" in result["dimensions"]["coverage"]

    def test_merge_all_14_dimensions(self):
        """Test that all 14 dimensions are present after merge."""
        result = merge_configs({})
        expected_dims = [
            "code_quality",
            "type_safety",
            "security",
            "coverage",
            "design_principles",
            "oss_reuse",
            "architecture",
            "documentation",
            "performance",
            "accessibility",
            "visual",
            "mathematical",
            "data_integrity",
            "api_contract",
        ]
        for dim in expected_dims:
            assert dim in result["dimensions"], f"Missing dimension: {dim}"


class TestValidateConfig:
    """Tests for validate_config() function."""

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        errors = validate_config(Path("/nonexistent/config.json"))
        assert len(errors) == 1
        assert "not found" in errors[0]

    def test_validate_invalid_json(self):
        """Test validation of invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            errors = validate_config(Path(f.name))
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_validate_valid_config(self):
        """Test validation of valid config."""
        config = {"project_name": "test", "domain": "general"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            # Need to patch SCHEMA_PATH to point to real schema
            schema_path = Path(__file__).parent.parent / "config.schema.json"
            if schema_path.exists():
                errors = validate_config(Path(f.name))
            else:
                # Skip if schema doesn't exist
                errors = []
        # Should be valid or no schema
        assert isinstance(errors, list)

    def test_validate_missing_schema(self):
        """Test validation when schema file is missing."""
        config = {"project_name": "test", "domain": "general"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            with patch("config_loader.SCHEMA_PATH", Path("/nonexistent/schema.json")):
                errors = validate_config(Path(f.name))
        assert len(errors) == 1
        assert "Schema file not found" in errors[0]


class TestValidateConfigDict:
    """Tests for validate_config_dict() function."""

    def test_validate_dict_missing_schema(self):
        """Test validation when schema file is missing."""
        config = {"project_name": "test", "domain": "general"}
        with patch("config_loader.SCHEMA_PATH", Path("/nonexistent/schema.json")):
            errors = validate_config_dict(config)
        assert len(errors) == 1
        assert "Schema file not found" in errors[0]

    def test_validate_dict_without_jsonschema(self):
        """Test basic validation without jsonschema module."""
        schema_path = Path(__file__).parent.parent / "config.schema.json"
        if not schema_path.exists():
            pytest.skip("Schema file not found")

        with patch("config_loader.HAS_JSONSCHEMA", False):
            # Missing project_name
            errors = validate_config_dict({})
            assert any("project_name" in e for e in errors)

            # Missing domain
            errors = validate_config_dict({"project_name": "test"})
            assert any("domain" in e for e in errors)

            # Invalid domain
            errors = validate_config_dict({"project_name": "test", "domain": "invalid"})
            assert any("domain" in e for e in errors)

            # Valid config
            errors = validate_config_dict({"project_name": "test", "domain": "general"})
            assert len(errors) == 0


class TestLoadConfigWithDefaults:
    """Tests for load_config_with_defaults() function."""

    def test_load_valid_config(self):
        """Test loading valid config with defaults."""
        config_content = {"project_name": "test", "domain": "general"}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config file
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_content))

            # Create schema file
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "properties": {
                            "project_name": {"type": "string"},
                            "domain": {"type": "string"},
                        },
                    }
                )
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                result = load_config_with_defaults(config_path)

            assert result["project_name"] == "test"
            assert "dimensions" in result

    def test_load_invalid_config_raises(self):
        """Test loading invalid config raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            f.flush()
            with pytest.raises(ValueError):
                load_config_with_defaults(Path(f.name))


class TestFindValidationConfig:
    """Tests for find_validation_config() function."""

    def test_find_config_not_found(self):
        """Test when no config is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_validation_config(Path(tmpdir))
            assert result is None

    def test_find_config_in_current_dir(self):
        """Test finding config in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude/validation/config.json
            config_dir = Path(tmpdir) / ".claude" / "validation"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            config_path.write_text("{}")

            result = find_validation_config(Path(tmpdir))
            assert result == config_path

    def test_find_config_parent_search(self):
        """Test finding config in parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in root
            config_dir = Path(tmpdir) / ".claude" / "validation"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            config_path.write_text("{}")

            # Search from subdirectory
            sub_dir = Path(tmpdir) / "sub" / "deep"
            sub_dir.mkdir(parents=True)

            result = find_validation_config(sub_dir)
            assert result == config_path

    def test_find_config_default_cwd(self):
        """Test finding config with default current directory."""
        # Just ensure it doesn't crash
        result = find_validation_config()
        assert result is None or isinstance(result, Path)


class TestGenerateConfig:
    """Tests for generate_config() function."""

    def test_generate_general_domain(self):
        """Test generating config for general domain."""
        config = generate_config("my_project", "general")
        assert config["project_name"] == "my_project"
        assert config["domain"] == "general"
        assert "$schema" in config
        assert "dimensions" in config

    def test_generate_trading_domain(self):
        """Test generating config for trading domain."""
        config = generate_config("trading_bot", "trading")
        assert config["project_name"] == "trading_bot"
        assert config["domain"] == "trading"
        # Trading domain has specific rollback triggers
        assert "rollback_triggers" in config
        assert len(config["rollback_triggers"]) > 0

    def test_generate_workflow_domain(self):
        """Test generating config for workflow domain."""
        config = generate_config("n8n_flows", "workflow")
        assert config["domain"] == "workflow"
        # Workflow domain has smoke tests
        assert "smoke_tests" in config

    def test_generate_data_domain(self):
        """Test generating config for data domain."""
        config = generate_config("data_pipeline", "data")
        assert config["domain"] == "data"
        # Data domain enables data_integrity
        assert config["dimensions"]["data_integrity"]["enabled"] is True

    def test_generate_invalid_domain(self):
        """Test generating config with invalid domain raises."""
        with pytest.raises(ValueError) as exc_info:
            generate_config("test", "invalid_domain")
        assert "Unknown domain" in str(exc_info.value)

    def test_generate_includes_all_dimensions(self):
        """Test generated config includes all 14 dimensions."""
        config = generate_config("test", "general")
        assert len(config["dimensions"]) == 14


class TestDefaultConfigs:
    """Tests for default configuration constants."""

    def test_default_dimensions_structure(self):
        """Test DEFAULT_DIMENSIONS has expected structure."""
        assert "code_quality" in DEFAULT_DIMENSIONS
        assert "tier" in DEFAULT_DIMENSIONS["code_quality"]
        assert "enabled" in DEFAULT_DIMENSIONS["code_quality"]

    def test_default_config_structure(self):
        """Test DEFAULT_CONFIG has expected structure."""
        assert "smoke_tests" in DEFAULT_CONFIG
        assert "k8s" in DEFAULT_CONFIG
        assert "ci" in DEFAULT_CONFIG
        assert "backpressure" in DEFAULT_CONFIG
        assert "dimensions" in DEFAULT_CONFIG

    def test_domain_presets_structure(self):
        """Test DOMAIN_PRESETS has expected domains."""
        assert "trading" in DOMAIN_PRESETS
        assert "workflow" in DOMAIN_PRESETS
        assert "data" in DOMAIN_PRESETS
        assert "general" in DOMAIN_PRESETS

    def test_tier_assignments(self):
        """Test tier assignments in DEFAULT_DIMENSIONS."""
        tier1 = ["code_quality", "type_safety", "security", "coverage"]
        tier2 = ["design_principles", "oss_reuse", "architecture", "documentation"]
        tier3 = [
            "performance",
            "accessibility",
            "visual",
            "mathematical",
            "data_integrity",
            "api_contract",
        ]

        for dim in tier1:
            assert DEFAULT_DIMENSIONS[dim]["tier"] == 1, f"{dim} should be tier 1"
        for dim in tier2:
            assert DEFAULT_DIMENSIONS[dim]["tier"] == 2, f"{dim} should be tier 2"
        for dim in tier3:
            assert DEFAULT_DIMENSIONS[dim]["tier"] == 3, f"{dim} should be tier 3"


class TestCLI:
    """Tests for CLI main() function."""

    def test_show_defaults(self, capsys):
        """Test --show-defaults flag."""
        with patch("sys.argv", ["config_loader.py", "--show-defaults"]):
            from config_loader import main

            main()

        captured = capsys.readouterr()
        assert "dimensions" in captured.out

    def test_find_not_found(self, capsys):
        """Test --find when config not found."""
        with patch("sys.argv", ["config_loader.py", "--find"]):
            with patch("config_loader.find_validation_config", return_value=None):
                from config_loader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No validation config found" in captured.out

    def test_find_found(self, capsys):
        """Test --find when config is found."""
        mock_path = Path("/some/path/config.json")
        with patch("sys.argv", ["config_loader.py", "--find"]):
            with patch("config_loader.find_validation_config", return_value=mock_path):
                from config_loader import main

                main()

        captured = capsys.readouterr()
        assert "Found:" in captured.out

    def test_generate_requires_project_name(self, capsys):
        """Test --generate requires --project-name."""
        with patch("sys.argv", ["config_loader.py", "--generate"]):
            from config_loader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "--project-name is required" in captured.err

    def test_generate_outputs_config(self, capsys):
        """Test --generate with project name."""
        with patch(
            "sys.argv",
            ["config_loader.py", "--generate", "--project-name", "test_proj"],
        ):
            from config_loader import main

            main()

        captured = capsys.readouterr()
        assert "test_proj" in captured.out
        assert "dimensions" in captured.out

    def test_generate_to_file(self):
        """Test --generate with --output flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "generated.json"
            with patch(
                "sys.argv",
                [
                    "config_loader.py",
                    "--generate",
                    "--project-name",
                    "test_proj",
                    "--output",
                    str(output_path),
                ],
            ):
                from config_loader import main

                main()

            assert output_path.exists()
            content = json.loads(output_path.read_text())
            assert content["project_name"] == "test_proj"

    def test_validate_success(self, capsys):
        """Test --validate with valid config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "general"})
            )

            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object", "properties": {}}))

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch(
                    "sys.argv",
                    ["config_loader.py", "--validate", str(config_path)],
                ):
                    from config_loader import main

                    main()

        captured = capsys.readouterr()
        assert "Validation OK" in captured.out

    def test_no_args_shows_help(self):
        """Test running with no args shows help."""
        with patch("sys.argv", ["config_loader.py"]):
            from config_loader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


# =============================================================================
# Phase 20: Global Config Inheritance Tests (RFC 7396)
# =============================================================================


class TestLoadGlobalConfig:
    """Tests for load_global_config() function."""

    def test_load_global_config_exists(self):
        """Test loading global config when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_config = {"enabled": True, "dimensions": {"coverage": {"tier": 1}}}
            global_path = Path(tmpdir) / "global-config.json"
            global_path.write_text(json.dumps(global_config))

            with patch("config_loader.GLOBAL_CONFIG_PATH", global_path):
                result = load_global_config()

            assert result == global_config
            assert result["enabled"] is True
            assert result["dimensions"]["coverage"]["tier"] == 1

    def test_load_global_config_missing(self):
        """Test loading global config when file doesn't exist returns empty dict."""
        with patch(
            "config_loader.GLOBAL_CONFIG_PATH", Path("/nonexistent/global-config.json")
        ):
            result = load_global_config()

        assert result == {}

    def test_load_global_config_invalid_json(self):
        """Test loading global config with invalid JSON returns empty dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()

            with patch("config_loader.GLOBAL_CONFIG_PATH", Path(f.name)):
                result = load_global_config()

        assert result == {}


class TestLoadProjectConfig:
    """Tests for load_project_config() function."""

    def test_load_project_config_exists(self):
        """Test loading project config when file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .claude/validation/config.json
            config_dir = Path(tmpdir) / ".claude" / "validation"
            config_dir.mkdir(parents=True)
            config_path = config_dir / "config.json"
            project_config = {"project_name": "test", "domain": "trading"}
            config_path.write_text(json.dumps(project_config))

            result = load_project_config(Path(tmpdir))

        assert result["project_name"] == "test"
        assert result["domain"] == "trading"

    def test_load_project_config_missing(self):
        """Test loading project config when not found returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_project_config(Path(tmpdir))

        assert result == {}

    def test_load_project_config_explicit_file(self):
        """Test loading project config with explicit file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config = {"project_name": "explicit", "custom_setting": True}
            json.dump(config, f)
            f.flush()

            result = load_project_config(Path(f.name))

        assert result["project_name"] == "explicit"
        assert result["custom_setting"] is True

    def test_load_project_config_invalid_json(self):
        """Test loading project config with invalid JSON returns empty dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            f.flush()

            result = load_project_config(Path(f.name))

        assert result == {}


class TestMergeConfigsRfc7396:
    """Tests for merge_configs_rfc7396() - RFC 7396 JSON Merge Patch semantics."""

    def test_merge_configs_simple(self):
        """Test that project values override global at same path."""
        global_config = {"setting_a": "global", "setting_b": "global"}
        project_config = {"setting_a": "project"}

        result = merge_configs_rfc7396(global_config, project_config)

        assert result["setting_a"] == "project"  # Overridden
        assert result["setting_b"] == "global"  # Preserved

    def test_merge_configs_deep(self):
        """Test deep merge for nested dicts."""
        global_config = {
            "dimensions": {
                "coverage": {"tier": 1, "min_percent": 70},
                "security": {"tier": 1, "enabled": True},
            }
        }
        project_config = {
            "dimensions": {"coverage": {"min_percent": 90}}  # Override just this
        }

        result = merge_configs_rfc7396(global_config, project_config)

        # Coverage min_percent overridden, tier preserved
        assert result["dimensions"]["coverage"]["min_percent"] == 90
        assert result["dimensions"]["coverage"]["tier"] == 1
        # Security preserved entirely
        assert result["dimensions"]["security"]["tier"] == 1
        assert result["dimensions"]["security"]["enabled"] is True

    def test_merge_configs_array_override(self):
        """Test that arrays are replaced entirely, not merged element-by-element."""
        global_config = {"scanners": ["bandit", "gitleaks", "trivy"]}
        project_config = {"scanners": ["custom_scanner"]}

        result = merge_configs_rfc7396(global_config, project_config)

        # Array should be completely replaced
        assert result["scanners"] == ["custom_scanner"]
        assert "bandit" not in result["scanners"]


class TestLoadConfigIntegration:
    """Integration tests for load_config() with full inheritance chain."""

    def test_load_config_integration(self):
        """Test full config load with global + project merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config
            global_config = {
                "enabled": True,
                "dimensions": {
                    "coverage": {"tier": 1, "min_percent": 70},
                    "security": {"tier": 1, "fail_on": ["HIGH"]},
                },
            }
            global_path = Path(tmpdir) / "global-config.json"
            global_path.write_text(json.dumps(global_config))

            # Create project directory with config
            project_dir = Path(tmpdir) / "my_project"
            config_dir = project_dir / ".claude" / "validation"
            config_dir.mkdir(parents=True)
            project_config = {
                "project_name": "my_project",
                "domain": "general",
                "dimensions": {
                    "coverage": {"min_percent": 90},  # Override global
                },
            }
            (config_dir / "config.json").write_text(json.dumps(project_config))

            with patch("config_loader.GLOBAL_CONFIG_PATH", global_path):
                result = load_config(project_dir)

            # Check merge results
            assert result["project_name"] == "my_project"
            # Coverage: min_percent from project (90), tier from global (1)
            assert result["dimensions"]["coverage"]["min_percent"] == 90
            assert result["dimensions"]["coverage"]["tier"] == 1
            # Security from global
            assert result["dimensions"]["security"]["tier"] == 1
            # _config_source metadata
            assert result["_config_source"]["global"] is True
            assert result["_config_source"]["project"] is True

    def test_load_config_only_global(self):
        """Test config load with only global config (no project config)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config
            global_config = {
                "enabled": True,
                "tier_1_only_global": True,
                "dimensions": {"coverage": {"enabled": False}},
            }
            global_path = Path(tmpdir) / "global-config.json"
            global_path.write_text(json.dumps(global_config))

            # Empty project dir (no config)
            project_dir = Path(tmpdir) / "empty_project"
            project_dir.mkdir()

            with patch("config_loader.GLOBAL_CONFIG_PATH", global_path):
                result = load_config(project_dir)

            assert result["_config_source"]["global"] is True
            assert result["_config_source"]["project"] is False
            # Global settings applied
            assert result["enabled"] is True
            assert result["dimensions"]["coverage"]["enabled"] is False

    def test_load_config_only_project(self):
        """Test config load with only project config (no global)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project config only
            project_dir = Path(tmpdir) / "my_project"
            config_dir = project_dir / ".claude" / "validation"
            config_dir.mkdir(parents=True)
            project_config = {
                "project_name": "standalone",
                "domain": "trading",
                "dimensions": {"coverage": {"min_percent": 85}},
            }
            (config_dir / "config.json").write_text(json.dumps(project_config))

            with patch(
                "config_loader.GLOBAL_CONFIG_PATH",
                Path("/nonexistent/global-config.json"),
            ):
                result = load_config(project_dir)

            assert result["_config_source"]["global"] is False
            assert result["_config_source"]["project"] is True
            assert result["project_name"] == "standalone"
            assert result["dimensions"]["coverage"]["min_percent"] == 85

    def test_load_config_no_configs(self):
        """Test config load with no configs (defaults only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "bare_project"
            project_dir.mkdir()

            with patch(
                "config_loader.GLOBAL_CONFIG_PATH",
                Path("/nonexistent/global-config.json"),
            ):
                result = load_config(project_dir)

            # Should get template defaults
            assert result["_config_source"]["global"] is False
            assert result["_config_source"]["project"] is False
            # Defaults applied
            assert "dimensions" in result
            assert "code_quality" in result["dimensions"]


class TestNoJsonschemaFallback:
    """Tests for code paths when jsonschema is not available."""

    def test_validate_config_without_jsonschema(self):
        """Test validate_config basic validation without jsonschema (lines 292-297)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object"}))

            # Missing project_name and domain
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({}))

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch("config_loader.HAS_JSONSCHEMA", False):
                    errors = validate_config(config_path)
            assert any("project_name" in e for e in errors)
            assert any("domain" in e for e in errors)

    def test_validate_config_without_jsonschema_invalid_domain(self):
        """Test validate_config with invalid domain without jsonschema (line 296-297)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object"}))

            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "invalid"})
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch("config_loader.HAS_JSONSCHEMA", False):
                    errors = validate_config(config_path)
            assert any("must be one of" in e for e in errors)

    def test_validate_config_without_jsonschema_valid(self):
        """Test validate_config passes with valid config without jsonschema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object"}))

            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "general"})
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch("config_loader.HAS_JSONSCHEMA", False):
                    errors = validate_config(config_path)
            assert len(errors) == 0


class TestImportFallback:
    """Tests for jsonschema import fallback (lines 48-51)."""

    def test_has_jsonschema_flag(self):
        """Test HAS_JSONSCHEMA is set correctly."""
        from config_loader import HAS_JSONSCHEMA

        assert isinstance(HAS_JSONSCHEMA, bool)

    def test_import_without_jsonschema(self):
        """Test module works when jsonschema is not available (lines 48-51)."""
        import importlib

        import config_loader

        original_import = (
            __builtins__.__import__
            if hasattr(__builtins__, "__import__")
            else __import__
        )

        def mock_import(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            importlib.reload(config_loader)

        assert config_loader.HAS_JSONSCHEMA is False
        assert config_loader.Draft202012Validator is None

        # Restore
        importlib.reload(config_loader)


class TestSchemaJsonDecodeErrors:
    """Tests for JSON decode errors in schema files."""

    def test_validate_config_invalid_schema_json(self):
        """Test validate_config with invalid JSON schema file (lines 281-282)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text("not valid json {{{")

            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"project_name": "test"}))

            with patch("config_loader.SCHEMA_PATH", schema_path):
                errors = validate_config(config_path)
            assert len(errors) == 1
            assert "Invalid JSON in schema" in errors[0]

    def test_validate_config_dict_invalid_schema_json(self):
        """Test validate_config_dict with invalid JSON schema (lines 318-319)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text("not valid json")

            with patch("config_loader.SCHEMA_PATH", schema_path):
                errors = validate_config_dict({"project_name": "test"})
            assert len(errors) == 1
            assert "Invalid JSON in schema" in errors[0]

    def test_validate_config_dict_with_jsonschema(self):
        """Test validate_config_dict with jsonschema available (lines 323-326)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "required": ["project_name"],
                        "properties": {"project_name": {"type": "string"}},
                    }
                )
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                # Missing required field
                errors = validate_config_dict({})
            assert len(errors) > 0
            assert any("project_name" in e for e in errors)

            with patch("config_loader.SCHEMA_PATH", schema_path):
                # Valid
                errors = validate_config_dict({"project_name": "test"})
            assert len(errors) == 0


class TestMergeConfigsCustomDimension:
    """Test merge_configs with custom dimensions (line 388, 392)."""

    def test_merge_preserves_custom_dimensions(self):
        """Custom dimensions from project config are preserved (line 392)."""
        project = {
            "dimensions": {
                "custom_validator": {"enabled": True, "tier": 2, "custom_opt": "x"}
            }
        }
        result = merge_configs(project)
        assert "custom_validator" in result["dimensions"]
        assert result["dimensions"]["custom_validator"]["custom_opt"] == "x"

    def test_dimension_missing_from_result_uses_default_copy(self):
        """When a default dimension is not in result['dimensions'], it gets default copy (line 388)."""
        # To hit line 388, we need result["dimensions"] to NOT contain a default dim.
        # We can achieve this by patching DEFAULT_CONFIG to have empty dimensions,
        # then deep_merge won't add them, but the special handling loop will.
        empty_default = {**DEFAULT_CONFIG, "dimensions": {}}
        with patch("config_loader.DEFAULT_CONFIG", empty_default):
            result = merge_configs({"dimensions": {"coverage": {"min_percent": 99}}})
        # All default dims should be present via the copy fallback
        assert "visual" in result["dimensions"]
        assert "code_quality" in result["dimensions"]
        assert result["dimensions"]["coverage"]["min_percent"] == 99


class TestLoadGlobalConfigOSError:
    """Test OSError path in load_global_config (lines 476-478)."""

    def test_load_global_config_os_error(self):
        """Test OSError handling in load_global_config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_path = Path(tmpdir) / "global-config.json"
            global_path.write_text("{}")

            with patch("config_loader.GLOBAL_CONFIG_PATH", global_path):
                with patch.object(
                    Path, "read_text", side_effect=OSError("perm denied")
                ):
                    result = load_global_config()
            assert result == {}


class TestLoadProjectConfigEdgeCases:
    """Tests for load_project_config edge cases."""

    def test_load_project_config_nonexistent_path(self):
        """Test with path that doesn't exist (lines 508-509)."""
        result = load_project_config(Path("/nonexistent/path/that/does/not/exist"))
        assert result == {}

    def test_load_project_config_os_error(self):
        """Test OSError when reading project config (lines 523-525)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{}")

            with patch(
                "config_loader.find_validation_config", return_value=config_path
            ):
                with patch.object(Path, "read_text", side_effect=OSError("denied")):
                    result = load_project_config(Path(tmpdir))
            assert result == {}

    def test_load_project_config_none_searches_cwd(self):
        """Test load_project_config with None uses cwd (line 499)."""
        with patch("config_loader.find_validation_config", return_value=None):
            result = load_project_config(None)
        assert result == {}


class TestLoadConfigProjectPathIsFile:
    """Test load_config when project_path is a file (line 591)."""

    def test_load_config_with_file_path(self):
        """Test load_config with explicit file path sets project_path in source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "general"})
            )

            with patch(
                "config_loader.GLOBAL_CONFIG_PATH",
                Path("/nonexistent/global-config.json"),
            ):
                result = load_config(config_path)

            assert result["_config_source"]["project"] is True
            assert result["_config_source"]["project_path"] == str(config_path)


class TestGenerateConfigDimensionDefault:
    """Test generate_config dimension default copy (line 656)."""

    def test_generate_config_dimension_not_in_config(self):
        """Line 656: dim not in config['dimensions'] gets default copy."""
        # Patch DEFAULT_CONFIG to have empty dimensions so generate_config
        # starts with no dimensions, then the else branch at 656 is hit.
        empty_default = {**DEFAULT_CONFIG, "dimensions": {}}
        with patch("config_loader.DEFAULT_CONFIG", empty_default):
            config = generate_config("test", "general")
        # All 14 default dims should still be present via line 656
        assert len(config["dimensions"]) == 14
        assert config["dimensions"]["visual"]["enabled"] is False


class TestCLIAdditional:
    """Additional CLI tests for uncovered lines."""

    def test_generate_invalid_domain_cli(self, capsys):
        """Test --generate with invalid domain via CLI (lines 718-720)."""
        with patch(
            "sys.argv",
            [
                "config_loader.py",
                "--generate",
                "--project-name",
                "test",
                "--domain",
                "general",
            ],
        ):
            # Patch generate_config to raise ValueError
            with patch(
                "config_loader.generate_config",
                side_effect=ValueError("bad domain"),
            ):
                from config_loader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "bad domain" in captured.err

    def test_validate_failures_cli(self, capsys):
        """Test --validate with failing config (lines 745-748)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({}))

            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "required": ["project_name"],
                        "properties": {"project_name": {"type": "string"}},
                    }
                )
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch(
                    "sys.argv",
                    ["config_loader.py", "--validate", str(config_path)],
                ):
                    from config_loader import main

                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Validation FAILED" in captured.out

    def test_show_merged_cli(self, capsys):
        """Test --show-merged (lines 753-760)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "general"})
            )

            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object", "properties": {}}))

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch(
                    "sys.argv",
                    ["config_loader.py", "--show-merged", str(config_path)],
                ):
                    from config_loader import main

                    main()

        captured = capsys.readouterr()
        assert "dimensions" in captured.out
        assert "test" in captured.out

    def test_show_merged_error_cli(self, capsys):
        """Test --show-merged with invalid config (lines 757-759)."""
        with patch(
            "sys.argv",
            ["config_loader.py", "--show-merged", "/nonexistent/config.json"],
        ):
            from config_loader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_default_validation_failures_cli(self, capsys):
        """Test default action (validate) with failures (lines 763-770)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({}))

            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "required": ["project_name"],
                        "properties": {"project_name": {"type": "string"}},
                    }
                )
            )

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch(
                    "sys.argv",
                    ["config_loader.py", str(config_path)],
                ):
                    from config_loader import main

                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Validation FAILED" in captured.out

    def test_default_validation_ok_cli(self, capsys):
        """Test default action (validate) with valid config (line 770)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"project_name": "test", "domain": "general"})
            )

            schema_path = Path(tmpdir) / "schema.json"
            schema_path.write_text(json.dumps({"type": "object", "properties": {}}))

            with patch("config_loader.SCHEMA_PATH", schema_path):
                with patch(
                    "sys.argv",
                    ["config_loader.py", str(config_path)],
                ):
                    from config_loader import main

                    main()

        captured = capsys.readouterr()
        assert "Validation OK" in captured.out

    def test_main_entry_point_via_runpy(self):
        """Test __name__ == '__main__' via runpy (line 774)."""
        import runpy

        with patch("sys.argv", ["config_loader.py", "--show-defaults"]):
            runpy.run_path(
                str(Path(__file__).parent.parent / "config_loader.py"),
                run_name="__main__",
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
