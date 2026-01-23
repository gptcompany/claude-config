#!/usr/bin/env python3
"""Orchestrator Integration - Connects confidence loop to validation orchestrator."""

import logging
from typing import Any, Protocol

from .grafana_reporter import GrafanaReporter
from .loop_controller import LoopState, ProgressiveRefinementLoop, RefinementStage
from .terminal_reporter import TerminalReporter
from .termination import TerminationEvaluator, TerminationResult

logger = logging.getLogger(__name__)


class ValidationOrchestrator(Protocol):
    async def run_all(self) -> Any: ...

    async def validate_file(self, file_path: str, tier: int = 1) -> Any: ...


class MultiModalValidator(Protocol):
    async def validate(self, **kwargs: Any) -> Any: ...


class ConfidenceLoopOrchestrator:
    def __init__(
        self,
        base_orchestrator: ValidationOrchestrator | None = None,
        loop: ProgressiveRefinementLoop | None = None,
        multimodal_validator: MultiModalValidator | None = None,
        terminal_reporter: TerminalReporter | None = None,
        grafana_reporter: GrafanaReporter | None = None,
    ):
        self.orchestrator = base_orchestrator
        self.loop = loop or ProgressiveRefinementLoop(
            multimodal_validator=multimodal_validator
        )
        self.multimodal_validator = multimodal_validator
        self.terminal = terminal_reporter or TerminalReporter()
        self.grafana = grafana_reporter
        self._current_state: LoopState | None = None
        self._last_result: TerminationResult | None = None
        self._previous_stage: RefinementStage | None = None

    async def run_with_confidence(
        self,
        validation_input: dict[str, Any] | None = None,
        confidence_threshold: float = 0.95,
        max_iterations: int = 10,
        report_progress: bool = True,
    ) -> tuple[LoopState, TerminationResult]:
        if self.loop.termination.confidence_threshold != confidence_threshold:
            self.loop.termination = TerminationEvaluator(
                confidence_threshold=confidence_threshold, max_iterations=max_iterations
            )
        else:
            self.loop.termination.reset()

        state = self.loop.create_initial_state()
        self._current_state = state
        self._previous_stage = None
        self._validation_input = validation_input

        while True:
            state, result = await self.loop.run_iteration(state)
            self._current_state = state
            self._last_result = result

            if report_progress:
                self._report_iteration(state, result)

            if self._previous_stage is not None and self._previous_stage != state.stage:
                self._report_stage_transition(self._previous_stage, state.stage)

            self._previous_stage = state.stage

            if result.should_stop:
                if report_progress:
                    self._report_final(state, result)
                return state, result

    def _report_iteration(self, state: LoopState, result: TerminationResult) -> None:
        self.terminal.report_iteration(state, result)

        if self.grafana:
            self.grafana.push_iteration_metrics(state)
            if state.stage_confidence:
                scores = {s.value: c for s, c in state.stage_confidence.items()}
                self.grafana.push_dimension_scores(scores)

    def _report_stage_transition(
        self, from_stage: RefinementStage, to_stage: RefinementStage
    ) -> None:
        self.terminal.report_stage_transition(from_stage, to_stage)

        if self.grafana:
            self.grafana.create_annotation(
                f"Stage transition: {from_stage.value} -> {to_stage.value}",
                ["confidence-loop", "stage-change"],
            )

    def _report_final(self, state: LoopState, result: TerminationResult) -> None:
        self.terminal.report_final(state, result)

        if self.grafana:
            self.grafana.create_annotation(
                f"Loop terminated: {result.reason} (confidence={state.confidence:.2%})",
                ["confidence-loop", "termination", result.reason],
            )

    def get_current_confidence(self) -> float:
        if self._current_state is None:
            return 0.0
        return self._current_state.confidence

    def get_dimension_breakdown(self) -> dict[str, float]:
        if self._current_state is None:
            return {}
        return {s.value: c for s, c in self._current_state.stage_confidence.items()}

    @property
    def current_state(self) -> LoopState | None:
        return self._current_state

    @property
    def last_result(self) -> TerminationResult | None:
        return self._last_result

    async def run_single_validation(
        self, file_path: str | None = None
    ) -> tuple[bool, float]:
        if self.orchestrator is None:
            logger.warning("No orchestrator configured")
            return True, 0.0

        if file_path:
            result = await self.orchestrator.validate_file(file_path)
            passed = not getattr(result, "has_blockers", False)
            confidence = 1.0 if passed else 0.0
        else:
            result = await self.orchestrator.run_all()
            passed = not getattr(result, "blocked", True)
            confidence = 1.0 if passed else 0.0

        return passed, confidence


__all__ = ["ConfidenceLoopOrchestrator"]
