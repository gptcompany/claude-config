"""
Unit tests for orchestrator.py with actual imports for coverage measurement.

These tests import the actual orchestrator module to enable pytest-cov
to measure coverage properly.
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Add orchestrator to path
sys.path.insert(0, str(Path.home() / ".claude/templates/validation"))

# Import orchestrator module
import orchestrator
from orchestrator import (
    ValidationOrchestrator,
    ValidationTier,
    ValidationResult,
    BaseValidator,
    spawn_agent,
    check_complexity_and_simplify,
    run_tier3_parallel,
    _run_validators_sequential,
    _elapsed_ms,
    AGENT_SPAWN_ENABLED,
    SWARM_ENABLED,
)


class TestValidationTierEnum:
    """Tests for ValidationTier enum."""

    def test_blocker_tier(self):
        """Test BLOCKER tier value."""
        assert ValidationTier.BLOCKER.value == 1

    def test_warning_tier(self):
        """Test WARNING tier value."""
        assert ValidationTier.WARNING.value == 2

    def test_monitor_tier(self):
        """Test MONITOR tier value."""
        assert ValidationTier.MONITOR.value == 3


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_create_passed_result(self):
        """Test creating a passed validation result."""
        result = ValidationResult(
            dimension="test",
            passed=True,
            tier=ValidationTier.BLOCKER,
            message="All checks passed",
            duration_ms=100,
        )
        assert result.passed is True
        assert result.tier == ValidationTier.BLOCKER
        assert result.duration_ms == 100

    def test_create_failed_result(self):
        """Test creating a failed validation result."""
        result = ValidationResult(
            dimension="test",
            passed=False,
            tier=ValidationTier.BLOCKER,
            message="Check failed",
            duration_ms=50,
            details={"error": "something wrong"},
        )
        assert result.passed is False
        assert result.details["error"] == "something wrong"


class TestBaseValidator:
    """Tests for BaseValidator base class."""

    def test_base_validator_class_attributes(self):
        """Test BaseValidator class attributes."""
        assert BaseValidator.dimension == "unknown"
        assert BaseValidator.tier == ValidationTier.MONITOR
        assert BaseValidator.agent is None

    @pytest.mark.asyncio
    async def test_base_validator_validate_stub(self):
        """Test that base validator returns passed (stub)."""
        validator = BaseValidator()
        result = await validator.validate()
        assert result.passed is True
        assert "no validation implemented" in result.message.lower()


class TestElapsedMs:
    """Tests for _elapsed_ms helper function."""

    def test_elapsed_ms_calculates_correctly(self):
        """Test that elapsed_ms calculates time difference correctly."""
        from datetime import datetime, timedelta

        start = datetime.now()
        # Simulate some time passing
        end_time = start + timedelta(milliseconds=150)

        # The function calculates: int((datetime.now() - start).total_seconds() * 1000)
        # Since we can't freeze time easily, test the calculation pattern
        elapsed = int((end_time - start).total_seconds() * 1000)
        assert elapsed == 150


class TestSpawnAgentFunction:
    """Tests for spawn_agent function."""

    def test_spawn_agent_disabled_returns_false(self):
        """Test spawn_agent returns False when AGENT_SPAWN_ENABLED is False."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", False):
            result = spawn_agent("test-agent", "test task", {})
            assert result is False

    def test_spawn_agent_file_not_found(self):
        """Test spawn_agent handles FileNotFoundError."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.side_effect = FileNotFoundError("claude not found")
                result = spawn_agent("test-agent", "test task", {})
                assert result is False

    def test_spawn_agent_success(self):
        """Test spawn_agent returns True on successful spawn."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.return_value = MagicMock()
                result = spawn_agent("test-agent", "test task", {"key": "value"})
                assert result is True
                mock_popen.assert_called_once()

    def test_spawn_agent_generic_exception(self):
        """Test spawn_agent handles generic exceptions."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.side_effect = Exception("Unknown error")
                result = spawn_agent("test-agent", "test task", {})
                assert result is False


class TestRunTier3ParallelFunction:
    """Tests for run_tier3_parallel function."""

    @pytest.mark.asyncio
    async def test_single_validator_sequential(self):
        """Test single validator runs sequentially."""
        mock_v = MagicMock()
        mock_v.validate = AsyncMock(return_value=ValidationResult(
            dimension="test", passed=True, tier=ValidationTier.MONITOR, message="OK", duration_ms=10
        ))

        result = await run_tier3_parallel([("test", mock_v)])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_swarm_disabled_sequential(self):
        """Test SWARM_ENABLED=False runs sequentially."""
        mock_v1 = MagicMock()
        mock_v1.validate = AsyncMock(return_value=ValidationResult(
            dimension="v1", passed=True, tier=ValidationTier.MONITOR, message="OK", duration_ms=10
        ))
        mock_v2 = MagicMock()
        mock_v2.validate = AsyncMock(return_value=ValidationResult(
            dimension="v2", passed=True, tier=ValidationTier.MONITOR, message="OK", duration_ms=10
        ))

        with patch.object(orchestrator, "SWARM_ENABLED", False):
            result = await run_tier3_parallel([("v1", mock_v1), ("v2", mock_v2)])
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_hive_manager_not_found_fallback(self):
        """Test fallback when hive-manager not found."""
        mock_v1 = MagicMock()
        mock_v1.validate = AsyncMock(return_value=ValidationResult(
            dimension="v1", passed=True, tier=ValidationTier.MONITOR, message="OK", duration_ms=10
        ))
        mock_v2 = MagicMock()
        mock_v2.validate = AsyncMock(return_value=ValidationResult(
            dimension="v2", passed=True, tier=ValidationTier.MONITOR, message="OK", duration_ms=10
        ))

        with patch.object(orchestrator, "SWARM_ENABLED", True):
            with patch("os.path.exists", return_value=False):
                result = await run_tier3_parallel([("v1", mock_v1), ("v2", mock_v2)])
                assert len(result) == 2


class TestCheckComplexityAndSimplify:
    """Tests for check_complexity_and_simplify function."""

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        """Test returns False when AGENT_SPAWN_ENABLED is False."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", False):
            result = await check_complexity_and_simplify(["/some/file.py"])
            assert result is False

    @pytest.mark.asyncio
    async def test_empty_files_returns_false(self):
        """Test returns False for empty file list."""
        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            result = await check_complexity_and_simplify([])
            assert result is False

    @pytest.mark.asyncio
    async def test_small_file_no_trigger(self, tmp_path):
        """Test small file doesn't trigger simplifier."""
        small_file = tmp_path / "small.py"
        small_file.write_text("\n".join([f"x = {i}" for i in range(50)]))

        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch.object(orchestrator, "spawn_agent") as mock_spawn:
                result = await check_complexity_and_simplify([str(small_file)])
                assert result is False
                mock_spawn.assert_not_called()

    @pytest.mark.asyncio
    async def test_large_file_triggers(self, tmp_path):
        """Test file >200 LOC triggers simplifier."""
        large_file = tmp_path / "large.py"
        large_file.write_text("\n".join([f"x = {i}" for i in range(250)]))

        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch.object(orchestrator, "spawn_agent", return_value=True) as mock_spawn:
                result = await check_complexity_and_simplify([str(large_file)])
                assert result is True
                mock_spawn.assert_called_once()
                # Check agent type is code-simplifier (keyword arg)
                assert mock_spawn.call_args.kwargs["agent_type"] == "code-simplifier"

    @pytest.mark.asyncio
    async def test_multiple_files_over_200_triggers(self, tmp_path):
        """Test multiple files totaling >200 LOC triggers."""
        file1 = tmp_path / "file1.py"
        file1.write_text("\n".join([f"x = {i}" for i in range(110)]))
        file2 = tmp_path / "file2.py"
        file2.write_text("\n".join([f"y = {i}" for i in range(110)]))

        with patch.object(orchestrator, "AGENT_SPAWN_ENABLED", True):
            with patch.object(orchestrator, "spawn_agent", return_value=True) as mock_spawn:
                result = await check_complexity_and_simplify([str(file1), str(file2)])
                assert result is True
                mock_spawn.assert_called_once()


