"""Behavioral Validator - DOM Structure Similarity Checking.

Uses tree edit distance to compare DOM structures between baseline
and current HTML documents. Returns confidence score based on similarity.

Tier 3 validator (Monitor) - emits metrics, doesn't block.
"""

from .dom_diff import ZSS_AVAILABLE, ComparisonResult, DOMComparator, DOMNode
from .validator import (
    BehavioralConfig,
    BehavioralValidator,
    ValidationResult,
    ValidationTier,
)

__all__ = [
    # Main exports
    "BehavioralValidator",
    "BehavioralConfig",
    # Types
    "ValidationResult",
    "ValidationTier",
    # DOM comparison
    "DOMComparator",
    "DOMNode",
    "ComparisonResult",
    "ZSS_AVAILABLE",
]
