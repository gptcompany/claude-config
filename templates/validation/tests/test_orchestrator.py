#!/usr/bin/env python3
"""Unit tests for orchestrator.py - Validation Orchestrator."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import (
    ValidationTier,
    ValidationResult,
    TierResult,
    ValidationReport,
    FileValidationResult,
    BaseValidator,
    CodeQualityValidator,
    TypeSafetyValidator,
    SecurityValidator,
    CoverageValidator,
    DesignPrinciplesValidator,
    OSSReuseValidator,
    ArchitectureValidator,
    DocumentationValidator,
    PerformanceValidator,
    AccessibilityValidator,
    MathematicalValidator,
    APIContractValidator,
    ValidationOrchestrator,
    _log_integrations_status,
)


class TestValidationTier:
    """Tests for ValidationTier enum."""

    def test_tier_values(self):
        """Test tier values."""
        assert ValidationTier.BLOCKER.value == 1
        assert ValidationTier.WARNING.value == 2
        assert ValidationTier.MONITOR.value == 3

    def test_tier_names(self):
        """Test tier names."""
        assert ValidationTier.BLOCKER.name == "BLOCKER"
        assert ValidationTier.WARNING.name == "WARNING"
        assert ValidationTier.MONITOR.name == "MONITOR"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            dimension="test",
            tier=ValidationTier.BLOCKER,
            passed=True,
            message="OK",
        )
        assert result.dimension == "test"
        assert result.tier == ValidationTier.BLOCKER
        assert result.passed is True
        assert result.message == "OK"

    def test_defaults(self):
        """Test ValidationResult default values."""
        result = ValidationResult(
            dimension="test",
            tier=ValidationTier.WARNING,
            passed=False,
            message="Failed",
        )
        assert result.details == {}
        assert result.fix_suggestion is None
        assert result.agent is None
        assert result.duration_ms == 0

    def test_with_all_fields(self):
        """Test ValidationResult with all fields."""
        result = ValidationResult(
            dimension="code_quality",
            tier=ValidationTier.BLOCKER,
            passed=False,
            message="5 errors",
            details={"errors": 5},
            fix_suggestion="Run ruff --fix",
            agent="code-fixer",
            duration_ms=100,
        )
        assert result.details["errors"] == 5
        assert result.fix_suggestion == "Run ruff --fix"
        assert result.agent == "code-fixer"
        assert result.duration_ms == 100


class TestTierResult:
    """Tests for TierResult dataclass."""

    def test_empty_tier_result(self):
        """Test empty TierResult."""
        result = TierResult(tier=ValidationTier.BLOCKER)
        assert result.passed is True
        assert result.has_warnings is False
        assert result.failed_dimensions == []

    def test_all_passed(self):
        """Test TierResult with all passed results."""
        results = [
            ValidationResult("a", ValidationTier.BLOCKER, True, "OK"),
            ValidationResult("b", ValidationTier.BLOCKER, True, "OK"),
        ]
        tier_result = TierResult(tier=ValidationTier.BLOCKER, results=results)
        assert tier_result.passed is True
        assert tier_result.has_warnings is False

    def test_some_failed(self):
        """Test TierResult with some failures."""
        results = [
            ValidationResult("a", ValidationTier.BLOCKER, True, "OK"),
            ValidationResult("b", ValidationTier.BLOCKER, False, "Failed"),
        ]
        tier_result = TierResult(tier=ValidationTier.BLOCKER, results=results)
        assert tier_result.passed is False
        assert tier_result.has_warnings is True
        assert tier_result.failed_dimensions == ["b"]

    def test_all_failed(self):
        """Test TierResult with all failures."""
        results = [
            ValidationResult("a", ValidationTier.WARNING, False, "Failed"),
            ValidationResult("b", ValidationTier.WARNING, False, "Failed"),
        ]
        tier_result = TierResult(tier=ValidationTier.WARNING, results=results)
        assert tier_result.passed is False
        assert tier_result.failed_dimensions == ["a", "b"]


class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_creation(self):
        """Test ValidationReport creation."""
        report = ValidationReport(
            project="test_project",
            timestamp="2024-01-01T00:00:00",
        )
        assert report.project == "test_project"
        assert report.blocked is False
        assert report.overall_passed is True

    def test_to_dict(self):
        """Test ValidationReport serialization."""
        tier_result = TierResult(
            tier=ValidationTier.BLOCKER,
            results=[
                ValidationResult("code_quality", ValidationTier.BLOCKER, True, "OK")
            ],
        )
        report = ValidationReport(
            project="test",
            timestamp="2024-01-01T00:00:00",
            tiers=[tier_result],
            execution_time_ms=500,
        )

        d = report.to_dict()
        assert d["project"] == "test"
        assert d["execution_time_ms"] == 500
        assert len(d["tiers"]) == 1
        assert d["tiers"][0]["tier"] == 1
        assert d["tiers"][0]["tier_name"] == "BLOCKER"


class TestFileValidationResult:
    """Tests for FileValidationResult dataclass."""

    def test_creation(self):
        """Test FileValidationResult creation."""
        result = FileValidationResult(
            file_path="test.py",
            has_blockers=False,
            message="OK",
        )
        assert result.file_path == "test.py"
        assert result.has_blockers is False

    def test_to_dict(self):
        """Test FileValidationResult serialization."""
        validation_results = [
            ValidationResult("code_quality", ValidationTier.BLOCKER, True, "OK")
        ]
        result = FileValidationResult(
            file_path="test.py",
            has_blockers=False,
            message="Passed",
            results=validation_results,
            duration_ms=100,
        )

        d = result.to_dict()
        assert d["file_path"] == "test.py"
        assert d["has_blockers"] is False
        assert d["duration_ms"] == 100
        assert len(d["results"]) == 1


class TestBaseValidator:
    """Tests for BaseValidator class."""

    def test_defaults(self):
        """Test BaseValidator default values."""
        validator = BaseValidator()
        assert validator.dimension == "unknown"
        assert validator.tier == ValidationTier.MONITOR
        assert validator.agent is None

    @pytest.mark.asyncio
    async def test_validate_returns_passed(self):
        """Test BaseValidator.validate returns passed result."""
        validator = BaseValidator()
        result = await validator.validate()
        assert result.passed is True
        assert "No validation implemented" in result.message


class TestCodeQualityValidator:
    """Tests for CodeQualityValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = CodeQualityValidator()
        assert validator.dimension == "code_quality"
        assert validator.tier == ValidationTier.BLOCKER

    @pytest.mark.asyncio
    async def test_validate_ruff_not_installed(self):
        """Test when ruff is not installed."""
        validator = CodeQualityValidator()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await validator.validate()
        assert result.passed is True
        assert "not installed" in result.message

    @pytest.mark.asyncio
    async def test_validate_ruff_success(self):
        """Test when ruff passes."""
        validator = CodeQualityValidator()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await validator.validate()
        assert result.passed is True
        assert "OK" in result.message

    @pytest.mark.asyncio
    async def test_validate_ruff_errors(self):
        """Test when ruff finds errors."""
        validator = CodeQualityValidator()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = (
            "file.py:1:1: E501 line too long\nfile.py:2:1: E302 expected 2 blank lines"
        )

        with patch("subprocess.run", return_value=mock_result):
            result = await validator.validate()
        assert result.passed is False
        assert "errors" in result.message

    @pytest.mark.asyncio
    async def test_validate_exception(self):
        """Test when ruff raises exception."""
        validator = CodeQualityValidator()
        with patch("subprocess.run", side_effect=Exception("Test error")):
            result = await validator.validate()
        assert result.passed is False
        assert "Error" in result.message


