"""
Visual validation validators.

Provides visual comparison tools for image-based validation:
- VisualTargetValidator: Combined ODiff + SSIM visual comparison
- ODiffRunner: Fast pixel-level comparison using ODiff CLI
- PerceptualComparator: SSIM-based perceptual comparison
"""

from .perceptual import SKIMAGE_AVAILABLE, PerceptualComparator, PerceptualResult
from .pixel_diff import ODiffResult, ODiffRunner
from .validator import VisualComparisonResult, VisualTargetValidator

__all__ = [
    # Main validator
    "VisualTargetValidator",
    "VisualComparisonResult",
    # Pixel comparison
    "ODiffRunner",
    "ODiffResult",
    # Perceptual comparison
    "PerceptualComparator",
    "PerceptualResult",
    "SKIMAGE_AVAILABLE",
]
