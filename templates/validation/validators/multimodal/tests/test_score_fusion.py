#!/usr/bin/env python3
"""Tests for ScoreFusion weighted score fusion algorithm."""

import pytest

from validators.multimodal.score_fusion import DimensionScore, FusionResult, ScoreFusion


class TestDimensionScore:
    """Tests for DimensionScore dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating DimensionScore with required fields."""
        score = DimensionScore(
            dimension="visual_target",
            value=0.95,
            weight=0.35,
        )
        assert score.dimension == "visual_target"
        assert score.value == 0.95
        assert score.weight == 0.35
        assert score.reliability == 1.0  # Default

    def test_creation_with_reliability(self):
        """Test creating DimensionScore with custom reliability."""
        score = DimensionScore(
            dimension="behavioral",
            value=0.88,
            weight=0.25,
            reliability=0.9,
        )
        assert score.reliability == 0.9

    def test_boundary_values(self):
        """Test DimensionScore with boundary values."""
        # Minimum values
        score_min = DimensionScore("test", 0.0, 0.0, 0.0)
        assert score_min.value == 0.0
        assert score_min.weight == 0.0
        assert score_min.reliability == 0.0

        # Maximum values
        score_max = DimensionScore("test", 1.0, 1.0, 1.0)
        assert score_max.value == 1.0
        assert score_max.weight == 1.0
        assert score_max.reliability == 1.0


class TestFusionResult:
    """Tests for FusionResult dataclass."""

    def test_creation_with_required_fields(self):
        """Test creating FusionResult with required fields."""
        result = FusionResult(fused_score=0.92)
        assert result.fused_score == 0.92
        assert result.dimension_contributions == {}
        assert result.effective_weights == {}
        assert result.missing_dimensions == []
        assert result.details == {}

    def test_creation_with_all_fields(self):
        """Test creating FusionResult with all fields."""
        result = FusionResult(
            fused_score=0.85,
            dimension_contributions={"visual": 0.5, "behavioral": 0.35},
            effective_weights={"visual": 0.35, "behavioral": 0.25},
            missing_dimensions=["performance"],
            details={"total_weight": 0.60},
        )
        assert result.fused_score == 0.85
        assert result.dimension_contributions["visual"] == 0.5
        assert result.missing_dimensions == ["performance"]


class TestScoreFusion:
    """Tests for ScoreFusion class."""

    def test_init_default_weights(self):
        """Test ScoreFusion initializes with default weights."""
        fusion = ScoreFusion()

        assert fusion.base_weights["visual_target"] == 0.35
        assert fusion.base_weights["behavioral"] == 0.25
        assert fusion.base_weights["accessibility"] == 0.20
        assert fusion.base_weights["performance"] == 0.20

    def test_init_custom_weights(self):
        """Test ScoreFusion accepts custom weights."""
        custom = {"visual": 0.5, "behavioral": 0.5}
        fusion = ScoreFusion(base_weights=custom)

        assert fusion.base_weights["visual"] == 0.5
        assert fusion.base_weights["behavioral"] == 0.5
        assert "visual_target" not in fusion.base_weights

    def test_get_weight_existing(self):
        """Test get_weight returns correct weight for existing dimension."""
        fusion = ScoreFusion()
        assert fusion.get_weight("visual_target") == 0.35

    def test_get_weight_nonexistent(self):
        """Test get_weight returns 0.0 for unknown dimension."""
        fusion = ScoreFusion()
        assert fusion.get_weight("unknown_dimension") == 0.0

    def test_set_weight(self):
        """Test set_weight updates weight correctly."""
        fusion = ScoreFusion()
        fusion.set_weight("visual_target", 0.50)
        assert fusion.base_weights["visual_target"] == 0.50

    def test_set_weight_new_dimension(self):
        """Test set_weight adds new dimension."""
        fusion = ScoreFusion()
        fusion.set_weight("new_dimension", 0.15)
        assert fusion.base_weights["new_dimension"] == 0.15