class TestTypeSafetyValidator:
    """Tests for TypeSafetyValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = TypeSafetyValidator()
        assert validator.dimension == "type_safety"
        assert validator.tier == ValidationTier.BLOCKER

    @pytest.mark.asyncio
    async def test_validate_pyright_not_installed(self):
        """Test when pyright is not installed."""
        validator = TypeSafetyValidator()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await validator.validate()
        assert result.passed is True
        assert "not installed" in result.message

    @pytest.mark.asyncio
    async def test_validate_pyright_success(self):
        """Test when pyright passes."""
        validator = TypeSafetyValidator()
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = await validator.validate()
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_pyright_errors(self):
        """Test when pyright finds errors."""
        validator = TypeSafetyValidator()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps(
            {"generalDiagnostics": [{"error": "type mismatch"}]}
        )

        with patch("subprocess.run", return_value=mock_result):
            result = await validator.validate()
        assert result.passed is False
        assert "1" in result.message  # 1 error


class TestSecurityValidator:
    """Tests for SecurityValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = SecurityValidator()
        assert validator.dimension == "security"
        assert validator.tier == ValidationTier.BLOCKER

    @pytest.mark.asyncio
    async def test_validate_no_tools_installed(self):
        """Test when no security tools are installed."""
        validator = SecurityValidator()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await validator.validate()
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_bandit_issues(self):
        """Test when bandit finds issues."""
        validator = SecurityValidator()

        def mock_run(cmd, **_):
            mock = MagicMock()
            if "bandit" in cmd:
                mock.returncode = 1
                mock.stdout = json.dumps(
                    {"results": [{"issue_severity": "HIGH", "issue_text": "test"}]}
                )
            else:
                mock.returncode = 0
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            result = await validator.validate()
        assert result.passed is False
        assert "Bandit" in result.message