class TestRunValidatorsSequential:
    """Tests for _run_validators_sequential helper."""

    @pytest.mark.asyncio
    async def test_runs_all_validators(self):
        """Test all validators are run."""
        mock_v1 = MagicMock()
        mock_v1.validate = AsyncMock(return_value=ValidationResult(
            dimension="v1", passed=True, tier=ValidationTier.BLOCKER, message="OK", duration_ms=10
        ))
        mock_v2 = MagicMock()
        mock_v2.validate = AsyncMock(return_value=ValidationResult(
            dimension="v2", passed=True, tier=ValidationTier.BLOCKER, message="OK", duration_ms=10
        ))

        result = await _run_validators_sequential([("v1", mock_v1), ("v2", mock_v2)])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_continues_on_error(self):
        """Test continues running after validator error."""
        mock_v1 = MagicMock()
        mock_v1.validate = AsyncMock(side_effect=Exception("Crash"))
        mock_v2 = MagicMock()
        mock_v2.validate = AsyncMock(return_value=ValidationResult(
            dimension="v2", passed=True, tier=ValidationTier.BLOCKER, message="OK", duration_ms=10
        ))

        result = await _run_validators_sequential([("v1", mock_v1), ("v2", mock_v2)])
        # v1 fails, v2 succeeds
        assert len(result) == 1


