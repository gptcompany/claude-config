"""
MultiModal Validator Package.

Provides multi-dimensional score fusion for combining validation
results from visual, behavioral, accessibility, and performance
validators into unified confidence scoring.
"""

from .score_fusion import DimensionScore, FusionResult, ScoreFusion
from .validator import (
    MultiModalConfig,
    MultiModalResult,
    MultiModalValidator,
    ValidationResult,
    ValidationTier,
)

__all__ = [
    # Score fusion
    "ScoreFusion",
    "DimensionScore",
    "FusionResult",
    # Validator
    "MultiModalValidator",
    "MultiModalConfig",
    "MultiModalResult",
    # Base types
    "ValidationResult",
    "ValidationTier",
]
