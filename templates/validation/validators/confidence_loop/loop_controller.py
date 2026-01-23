#!/usr/bin/env python3
"""Progressive Refinement Loop - Confidence-based iterative refinement with three stages."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from .termination import TerminationEvaluator, TerminationResult


class RefinementStage(Enum):
    LAYOUT = "layout"
    STYLE = "style"
    POLISH = "polish"


@dataclass
class LoopState:
    iteration: int = 0
    stage: RefinementStage = RefinementStage.LAYOUT
    confidence: float = 0.0
    stage_confidence: dict[RefinementStage, float] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    last_update: datetime | None = None


class Validator(Protocol):
    async def validate(self, **kwargs: Any) -> Any: ...


class ProgressiveRefinementLoop:
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
        self.validator = multimodal_validator
        self.termination = termination_evaluator or TerminationEvaluator()
        self.stage_thresholds = self.DEFAULT_STAGE_THRESHOLDS.copy()
        if stage_thresholds:
            self.stage_thresholds.update(stage_thresholds)

    def get_current_stage(self, confidence: float) -> RefinementStage:
        if confidence >= self.stage_thresholds[RefinementStage.STYLE]:
            return RefinementStage.POLISH
        if confidence >= self.stage_thresholds[RefinementStage.LAYOUT]:
            return RefinementStage.STYLE
        return RefinementStage.LAYOUT

    def get_feedback(self, state: LoopState) -> str:
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

        if state.stage_confidence:
            stage_info = [
                f"{s.value}={c:.1%}" for s, c in state.stage_confidence.items()
            ]
            feedback += f" | Stages: {', '.join(stage_info)}"

        return feedback

    async def _get_confidence(self, state: LoopState) -> float:
        if self.validator is None:
            return state.confidence

        try:
            result = await self.validator.validate()
            confidence = getattr(result, "confidence", None)
            if confidence is not None:
                return float(confidence)

            details = getattr(result, "details", None)
            if details and "fused_confidence" in details:
                return float(details["fused_confidence"])

            return 1.0 if getattr(result, "passed", False) else 0.0
        except Exception:
            return state.confidence

    async def run_iteration(
        self, state: LoopState
    ) -> tuple[LoopState, TerminationResult]:
        now = datetime.now()
        new_confidence = await self._get_confidence(state)
        new_stage = self.get_current_stage(new_confidence)

        new_stage_confidence = state.stage_confidence.copy()
        new_stage_confidence[new_stage] = max(
            new_stage_confidence.get(new_stage, 0.0), new_confidence
        )

        history_entry = {
            "iteration": state.iteration + 1,
            "confidence": new_confidence,
            "stage": new_stage.value,
            "timestamp": now.isoformat(),
        }

        new_state = LoopState(
            iteration=state.iteration + 1,
            stage=new_stage,
            confidence=new_confidence,
            stage_confidence=new_stage_confidence,
            history=state.history + [history_entry],
            started_at=state.started_at or now,
            last_update=now,
        )

        return new_state, self.termination.evaluate(new_confidence)

    async def run(
        self, initial_state: LoopState | None = None
    ) -> tuple[LoopState, TerminationResult]:
        state = initial_state or LoopState()
        self.termination.reset()

        while True:
            state, result = await self.run_iteration(state)
            if result.should_stop:
                return state, result

    def create_initial_state(self) -> LoopState:
        return LoopState(
            iteration=0,
            stage=RefinementStage.LAYOUT,
            confidence=0.0,
            stage_confidence={},
            history=[],
            started_at=datetime.now(),
            last_update=None,
        )


__all__ = ["ProgressiveRefinementLoop", "LoopState", "RefinementStage"]
