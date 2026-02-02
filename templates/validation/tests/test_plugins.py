#!/usr/bin/env python3
"""Unit tests for plugins.py - Plugin System for Custom Validators."""

import json
import sys
from pathlib import Path

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins import (
    PLUGIN_INTERFACE,
    PluginSpec,
    load_plugin,
    load_plugins,
    parse_plugin_spec,
)

# =============================================================================
# parse_plugin_spec tests (4 tests)
# =============================================================================


class TestParsePluginSpec:
    """Tests for parse_plugin_spec function."""

    def test_parse_pypi_spec(self):
        """Test parsing a PyPI package spec."""
        spec = parse_plugin_spec("my-validator")

        assert spec.source == "my-validator"
        assert spec.type == "pypi"
        assert spec.name == "my_validator"  # Hyphens converted to underscores
        assert spec.path is None

    def test_parse_local_absolute(self):
        """Test parsing an absolute local path."""
        spec = parse_plugin_spec("/path/to/validator")

        assert spec.source == "/path/to/validator"
        assert spec.type == "local"
        assert spec.name == "validator"
        assert spec.path == Path("/path/to/validator")

    def test_parse_local_relative(self):
        """Test parsing a relative local path."""
        spec = parse_plugin_spec("./validators/custom")

        assert spec.source == "./validators/custom"
        assert spec.type == "local"
        assert spec.name == "custom"
        assert spec.path is not None
        assert "custom" in str(spec.path)

    def test_parse_git_spec(self):
        """Test parsing a git URL spec."""
        spec = parse_plugin_spec("git+https://github.com/user/my-validator")

        assert spec.source == "git+https://github.com/user/my-validator"
        assert spec.type == "git"
        assert spec.name == "my-validator"
        assert spec.path is None

    def test_parse_git_spec_with_git_extension(self):
        """Test parsing a git URL with .git extension."""
        spec = parse_plugin_spec("git+https://github.com/user/repo.git")

        assert spec.type == "git"
        assert spec.name == "repo"  # .git stripped

    def test_parse_tilde_path(self):
        """Test parsing a tilde-expanded path."""
        spec = parse_plugin_spec("~/validators/custom")

        assert spec.type == "local"
        assert spec.name == "custom"
        # Path should have tilde expanded
        assert "~" not in str(spec.path)


# =============================================================================
# load_plugin tests (4 tests)
# =============================================================================


