#!/usr/bin/env python3
"""Multi-dimensional Score Fusion Validator orchestrating visual, behavioral, accessibility, performance."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .score_fusion import DimensionScore, FusionResult, ScoreFusion


class ValidationTier(Enum):
    BLOCKER = 1
    WARNING = 2
    MONITOR = 3


@dataclass
class ValidationResult:
    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0
    confidence: float = 1.0


class BaseValidator:
    dimension: str = "unknown"
    tier: ValidationTier = ValidationTier.MONITOR
    agent: str | None = None

    async def validate(self, *args: Any, **kwargs: Any) -> ValidationResult:
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


@dataclass
class MultiModalConfig:
    enabled_dimensions: list[str] = field(
        default_factory=lambda: ["visual", "behavioral", "accessibility", "performance"]
    )
    confidence_threshold: float = 0.90
    custom_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class MultiModalResult:
    confidence: float
    match: bool
    dimension_scores: dict[str, float] = field(default_factory=dict)
    dimension_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_dimensions: list[str] = field(default_factory=list)
    failed_dimensions: list[str] = field(default_factory=list)
    threshold: float = 0.90


class MultiModalValidator(BaseValidator):
    dimension = "multimodal"
    tier = ValidationTier.MONITOR

    DEFAULT_WEIGHTS = {
        "visual": 0.35,
        "behavioral": 0.25,
        "accessibility": 0.20,
        "performance": 0.20,
    }

    DIMENSION_MAP = {
        "visual": "visual_target",
        "behavioral": "behavioral",
        "accessibility": "accessibility",
        "performance": "performance",
    }

    def __init__(self, config: MultiModalConfig | dict | None = None):
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

        weights = self.DEFAULT_WEIGHTS.copy()
        weights.update(self.config.custom_weights)

        fusion_weights = {
            "visual_target": weights.get("visual", 0.35),
            "behavioral": weights.get("behavioral", 0.25),
            "accessibility": weights.get("accessibility", 0.20),
            "performance": weights.get("performance", 0.20),
        }

        self.fusion = ScoreFusion(base_weights=fusion_weights)
        self._weights = weights

    async def validate(
        self,
        dimension_scores: dict[str, float] | None = None,
        dimension_reliabilities: dict[str, float] | None = None,
        validators: dict[str, BaseValidator] | None = None,
        validator_args: dict[str, dict[str, Any]] | None = None,
    ) -> ValidationResult:
        start = datetime.now()

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
                    confidence = getattr(result, "confidence", None)
                    if confidence is None:
                        confidence = 1.0 if result.passed else 0.0
                    collected_scores[dim_name] = confidence
                    dimension_details[dim_name] = result.details
                except Exception as e:
                    failed_dimensions.append(dim_name)
                    dimension_details[dim_name] = {"error": str(e)}

        if dimension_scores:
            for dim_name, score in dimension_scores.items():
                if dim_name in self.config.enabled_dimensions:
                    collected_scores[dim_name] = score

        final_scores = {
            k: v
            for k, v in collected_scores.items()
            if k in self.config.enabled_dimensions
        }

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

        fusion_scores: list[DimensionScore] = []
        for dim_name, score in final_scores.items():
            internal_name = self.DIMENSION_MAP.get(dim_name, dim_name)
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

        fusion_result: FusionResult = self.fusion.fuse_with_details(fusion_scores)
        match = fusion_result.fused_score >= self.config.confidence_threshold
        missing = [d for d in self.config.enabled_dimensions if d not in final_scores]

        message = (
            f"Multi-modal {'match' if match else 'mismatch'}: {fusion_result.fused_score:.1%} confidence "
            f"(threshold: {self.config.confidence_threshold:.1%})"
        )

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
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
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )

    def fuse_scores(
        self,
        scores: dict[str, float],
        reliabilities: dict[str, float] | None = None,
    ) -> MultiModalResult:
        reliabilities = reliabilities or {}
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

        fusion_scores: list[DimensionScore] = []
        for dim_name, score in enabled_scores.items():
            internal_name = self.DIMENSION_MAP.get(dim_name, dim_name)
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

        fusion_result = self.fusion.fuse_with_details(fusion_scores)
        match = fusion_result.fused_score >= self.config.confidence_threshold
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
