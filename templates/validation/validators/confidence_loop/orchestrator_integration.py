#!/usr/bin/env python3
"""
Orchestrator Integration - Connects confidence loop to validation orchestrator.

Provides the bridge between the confidence loop components and the existing
ValidationOrchestrator, enabling confidence-based validation workflows.
"""

import logging
from typing import Any, Protocol

from .grafana_reporter import GrafanaReporter
from .loop_controller import LoopState, ProgressiveRefinementLoop, RefinementStage
from .terminal_reporter import TerminalReporter
from .termination import TerminationEvaluator, TerminationResult

logger = logging.getLogger(__name__)


class ValidationOrchestrator(Protocol):
    """Protocol for ValidationOrchestrator compatibility."""

    async def run_all(self) -> Any:
        """Run all validation tiers."""
        ...

    async def validate_file(self, file_path: str, tier: int = 1) -> Any:
        """Validate a single file."""
        ...


class MultiModalValidator(Protocol):
    """Protocol for MultiModalValidator compatibility."""

    async def validate(self, **kwargs: Any) -> Any:
        """Run validation and return result with confidence."""
        ...


class ConfidenceLoopOrchestrator:
    """
    Integration layer connecting confidence loop to existing orchestrator.

    Wraps a ValidationOrchestrator and ProgressiveRefinementLoop to provide
    confidence-based validation workflows with dual reporting (terminal + Grafana).

    Usage:
        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=validation_orchestrator,
            loop=progressive_refinement_loop,
        )

        state, result = await orchestrator.run_with_confidence(
            validation_input={"file": "src/app.py"},
            confidence_threshold=0.95,
        )
    """

    def __init__(
        self,
        base_orchestrator: ValidationOrchestrator | None = None,
        loop: ProgressiveRefinementLoop | None = None,
        multimodal_validator: MultiModalValidator | None = None,
        terminal_reporter: TerminalReporter | None = None,
        grafana_reporter: GrafanaReporter | None = None,
    ):
        """
        Initialize orchestrator integration.

        Args:
            base_orchestrator: Existing ValidationOrchestrator instance
            loop: ProgressiveRefinementLoop instance
            multimodal_validator: Optional MultiModalValidator for confidence scoring
            terminal_reporter: Terminal reporter (creates default if None)
            grafana_reporter: Grafana reporter (optional)
        """
        self.orchestrator = base_orchestrator
        self.loop = loop or ProgressiveRefinementLoop(
            multimodal_validator=multimodal_validator,
        )
        self.multimodal_validator = multimodal_validator
        self.terminal = terminal_reporter or TerminalReporter()
        self.grafana = grafana_reporter

        # Track state
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
        """
        Run validation loop until confidence threshold met.

        Executes iterations of:
        1. Run validation (via loop's validator or orchestrator)
        2. Get confidence score
        3. Report progress (terminal + Grafana)
        4. Check termination conditions
        5. Continue or stop

        Args:
            validation_input: Input data for validation
            confidence_threshold: Target confidence (0.0 to 1.0)
            max_iterations: Maximum iterations before forced stop
            report_progress: Whether to report progress to terminal/Grafana

        Returns:
            Tuple of (final state, termination result)
        """
        # Configure termination evaluator if loop doesn't have one
        if self.loop.termination.confidence_threshold != confidence_threshold:
            self.loop.termination = TerminationEvaluator(
                confidence_threshold=confidence_threshold,
                max_iterations=max_iterations,
            )
        else:
            self.loop.termination.reset()

        # Initialize state
        state = self.loop.create_initial_state()
        self._current_state = state
        self._previous_stage = None

        # Store validation input for potential use
        self._validation_input = validation_input

        # Run loop with reporting
        while True:
            state, result = await self.loop.run_iteration(state)
            self._current_state = state
            self._last_result = result

            # Report progress
            if report_progress:
                self._report_iteration(state, result)

            # Check for stage transition
            if self._previous_stage is not None and self._previous_stage != state.stage:
                self._report_stage_transition(self._previous_stage, state.stage)

            self._previous_stage = state.stage

            # Check termination
            if result.should_stop:
                if report_progress:
                    self._report_final(state, result)
                return state, result

    def _report_iteration(self, state: LoopState, result: TerminationResult) -> None:
        """Report iteration progress to terminal and Grafana."""
        # Terminal
        self.terminal.report_iteration(state, result)

        # Grafana (if configured)
        if self.grafana:
            self.grafana.push_iteration_metrics(state)

            # Push dimension scores if available
            if state.stage_confidence:
                scores = {s.value: c for s, c in state.stage_confidence.items()}
                self.grafana.push_dimension_scores(scores)

    def _report_stage_transition(
        self, from_stage: RefinementStage, to_stage: RefinementStage
    ) -> None:
        """Report stage transition."""
        self.terminal.report_stage_transition(from_stage, to_stage)

        if self.grafana:
            self.grafana.create_annotation(
                f"Stage transition: {from_stage.value} -> {to_stage.value}",
                ["confidence-loop", "stage-change"],
            )

    def _report_final(self, state: LoopState, result: TerminationResult) -> None:
        """Report final summary."""
        self.terminal.report_final(state, result)

        if self.grafana:
            self.grafana.create_annotation(
                f"Loop terminated: {result.reason} (confidence={state.confidence:.2%})",
                ["confidence-loop", "termination", result.reason],
            )

    def get_current_confidence(self) -> float:
        """
        Get current unified confidence from all validators.

        Returns:
            Current confidence score (0.0 to 1.0), or 0.0 if no state
        """
        if self._current_state is None:
            return 0.0
        return self._current_state.confidence

    def get_dimension_breakdown(self) -> dict[str, float]:
        """
        Get per-dimension confidence breakdown.

        Returns:
            Dict mapping dimension name to confidence score
        """
        if self._current_state is None:
            return {}

        # Convert RefinementStage keys to string
        return {
            stage.value: confidence
            for stage, confidence in self._current_state.stage_confidence.items()
        }

    @property
    def current_state(self) -> LoopState | None:
        """Get current loop state."""
        return self._current_state

    @property
    def last_result(self) -> TerminationResult | None:
        """Get last termination result."""
        return self._last_result

    async def run_single_validation(
        self, file_path: str | None = None
    ) -> tuple[bool, float]:
        """
        Run a single validation pass without looping.

        Useful for quick checks or integration with existing workflows.

        Args:
            file_path: Optional file path for file-specific validation

        Returns:
            Tuple of (passed, confidence)
        """
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