class TestScoreFusionFuse:
    """Tests for ScoreFusion.fuse() method."""

    def test_fuse_all_dimensions(self):
        """Test fusing all 4 dimensions produces weighted average."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 1.0, 0.35, 1.0),
            DimensionScore("behavioral", 1.0, 0.25, 1.0),
            DimensionScore("accessibility", 1.0, 0.20, 1.0),
            DimensionScore("performance", 1.0, 0.20, 1.0),
        ]

        result = fusion.fuse(scores)
        assert result == pytest.approx(1.0)

    def test_fuse_all_dimensions_mixed_scores(self):
        """Test fusing all dimensions with different scores."""
        fusion = ScoreFusion()
        # visual=0.9, behavioral=0.8, a11y=0.7, perf=0.6
        # Expected: (0.9*0.35 + 0.8*0.25 + 0.7*0.20 + 0.6*0.20) / 1.0
        #         = (0.315 + 0.20 + 0.14 + 0.12) / 1.0 = 0.775
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 1.0),
            DimensionScore("accessibility", 0.7, 0.20, 1.0),
            DimensionScore("performance", 0.6, 0.20, 1.0),
        ]

        result = fusion.fuse(scores)
        assert result == pytest.approx(0.775)

    def test_fuse_missing_dimension(self):
        """Test weights renormalize correctly when dimension missing."""
        fusion = ScoreFusion()
        # Only visual and behavioral (0.35 + 0.25 = 0.60 total weight)
        # visual=1.0, behavioral=0.5
        # Expected: (1.0*0.35 + 0.5*0.25) / 0.60 = (0.35 + 0.125) / 0.60 = 0.7917
        scores = [
            DimensionScore("visual_target", 1.0, 0.35, 1.0),
            DimensionScore("behavioral", 0.5, 0.25, 1.0),
        ]

        result = fusion.fuse(scores)
        expected = (1.0 * 0.35 + 0.5 * 0.25) / (0.35 + 0.25)
        assert result == pytest.approx(expected)

    def test_fuse_single_dimension(self):
        """Test single dimension returns that value."""
        fusion = ScoreFusion()
        scores = [DimensionScore("visual_target", 0.88, 0.35, 1.0)]

        result = fusion.fuse(scores)
        assert result == pytest.approx(0.88)

    def test_fuse_empty_scores(self):
        """Test empty scores list returns 0.0."""
        fusion = ScoreFusion()
        result = fusion.fuse([])
        assert result == 0.0

    def test_reliability_adjustment(self):
        """Test low reliability reduces effective weight."""
        fusion = ScoreFusion()
        # Same scores but visual has low reliability
        # visual: 1.0 * 0.35 * 0.5 = 0.175 effective
        # behavioral: 0.5 * 0.25 * 1.0 = 0.125 effective
        # Total weight: 0.175 + 0.25 = 0.425
        # Numerator: 1.0 * 0.175 + 0.5 * 0.25 = 0.175 + 0.125 = 0.30
        # Result: 0.30 / 0.425 = 0.7059
        scores = [
            DimensionScore("visual_target", 1.0, 0.35, 0.5),  # Low reliability
            DimensionScore("behavioral", 0.5, 0.25, 1.0),  # Full reliability
        ]

        result = fusion.fuse(scores)
        expected = (1.0 * 0.35 * 0.5 + 0.5 * 0.25 * 1.0) / (0.35 * 0.5 + 0.25 * 1.0)
        assert result == pytest.approx(expected)

    def test_zero_total_weight(self):
        """Test handles zero total weight gracefully."""
        fusion = ScoreFusion()
        # All scores have zero weight or zero reliability
        scores = [
            DimensionScore("visual_target", 0.9, 0.0, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 0.0),
        ]

        result = fusion.fuse(scores)
        assert result == 0.0

    def test_boundary_values_scores_zero(self):
        """Test fusion with all scores at 0.0."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.0, 0.35, 1.0),
            DimensionScore("behavioral", 0.0, 0.25, 1.0),
        ]

        result = fusion.fuse(scores)
        assert result == 0.0

    def test_boundary_values_scores_one(self):
        """Test fusion with all scores at 1.0."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 1.0, 0.35, 1.0),
            DimensionScore("behavioral", 1.0, 0.25, 1.0),
        ]

        result = fusion.fuse(scores)
        assert result == pytest.approx(1.0)


class TestScoreFusionFuseWithDetails:
    """Tests for ScoreFusion.fuse_with_details() method."""

    def test_fuse_with_details_basic(self):
        """Test fuse_with_details returns complete breakdown."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 1.0),
        ]

        result = fusion.fuse_with_details(scores)

        assert isinstance(result, FusionResult)
        assert result.fused_score == pytest.approx((0.9 * 0.35 + 0.8 * 0.25) / 0.60)
        assert "visual_target" in result.dimension_contributions
        assert "behavioral" in result.dimension_contributions
        assert result.effective_weights["visual_target"] == 0.35
        assert result.effective_weights["behavioral"] == 0.25

    def test_fuse_with_details_empty_scores(self):
        """Test fuse_with_details handles empty list."""
        fusion = ScoreFusion()
        result = fusion.fuse_with_details([])

        assert result.fused_score == 0.0
        assert result.details.get("error") == "No scores provided"

    def test_fuse_with_details_zero_weight(self):
        """Test fuse_with_details handles zero total weight."""
        fusion = ScoreFusion()
        scores = [DimensionScore("visual_target", 0.9, 0.0, 1.0)]

        result = fusion.fuse_with_details(scores)

        assert result.fused_score == 0.0
        assert "error" in result.details

    def test_fuse_with_details_missing_dimensions(self):
        """Test missing dimensions are identified correctly."""
        fusion = ScoreFusion()
        scores = [DimensionScore("visual_target", 0.9, 0.35, 1.0)]

        result = fusion.fuse_with_details(scores)

        # Should identify behavioral, accessibility, performance as missing
        assert "behavioral" in result.missing_dimensions
        assert "accessibility" in result.missing_dimensions
        assert "performance" in result.missing_dimensions
        assert len(result.missing_dimensions) == 3

    def test_fuse_with_details_all_dimensions_present(self):
        """Test no missing dimensions when all present."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 1.0),
            DimensionScore("accessibility", 0.7, 0.20, 1.0),
            DimensionScore("performance", 0.6, 0.20, 1.0),
        ]

        result = fusion.fuse_with_details(scores)

        assert result.missing_dimensions == []
        assert result.details["dimensions_present"] == 4
        assert result.details["dimensions_expected"] == 4

    def test_fuse_with_details_reliability_in_effective_weights(self):
        """Test effective weights include reliability adjustment."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 0.5),  # 50% reliability
            DimensionScore("behavioral", 0.8, 0.25, 1.0),  # 100% reliability
        ]

        result = fusion.fuse_with_details(scores)

        # Effective weight = base_weight * reliability
        assert result.effective_weights["visual_target"] == pytest.approx(0.35 * 0.5)
        assert result.effective_weights["behavioral"] == pytest.approx(0.25 * 1.0)

    def test_fuse_with_details_contributions_sum_to_fused(self):
        """Test dimension contributions sum to fused score."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 1.0),
            DimensionScore("accessibility", 0.7, 0.20, 1.0),
        ]

        result = fusion.fuse_with_details(scores)

        total_contribution = sum(result.dimension_contributions.values())
        assert total_contribution == pytest.approx(result.fused_score)

    def test_fuse_with_details_total_effective_weight(self):
        """Test total effective weight is tracked correctly."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.9, 0.35, 1.0),
            DimensionScore("behavioral", 0.8, 0.25, 0.8),
        ]

        result = fusion.fuse_with_details(scores)

        expected_total = 0.35 * 1.0 + 0.25 * 0.8  # 0.35 + 0.20 = 0.55
        assert result.details["total_effective_weight"] == pytest.approx(expected_total)


