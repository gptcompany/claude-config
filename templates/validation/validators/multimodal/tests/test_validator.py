#!/usr/bin/env python3
"""Tests for MultiModalValidator multi-dimensional score fusion."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from validators.multimodal.validator import (
    BaseValidator,
    MultiModalConfig,
    MultiModalResult,
    MultiModalValidator,
    ValidationResult,
    ValidationTier,
)


class TestMultiModalConfig:
    """Tests for MultiModalConfig dataclass."""

    def test_default_config(self):
        """Test MultiModalConfig with defaults."""
        config = MultiModalConfig()
        assert config.enabled_dimensions == [
            "visual",
            "behavioral",
            "accessibility",
            "performance",
        ]
        assert config.confidence_threshold == 0.90
        assert config.custom_weights == {}

    def test_custom_config(self):
        """Test MultiModalConfig with custom values."""
        config = MultiModalConfig(
            enabled_dimensions=["visual", "behavioral"],
            confidence_threshold=0.85,
            custom_weights={"visual": 0.6, "behavioral": 0.4},
        )
        assert config.enabled_dimensions == ["visual", "behavioral"]
        assert config.confidence_threshold == 0.85
        assert config.custom_weights["visual"] == 0.6


class TestMultiModalResult:
    """Tests for MultiModalResult dataclass."""

    def test_default_result(self):
        """Test MultiModalResult with defaults."""
        result = MultiModalResult(confidence=0.92, match=True)
        assert result.confidence == 0.92
        assert result.match is True
        assert result.dimension_scores == {}
        assert result.missing_dimensions == []
        assert result.threshold == 0.90

    def test_full_result(self):
        """Test MultiModalResult with all fields."""
        result = MultiModalResult(
            confidence=0.85,
            match=False,
            dimension_scores={"visual": 0.9, "behavioral": 0.7},
            missing_dimensions=["accessibility", "performance"],
            threshold=0.90,
        )
        assert result.confidence == 0.85
        assert result.dimension_scores["visual"] == 0.9
        assert len(result.missing_dimensions) == 2


class TestMultiModalValidator:
    """Tests for MultiModalValidator class."""

    def test_init_default_config(self):
        """Test validator initializes with default config."""
        validator = MultiModalValidator()

        assert validator.dimension == "multimodal"
        assert validator.tier == ValidationTier.MONITOR
        assert validator.config.confidence_threshold == 0.90
        assert len(validator.config.enabled_dimensions) == 4

    def test_init_with_dict_config(self):
        """Test validator accepts dict config."""
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual", "behavioral"],
                "confidence_threshold": 0.85,
            }
        )

        assert validator.config.enabled_dimensions == ["visual", "behavioral"]
        assert validator.config.confidence_threshold == 0.85

    def test_init_with_config_object(self):
        """Test validator accepts MultiModalConfig object."""
        config = MultiModalConfig(
            enabled_dimensions=["visual"],
            confidence_threshold=0.75,
        )
        validator = MultiModalValidator(config=config)

        assert validator.config.enabled_dimensions == ["visual"]
        assert validator.config.confidence_threshold == 0.75

    def test_init_custom_weights(self):
        """Test custom weights are applied."""
        validator = MultiModalValidator(
            config={
                "custom_weights": {"visual": 0.8, "behavioral": 0.2},
            }
        )

        assert validator._weights["visual"] == 0.8
        assert validator._weights["behavioral"] == 0.2

    def test_map_dimension_name(self):
        """Test dimension name mapping."""
        validator = MultiModalValidator()

        assert validator._map_dimension_name("visual") == "visual_target"
        assert validator._map_dimension_name("behavioral") == "behavioral"
        assert validator._map_dimension_name("accessibility") == "accessibility"
        assert validator._map_dimension_name("unknown") == "unknown"


class TestMultiModalValidatorValidate:
    """Tests for async validate() method."""

    @pytest.mark.asyncio
    async def test_validate_no_inputs(self):
        """Test validate with no scores or validators returns ready state."""
        validator = MultiModalValidator()

        result = await validator.validate()

        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.details.get("configured") is False
        assert "ready" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_all_dimensions(self):
        """Test validate runs all dimensions and fuses scores."""
        validator = MultiModalValidator()

        result = await validator.validate(
            dimension_scores={
                "visual": 0.95,
                "behavioral": 0.90,
                "accessibility": 0.85,
                "performance": 0.80,
            }
        )

        assert result.passed is True
        assert result.confidence > 0
        assert "dimension_scores" in result.details
        assert len(result.details["dimension_scores"]) == 4

    @pytest.mark.asyncio
    async def test_validate_subset_dimensions(self):
        """Test only enabled dimensions run."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        result = await validator.validate(
            dimension_scores={
                "visual": 0.95,
                "behavioral": 0.90,
                "accessibility": 0.85,  # Should be ignored
                "performance": 0.80,  # Should be ignored
            }
        )

        assert len(result.details["dimension_scores"]) == 2
        assert "visual" in result.details["dimension_scores"]
        assert "behavioral" in result.details["dimension_scores"]
        assert "accessibility" not in result.details["dimension_scores"]

    @pytest.mark.asyncio
    async def test_validate_custom_weights(self):
        """Test custom weights are respected in fusion."""
        # High weight on visual (0.9), low on behavioral (0.1)
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual", "behavioral"],
                "custom_weights": {"visual": 0.9, "behavioral": 0.1},
            }
        )

        result = await validator.validate(
            dimension_scores={
                "visual": 1.0,  # Perfect visual
                "behavioral": 0.0,  # Failed behavioral
            }
        )

        # With 90% weight on visual (1.0), result should be high
        assert result.confidence > 0.8

    @pytest.mark.asyncio
    async def test_validate_confidence_threshold_match(self):
        """Test match determination based on threshold."""
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual"],
                "confidence_threshold": 0.90,
            }
        )

        # Score above threshold
        result = await validator.validate(dimension_scores={"visual": 0.95})

        assert result.details["match"] is True
        assert "match" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_confidence_threshold_mismatch(self):
        """Test mismatch when below threshold."""
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual"],
                "confidence_threshold": 0.90,
            }
        )

        # Score below threshold
        result = await validator.validate(dimension_scores={"visual": 0.80})

        assert result.details["match"] is False
        assert "mismatch" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_details_breakdown(self):
        """Test per-dimension scores in details."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        result = await validator.validate(
            dimension_scores={"visual": 0.9, "behavioral": 0.8}
        )

        assert "dimension_scores" in result.details
        assert result.details["dimension_scores"]["visual"] == 0.9
        assert result.details["dimension_scores"]["behavioral"] == 0.8
        assert "dimension_contributions" in result.details
        assert "effective_weights" in result.details

    @pytest.mark.asyncio
    async def test_validate_with_validators(self):
        """Test validate with actual validator instances."""
        # Create mock validator
        mock_validator = MagicMock(spec=BaseValidator)
        mock_validator.validate = AsyncMock(
            return_value=ValidationResult(
                dimension="visual",
                tier=ValidationTier.MONITOR,
                passed=True,
                message="OK",
                confidence=0.95,
            )
        )

        validator = MultiModalValidator(config={"enabled_dimensions": ["visual"]})

        result = await validator.validate(
            validators={"visual": mock_validator},
            validator_args={"visual": {"arg1": "value1"}},
        )

        mock_validator.validate.assert_called_once_with(arg1="value1")
        assert result.confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_validate_validator_unavailable(self):
        """Test graceful degradation when validator fails."""
        # Create mock that raises exception
        mock_validator = MagicMock(spec=BaseValidator)
        mock_validator.validate = AsyncMock(side_effect=Exception("Validator crashed"))

        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        # Should not raise, should continue with available scores
        result = await validator.validate(
            validators={"visual": mock_validator},
            dimension_scores={"behavioral": 0.88},  # Fallback score
        )

        assert result.passed is True
        assert "visual" in result.details["failed_dimensions"]
        assert "behavioral" in result.details["dimension_scores"]

    @pytest.mark.asyncio
    async def test_validate_returns_validation_result(self):
        """Test validate returns correct ValidationResult structure."""
        validator = MultiModalValidator()

        result = await validator.validate(dimension_scores={"visual": 0.9})

        assert isinstance(result, ValidationResult)
        assert result.dimension == "multimodal"
        assert result.tier == ValidationTier.MONITOR
        assert result.passed is True  # Tier 3 never blocks
        assert hasattr(result, "confidence")
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_validate_missing_dimensions(self):
        """Test missing dimensions are tracked."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral", "accessibility"]}
        )

        result = await validator.validate(
            dimension_scores={"visual": 0.9}  # Missing behavioral and accessibility
        )

        assert "behavioral" in result.details["missing_dimensions"]
        assert "accessibility" in result.details["missing_dimensions"]

    @pytest.mark.asyncio
    async def test_validate_with_reliabilities(self):
        """Test reliability-adjusted weighting."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        # Visual has low reliability - should reduce its effective weight
        result = await validator.validate(
            dimension_scores={"visual": 1.0, "behavioral": 0.5},
            dimension_reliabilities={"visual": 0.1, "behavioral": 1.0},
        )

        # Behavioral should dominate due to higher reliability
        assert result.confidence < 0.9  # Not close to visual's 1.0

    @pytest.mark.asyncio
    async def test_validate_no_scores_available(self):
        """Test when no scores can be collected."""
        validator = MultiModalValidator(config={"enabled_dimensions": ["visual"]})

        # Provide score for different dimension than enabled
        result = await validator.validate(
            dimension_scores={"behavioral": 0.9}  # Not enabled
        )

        assert result.passed is False
        assert result.confidence == 0.0
        assert "no dimension scores" in result.message.lower()


class TestMultiModalValidatorFuseScores:
    """Tests for synchronous fuse_scores() method."""

    def test_fuse_scores_basic(self):
        """Test basic score fusion."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        result = validator.fuse_scores(scores={"visual": 0.9, "behavioral": 0.8})

        assert isinstance(result, MultiModalResult)
        assert result.confidence > 0
        assert result.dimension_scores["visual"] == 0.9
        assert result.dimension_scores["behavioral"] == 0.8

    def test_fuse_scores_match_threshold(self):
        """Test match determination in fuse_scores."""
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual"],
                "confidence_threshold": 0.85,
            }
        )

        # Above threshold
        result_match = validator.fuse_scores(scores={"visual": 0.90})
        assert result_match.match is True

        # Below threshold
        result_mismatch = validator.fuse_scores(scores={"visual": 0.80})
        assert result_mismatch.match is False

    def test_fuse_scores_empty(self):
        """Test fuse_scores with empty scores."""
        validator = MultiModalValidator()

        result = validator.fuse_scores(scores={})

        assert result.confidence == 0.0
        assert result.match is False
        assert len(result.missing_dimensions) == 4

    def test_fuse_scores_filters_disabled(self):
        """Test fuse_scores filters non-enabled dimensions."""
        validator = MultiModalValidator(config={"enabled_dimensions": ["visual"]})

        result = validator.fuse_scores(
            scores={
                "visual": 0.9,
                "behavioral": 0.5,  # Should be ignored
            }
        )

        assert "visual" in result.dimension_scores
        assert "behavioral" not in result.dimension_scores

    def test_fuse_scores_with_reliabilities(self):
        """Test reliability adjustment in fuse_scores."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        result = validator.fuse_scores(
            scores={"visual": 1.0, "behavioral": 0.5},
            reliabilities={"visual": 0.1, "behavioral": 1.0},
        )

        # Behavioral should dominate
        assert result.confidence < 0.9

    def test_fuse_scores_missing_dimensions(self):
        """Test missing dimensions tracking."""
        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral", "accessibility"]}
        )

        result = validator.fuse_scores(scores={"visual": 0.9})

        assert "behavioral" in result.missing_dimensions
        assert "accessibility" in result.missing_dimensions
        assert len(result.missing_dimensions) == 2


class TestMultiModalValidatorIntegration:
    """Integration tests for MultiModalValidator."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock_validators(self):
        """Test full validation pipeline with mocked validators."""

        # Create mock validators for each dimension
        def make_mock_validator(dimension: str, score: float):
            mock = MagicMock(spec=BaseValidator)
            mock.validate = AsyncMock(
                return_value=ValidationResult(
                    dimension=dimension,
                    tier=ValidationTier.MONITOR,
                    passed=True,
                    message=f"{dimension} OK",
                    confidence=score,
                    details={"score": score},
                )
            )
            return mock

        visual_mock = make_mock_validator("visual", 0.95)
        behavioral_mock = make_mock_validator("behavioral", 0.88)

        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual", "behavioral"],
                "confidence_threshold": 0.85,
            }
        )

        result = await validator.validate(
            validators={
                "visual": visual_mock,
                "behavioral": behavioral_mock,
            }
        )

        assert result.passed is True
        assert result.confidence > 0.85
        assert result.details["match"] is True
        assert "visual" in result.details["dimension_scores"]
        assert "behavioral" in result.details["dimension_scores"]

    @pytest.mark.asyncio
    async def test_mixed_validators_and_scores(self):
        """Test mixing validator instances with direct scores."""
        mock_validator = MagicMock(spec=BaseValidator)
        mock_validator.validate = AsyncMock(
            return_value=ValidationResult(
                dimension="visual",
                tier=ValidationTier.MONITOR,
                passed=True,
                message="OK",
                confidence=0.90,
            )
        )

        validator = MultiModalValidator(
            config={"enabled_dimensions": ["visual", "behavioral"]}
        )

        result = await validator.validate(
            validators={"visual": mock_validator},
            dimension_scores={"behavioral": 0.85},  # Direct score
        )

        assert "visual" in result.details["dimension_scores"]
        assert "behavioral" in result.details["dimension_scores"]
        assert result.details["dimension_scores"]["visual"] == 0.90
        assert result.details["dimension_scores"]["behavioral"] == 0.85

    def test_weights_normalized_correctly(self):
        """Test that custom weights are correctly normalized in fusion."""
        validator = MultiModalValidator(
            config={
                "enabled_dimensions": ["visual", "behavioral"],
                "custom_weights": {"visual": 3.0, "behavioral": 1.0},  # Sum = 4.0
            }
        )

        # Visual gets 75% weight, behavioral 25%
        result = validator.fuse_scores(scores={"visual": 1.0, "behavioral": 0.0})

        # Expected: (1.0 * 3.0 + 0.0 * 1.0) / 4.0 = 0.75
        assert result.confidence == pytest.approx(0.75)