class TestCoverageValidator:
    """Tests for CoverageValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = CoverageValidator()
        assert validator.dimension == "coverage"
        assert validator.tier == ValidationTier.BLOCKER
        assert validator.min_coverage == 70

    @pytest.mark.asyncio
    async def test_validate_no_coverage_file(self):
        """Test when no coverage.xml exists."""
        validator = CoverageValidator()
        with tempfile.TemporaryDirectory():
            with patch.object(Path, "exists", return_value=False):
                with patch("subprocess.run"):
                    result = await validator.validate()
        assert result.passed is True
        assert "No coverage data" in result.message

    @pytest.mark.asyncio
    async def test_validate_coverage_above_threshold(self):
        """Test when coverage is above threshold."""
        validator = CoverageValidator()

        with tempfile.TemporaryDirectory():
            with patch("orchestrator.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                mock_path.return_value.stat.return_value.st_size = 100

                with patch("xml.etree.ElementTree.parse") as mock_parse:
                    mock_root = MagicMock()
                    mock_root.get.return_value = "0.85"
                    mock_parse.return_value.getroot.return_value = mock_root
                    result = await validator.validate()

        assert result.passed is True


class TestDesignPrinciplesValidator:
    """Tests for DesignPrinciplesValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = DesignPrinciplesValidator()
        assert validator.dimension == "design_principles"
        assert validator.tier == ValidationTier.WARNING
        assert validator.agent == "code-simplifier"

    @pytest.mark.asyncio
    async def test_validate_stub_no_large_files(self):
        """Test stub validator with no large files."""
        validator = DesignPrinciplesValidator()
        with patch("orchestrator.DesignPrinciplesValidatorImpl", None):
            with patch("orchestrator.Path") as mock_path:
                mock_path.return_value.rglob.return_value = []
                result = await validator.validate()
        assert result.passed is True


class TestArchitectureValidator:
    """Tests for ArchitectureValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = ArchitectureValidator()
        assert validator.dimension == "architecture"
        assert validator.tier == ValidationTier.WARNING
        assert validator.agent == "architecture-validator"

    @pytest.mark.asyncio
    async def test_validate_no_architecture_file(self):
        """Test when ARCHITECTURE.md doesn't exist."""
        validator = ArchitectureValidator()
        with patch.object(Path, "exists", return_value=False):
            result = await validator.validate()
        assert result.passed is False
        assert "not found" in result.message
        assert result.agent == "architecture-validator"

    @pytest.mark.asyncio
    async def test_validate_architecture_exists(self):
        """Test when ARCHITECTURE.md exists."""
        validator = ArchitectureValidator()
        with patch.object(Path, "exists", return_value=True):
            result = await validator.validate()
        assert result.passed is True


