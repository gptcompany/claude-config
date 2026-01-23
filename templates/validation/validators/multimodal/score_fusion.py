#!/usr/bin/env python3
"""
ScoreFusion - Weighted Quasi-Arithmetic Mean Score Fusion.

Combines scores from multiple validation dimensions into a single
unified confidence score using adaptive weighting based on reliability.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionScore:
    """Score from a single validation dimension."""

    dimension: str
    value: float  # 0.0 to 1.0 (confidence score)
    weight: float  # Base weight for this dimension
    reliability: float = 1.0  # 0.0 to 1.0 (how trustworthy this score is)


@dataclass
class FusionResult:
    """Result from score fusion including detailed breakdown."""

    fused_score: float  # Combined confidence (0.0 to 1.0)
    dimension_contributions: dict[str, float] = field(default_factory=dict)
    effective_weights: dict[str, float] = field(default_factory=dict)
    missing_dimensions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class ScoreFusion:
    """
    Weighted quasi-arithmetic mean fusion for multi-dimensional scores.

    Combines multiple validation dimension scores into a single unified
    confidence score using adaptive weighting based on reliability.

    Formula:
        effective_weight = base_weight * reliability
        fused_score = sum(score * effective_weight) / sum(effective_weight)

    Default weights (from research):
        - visual_target: 0.35
        - behavioral: 0.25
        - accessibility: 0.20
        - performance: 0.20

    Missing dimensions are handled by renormalizing weights across
    available dimensions.

    Usage:
        fusion = ScoreFusion()
        scores = [
            DimensionScore("visual_target", 0.95, 0.35, 1.0),
            DimensionScore("behavioral", 0.88, 0.25, 0.9),
        ]
        result = fusion.fuse(scores)
        print(f"Fused confidence: {result}")
    """

    DEFAULT_WEIGHTS = {
        "visual_target": 0.35,
        "behavioral": 0.25,
        "accessibility": 0.20,
        "performance": 0.20,
    }

    def __init__(self, base_weights: dict[str, float] | None = None):
        """
        Initialize fusion with optional custom weights.

        Args:
            base_weights: Dict mapping dimension names to weights.
                          If None, uses DEFAULT_WEIGHTS.
        """
        self.base_weights = base_weights or self.DEFAULT_WEIGHTS.copy()

    def fuse(self, scores: list[DimensionScore]) -> float:
        """
        Fuse multiple dimension scores into single confidence.

        Uses weighted quasi-arithmetic mean with reliability adjustment:
        - effective_weight = weight * reliability
        - fused = sum(score * effective_weight) / sum(effective_weight)

        Args:
            scores: List of DimensionScore objects

        Returns:
            Fused confidence score (0.0 to 1.0)

        Raises:
            ValueError: If no valid scores provided
        """
        if not scores:
            return 0.0

        numerator = 0.0
        denominator = 0.0

        for score in scores:
            # Calculate effective weight (base weight * reliability)
            effective_weight = score.weight * score.reliability

            numerator += score.value * effective_weight
            denominator += effective_weight

        # Handle edge case of zero total weight
        if denominator == 0.0:
            return 0.0

        return numerator / denominator

    def fuse_with_details(self, scores: list[DimensionScore]) -> FusionResult:
        """
        Fuse scores and return detailed breakdown per dimension.

        Provides transparency into how each dimension contributed
        to the final score, including effective weights after
        reliability adjustment and individual contributions.

        Args:
            scores: List of DimensionScore objects

        Returns:
            FusionResult with fused score and detailed breakdown
        """
        if not scores:
            return FusionResult(
                fused_score=0.0,
                details={"error": "No scores provided"},
            )

        numerator = 0.0
        denominator = 0.0
        contributions: dict[str, float] = {}
        effective_weights: dict[str, float] = {}

        for score in scores:
            effective_weight = score.weight * score.reliability
            contribution = score.value * effective_weight

            numerator += contribution
            denominator += effective_weight

            effective_weights[score.dimension] = effective_weight
            contributions[score.dimension] = contribution

        # Handle zero total weight
        if denominator == 0.0:
            return FusionResult(
                fused_score=0.0,
                effective_weights=effective_weights,
                details={"error": "Zero total effective weight"},
            )

        fused_score = numerator / denominator

        # Calculate per-dimension contribution as percentage of final score
        dimension_contributions = {
            dim: (contrib / denominator) for dim, contrib in contributions.items()
        }

        # Identify missing dimensions from base_weights
        present_dims = {s.dimension for s in scores}
        missing = [dim for dim in self.base_weights if dim not in present_dims]

        return FusionResult(
            fused_score=fused_score,
            dimension_contributions=dimension_contributions,
            effective_weights=effective_weights,
            missing_dimensions=missing,
            details={
                "total_effective_weight": denominator,
                "dimensions_present": len(scores),
                "dimensions_expected": len(self.base_weights),
            },
        )

    def get_weight(self, dimension: str) -> float:
        """
        Get base weight for a dimension.

        Args:
            dimension: Dimension name

        Returns:
            Base weight (defaults to 0.0 if not configured)
        """
        return self.base_weights.get(dimension, 0.0)

    def set_weight(self, dimension: str, weight: float) -> None:
        """
        Set base weight for a dimension.

        Args:
            dimension: Dimension name
            weight: New weight value
        """
        self.base_weights[dimension] = weight


__all__ = ["ScoreFusion", "DimensionScore", "FusionResult"]
