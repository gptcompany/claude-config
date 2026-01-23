#!/usr/bin/env python3
"""
MultiModalValidator - Multi-dimensional Score Fusion Validator.

Tier 3 validator that orchestrates multiple validation dimensions
(visual, behavioral, accessibility, performance) and fuses their
scores into a unified confidence measurement.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .score_fusion import DimensionScore, FusionResult, ScoreFusion


# Base types (with fallback for standalone testing)
class ValidationTier(Enum):
    """Validation tiers with different behaviors."""

    BLOCKER = 1  # Must pass - blocks merge/deploy
    WARNING = 2  # Warn + suggest fix - doesn't block
    MONITOR = 3  # Metrics only - emit to dashboards


@dataclass
class ValidationResult:
    """Result from a single dimension validator."""

    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0
    confidence: float = 1.0  # Confidence score (0.0 to 1.0)


class BaseValidator:
    """Base class for dimension validators."""

    dimension: str = "unknown"
    tier: ValidationTier = ValidationTier.MONITOR
    agent: str | None = None

    async def validate(self, *args: Any, **kwargs: Any) -> ValidationResult:
        """Run validation. Override in subclasses."""
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


@dataclass
class MultiModalConfig:
    """Configuration for MultiModalValidator."""

    enabled_dimensions: list[str] = field(
        default_factory=lambda: ["visual", "behavioral", "accessibility", "performance"]
    )
    confidence_threshold: float = 0.90  # Threshold for "match" determination
    custom_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class MultiModalResult:
    """Result from multi-modal validation including per-dimension breakdown."""

    confidence: float  # Fused confidence score (0.0 to 1.0)
    match: bool  # True if confidence >= threshold
    dimension_scores: dict[str, float] = field(default_factory=dict)
    dimension_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_dimensions: list[str] = field(default_factory=list)
    failed_dimensions: list[str] = field(default_factory=list)
    threshold: float = 0.90


class MultiModalValidator(BaseValidator):
    """
    Tier 3: Multi-dimensional Score Fusion Validator.

    Orchestrates multiple validation dimensions and fuses their
    scores into a unified confidence measurement.

    Supported dimensions:
    - visual: VisualTargetValidator (ODiff + SSIM)
    - behavioral: BehavioralValidator (DOM structure)
    - accessibility: From orchestrator or placeholder
    - performance: From orchestrator or placeholder

    Usage:
        validator = MultiModalValidator(config={
            "enabled_dimensions": ["visual", "behavioral"],
            "confidence_threshold": 0.90,
        })

        # With pre-collected dimension scores
        result = await validator.validate(
            dimension_scores={
                "visual": 0.95,
                "behavioral": 0.88,
            }
        )

        # Or with validator instances
        result = await validator.validate(
            validators={
                "visual": visual_validator,
                "behavioral": behavioral_validator,
            },
            validator_args={
                "visual": {"baseline": "b.png", "current": "c.png"},
                "behavioral": {"baseline_html": "<div>A</div>", "current_html": "<div>B</div>"},
            }
        )
    """

    dimension = "multimodal"
    tier = ValidationTier.MONITOR

    DEFAULT_WEIGHTS = {
        "visual": 0.35,
        "behavioral": 0.25,
        "accessibility": 0.20,
        "performance": 0.20,
    }

    def __init__(self, config: MultiModalConfig | dict | None = None):
        """
        Initialize validator with optional config.

        Args:
            config: MultiModalConfig or dict with config options
        """
        if config is None:
            self.config = MultiModalConfig()
        elif isinstance(config, dict):
            self.config = MultiModalConfig(
                enabled_dimensions=config.get(
                    "enabled_dimensions",
                    ["visual", "behavioral", "accessibility", "performance"],
                ),
                confidence_threshold=config.get("confidence_threshold", 0.90),
                custom_weights=config.get("custom_weights", {}),
            )
        else:
            self.config = config

        # Build weights from defaults + custom overrides
        weights = self.DEFAULT_WEIGHTS.copy()
        weights.update(self.config.custom_weights)

        # Use correct dimension names for score fusion
        fusion_weights = {
            "visual_target": weights.get("visual", 0.35),
            "behavioral": weights.get("behavioral", 0.25),
            "accessibility": weights.get("accessibility", 0.20),
            "performance": weights.get("performance", 0.20),
        }

        self.fusion = ScoreFusion(base_weights=fusion_weights)
        self._weights = weights

    def _map_dimension_name(self, dimension: str) -> str:
        """
        Map external dimension names to internal ScoreFusion names.

        Args:
            dimension: External dimension name (e.g., "visual")

        Returns:
            Internal ScoreFusion dimension name (e.g., "visual_target")
        """
        mapping = {
            "visual": "visual_target",
            "behavioral": "behavioral",
            "accessibility": "accessibility",
            "performance": "performance",
        }
        return mapping.get(dimension, dimension)

    async def validate(
        self,
        dimension_scores: dict[str, float] | None = None,
        dimension_reliabilities: dict[str, float] | None = None,
        validators: dict[str, BaseValidator] | None = None,
        validator_args: dict[str, dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """
        Run multi-modal validation and return unified confidence.

        Can be called in two modes:
        1. With pre-collected scores (dimension_scores)
        2. With validator instances (validators + validator_args)

        Args:
            dimension_scores: Dict mapping dimension names to scores
            dimension_reliabilities: Optional dict mapping dimensions to reliability values
            validators: Dict mapping dimension names to validator instances
            validator_args: Dict mapping dimension names to args for validators

        Returns:
            ValidationResult with unified confidence and breakdown
        """
        start = datetime.now()

        # If no inputs, return "ready but not configured"
        if dimension_scores is None and validators is None:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="MultiModalValidator ready (no scores provided)",
                details={
                    "configured": False,
                    "enabled_dimensions": self.config.enabled_dimensions,
                    "threshold": self.config.confidence_threshold,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Collect scores from validators if provided
        collected_scores: dict[str, float] = {}
        collected_reliabilities: dict[str, float] = dimension_reliabilities or {}
        dimension_details: dict[str, dict[str, Any]] = {}
        failed_dimensions: list[str] = []

        if validators:
            validator_args = validator_args or {}

            for dim_name, validator in validators.items():
                if dim_name not in self.config.enabled_dimensions:
                    continue

                try:
                    args = validator_args.get(dim_name, {})
                    result = await validator.validate(**args)

                    # Extract confidence from result
                    confidence = getattr(result, "confidence", None)
                    if confidence is None:
                        # Fallback: use passed as 1.0/0.0
                        confidence = 1.0 if result.passed else 0.0

                    collected_scores[dim_name] = confidence
                    dimension_details[dim_name] = result.details

                except Exception as e:
                    # Graceful degradation: log error, continue without this dimension
                    failed_dimensions.append(dim_name)
                    dimension_details[dim_name] = {"error": str(e)}

        # Merge with pre-provided scores (pre-provided takes precedence)
        if dimension_scores:
            for dim_name, score in dimension_scores.items():
                if dim_name in self.config.enabled_dimensions:
                    collected_scores[dim_name] = score

        # Filter to only enabled dimensions
        final_scores = {
            k: v
            for k, v in collected_scores.items()
            if k in self.config.enabled_dimensions
        }

        # If no scores collected, return error
        if not final_scores:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                confidence=0.0,
                message="No dimension scores available",
                details={
                    "enabled_dimensions": self.config.enabled_dimensions,
                    "failed_dimensions": failed_dimensions,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Build DimensionScore objects for fusion
        fusion_scores: list[DimensionScore] = []
        for dim_name, score in final_scores.items():
            internal_name = self._map_dimension_name(dim_name)
            weight = self._weights.get(dim_name, 0.20)
            reliability = collected_reliabilities.get(dim_name, 1.0)

            fusion_scores.append(
                DimensionScore(
                    dimension=internal_name,
                    value=score,
                    weight=weight,
                    reliability=reliability,
                )
            )

        # Fuse scores
        fusion_result: FusionResult = self.fusion.fuse_with_details(fusion_scores)

        # Determine match based on threshold
        match = fusion_result.fused_score >= self.config.confidence_threshold

        # Identify missing dimensions
        missing = [d for d in self.config.enabled_dimensions if d not in final_scores]

        # Build message
        if match:
            message = (
                f"Multi-modal match: {fusion_result.fused_score:.1%} confidence "
                f"(threshold: {self.config.confidence_threshold:.1%})"
            )
        else:
            message = (
                f"Multi-modal mismatch: {fusion_result.fused_score:.1%} confidence "
                f"(threshold: {self.config.confidence_threshold:.1%})"
            )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,  # Tier 3 doesn't block
            confidence=fusion_result.fused_score,
            message=message,
            details={
                "fused_confidence": fusion_result.fused_score,
                "match": match,
                "threshold": self.config.confidence_threshold,
                "dimension_scores": final_scores,
                "dimension_contributions": fusion_result.dimension_contributions,
                "effective_weights": fusion_result.effective_weights,
                "missing_dimensions": missing,
                "failed_dimensions": failed_dimensions,
                "dimension_details": dimension_details,
                "enabled_dimensions": self.config.enabled_dimensions,
            },
            duration_ms=duration_ms,
        )

    def fuse_scores(
        self,
        scores: dict[str, float],
        reliabilities: dict[str, float] | None = None,
    ) -> MultiModalResult:
        """
        Synchronous score fusion for direct use.

        Convenience method for fusing pre-collected scores without
        running validators.

        Args:
            scores: Dict mapping dimension names to scores
            reliabilities: Optional dict mapping dimensions to reliability values

        Returns:
            MultiModalResult with fused confidence and breakdown
        """
        reliabilities = reliabilities or {}

        # Filter to enabled dimensions
        enabled_scores = {
            k: v for k, v in scores.items() if k in self.config.enabled_dimensions
        }

        if not enabled_scores:
            return MultiModalResult(
                confidence=0.0,
                match=False,
                missing_dimensions=self.config.enabled_dimensions.copy(),
                threshold=self.config.confidence_threshold,
            )

        # Build DimensionScore objects
        fusion_scores: list[DimensionScore] = []
        for dim_name, score in enabled_scores.items():
            internal_name = self._map_dimension_name(dim_name)
            weight = self._weights.get(dim_name, 0.20)
            reliability = reliabilities.get(dim_name, 1.0)

            fusion_scores.append(
                DimensionScore(
                    dimension=internal_name,
                    value=score,
                    weight=weight,
                    reliability=reliability,
                )
            )

        # Fuse
        fusion_result = self.fusion.fuse_with_details(fusion_scores)
        match = fusion_result.fused_score >= self.config.confidence_threshold

        # Missing dimensions
        missing = [d for d in self.config.enabled_dimensions if d not in enabled_scores]

        return MultiModalResult(
            confidence=fusion_result.fused_score,
            match=match,
            dimension_scores=enabled_scores,
            missing_dimensions=missing,
            threshold=self.config.confidence_threshold,
        )


__all__ = [
    "MultiModalValidator",
    "MultiModalConfig",
    "MultiModalResult",
    "ValidationResult",
    "ValidationTier",
]
