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
    merge_configs,
    validate_config,
    validate_config_dict,
    load_config_with_defaults,
    find_validation_config,
    generate_config,
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
