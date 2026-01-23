#!/usr/bin/env python3
"""Terminal Reporter for confidence loop progress with optional rich formatting."""

from .loop_controller import LoopState, RefinementStage
from .termination import TerminationResult


class TerminalReporter:
    def __init__(self, use_rich: bool = True):
        self._use_rich = use_rich and self._rich_available()
        self._console = None
        if self._use_rich:
            from rich.console import Console

            self._console = Console()

    @staticmethod
    def _rich_available() -> bool:
        try:
            import rich  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def use_rich(self) -> bool:
        return self._use_rich

    def format_confidence_bar(self, confidence: float, width: int = 40) -> str:
        confidence = max(0.0, min(1.0, confidence))
        filled = int(confidence * width)
        bar = "[" + "=" * filled + ">" * (1 if filled < width else 0)
        bar = bar[: width + 1] + " " * max(0, width - len(bar) + 1) + "]"
        return f"{bar} {confidence * 100:.0f}%"

    def _get_stage_name(self, stage: RefinementStage) -> str:
        names = {
            RefinementStage.LAYOUT: "Layout",
            RefinementStage.STYLE: "Style",
            RefinementStage.POLISH: "Polish",
        }
        return names.get(stage, stage.value if stage else "Unknown")

    def report_iteration(self, state: LoopState, result: TerminationResult) -> str:
        stage_name = self._get_stage_name(state.stage)
        confidence_bar = self.format_confidence_bar(state.confidence)

        lines = [
            f"Iteration {state.iteration}: Stage={stage_name}",
            f"Confidence: {confidence_bar}",
        ]

        if state.stage_confidence:
            breakdown = [
                f"{self._get_stage_name(s)}={conf * 100:.0f}%"
                for s, conf in state.stage_confidence.items()
            ]
            lines.append(f"Stages: {', '.join(breakdown)}")

        lines.append(
            f"Status: {'STOPPING (' + result.reason + ')' if result.should_stop else 'Continuing...'}"
        )

        output = "\n".join(lines)
        if self._use_rich and self._console:
            self._console.print(output)
        else:
            print(output)
        return output

    def report_stage_transition(
        self, from_stage: RefinementStage, to_stage: RefinementStage
    ) -> str:
        output = f">>> Stage transition: {self._get_stage_name(from_stage)} -> {self._get_stage_name(to_stage)}"
        if self._use_rich and self._console:
            self._console.print(f"[bold green]{output}[/bold green]")
        else:
            print(output)
        return output

    def report_final(self, state: LoopState, result: TerminationResult) -> str:
        reasons = {
            "threshold_met": "Confidence threshold reached!",
            "progress_stalled": "Progress stalled (no improvement)",
            "max_iterations": "Maximum iterations reached",
            "continue": "Loop still running",
        }

        lines = [
            "=" * 50,
            "REFINEMENT COMPLETE",
            "=" * 50,
            f"Final confidence: {self.format_confidence_bar(state.confidence)}",
            f"Iterations: {state.iteration}",
            f"Final stage: {self._get_stage_name(state.stage)}",
            f"Termination reason: {reasons.get(result.reason, result.reason)}",
            "=" * 50,
        ]

        output = "\n".join(lines)
        if self._use_rich and self._console:
            self._console.print(output)
        else:
            print(output)
        return output


__all__ = ["TerminalReporter"]