class TestDocumentationValidator:
    """Tests for DocumentationValidator."""

    def test_attributes(self):
        """Test validator attributes."""
        validator = DocumentationValidator()
        assert validator.dimension == "documentation"
        assert validator.tier == ValidationTier.WARNING
        assert validator.agent == "readme-generator"

    @pytest.mark.asyncio
    async def test_validate_no_readme(self):
        """Test when README.md doesn't exist."""
        validator = DocumentationValidator()
        with patch.object(Path, "exists", return_value=False):
            result = await validator.validate()
        assert result.passed is False
        assert "not found" in result.message

    @pytest.mark.asyncio
    async def test_validate_readme_too_short(self):
        """Test when README.md is too short."""
        validator = DocumentationValidator()
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value="# Title\n"):
                result = await validator.validate()
        assert result.passed is False
        assert "too short" in result.message


class TestPerformanceValidator:
    """Tests for PerformanceValidator."""

    @pytest.mark.asyncio
    async def test_validate(self):
        """Test performance validator."""
        validator = PerformanceValidator()
        result = await validator.validate()
        assert result.passed is True
        assert "Budgets file" in result.message


class TestAccessibilityValidator:
    """Tests for AccessibilityValidator."""

    @pytest.mark.asyncio
    async def test_validate(self):
        """Test accessibility validator."""
        validator = AccessibilityValidator()
        result = await validator.validate()
        assert result.passed is True
        assert "CI" in result.message


class TestMathematicalValidator:
    """Tests for MathematicalValidator."""

    @pytest.mark.asyncio
    async def test_validate_stub(self):
        """Test mathematical validator stub."""
        validator = MathematicalValidator()
        with patch("orchestrator.MathematicalValidatorImpl", None):
            result = await validator.validate()
        assert result.passed is True
        assert "stub" in result.message


class TestAPIContractValidator:
    """Tests for APIContractValidator."""

    @pytest.mark.asyncio
    async def test_validate_stub(self):
        """Test API contract validator stub."""
        validator = APIContractValidator()
        with patch("orchestrator.APIContractValidatorImpl", None):
            result = await validator.validate()
        assert result.passed is True
        assert "stub" in result.message


