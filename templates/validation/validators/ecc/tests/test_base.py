"""
Tests for ECCValidatorBase.

Tests the base class helpers used by all ECC validators.
"""

import subprocess
from unittest.mock import patch, MagicMock

from ..base import ECCValidatorBase, ValidationResult, ValidationTier


class ConcreteValidator(ECCValidatorBase):
    """Concrete implementation for testing abstract base class."""

    dimension = "test_dimension"
    tier = ValidationTier.MONITOR
    agent = "test-agent"

    async def validate(self) -> ValidationResult:
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="Test passed",
            details={},
        )


class TestECCValidatorBaseAttributes:
    """Test ECCValidatorBase class attributes."""

    def test_default_timeout(self):
        """Default timeout is 300 seconds (5 min)."""
        validator = ConcreteValidator()
        assert validator.timeout == 300

    def test_agent_attribute(self):
        """Agent attribute is set correctly."""
        validator = ConcreteValidator()
        assert validator.agent == "test-agent"


class TestECCValidatorBaseCheckToolInstalled:
    """Test _check_tool_installed method."""

    def test_tool_exists(self):
        """Return True when tool exists."""
        validator = ConcreteValidator()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = validator._check_tool_installed("python3")

        assert result is True
        mock_run.assert_called_once()

    def test_tool_not_exists(self):
        """Return False when tool not found."""
        validator = ConcreteValidator()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = validator._check_tool_installed("nonexistent-tool-xyz")

        assert result is False

    def test_which_timeout(self):
        """Return False on timeout."""
        validator = ConcreteValidator()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("which", 5)
            result = validator._check_tool_installed("slow-tool")

        assert result is False

    def test_which_file_not_found(self):
        """Return False when which binary not found."""
        validator = ConcreteValidator()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("which not found")
            result = validator._check_tool_installed("some-tool")

        assert result is False


class TestECCValidatorBaseParseJson:
    """Test _parse_json_output method."""

    def test_valid_json(self):
        """Parse valid JSON."""
        validator = ConcreteValidator()
        result = validator._parse_json_output('{"key": "value", "count": 42}')
        assert result == {"key": "value", "count": 42}

    def test_invalid_json(self):
        """Return empty dict on invalid JSON."""
        validator = ConcreteValidator()
        result = validator._parse_json_output("not valid json")
        assert result == {}

    def test_empty_string(self):
        """Return empty dict on empty string."""
        validator = ConcreteValidator()
        result = validator._parse_json_output("")
        assert result == {}


class TestECCValidatorBaseSkipResult:
    """Test _skip_result method."""

    def test_skip_result_fields(self):
        """Skip result has correct fields."""
        validator = ConcreteValidator()
        result = validator._skip_result("No config file found")

        assert result.passed is True
        assert "skipped" in result.message
        assert result.details["skipped"] is True
        assert result.details["reason"] == "No config file found"


class TestECCValidatorBaseErrorResult:
    """Test _error_result method."""

    def test_error_result_fields(self):
        """Error result has correct fields."""
        validator = ConcreteValidator()
        result = validator._error_result("Connection failed", duration_ms=150)

        assert result.passed is False
        assert "Error" in result.message
        assert result.details["error"] == "Connection failed"
        assert result.duration_ms == 150
        assert result.agent == "test-agent"