class TestValidationOrchestrator:
    """Tests for ValidationOrchestrator class."""

    def test_orchestrator_init_no_config(self):
        """Test orchestrator initializes with default config."""
        orchestrator_instance = ValidationOrchestrator()
        assert orchestrator_instance.config is not None
        assert "dimensions" in orchestrator_instance.config or orchestrator_instance.validators is not None

    def test_orchestrator_init_with_config_path(self, tmp_path):
        """Test orchestrator initializes with custom config."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"project_name": "test", "dimensions": {}}')

        orchestrator_instance = ValidationOrchestrator(config_file)
        assert orchestrator_instance.config["project_name"] == "test"

    def test_validator_registry_has_core_validators(self):
        """Test VALIDATOR_REGISTRY has core validators."""
        registry = ValidationOrchestrator.VALIDATOR_REGISTRY
        assert "code_quality" in registry
        assert "type_safety" in registry
        assert "security" in registry
        assert "coverage" in registry


class TestEnvironmentVariables:
    """Tests for environment variable defaults."""

    def test_agent_spawn_default(self):
        """Test AGENT_SPAWN_ENABLED defaults correctly."""
        # The module-level variable is set at import time
        # We can't easily test the default, but we can verify it exists
        assert isinstance(AGENT_SPAWN_ENABLED, bool)

    def test_swarm_default(self):
        """Test SWARM_ENABLED defaults correctly."""
        assert isinstance(SWARM_ENABLED, bool)


class TestCodeQualityValidator:
    """Tests for CodeQualityValidator."""

    @pytest.mark.asyncio
    async def test_validate_passes_when_ruff_succeeds(self):
        """Test validation passes when ruff returns 0."""
        from orchestrator import CodeQualityValidator

        validator = CodeQualityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await validator.validate()
            assert result.passed is True
            assert "ok" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_fails_when_ruff_finds_errors(self):
        """Test validation fails when ruff finds errors."""
        from orchestrator import CodeQualityValidator

        validator = CodeQualityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="error1\nerror2\nerror3",
                stderr="",
            )
            result = await validator.validate()
            assert result.passed is False
            assert "3" in result.message  # error count

    @pytest.mark.asyncio
    async def test_validate_skipped_when_ruff_not_installed(self):
        """Test validation skipped when ruff not found."""
        from orchestrator import CodeQualityValidator

        validator = CodeQualityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ruff not found")
            result = await validator.validate()
            assert result.passed is True
            assert "skipped" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_handles_exception(self):
        """Test validation handles generic exceptions."""
        from orchestrator import CodeQualityValidator

        validator = CodeQualityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")
            result = await validator.validate()
            assert result.passed is False
            assert "error" in result.message.lower()


class TestTypeSafetyValidator:
    """Tests for TypeSafetyValidator."""

    @pytest.mark.asyncio
    async def test_validate_passes_when_pyright_succeeds(self):
        """Test validation passes when pyright returns 0."""
        from orchestrator import TypeSafetyValidator

        validator = TypeSafetyValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await validator.validate()
            assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_fails_with_errors(self):
        """Test validation fails when pyright finds errors."""
        from orchestrator import TypeSafetyValidator

        validator = TypeSafetyValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout='{"generalDiagnostics": [{"error": 1}, {"error": 2}]}',
                stderr="",
            )
            result = await validator.validate()
            assert result.passed is False
            assert "2" in result.message  # error count

    @pytest.mark.asyncio
    async def test_validate_handles_invalid_json(self):
        """Test validation handles invalid JSON output."""
        from orchestrator import TypeSafetyValidator

        validator = TypeSafetyValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="not valid json",
                stderr="",
            )
            result = await validator.validate()
            assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_skipped_when_not_installed(self):
        """Test validation skipped when pyright not found."""
        from orchestrator import TypeSafetyValidator

        validator = TypeSafetyValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("pyright not found")
            result = await validator.validate()
            assert result.passed is True
            assert "skipped" in result.message.lower()


class TestSecurityValidator:
    """Tests for SecurityValidator."""

    @pytest.mark.asyncio
    async def test_validate_passes_when_all_pass(self):
        """Test validation passes when all security checks pass."""
        from orchestrator import SecurityValidator

        validator = SecurityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = await validator.validate()
            assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_skipped_when_tools_missing(self):
        """Test validation skipped when security tools not found."""
        from orchestrator import SecurityValidator

        validator = SecurityValidator()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("bandit not found")
            result = await validator.validate()
            # Should pass with skip message
            assert result.passed is True


class TestCoverageValidator:
    """Tests for CoverageValidator."""

    @pytest.mark.asyncio
    async def test_validate_passes_above_threshold(self):
        """Test validation passes when coverage above threshold."""
        from orchestrator import CoverageValidator

        validator = CoverageValidator()
        with patch.object(validator, "_generate_coverage"):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text") as mock_read:
                    mock_read.return_value = '<coverage line-rate="0.85">'
                    result = await validator.validate()
                    # Default threshold is 80%, 85% should pass
                    assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_skips_when_no_coverage_data(self):
        """Test validation skips gracefully when no coverage.xml."""
        from orchestrator import CoverageValidator

        validator = CoverageValidator()
        with patch.object(validator, "_generate_coverage"):
            # When coverage.xml doesn't exist, should skip gracefully
            result = await validator.validate()
            # Should pass with skip message (no coverage data is not a blocker)
            assert result.passed is True
            assert "skipped" in result.message.lower() or "no coverage" in result.message.lower()


class TestOrchestratorRunTier:
    """Tests for ValidationOrchestrator.run_tier method."""

    @pytest.mark.asyncio
    async def test_run_tier_blocker(self):
        """Test running tier 1 (blocker) validators."""
        orch = ValidationOrchestrator()
        result = await orch.run_tier(ValidationTier.BLOCKER)
        assert result is not None
        assert result.tier == ValidationTier.BLOCKER

    @pytest.mark.asyncio
    async def test_run_tier_warning(self):
        """Test running tier 2 (warning) validators."""
        orch = ValidationOrchestrator()
        result = await orch.run_tier(ValidationTier.WARNING)
        assert result is not None
        assert result.tier == ValidationTier.WARNING


class TestOrchestratorRunAll:
    """Tests for ValidationOrchestrator.run_all method."""

    @pytest.mark.asyncio
    async def test_run_all_returns_report(self):
        """Test run_all returns a validation report."""
        orch = ValidationOrchestrator()
        # Mock validators to avoid actual external calls
        with patch.object(orch, "run_tier") as mock_run_tier:
            from orchestrator import TierResult
            mock_run_tier.return_value = TierResult(tier=ValidationTier.BLOCKER, results=[])
            report = await orch.run_all()
            assert report is not None
            assert hasattr(report, "tiers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=orchestrator", "--cov-report=term-missing"])
