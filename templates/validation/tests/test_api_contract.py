#!/usr/bin/env python3
"""Unit tests for API contract validators."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.api_contract.oasdiff_runner import (
    BreakingChange,
    OasdiffResult,
    OasdiffRunner,
)
from validators.api_contract.spec_discovery import SpecDiscovery
from validators.api_contract.validator import APIContractValidator


class TestBreakingChange:
    """Tests for BreakingChange dataclass."""

    def test_creation(self):
        """Test BreakingChange creation."""
        change = BreakingChange(
            level="ERR",
            code="PATH_DELETED",
            path="/api/users",
            message="Path was deleted",
        )
        assert change.level == "ERR"
        assert change.code == "PATH_DELETED"
        assert change.path == "/api/users"
        assert change.message == "Path was deleted"

    def test_defaults(self):
        """Test BreakingChange default values."""
        change = BreakingChange(level="WARN", code="TEST", path="/test")
        assert change.message == ""


class TestOasdiffResult:
    """Tests for OasdiffResult dataclass."""

    def test_success_no_changes(self):
        """Test successful result with no breaking changes."""
        result = OasdiffResult(
            success=True,
            has_breaking_changes=False,
        )
        assert result.success is True
        assert result.has_breaking_changes is False
        assert result.changes == []
        assert result.error is None

    def test_success_with_changes(self):
        """Test successful result with breaking changes."""
        changes = [BreakingChange("ERR", "TEST", "/api")]
        result = OasdiffResult(
            success=True,
            has_breaking_changes=True,
            changes=changes,
        )
        assert len(result.changes) == 1

    def test_error_result(self):
        """Test error result."""
        result = OasdiffResult(
            success=False,
            has_breaking_changes=False,
            error="oasdiff not installed",
            oasdiff_available=False,
        )
        assert result.success is False
        assert result.error == "oasdiff not installed"
        assert result.oasdiff_available is False


class TestOasdiffRunner:
    """Tests for OasdiffRunner class."""

    def test_init_defaults(self):
        """Test default initialization."""
        runner = OasdiffRunner()
        assert runner.binary == "oasdiff"
        assert runner.timeout == 30

    def test_init_custom(self):
        """Test custom initialization."""
        runner = OasdiffRunner(binary="/usr/local/bin/oasdiff", timeout=60)
        assert runner.binary == "/usr/local/bin/oasdiff"
        assert runner.timeout == 60

    def test_is_available_cached(self):
        """Test is_available caching."""
        runner = OasdiffRunner()
        runner._available = True
        assert runner.is_available() is True

    def test_is_available_which_found(self):
        """Test is_available when shutil.which finds binary."""
        runner = OasdiffRunner()
        with patch("shutil.which", return_value="/usr/bin/oasdiff"):
            assert runner.is_available() is True
            assert runner._available is True

    def test_is_available_not_found(self):
        """Test is_available when binary not found."""
        runner = OasdiffRunner()
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                assert runner.is_available() is False
                assert runner._available is False

    def test_breaking_changes_not_available(self):
        """Test breaking_changes when oasdiff not installed."""
        runner = OasdiffRunner()
        runner._available = False
        result = runner.breaking_changes(Path("base.yaml"), Path("rev.yaml"))
        assert result.success is False
        assert result.oasdiff_available is False
        assert result.error and "not installed" in result.error

    def test_breaking_changes_base_not_found(self):
        """Test breaking_changes when base spec not found."""
        runner = OasdiffRunner()
        runner._available = True
        with tempfile.TemporaryDirectory() as tmpdir:
            rev = Path(tmpdir) / "rev.yaml"
            rev.write_text("openapi: 3.0.0")
            result = runner.breaking_changes(Path("/nonexistent"), rev)
        assert result.success is False
        assert result.error and "not found" in result.error

    def test_breaking_changes_revision_not_found(self):
        """Test breaking_changes when revision spec not found."""
        runner = OasdiffRunner()
        runner._available = True
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            base.write_text("openapi: 3.0.0")
            result = runner.breaking_changes(base, Path("/nonexistent"))
        assert result.success is False
        assert result.error and "not found" in result.error

    def test_breaking_changes_no_breaks(self):
        """Test breaking_changes with no breaking changes."""
        runner = OasdiffRunner()
        runner._available = True

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            rev = Path(tmpdir) / "rev.yaml"
            base.write_text("openapi: 3.0.0")
            rev.write_text("openapi: 3.0.0")

            with patch("subprocess.run", return_value=mock_result):
                result = runner.breaking_changes(base, rev)

        assert result.success is True
        assert result.has_breaking_changes is False

    def test_breaking_changes_with_breaks(self):
        """Test breaking_changes with breaking changes detected."""
        runner = OasdiffRunner()
        runner._available = True

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(
            {
                "messages": [
                    {"level": "ERR", "code": "PATH_DELETED", "path": "/api/users"}
                ]
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            rev = Path(tmpdir) / "rev.yaml"
            base.write_text("openapi: 3.0.0")
            rev.write_text("openapi: 3.0.0")

            with patch("subprocess.run", return_value=mock_result):
                result = runner.breaking_changes(base, rev)

        assert result.success is True
        assert result.has_breaking_changes is True
        assert len(result.changes) == 1

    def test_breaking_changes_error(self):
        """Test breaking_changes with command error."""
        runner = OasdiffRunner()
        runner._available = True

        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "Error message"

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            rev = Path(tmpdir) / "rev.yaml"
            base.write_text("openapi: 3.0.0")
            rev.write_text("openapi: 3.0.0")

            with patch("subprocess.run", return_value=mock_result):
                result = runner.breaking_changes(base, rev)

        assert result.success is False
        assert result.error and "Error message" in result.error

    def test_breaking_changes_timeout(self):
        """Test breaking_changes with timeout."""
        import subprocess

        runner = OasdiffRunner()
        runner._available = True

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            rev = Path(tmpdir) / "rev.yaml"
            base.write_text("openapi: 3.0.0")
            rev.write_text("openapi: 3.0.0")

            with patch(
                "subprocess.run", side_effect=subprocess.TimeoutExpired("oasdiff", 30)
            ):
                result = runner.breaking_changes(base, rev)

        assert result.success is False
        assert result.error and "timeout" in result.error

    def test_breaking_changes_file_not_found(self):
        """Test breaking_changes when binary disappears."""
        runner = OasdiffRunner()
        runner._available = True

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            rev = Path(tmpdir) / "rev.yaml"
            base.write_text("openapi: 3.0.0")
            rev.write_text("openapi: 3.0.0")

            with patch("subprocess.run", side_effect=FileNotFoundError):
                result = runner.breaking_changes(base, rev)

        assert result.success is False
        assert result.oasdiff_available is False

    def test_parse_breaking_changes_empty(self):
        """Test parsing empty output."""
        runner = OasdiffRunner()
        changes = runner._parse_breaking_changes("")
        assert changes == []

    def test_parse_breaking_changes_dict_format(self):
        """Test parsing dict format with messages."""
        runner = OasdiffRunner()
        output = json.dumps(
            {
                "messages": [
                    {"level": "ERR", "code": "TEST", "path": "/api", "message": "Test"}
                ]
            }
        )
        changes = runner._parse_breaking_changes(output)
        assert len(changes) == 1
        assert changes[0].code == "TEST"

    def test_parse_breaking_changes_list_format(self):
        """Test parsing list format."""
        runner = OasdiffRunner()
        output = json.dumps(
            [{"level": "WARN", "code": "CHANGE", "path": "/test", "message": "Changed"}]
        )
        changes = runner._parse_breaking_changes(output)
        assert len(changes) == 1
        assert changes[0].level == "WARN"

    def test_parse_breaking_changes_invalid_json(self):
        """Test parsing invalid JSON."""
        runner = OasdiffRunner()
        changes = runner._parse_breaking_changes("not json")
        assert changes == []

    def test_diff_not_available(self):
        """Test diff when oasdiff not installed."""
        runner = OasdiffRunner()
        runner._available = False
        result = runner.diff(Path("base.yaml"), Path("rev.yaml"))
        assert "error" in result
        assert result["oasdiff_available"] is False

    def test_diff_success(self):
        """Test diff with successful result."""
        runner = OasdiffRunner()
        runner._available = True

        mock_result = MagicMock()
        mock_result.stdout = json.dumps({"changes": []})
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = runner.diff(Path("base.yaml"), Path("rev.yaml"))

        assert result["changes"] == []

    def test_diff_error(self):
        """Test diff with error."""
        runner = OasdiffRunner()
        runner._available = True

        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            result = runner.diff(Path("base.yaml"), Path("rev.yaml"))

        assert "error" in result


class TestSpecDiscovery:
    """Tests for SpecDiscovery class."""

    def test_init_default(self):
        """Test default initialization."""
        discovery = SpecDiscovery()
        assert discovery.custom_paths == []

    def test_init_custom_paths(self):
        """Test initialization with custom paths."""
        discovery = SpecDiscovery(["api/spec.yaml"])
        assert "api/spec.yaml" in discovery.custom_paths

    def test_find_specs_empty_dir(self):
        """Test finding specs in empty directory."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            specs = discovery.find_specs(Path(tmpdir))
        assert specs == []

    def test_find_specs_standard_path(self):
        """Test finding spec at standard path."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = Path(tmpdir) / "openapi.yaml"
            spec_path.write_text("openapi: 3.0.0")
            specs = discovery.find_specs(Path(tmpdir))
        assert len(specs) == 1
        assert specs[0].name == "openapi.yaml"

    def test_find_specs_custom_path(self):
        """Test finding spec at custom path."""
        discovery = SpecDiscovery(["custom/api.yaml"])
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom"
            custom_dir.mkdir()
            spec_path = custom_dir / "api.yaml"
            spec_path.write_text("openapi: 3.0.0")
            specs = discovery.find_specs(Path(tmpdir))
        assert len(specs) == 1

    def test_find_specs_multiple(self):
        """Test finding multiple specs."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "openapi.yaml").write_text("openapi: 3.0.0")
            (Path(tmpdir) / "swagger.json").write_text("{}")
            specs = discovery.find_specs(Path(tmpdir))
        assert len(specs) == 2

    def test_find_specs_skips_node_modules(self):
        """Test that node_modules is skipped."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            nm = Path(tmpdir) / "node_modules"
            nm.mkdir()
            (nm / "openapi.yaml").write_text("openapi: 3.0.0")
            specs = discovery.find_specs(Path(tmpdir))
        assert len(specs) == 0

    def test_find_baseline_from_config(self):
        """Test finding baseline from config."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.yaml"
            baseline.write_text("openapi: 3.0.0")
            config = {"baseline_spec": "baseline.yaml"}
            result = discovery.find_baseline(Path(tmpdir), config)
        assert result is not None
        assert result.name == "baseline.yaml"

    def test_find_baseline_not_found(self):
        """Test finding baseline when not found."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"baseline_spec": "nonexistent.yaml"}
            result = discovery.find_baseline(Path(tmpdir), config)
        assert result is None

    def test_find_baseline_no_config(self):
        """Test finding baseline with no config."""
        discovery = SpecDiscovery()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = discovery.find_baseline(Path(tmpdir), {})
        assert result is None


class TestAPIContractValidator:
    """Tests for APIContractValidator class."""

    def test_import(self):
        """Test validator can be imported."""
        assert APIContractValidator is not None

    def test_attributes(self):
        """Test validator attributes."""
        validator = APIContractValidator()
        assert validator.dimension == "api_contract"
        assert validator.agent is None

    def test_default_config(self):
        """Test default config merging."""
        validator = APIContractValidator({"oasdiff_timeout": 60})
        assert validator.config["oasdiff_timeout"] == 60
        assert validator.config["oasdiff_binary"] == "oasdiff"

    @pytest.mark.asyncio
    async def test_validate_no_specs(self):
        """Test validate when no specs found."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = []
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = False

        result = await validator.validate()
        assert result.passed is True
        assert "No OpenAPI specs found" in result.message
        assert result.details["specs_found"] == 0

    @pytest.mark.asyncio
    async def test_validate_specs_but_no_oasdiff(self):
        """Test validate with specs but oasdiff not installed."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = False

        result = await validator.validate()
        assert result.passed is True
        assert "oasdiff not installed" in result.message
        assert result.details["specs_found"] == 1
        assert result.details["oasdiff_available"] is False

    @pytest.mark.asyncio
    async def test_validate_no_baseline(self):
        """Test validate with specs and oasdiff but no baseline."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.discovery.find_baseline.return_value = None
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True

        result = await validator.validate()
        assert result.passed is True
        assert "no baseline configured" in result.message
        assert result.details["baseline_configured"] is False

    @pytest.mark.asyncio
    async def test_validate_oasdiff_error(self):
        """Test validate when oasdiff returns error."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.discovery.find_baseline.return_value = Path("baseline.yaml")
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True
        validator.runner.breaking_changes.return_value = OasdiffResult(
            success=False,
            has_breaking_changes=False,
            error="parse error",
            oasdiff_available=True,
        )

        result = await validator.validate()
        assert result.passed is True
        assert "oasdiff error" in result.message
        assert result.details["error"] == "parse error"

    @pytest.mark.asyncio
    async def test_validate_no_breaking_changes(self):
        """Test validate with no breaking changes."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("a.yaml"), Path("b.yaml")]
        validator.discovery.find_baseline.return_value = Path("baseline.yaml")
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True
        validator.runner.breaking_changes.return_value = OasdiffResult(
            success=True,
            has_breaking_changes=False,
        )

        result = await validator.validate()
        assert result.passed is True
        assert "No breaking changes" in result.message
        assert result.details["breaking_changes_count"] == 0
        assert result.details["specs_found"] == 2

    @pytest.mark.asyncio
    async def test_validate_with_breaking_changes(self):
        """Test validate with breaking changes detected."""
        changes = [
            BreakingChange(
                level="ERR", code="PATH_DELETED", path="/api/users", message="deleted"
            ),
            BreakingChange(
                level="ERR", code="METHOD_REMOVED", path="/api/items", message="removed"
            ),
            BreakingChange(
                level="WARN",
                code="PARAM_CHANGED",
                path="/api/orders",
                message="changed",
            ),
        ]
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.discovery.find_baseline.return_value = Path("baseline.yaml")
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True
        validator.runner.breaking_changes.return_value = OasdiffResult(
            success=True,
            has_breaking_changes=True,
            changes=changes,
        )

        result = await validator.validate()
        assert result.passed is True  # Tier 3 never blocks
        assert "3 breaking changes" in result.message
        assert result.details["by_level"] == {"ERR": 2, "WARN": 1}
        assert len(result.details["breaking_changes"]) == 3
        assert result.fix_suggestion is not None
        assert "PATH_DELETED" in result.fix_suggestion

    @pytest.mark.asyncio
    async def test_validate_breaking_changes_limited_to_20(self):
        """Test that breaking changes details are limited to 20."""
        changes = [
            BreakingChange(
                level="ERR", code=f"CODE_{i}", path=f"/api/{i}", message=f"msg {i}"
            )
            for i in range(25)
        ]
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.discovery.find_baseline.return_value = Path("baseline.yaml")
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True
        validator.runner.breaking_changes.return_value = OasdiffResult(
            success=True,
            has_breaking_changes=True,
            changes=changes,
        )

        result = await validator.validate()
        assert result.details["breaking_changes_count"] == 25
        assert len(result.details["breaking_changes"]) == 20

    @pytest.mark.asyncio
    async def test_validate_fix_suggestion_limited_to_3(self):
        """Test fix_suggestion only includes first 3 codes."""
        changes = [
            BreakingChange(level="ERR", code=f"CODE_{i}", path=f"/api/{i}")
            for i in range(5)
        ]
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = [Path("openapi.yaml")]
        validator.discovery.find_baseline.return_value = Path("baseline.yaml")
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = True
        validator.runner.breaking_changes.return_value = OasdiffResult(
            success=True,
            has_breaking_changes=True,
            changes=changes,
        )

        result = await validator.validate()
        assert result.fix_suggestion is not None
        assert "CODE_0" in result.fix_suggestion
        assert "CODE_2" in result.fix_suggestion
        assert "CODE_4" not in result.fix_suggestion

    @pytest.mark.asyncio
    async def test_validate_duration_ms(self):
        """Test that duration_ms is set."""
        validator = APIContractValidator()
        validator.discovery = MagicMock()
        validator.discovery.find_specs.return_value = []
        validator.runner = MagicMock()
        validator.runner.is_available.return_value = False

        result = await validator.validate()
        assert result.duration_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