class TestScoreFusionEdgeCases:
    """Edge case tests for ScoreFusion."""

    def test_custom_dimension_names(self):
        """Test fusion works with arbitrary dimension names."""
        fusion = ScoreFusion({"custom_a": 0.6, "custom_b": 0.4})
        scores = [
            DimensionScore("custom_a", 0.9, 0.6, 1.0),
            DimensionScore("custom_b", 0.7, 0.4, 1.0),
        ]

        result = fusion.fuse(scores)
        expected = (0.9 * 0.6 + 0.7 * 0.4) / 1.0
        assert result == pytest.approx(expected)

    def test_very_small_weights(self):
        """Test fusion handles very small weights."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("a", 1.0, 0.001, 1.0),
            DimensionScore("b", 0.0, 0.001, 1.0),
        ]

        result = fusion.fuse(scores)
        assert result == pytest.approx(0.5)  # Equal weights, so average

    def test_very_small_reliability(self):
        """Test fusion handles very small reliability."""
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 1.0, 0.35, 0.001),
            DimensionScore("behavioral", 0.5, 0.25, 1.0),
        ]

        result = fusion.fuse(scores)
        # Visual contribution nearly 0, behavioral dominates
        expected = (1.0 * 0.35 * 0.001 + 0.5 * 0.25 * 1.0) / (0.35 * 0.001 + 0.25)
        assert result == pytest.approx(expected)

    def test_unequal_weights_dont_sum_to_one(self):
        """Test fusion normalizes weights that don't sum to 1."""
        fusion = ScoreFusion({"a": 1.0, "b": 1.0})  # Sum = 2.0
        scores = [
            DimensionScore("a", 0.8, 1.0, 1.0),
            DimensionScore("b", 0.4, 1.0, 1.0),
        ]

        result = fusion.fuse(scores)
        # (0.8*1 + 0.4*1) / 2 = 0.6
        assert result == pytest.approx(0.6)
