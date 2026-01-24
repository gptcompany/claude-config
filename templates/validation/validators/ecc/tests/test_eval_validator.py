"""
Tests for EvalValidator.

Tests eval metrics extraction from JSON result files.
"""

import json
import pytest

from ..eval_validator import EvalValidator
from ..base import ValidationTier


class TestEvalValidatorBasics:
    """Test EvalValidator class attributes."""

    def test_dimension(self):
        """EvalValidator has correct dimension."""
        assert EvalValidator.dimension == "eval_metrics"

    def test_tier_is_monitor(self):
        """EvalValidator is Tier 3 (MONITOR)."""
        assert EvalValidator.tier == ValidationTier.MONITOR

    def test_agent_name(self):
        """EvalValidator links to eval-harness agent."""
        assert EvalValidator.agent == "eval-harness"


class TestEvalValidatorNoEvals:
    """Test EvalValidator when no evals exist."""

    @pytest.mark.asyncio
    async def test_no_evals_directory(self, tmp_path):
        """Pass when no .claude/evals/ directory exists."""
        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True  # Always passes (monitoring)
        assert result.details.get("has_evals") is False

    @pytest.mark.asyncio
    async def test_empty_evals_directory(self, tmp_path):
        """Pass when evals directory is empty."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("results_found") == 0


class TestEvalValidatorMetrics:
    """Test EvalValidator metric extraction."""

    @pytest.mark.asyncio
    async def test_extract_pass_at_1(self, tmp_path):
        """Extract pass@1 metric from results."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        results_file = evals_dir / "results.json"
        results_file.write_text(
            json.dumps(
                {
                    "pass_at_1": 0.85,
                    "n_samples": 100,
                }
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("pass_at_1") == 0.85
        assert "pass@1=85%" in result.message

    @pytest.mark.asyncio
    async def test_extract_multiple_pass_at_k(self, tmp_path):
        """Extract pass@1, pass@5, pass@10 metrics."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        results_file = evals_dir / "results.json"
        results_file.write_text(
            json.dumps(
                {
                    "pass_at_1": 0.75,
                    "pass_at_5": 0.90,
                    "pass_at_10": 0.95,
                }
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("pass_at_1") == 0.75
        assert result.details.get("pass_at_5") == 0.90
        assert result.details.get("pass_at_10") == 0.95

    @pytest.mark.asyncio
    async def test_extract_passed_total_format(self, tmp_path):
        """Extract metrics from passed/total format."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        results_file = evals_dir / "results.json"
        results_file.write_text(
            json.dumps(
                {
                    "passed": 80,
                    "total": 100,
                }
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("pass_at_1") == 0.8

    @pytest.mark.asyncio
    async def test_multiple_result_files(self, tmp_path):
        """Aggregate metrics from multiple result files."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        # Multiple eval results
        (evals_dir / "eval1.json").write_text(
            json.dumps(
                {
                    "pass_at_1": 0.80,
                }
            )
        )
        (evals_dir / "eval2.json").write_text(
            json.dumps(
                {
                    "pass_at_1": 0.90,
                }
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("total_evals") == 2
        # Average of 0.80 and 0.90 = 0.85
        assert result.details.get("pass_at_1") == 0.85

    @pytest.mark.asyncio
    async def test_list_format_results(self, tmp_path):
        """Handle results in list format."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        results_file = evals_dir / "results.json"
        results_file.write_text(
            json.dumps(
                [
                    {"pass_at_1": 0.70},
                    {"pass_at_1": 0.80},
                    {"pass_at_1": 0.90},
                ]
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details.get("total_evals") == 3
        # Average of 0.70, 0.80, 0.90 = 0.8
        assert result.details.get("pass_at_1") == 0.8


class TestEvalValidatorAlwaysPasses:
    """Test that EvalValidator always passes (Tier 3 monitoring)."""

    @pytest.mark.asyncio
    async def test_always_passes_no_evals(self, tmp_path):
        """Pass even with no evals."""
        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_always_passes_with_evals(self, tmp_path):
        """Pass even with poor eval results."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        # Poor results
        (evals_dir / "results.json").write_text(
            json.dumps(
                {
                    "pass_at_1": 0.10,  # 10% pass rate
                }
            )
        )

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True  # Still passes (monitoring only)
        assert result.details.get("pass_at_1") == 0.1

    @pytest.mark.asyncio
    async def test_always_passes_invalid_json(self, tmp_path):
        """Pass even with invalid JSON files."""
        evals_dir = tmp_path / ".claude" / "evals"
        evals_dir.mkdir(parents=True)

        (evals_dir / "bad.json").write_text("not valid json {")

        validator = EvalValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