class TestLoadPlugin:
    """Tests for load_plugin function."""

    def test_load_local_plugin(self, tmp_path):
        """Test loading a local plugin with Validator class."""
        # Create a test plugin module
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        init_file = plugin_dir / "__init__.py"
        init_file.write_text("""
from dataclasses import dataclass

@dataclass
class ValidationResult:
    dimension: str
    tier: int
    passed: bool
    message: str

class Validator:
    dimension = "test_dimension"
    tier = 3

    async def validate(self):
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="Test passed"
        )
""")

        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="test_plugin",
            path=plugin_dir,
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is not None
        assert validator_cls.dimension == "test_dimension"
        assert validator_cls.tier == 3

    def test_load_missing_plugin(self, tmp_path):
        """Test loading a plugin that doesn't exist returns None."""
        spec = PluginSpec(
            source=str(tmp_path / "nonexistent"),
            type="local",
            name="nonexistent",
            path=tmp_path / "nonexistent",
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is None

    def test_load_invalid_plugin(self, tmp_path):
        """Test loading a module without Validator class returns None."""
        # Create a plugin without Validator class
        plugin_dir = tmp_path / "invalid_plugin"
        plugin_dir.mkdir()
        init_file = plugin_dir / "__init__.py"
        init_file.write_text("""
# No Validator class or get_validator function
def some_function():
    pass
""")

        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="invalid_plugin",
            path=plugin_dir,
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is None

    def test_load_plugin_with_get_validator(self, tmp_path):
        """Test loading a plugin using get_validator() function."""
        plugin_dir = tmp_path / "get_validator_plugin"
        plugin_dir.mkdir()
        init_file = plugin_dir / "__init__.py"
        init_file.write_text("""
class MyValidator:
    dimension = "custom_dimension"
    tier = 2

    async def validate(self):
        return {"passed": True}

def get_validator():
    return MyValidator
""")

        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="get_validator_plugin",
            path=plugin_dir,
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is not None
        assert validator_cls.dimension == "custom_dimension"
        assert validator_cls.tier == 2

    def test_load_pypi_plugin_not_installed(self):
        """Test loading a PyPI plugin that isn't installed."""
        spec = PluginSpec(
            source="nonexistent-package-xyz",
            type="pypi",
            name="nonexistent_package_xyz",
            path=None,
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is None

    def test_load_git_plugin_not_implemented(self):
        """Test that git plugins return None with warning."""
        spec = PluginSpec(
            source="git+https://github.com/user/repo",
            type="git",
            name="repo",
            path=None,
        )

        validator_cls = load_plugin(spec)

        assert validator_cls is None


# =============================================================================
# Integration tests (4 tests)
# =============================================================================


class TestPluginIntegration:
    """Integration tests for plugin system with orchestrator."""

    def test_orchestrator_loads_plugins(self, tmp_path):
        """Test that orchestrator loads plugins from config."""
        # Create a test plugin
        plugin_dir = tmp_path / "my_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
class Validator:
    dimension = "my_plugin"
    tier = None  # Will be set to default

    async def validate(self):
        return {"passed": True, "dimension": "my_plugin"}
""")

        # Create config with plugin
        config = {
            "project_name": "test",
            "plugins": [str(plugin_dir)],
            "dimensions": {},
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        # Import and create orchestrator
        from orchestrator import ValidationOrchestrator

        orchestrator = ValidationOrchestrator(config_file)

        # Check plugin was loaded
        assert "my_plugin" in orchestrator.validators

    def test_plugin_default_tier(self, tmp_path):
        """Test that plugins default to Tier 3 (MONITOR)."""
        # Create a test plugin without tier
        plugin_dir = tmp_path / "default_tier_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
class Validator:
    dimension = "default_tier_plugin"
    # No tier attribute

    async def validate(self):
        return {"passed": True}
""")

        config = {
            "project_name": "test",
            "plugins": [str(plugin_dir)],
            "dimensions": {},
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from orchestrator import ValidationOrchestrator, ValidationTier

        orchestrator = ValidationOrchestrator(config_file)

        # Plugin should default to MONITOR tier
        assert "default_tier_plugin" in orchestrator.validators
        assert (
            orchestrator.validators["default_tier_plugin"].tier
            == ValidationTier.MONITOR
        )

    def test_plugin_can_override_tier(self, tmp_path):
        """Test that config can override plugin tier."""
        # Create a test plugin
        plugin_dir = tmp_path / "override_tier_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
class Validator:
    dimension = "override_tier_plugin"
    tier = 3  # Default to MONITOR

    async def validate(self):
        return {"passed": True}
""")

        config = {
            "project_name": "test",
            "plugins": [str(plugin_dir)],
            "dimensions": {
                "override_tier_plugin": {
                    "enabled": True,
                    "tier": 1,
                }  # Override to BLOCKER
            },
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from orchestrator import ValidationOrchestrator, ValidationTier

        orchestrator = ValidationOrchestrator(config_file)

        # Plugin tier should be overridden to BLOCKER
        assert "override_tier_plugin" in orchestrator.validators
        assert (
            orchestrator.validators["override_tier_plugin"].tier
            == ValidationTier.BLOCKER
        )

    def test_empty_plugins_list(self, tmp_path):
        """Test that empty plugins list doesn't cause errors."""
        config = {
            "project_name": "test",
            "plugins": [],
            "dimensions": {},
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config))

        from orchestrator import ValidationOrchestrator

        # Should not raise
        orchestrator = ValidationOrchestrator(config_file)

        # Should have default validators, no plugins
        assert len(orchestrator.validators) > 0


# =============================================================================
# Additional edge case tests
# =============================================================================


class TestLoadPlugins:
    """Tests for load_plugins function."""

    def test_load_multiple_plugins(self, tmp_path):
        """Test loading multiple plugins at once."""
        # Create two plugins
        plugin1 = tmp_path / "plugin1"
        plugin1.mkdir()
        (plugin1 / "__init__.py").write_text("""
class Validator:
    dimension = "plugin1"
    async def validate(self): pass
""")

        plugin2 = tmp_path / "plugin2"
        plugin2.mkdir()
        (plugin2 / "__init__.py").write_text("""
class Validator:
    dimension = "plugin2"
    async def validate(self): pass
""")

        result = load_plugins([str(plugin1), str(plugin2)])

        assert "plugin1" in result
        assert "plugin2" in result

    def test_load_plugins_skips_failures(self, tmp_path):
        """Test that load_plugins skips failed plugins gracefully."""
        # Create one valid and one invalid plugin
        valid_plugin = tmp_path / "valid"
        valid_plugin.mkdir()
        (valid_plugin / "__init__.py").write_text("""
class Validator:
    dimension = "valid"
    async def validate(self): pass
""")

        result = load_plugins(
            [
                str(valid_plugin),
                str(tmp_path / "nonexistent"),  # This doesn't exist
            ]
        )

        # Should have the valid plugin but not the invalid one
        assert "valid" in result
        assert "nonexistent" not in result


class TestPluginInterface:
    """Tests for PLUGIN_INTERFACE documentation."""

    def test_plugin_interface_documented(self):
        """Test that PLUGIN_INTERFACE contains required documentation."""
        assert "Validator" in PLUGIN_INTERFACE
        assert "get_validator" in PLUGIN_INTERFACE
        assert "dimension" in PLUGIN_INTERFACE
        assert "tier" in PLUGIN_INTERFACE
        assert "validate" in PLUGIN_INTERFACE


class TestLoadModuleFromPath:
    """Tests for _load_module_from_path edge cases."""

    def test_load_single_py_file(self, tmp_path):
        """Test loading a single .py file as plugin."""
        from plugins import _load_module_from_path

        py_file = tmp_path / "my_validator.py"
        py_file.write_text("""
class Validator:
    dimension = "file_plugin"
    async def validate(self): pass
""")
        module = _load_module_from_path(py_file, "my_validator_file")
        assert module is not None
        assert hasattr(module, "Validator")
        assert module.Validator.dimension == "file_plugin"

    def test_load_dir_without_init(self, tmp_path):
        """Test loading a directory without __init__.py (namespace package)."""
        from plugins import _load_module_from_path

        plugin_dir = tmp_path / "ns_plugin"
        plugin_dir.mkdir()
        # No __init__.py - namespace package path
        (plugin_dir / "helper.py").write_text("x = 1")

        # This may or may not succeed depending on namespace package resolution
        # but it should not raise
        _load_module_from_path(plugin_dir, "ns_plugin_test_unique")
        # Result can be None or a module - we just verify no crash

    def test_load_invalid_path(self, tmp_path):
        """Test loading a non-py, non-dir path returns None."""
        from plugins import _load_module_from_path

        bad_file = tmp_path / "data.txt"
        bad_file.write_text("not python")
        result = _load_module_from_path(bad_file, "bad_module")
        assert result is None

    def test_load_module_exception(self, tmp_path):
        """Test that exceptions during module load return None."""
        from plugins import _load_module_from_path

        py_file = tmp_path / "broken.py"
        py_file.write_text("raise RuntimeError('broken module')")
        result = _load_module_from_path(py_file, "broken_module_test")
        assert result is None

    def test_spec_is_none(self, tmp_path, monkeypatch):
        """Test when spec_from_file_location returns None."""
        import importlib.util

        from plugins import _load_module_from_path

        py_file = tmp_path / "good.py"
        py_file.write_text("x = 1")

        monkeypatch.setattr(
            importlib.util, "spec_from_file_location", lambda *a, **k: None
        )
        result = _load_module_from_path(py_file, "spec_none_test")
        assert result is None


class TestLoadPluginEdgeCases:
    """Edge case tests for load_plugin."""

    def test_local_plugin_no_path(self):
        """Test local plugin with path=None."""
        spec = PluginSpec(source="test", type="local", name="test", path=None)
        result = load_plugin(spec)
        assert result is None

    def test_unknown_plugin_type(self):
        """Test unknown plugin type returns None."""
        spec = PluginSpec(source="test", type="unknown", name="test", path=None)
        result = load_plugin(spec)
        assert result is None

    def test_module_loaded_but_none(self, tmp_path, monkeypatch):
        """Test when _load_module_from_path returns None."""
        import plugins as plugins_mod

        spec = PluginSpec(
            source="test", type="local", name="test_none_mod", path=tmp_path
        )
        monkeypatch.setattr(plugins_mod, "_load_module_from_path", lambda *a: None)
        result = load_plugin(spec)
        assert result is None

    def test_get_validator_returns_none(self, tmp_path):
        """Test plugin with get_validator() that returns None."""
        plugin_dir = tmp_path / "returns_none_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
def get_validator():
    return None
""")
        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="returns_none_plugin",
            path=plugin_dir,
        )
        result = load_plugin(spec)
        assert result is None

    def test_get_validator_not_callable(self, tmp_path):
        """Test plugin with get_validator that is not callable."""
        plugin_dir = tmp_path / "not_callable_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
get_validator = "not a function"
""")
        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="not_callable_plugin",
            path=plugin_dir,
        )
        result = load_plugin(spec)
        assert result is None

    def test_get_validator_returns_non_type(self, tmp_path):
        """Test plugin with get_validator() returning non-type."""
        plugin_dir = tmp_path / "non_type_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "__init__.py").write_text("""
def get_validator():
    return "not a class"
""")
        spec = PluginSpec(
            source=str(plugin_dir),
            type="local",
            name="non_type_plugin",
            path=plugin_dir,
        )
        result = load_plugin(spec)
        assert result is None

    def test_load_plugin_exception(self, monkeypatch):
        """Test load_plugin catches unexpected exceptions."""
        import plugins as plugins_mod

        spec = PluginSpec(
            source="test", type="local", name="exc_test", path=Path("/tmp")
        )

        def raise_exc(*a, **k):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(plugins_mod, "_load_module_from_path", raise_exc)
        # path.exists() will be True for /tmp
        result = load_plugin(spec)
        assert result is None


class TestLoadPluginsEdgeCases:
    """Edge cases for load_plugins."""

    def test_load_plugins_exception_in_parse(self, monkeypatch):
        """Test load_plugins handles exception during parse."""
        import plugins as plugins_mod

        def bad_parse(s):
            raise ValueError("bad spec")

        monkeypatch.setattr(plugins_mod, "parse_plugin_spec", bad_parse)
        result = load_plugins(["bad-spec"])
        assert result == {}

    def test_load_plugins_empty(self):
        """Test load_plugins with empty list."""
        result = load_plugins([])
        assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
