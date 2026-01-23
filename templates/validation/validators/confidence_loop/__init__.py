"""
Confidence Loop - Progressive refinement with confidence-based termination.

Implements Self-Refine pattern with three-stage refinement:
1. LAYOUT - Get structure right
2. STYLE - Get appearance right
3. POLISH - Fine-tune details
"""

from .loop_controller import LoopState, ProgressiveRefinementLoop, RefinementStage
from .termination import TerminationEvaluator, TerminationResult

__all__ = [
    # Loop controller
    "ProgressiveRefinementLoop",
    "LoopState",
    "RefinementStage",
    # Termination
    "TerminationEvaluator",
    "TerminationResult",
]