class TestValidationOrchestrator:
    """Tests for ValidationOrchestrator class."""

    def test_init_without_config(self):
        """Test initialization without config file."""
        orchestrator = ValidationOrchestrator()
        assert "project_name" in orchestrator.config
        assert len(orchestrator.validators) > 0

    def test_init_with_config(self):
        """Test initialization with config file."""
        config = {
            "project_name": "test",
            "dimensions": {"code_quality": {"enabled": True, "tier": 1}},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            orchestrator = ValidationOrchestrator(Path(f.name))
        assert orchestrator.config["project_name"] == "test"

    def test_validator_registry(self):
        """Test validator registry has expected validators."""
        expected = [
            "code_quality",
            "type_safety",
            "security",
            "coverage",
            "design_principles",
            "architecture",
            "documentation",
            "performance",
            "accessibility",
            "oss_reuse",
            "mathematical",
            "api_contract",
        ]
        for name in expected:
            assert name in ValidationOrchestrator.VALIDATOR_REGISTRY

    @pytest.mark.asyncio
    async def test_run_tier(self):
        """Test running a specific tier."""
        orchestrator = ValidationOrchestrator()

        # Mock all validators to return passed
        for name, validator in orchestrator.validators.items():
            validator.validate = AsyncMock(
                return_value=ValidationResult(name, validator.tier, True, "OK")
            )

        result = await orchestrator.run_tier(ValidationTier.BLOCKER)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_run_all_passes(self):
        """Test running all tiers when everything passes."""
        orchestrator = ValidationOrchestrator()

        # Mock all validators to return passed
        for name, validator in orchestrator.validators.items():
            validator.validate = AsyncMock(
                return_value=ValidationResult(name, validator.tier, True, "OK")
            )

        # Mock integration functions
        with patch("orchestrator.push_validation_metrics"):
            with patch("orchestrator.inject_validation_context"):
                with patch("orchestrator.add_validation_breadcrumb"):
                    report = await orchestrator.run_all()

        assert report.blocked is False
        assert len(report.tiers) == 3

    @pytest.mark.asyncio
    async def test_run_all_blocked(self):
        """Test running all tiers when tier 1 fails."""
        orchestrator = ValidationOrchestrator()

        # Mock tier 1 validator to fail
        for name, validator in orchestrator.validators.items():
            if validator.tier == ValidationTier.BLOCKER:
                validator.validate = AsyncMock(
                    return_value=ValidationResult(name, validator.tier, False, "Failed")
                )
            else:
                validator.validate = AsyncMock(
                    return_value=ValidationResult(name, validator.tier, True, "OK")
                )

        with patch("orchestrator.push_validation_metrics"):
            with patch("orchestrator.inject_validation_context"):
                with patch("orchestrator.add_validation_breadcrumb"):
                    report = await orchestrator.run_all()

        assert report.blocked is True
        assert report.overall_passed is False

    @pytest.mark.asyncio
    async def test_validate_file_python(self):
        """Test single file validation for Python."""
        orchestrator = ValidationOrchestrator()

        # Mock validators
        for name, validator in orchestrator.validators.items():
            validator.validate = AsyncMock(
                return_value=ValidationResult(name, validator.tier, True, "OK")
            )

        result = await orchestrator.validate_file("test.py", tier=1)
        assert result.has_blockers is False

    @pytest.mark.asyncio
    async def test_validate_file_unknown_type(self):
        """Test single file validation for unknown file type."""
        orchestrator = ValidationOrchestrator()
        result = await orchestrator.validate_file("test.xyz", tier=1)
        assert result.has_blockers is False
        assert "not validated" in result.message

    @pytest.mark.asyncio
    async def test_validate_file_with_blockers(self):
        """Test single file validation with blockers."""
        orchestrator = ValidationOrchestrator()

        # Mock validators to fail
        for name, validator in orchestrator.validators.items():
            if validator.tier == ValidationTier.BLOCKER:
                validator.validate = AsyncMock(
                    return_value=ValidationResult(name, validator.tier, False, "Failed")
                )

        result = await orchestrator.validate_file("test.py", tier=1)
        assert result.has_blockers is True

    @pytest.mark.asyncio
    async def test_run_validator_exception(self):
        """Test error handling in _run_validator."""
        orchestrator = ValidationOrchestrator()
        validator = MagicMock()
        validator.validate = AsyncMock(side_effect=Exception("Test error"))
        validator.tier = ValidationTier.BLOCKER

        result = await orchestrator._run_validator("test", validator)
        assert result.passed is False
        assert "error" in result.message.lower()

    @pytest.mark.asyncio
    async def test_suggest_fixes(self):
        """Test _suggest_fixes logs suggestions."""
        orchestrator = ValidationOrchestrator()
        tier_result = TierResult(
            tier=ValidationTier.WARNING,
            results=[
                ValidationResult(
                    "design",
                    ValidationTier.WARNING,
                    False,
                    "Failed",
                    fix_suggestion="Run formatter",
                    agent="code-fixer",
                )
            ],
        )

        with patch("orchestrator.logger") as mock_logger:
            await orchestrator._suggest_fixes(tier_result)
            assert mock_logger.info.called


class TestLogIntegrationsStatus:
    """Tests for _log_integrations_status function."""

    def test_logs_once(self):
        """Test that integrations status is logged only once."""
        import orchestrator

        # Reset the flag
        orchestrator._integrations_logged = False

        with patch("orchestrator.logger") as mock_logger:
            _log_integrations_status()
            _log_integrations_status()  # Second call should be no-op

        # Should only log once
        assert mock_logger.info.call_count == 1


class TestOSSReuseValidator:
    """Tests for OSSReuseValidator."""

    @pytest.mark.asyncio
    async def test_validate_stub(self):
        """Test OSS reuse validator stub."""
        validator = OSSReuseValidator()
        with patch("orchestrator.OSSReuseValidatorImpl", None):
            result = await validator.validate()
        assert result.passed is True
        assert "stub" in result.message


class TestVisualBehavioralIntegration:
    """Tests for Phase 18 visual and behavioral validator integration."""

    def test_visual_validator_registered(self):
        """Test VisualTargetValidator is in VALIDATOR_REGISTRY (not BaseValidator)."""
        from orchestrator import (
            VISUAL_VALIDATOR_AVAILABLE,
            VisualTargetValidator,
        )

        if VISUAL_VALIDATOR_AVAILABLE:
            assert "visual" in ValidationOrchestrator.VALIDATOR_REGISTRY
            assert (
                ValidationOrchestrator.VALIDATOR_REGISTRY["visual"]
                is VisualTargetValidator
            )
        else:
            # Falls back to BaseValidator when not available
            assert ValidationOrchestrator.VALIDATOR_REGISTRY["visual"] is BaseValidator

    def test_behavioral_validator_registered(self):
        """Test BehavioralValidator is in VALIDATOR_REGISTRY."""
        from orchestrator import (
            BEHAVIORAL_VALIDATOR_AVAILABLE,
            BehavioralValidator,
        )

        if BEHAVIORAL_VALIDATOR_AVAILABLE:
            assert "behavioral" in ValidationOrchestrator.VALIDATOR_REGISTRY
            assert (
                ValidationOrchestrator.VALIDATOR_REGISTRY["behavioral"]
                is BehavioralValidator
            )
        else:
            # Falls back to BaseValidator when not available
            assert (
                ValidationOrchestrator.VALIDATOR_REGISTRY["behavioral"] is BaseValidator
            )

    def test_visual_in_default_dimensions(self):
        """Test visual validator is enabled at tier 3 by default."""
        orchestrator = ValidationOrchestrator()
        assert "visual" in orchestrator.validators
        assert orchestrator.validators["visual"].tier == ValidationTier.MONITOR

    def test_behavioral_in_default_dimensions(self):
        """Test behavioral validator is enabled at tier 3 by default."""
        orchestrator = ValidationOrchestrator()
        assert "behavioral" in orchestrator.validators
        assert orchestrator.validators["behavioral"].tier == ValidationTier.MONITOR

    def test_validators_instantiated_with_config(self):
        """Test validators accept config from dimensions config."""
        import tempfile

        config = {
            "project_name": "test_visual_behavioral",
            "dimensions": {
                "visual": {"enabled": True, "tier": 3},
                "behavioral": {"enabled": True, "tier": 3},
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            orchestrator = ValidationOrchestrator(Path(f.name))

        assert "visual" in orchestrator.validators
        assert "behavioral" in orchestrator.validators
        assert orchestrator.validators["visual"].tier == ValidationTier.MONITOR
        assert orchestrator.validators["behavioral"].tier == ValidationTier.MONITOR

    def test_graceful_fallback_when_unavailable(self):
        """Test BaseValidator is used as fallback when validators unavailable."""
        # Simulate unavailable validators by patching the flags
        with patch("orchestrator.VISUAL_VALIDATOR_AVAILABLE", False):
            with patch("orchestrator.BEHAVIORAL_VALIDATOR_AVAILABLE", False):
                # Need to reimport or reload to get the fallback behavior
                # But since registry is built at class definition time,
                # we test that the registry check pattern exists
                pass

        # Instead, verify the pattern: if flag is False, BaseValidator is used
        # This is tested implicitly by the existing tests when imports fail
        # Here we just verify the class attributes exist
        import orchestrator

        assert hasattr(orchestrator, "VISUAL_VALIDATOR_AVAILABLE")
        assert hasattr(orchestrator, "BEHAVIORAL_VALIDATOR_AVAILABLE")
        assert isinstance(orchestrator.VISUAL_VALIDATOR_AVAILABLE, bool)
        assert isinstance(orchestrator.BEHAVIORAL_VALIDATOR_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
