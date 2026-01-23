#!/usr/bin/env python3
"""
Progressive Refinement Loop - Confidence-based iterative refinement.

Implements Self-Refine pattern with three-stage progressive refinement:
1. LAYOUT - Get structure right (threshold: 0.80)
2. STYLE - Get appearance right (threshold: 0.90)
3. POLISH - Fine-tune details (threshold: 0.95)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from .termination import TerminationEvaluator, TerminationResult


class RefinementStage(Enum):
    """Stages of progressive refinement."""

    LAYOUT = "layout"  # Stage 1: Get structure right
    STYLE = "style"  # Stage 2: Get appearance right
    POLISH = "polish"  # Stage 3: Fine-tune details


@dataclass
class LoopState:
    """State of the refinement loop."""

    iteration: int = 0
    stage: RefinementStage = RefinementStage.LAYOUT
    confidence: float = 0.0
    stage_confidence: dict[RefinementStage, float] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    last_update: datetime | None = None


class Validator(Protocol):
    """Protocol for validators that can produce confidence scores."""

    async def validate(self, **kwargs: Any) -> Any:
        """Run validation and return result with confidence."""
        ...


class ProgressiveRefinementLoop:
    """
    Confidence-based iterative refinement loop.

    Implements Self-Refine pattern that continues iterating until
    confidence threshold is met or progress stalls.

    Three-stage refinement:
    1. LAYOUT (threshold: 0.80) - Get structure right
    2. STYLE (threshold: 0.90) - Get appearance right
    3. POLISH (threshold: 0.95) - Fine-tune details

    Usage:
        loop = ProgressiveRefinementLoop(
            multimodal_validator=validator,
            termination_evaluator=evaluator,
        )

        state, result = await loop.run()
        print(f"Final confidence: {state.confidence}")
        print(f"Termination reason: {result.reason}")
    """

    DEFAULT_STAGE_THRESHOLDS = {
        RefinementStage.LAYOUT: 0.80,
        RefinementStage.STYLE: 0.90,
        RefinementStage.POLISH: 0.95,
    }

    def __init__(
        self,
        multimodal_validator: Validator | None = None,
        termination_evaluator: TerminationEvaluator | None = None,
        stage_thresholds: dict[RefinementStage, float] | None = None,
    ):
        """
        Initialize refinement loop.

        Args:
            multimodal_validator: Validator that produces confidence scores
            termination_evaluator: Evaluator for termination conditions
            stage_thresholds: Custom thresholds for each stage
        """
        self.validator = multimodal_validator
        self.termination = termination_evaluator or TerminationEvaluator()

        # Merge default thresholds with custom ones
        self.stage_thresholds = self.DEFAULT_STAGE_THRESHOLDS.copy()
        if stage_thresholds:
            self.stage_thresholds.update(stage_thresholds)

    def get_current_stage(self, confidence: float) -> RefinementStage:
        """
        Determine current stage based on confidence level.

        Args:
            confidence: Current confidence score (0.0 to 1.0)

        Returns:
            Current refinement stage
        """
        if confidence >= self.stage_thresholds[RefinementStage.STYLE]:
            return RefinementStage.POLISH
        elif confidence >= self.stage_thresholds[RefinementStage.LAYOUT]:
            return RefinementStage.STYLE
        else:
            return RefinementStage.LAYOUT

    def get_feedback(self, state: LoopState) -> str:
        """
        Generate human-readable feedback for current state.

        Args:
            state: Current loop state

        Returns:
            Human-readable feedback string
        """
        stage_names = {
            RefinementStage.LAYOUT: "Layout",
            RefinementStage.STYLE: "Style",
            RefinementStage.POLISH: "Polish",
        }

        stage_name = stage_names.get(state.stage, "Unknown")
        threshold = self.stage_thresholds.get(state.stage, 0.0)

        feedback = (
            f"Iteration {state.iteration}: "
            f"Stage={stage_name}, "
            f"Confidence={state.confidence:.1%} "
            f"(target: {threshold:.1%})"
        )

        # Add stage progress if available
        if state.stage_confidence:
            stage_info = []
            for stage, conf in state.stage_confidence.items():
                stage_info.append(f"{stage.value}={conf:.1%}")
            feedback += f" | Stages: {', '.join(stage_info)}"

        return feedback

    async def _get_confidence(self, state: LoopState) -> float:
        """
        Get confidence from validator or simulate.

        Args:
            state: Current loop state

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if self.validator is None:
            # No validator - return current confidence (for testing)
            return state.confidence

        try:
            result = await self.validator.validate()
            # Extract confidence from result (check value, not just attribute existence)
            confidence = getattr(result, "confidence", None)
            if confidence is not None:
                return float(confidence)

            # Check details dict for fused_confidence
            details = getattr(result, "details", None)
            if details and "fused_confidence" in details:
                return float(details["fused_confidence"])

            # Fallback: use passed as 1.0/0.0
            return 1.0 if getattr(result, "passed", False) else 0.0
        except Exception:
            # On error, return current confidence
            return state.confidence

    async def run_iteration(
        self, state: LoopState
    ) -> tuple[LoopState, TerminationResult]:
        """
        Run one iteration of the refinement loop.

        Args:
            state: Current loop state

        Returns:
            Tuple of (updated state, termination result)
        """
        now = datetime.now()

        # Update iteration count
        new_iteration = state.iteration + 1

        # Get new confidence from validator
        new_confidence = await self._get_confidence(state)

        # Determine stage based on confidence
        new_stage = self.get_current_stage(new_confidence)

        # Update stage confidence
        new_stage_confidence = state.stage_confidence.copy()
        new_stage_confidence[new_stage] = max(
            new_stage_confidence.get(new_stage, 0.0), new_confidence
        )

        # Record history entry
        history_entry = {
            "iteration": new_iteration,
            "confidence": new_confidence,
            "stage": new_stage.value,
            "timestamp": now.isoformat(),
        }
        new_history = state.history + [history_entry]

        # Create updated state
        new_state = LoopState(
            iteration=new_iteration,
            stage=new_stage,
            confidence=new_confidence,
            stage_confidence=new_stage_confidence,
            history=new_history,
            started_at=state.started_at or now,
            last_update=now,
        )

        # Evaluate termination
        termination_result = self.termination.evaluate(new_confidence)

        return new_state, termination_result

    async def run(
        self, initial_state: LoopState | None = None
    ) -> tuple[LoopState, TerminationResult]:
        """
        Run complete refinement loop until termination.

        Args:
            initial_state: Optional initial state (creates new if None)

        Returns:
            Tuple of (final state, termination result)
        """
        # Initialize state
        state = initial_state or LoopState()

        # Reset termination evaluator for fresh run
        self.termination.reset()

        # Run iterations until termination
        while True:
            state, result = await self.run_iteration(state)

            if result.should_stop:
                return state, result

    def create_initial_state(self) -> LoopState:
        """
        Create fresh initial state for a new loop.

        Returns:
            New LoopState initialized at LAYOUT stage
        """
        return LoopState(
            iteration=0,
            stage=RefinementStage.LAYOUT,
            confidence=0.0,
            stage_confidence={},
            history=[],
            started_at=datetime.now(),
            last_update=None,
        )


__all__ = [
    "ProgressiveRefinementLoop",
    "LoopState",
    "RefinementStage",
]
