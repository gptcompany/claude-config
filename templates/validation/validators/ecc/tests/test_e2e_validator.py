"""
Tests for E2EValidator.

Tests the Playwright E2E validation logic with mocked subprocess calls.
Does NOT require Playwright to be installed - all tests use mocks.
"""

import subprocess
from unittest.mock import MagicMock, patch
import json
import pytest

from ..e2e_validator import E2EValidator
from ..base import ValidationTier


class TestE2EValidatorBasics:
    """Test E2EValidator class attributes and initialization."""

    def test_dimension(self):
        """E2EValidator has correct dimension."""
        assert E2EValidator.dimension == "e2e_validation"

    def test_tier_is_blocker(self):
        """E2EValidator is Tier 1 (BLOCKER)."""
        assert E2EValidator.tier == ValidationTier.BLOCKER

    def test_agent_name(self):
        """E2EValidator links to e2e-runner agent."""
        assert E2EValidator.agent == "e2e-runner"

    def test_default_timeout(self):
        """E2EValidator has 5-minute timeout for E2E tests."""
        assert E2EValidator.timeout == 300


class TestE2EValidatorSkip:
    """Test E2EValidator skip conditions."""

    @pytest.mark.asyncio
    async def test_skip_no_playwright_config(self, tmp_path):
        """Skip cleanly when no playwright.config.ts exists."""
        validator = E2EValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert "skipped" in result.message.lower() or "skip" in result.message.lower()
        assert result.details.get("skipped") is True

    @pytest.mark.asyncio
    async def test_skip_npx_not_installed(self, tmp_path):
        """Skip cleanly when npx is not installed."""
        # Create a config file so we proceed to npx execution
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        # Mock _run_tool to raise FileNotFoundError
        async def mock_run_tool(*args, **kwargs):
            raise FileNotFoundError("npx not found")

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is True
        assert "skipped" in result.message.lower()


class TestE2EValidatorSuccess:
    """Test E2EValidator success scenarios."""

    @pytest.mark.asyncio
    async def test_all_tests_pass(self, tmp_path):
        """Pass when all tests pass."""
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "stats": {
                    "expected": 10,
                    "unexpected": 0,
                    "flaky": 0,
                    "skipped": 0,
                    "duration": 5000,
                }
            }
        )
        mock_result.stderr = ""

        async def mock_run_tool(*args, **kwargs):
            return mock_result

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is True
        assert result.details["total"] == 10
        assert result.details["passed"] == 10
        assert result.details["failed"] == 0
        assert result.fix_suggestion is None

    @pytest.mark.asyncio
    async def test_flaky_tests_allowed(self, tmp_path):
        """Pass when only flaky tests exist (no hard failures)."""
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "stats": {
                    "expected": 8,
                    "unexpected": 0,
                    "flaky": 2,
                    "skipped": 0,
                }
            }
        )
        mock_result.stderr = ""

        async def mock_run_tool(*args, **kwargs):
            return mock_result

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is True
        assert result.details["flaky"] == 2
        assert "flaky" in result.message


class TestE2EValidatorFailure:
    """Test E2EValidator failure scenarios."""

    @pytest.mark.asyncio
    async def test_failed_tests(self, tmp_path):
        """Fail when tests fail."""
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(
            {
                "stats": {
                    "expected": 8,
                    "unexpected": 2,
                    "flaky": 0,
                    "skipped": 0,
                }
            }
        )
        mock_result.stderr = "2 tests failed"

        async def mock_run_tool(*args, **kwargs):
            return mock_result

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is False
        assert result.details["failed"] == 2
        assert result.fix_suggestion is not None
        assert "debug" in result.fix_suggestion.lower()
        assert result.agent == "e2e-runner"

    @pytest.mark.asyncio
    async def test_timeout(self, tmp_path):
        """Error result when tests timeout."""
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        async def mock_run_tool(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="npx playwright test", timeout=300)

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is False
        assert "timed out" in result.message.lower()

    @pytest.mark.asyncio
    async def test_non_json_output_failure(self, tmp_path):
        """Fail when exit code != 0 and no JSON output."""
        (tmp_path / "playwright.config.ts").write_text("export default {}")

        validator = E2EValidator(project_path=tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: Something went wrong"
        mock_result.stderr = "Stack trace..."

        async def mock_run_tool(*args, **kwargs):
            return mock_result

        with patch.object(validator, "_run_tool", side_effect=mock_run_tool):
            result = await validator.validate()

        assert result.passed is False
        assert result.fix_suggestion is not None
