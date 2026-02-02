#!/usr/bin/env python3
"""
BehavioralValidator - DOM Structure Similarity Validator

Tier 3 validator that checks DOM structural similarity between
baseline and current HTML documents using tree edit distance.

Returns confidence score based on structural similarity.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .dom_diff import ZSS_AVAILABLE, ComparisonResult, DOMComparator


# Define types locally for standalone testing (matches orchestrator types)
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
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0
    confidence: float = 1.0  # Added for behavioral validator


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
class BehavioralConfig:
    """Configuration for BehavioralValidator."""

    similarity_threshold: float = 0.90  # Default threshold for "match"
    ignore_attributes: list[str] = field(
        default_factory=lambda: ["id", "class", "style"]
    )
    focus_selectors: list[str] | None = None  # Future: compare subset of DOM


class BehavioralValidator(BaseValidator):
    """
    Tier 3: Behavioral/DOM Structure Validator.

    Compares DOM structure between baseline and current HTML using
    tree edit distance. Returns confidence score based on similarity.

    Usage:
        validator = BehavioralValidator()
        result = await validator.validate(baseline_html, current_html)
        print(f"Confidence: {result.confidence}")
        print(f"Passed: {result.passed}")
    """

    dimension = "behavioral"
    tier = ValidationTier.MONITOR

    def __init__(self, config: BehavioralConfig | dict | None = None):
        """
        Initialize validator with optional config.

        Args:
            config: BehavioralConfig or dict with config options
        """
        if config is None:
            self.config = BehavioralConfig()
        elif isinstance(config, dict):
            self.config = BehavioralConfig(
                similarity_threshold=config.get("similarity_threshold", 0.90),
                ignore_attributes=config.get(
                    "ignore_attributes", ["id", "class", "style"]
                ),
                focus_selectors=config.get("focus_selectors"),
            )
        else:
            self.config = config

        self.comparator = DOMComparator(
            ignore_attributes=self.config.ignore_attributes,
            focus_selectors=self.config.focus_selectors,
        )

    async def validate(
        self, baseline_html: str = "", current_html: str = ""
    ) -> ValidationResult:
        """
        Compare baseline and current HTML structure.

        Args:
            baseline_html: Expected/reference HTML document
            current_html: Actual/current HTML document

        Returns:
            ValidationResult with confidence score and operation details
        """
        start = datetime.now()

        # Perform DOM comparison
        comparison: ComparisonResult = self.comparator.compare(
            baseline_html, current_html
        )

        # Determine pass/fail based on threshold
        passed = comparison.similarity_score >= self.config.similarity_threshold

        # Calculate confidence (same as similarity for this validator)
        confidence = comparison.similarity_score

        # Build message
        if passed:
            message = f"DOM structure match: {confidence:.1%} similarity"
        else:
            message = (
                f"DOM structure mismatch: {confidence:.1%} similarity "
                f"(threshold: {self.config.similarity_threshold:.1%})"
            )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=message,
            confidence=confidence,
            details={
                "similarity_score": comparison.similarity_score,
                "edit_distance": comparison.edit_distance,
                "tree1_size": comparison.tree1_size,
                "tree2_size": comparison.tree2_size,
                "operations": comparison.operations,
                "threshold": self.config.similarity_threshold,
                "ignore_attributes": self.config.ignore_attributes,
                "zss_available": comparison.zss_available,
            },
            duration_ms=duration_ms,
        )


# Export for testing
__all__ = [
    "BehavioralValidator",
    "BehavioralConfig",
    "ValidationResult",
    "ValidationTier",
    "ZSS_AVAILABLE",
]
