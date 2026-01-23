#!/usr/bin/env python3
"""
VisualTargetValidator - Tier 3 Visual Comparison Validator.

Combines ODiff pixel comparison and SSIM perceptual comparison
for comprehensive visual validation with fused confidence scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .perceptual import PerceptualComparator, PerceptualResult
from .pixel_diff import ODiffResult, ODiffRunner


# Base types (with fallback for standalone testing)
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


class BaseValidator:
    dimension = "unknown"
    tier = ValidationTier.MONITOR
    agent = None

    async def validate(self) -> ValidationResult:
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


@dataclass
class VisualComparisonResult:
    """Combined result from visual comparison."""

    confidence: float  # Fused score (0.0 to 1.0)
    match: bool  # True if confidence >= threshold
    pixel_score: float  # ODiff pixel score
    ssim_score: float  # SSIM perceptual score
    diff_path: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class VisualTargetValidator(BaseValidator):
    """
    Tier 3: Visual comparison validator.

    Combines two comparison methods for robust visual validation:
    1. ODiff (pixel-level): Fast SIMD-based pixel comparison
    2. SSIM (perceptual): Structural similarity for meaningful differences

    The fused confidence score weights both methods:
    confidence = (pixel_score * pixel_weight) + (ssim_score * ssim_weight)

    Usage:
        validator = VisualTargetValidator(config={
            "baseline_dir": "/path/to/baselines",
            "threshold": 0.85,
        })
        result = await validator.validate()

    Or for direct comparison:
        validator = VisualTargetValidator()
        result = validator.compare("baseline.png", "current.png")
    """

    dimension = "visual_target"
    tier = ValidationTier.MONITOR
    agent = None  # Visual differences need human review

    DEFAULT_CONFIG = {
        "threshold": 0.85,  # Minimum fused confidence for match
        "pixel_weight": 0.6,  # Weight for ODiff pixel score
        "ssim_weight": 0.4,  # Weight for SSIM perceptual score
        "odiff_threshold": 0.1,  # ODiff color threshold
        "odiff_antialiasing": True,  # Ignore antialiasing
        "ssim_threshold": 0.95,  # SSIM individual threshold
        "ssim_win_size": 7,  # SSIM window size
        "baseline_dir": None,  # Directory containing baseline images
        "current_dir": None,  # Directory containing current images
        "diff_dir": None,  # Directory to save diff images
        "patterns": ["**/*.png", "**/*.jpg", "**/*.jpeg"],  # Image patterns
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        # Initialize comparators
        self.odiff_runner = ODiffRunner(
            threshold=self.config["odiff_threshold"],
            antialiasing=self.config["odiff_antialiasing"],
        )
        self.perceptual_comparator = PerceptualComparator(
            threshold=self.config["ssim_threshold"],
            win_size=self.config["ssim_win_size"],
        )

    def is_available(self) -> dict[str, bool]:
        """Check availability of comparison tools."""
        return {
            "odiff": self.odiff_runner.is_available(),
            "ssim": self.perceptual_comparator.is_available(),
        }

    def _fuse_scores(
        self,
        pixel_score: float,
        ssim_score: float,
    ) -> float:
        """
        Fuse pixel and SSIM scores into combined confidence.

        Uses weighted average with configurable weights.
        Default: 60% pixel, 40% SSIM
        """
        pixel_weight = self.config["pixel_weight"]
        ssim_weight = self.config["ssim_weight"]

        # Normalize weights in case they don't sum to 1
        total_weight = pixel_weight + ssim_weight
        pixel_weight = pixel_weight / total_weight
        ssim_weight = ssim_weight / total_weight

        return (pixel_score * pixel_weight) + (ssim_score * ssim_weight)

    def compare(
        self,
        baseline: str,
        current: str,
        diff_output: str | None = None,
    ) -> VisualComparisonResult:
        """
        Compare two images using both pixel and perceptual methods.

        Args:
            baseline: Path to baseline/expected image
            current: Path to current/actual image
            diff_output: Optional path to save diff visualization

        Returns:
            VisualComparisonResult with fused confidence score
        """
        availability = self.is_available()

        # Check if at least one method is available
        if not availability["odiff"] and not availability["ssim"]:
            return VisualComparisonResult(
                confidence=0.0,
                match=False,
                pixel_score=0.0,
                ssim_score=0.0,
                error="No comparison tools available. Install odiff or scikit-image.",
                details={"availability": availability},
            )

        pixel_result: ODiffResult | None = None
        ssim_result: PerceptualResult | None = None

        # Run ODiff if available
        if availability["odiff"]:
            odiff_diff = (
                diff_output.replace(".png", "_pixel.png") if diff_output else None
            )
            pixel_result = self.odiff_runner.compare(
                baseline, current, odiff_diff or "/tmp/odiff_diff.png"
            )

        # Run SSIM if available
        if availability["ssim"]:
            ssim_diff = (
                diff_output.replace(".png", "_ssim.png") if diff_output else None
            )
            ssim_result = self.perceptual_comparator.compare(
                baseline, current, ssim_diff
            )

        # Extract scores (use 0.0 if method unavailable or failed)
        pixel_score = 0.0
        ssim_score = 0.0
        errors: list[str] = []

        if pixel_result:
            if pixel_result.error:
                errors.append(f"ODiff: {pixel_result.error}")
            else:
                pixel_score = pixel_result.pixel_score

        if ssim_result:
            if ssim_result.error:
                errors.append(f"SSIM: {ssim_result.error}")
            else:
                ssim_score = ssim_result.ssim_score

        # Handle case where both methods failed
        if pixel_score == 0.0 and ssim_score == 0.0 and errors:
            return VisualComparisonResult(
                confidence=0.0,
                match=False,
                pixel_score=0.0,
                ssim_score=0.0,
                error="; ".join(errors),
                details={"availability": availability},
            )

        # Adjust weights if only one method available/successful
        if pixel_score == 0.0 and ssim_score > 0.0:
            # Only SSIM available - use it exclusively
            confidence = ssim_score
        elif ssim_score == 0.0 and pixel_score > 0.0:
            # Only ODiff available - use it exclusively
            confidence = pixel_score
        else:
            # Both available - fuse scores
            confidence = self._fuse_scores(pixel_score, ssim_score)

        # Determine match based on threshold
        threshold = self.config["threshold"]
        match = confidence >= threshold

        # Determine diff path
        diff_path = None
        if not match:
            if pixel_result and pixel_result.diff_path:
                diff_path = pixel_result.diff_path
            elif ssim_result and ssim_result.diff_image_path:
                diff_path = ssim_result.diff_image_path

        return VisualComparisonResult(
            confidence=confidence,
            match=match,
            pixel_score=pixel_score,
            ssim_score=ssim_score,
            diff_path=diff_path,
            error="; ".join(errors) if errors else None,
            details={
                "availability": availability,
                "threshold": threshold,
                "pixel_weight": self.config["pixel_weight"],
                "ssim_weight": self.config["ssim_weight"],
                "odiff_details": pixel_result.details if pixel_result else {},
                "ssim_details": ssim_result.details if ssim_result else {},
            },
        )

    async def validate(self) -> ValidationResult:
        """
        Run visual validation on configured directories.

        Compares all images matching patterns in baseline_dir vs current_dir.
        Returns aggregated validation result.
        """
        start = datetime.now()

        baseline_dir = self.config.get("baseline_dir")
        current_dir = self.config.get("current_dir")

        # If no directories configured, just report availability
        if not baseline_dir or not current_dir:
            availability = self.is_available()
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="Visual validator ready (no directories configured)",
                details={
                    "availability": availability,
                    "configured": False,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        baseline_path = Path(baseline_dir)
        current_path = Path(current_dir)

        if not baseline_path.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Tier 3 doesn't block
                message=f"Baseline directory not found: {baseline_dir}",
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        if not current_path.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Tier 3 doesn't block
                message=f"Current directory not found: {current_dir}",
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Find all matching images
        baseline_images: list[Path] = []
        for pattern in self.config["patterns"]:
            baseline_images.extend(baseline_path.glob(pattern))

        if not baseline_images:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No baseline images found",
                details={"patterns": self.config["patterns"]},
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Compare each baseline with corresponding current
        results: list[dict[str, Any]] = []
        mismatches: list[str] = []
        total_confidence = 0.0

        diff_dir = self.config.get("diff_dir")
        if diff_dir:
            Path(diff_dir).mkdir(parents=True, exist_ok=True)

        for baseline_img in baseline_images:
            rel_path = baseline_img.relative_to(baseline_path)
            current_img = current_path / rel_path

            if not current_img.exists():
                mismatches.append(f"{rel_path}: missing")
                results.append(
                    {
                        "image": str(rel_path),
                        "status": "missing",
                        "confidence": 0.0,
                    }
                )
                continue

            diff_output = None
            if diff_dir:
                diff_output = str(Path(diff_dir) / f"{rel_path.stem}_diff.png")

            comparison = self.compare(
                str(baseline_img),
                str(current_img),
                diff_output,
            )

            total_confidence += comparison.confidence
            results.append(
                {
                    "image": str(rel_path),
                    "status": "match" if comparison.match else "mismatch",
                    "confidence": comparison.confidence,
                    "pixel_score": comparison.pixel_score,
                    "ssim_score": comparison.ssim_score,
                    "diff_path": comparison.diff_path,
                }
            )

            if not comparison.match:
                mismatches.append(f"{rel_path}: {comparison.confidence:.2f}")

        # Calculate average confidence
        avg_confidence = (
            total_confidence / len(baseline_images) if baseline_images else 0.0
        )
        match_count = len([r for r in results if r["status"] == "match"])

        # Tier 3 always passes (monitoring only)
        passed = True
        message = f"{match_count}/{len(baseline_images)} images match (avg confidence: {avg_confidence:.2f})"

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=message,
            details={
                "images_compared": len(baseline_images),
                "matches": match_count,
                "mismatches": len(mismatches),
                "average_confidence": avg_confidence,
                "threshold": self.config["threshold"],
                "mismatch_details": mismatches[:10],  # Limit to 10
                "availability": self.is_available(),
            },
            fix_suggestion=(
                f"Review visual differences: {', '.join(mismatches[:3])}"
                if mismatches
                else None
            ),
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


__all__ = ["VisualTargetValidator", "VisualComparisonResult"]
