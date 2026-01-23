#!/usr/bin/env python3
"""
Terminal Reporter - Rich progress display for confidence loops.

Provides human-readable output for confidence loop progress with optional
rich library integration for enhanced formatting.
"""

from .loop_controller import LoopState, RefinementStage
from .termination import TerminationResult


class TerminalReporter:
    """
    Terminal reporter for confidence loop feedback.

    Displays iteration progress, stage transitions, and final summaries.
    Falls back to plain text if rich library is not available.

    Usage:
        reporter = TerminalReporter()
        reporter.report_iteration(state, result)
        reporter.report_stage_transition(old_stage, new_stage)
        reporter.report_final(state, result)
    """

    def __init__(self, use_rich: bool = True):
        """
        Initialize terminal reporter.

        Args:
            use_rich: Whether to use rich library for formatting (if available)
        """
        self._use_rich = use_rich and self._rich_available()
        self._console = None
        if self._use_rich:
            from rich.console import Console

            self._console = Console()

    @staticmethod
    def _rich_available() -> bool:
        """Check if rich library is available."""
        try:
            import rich  # noqa: F401

            return True
        except ImportError:
            return False

    @property
    def use_rich(self) -> bool:
        """Whether rich formatting is enabled."""
        return self._use_rich

    def format_confidence_bar(self, confidence: float, width: int = 40) -> str:
        """
        Create visual progress bar for confidence.

        Args:
            confidence: Confidence value (0.0 to 1.0)
            width: Width of the bar in characters

        Returns:
            Visual progress bar string like "[=========>          ] 45%"
        """
        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))

        # Calculate filled portion
        filled = int(confidence * width)
        empty = width - filled

        # Build bar
        bar = "[" + "=" * filled + ">" * (1 if filled < width else 0)
        bar = bar[: width + 1]  # Ensure we don't exceed width + bracket
        bar += " " * max(0, width - len(bar) + 1) + "]"

        # Add percentage
        percentage = self._format_percentage(confidence)
        return f"{bar} {percentage}"

    def _format_percentage(self, value: float) -> str:
        """Format a value as percentage string."""
        return f"{value * 100:.0f}%"

    def _get_stage_name(self, stage: RefinementStage) -> str:
        """Get human-readable stage name."""
        stage_names = {
            RefinementStage.LAYOUT: "Layout",
            RefinementStage.STYLE: "Style",
            RefinementStage.POLISH: "Polish",
        }
        return stage_names.get(stage, stage.value if stage else "Unknown")

    def report_iteration(self, state: LoopState, result: TerminationResult) -> str:
        """
        Display current iteration state in terminal.

        Args:
            state: Current loop state
            result: Current termination result

        Returns:
            Formatted string for the iteration report
        """
        stage_name = self._get_stage_name(state.stage)
        confidence_bar = self.format_confidence_bar(state.confidence)

        lines = [
            f"Iteration {state.iteration}: Stage={stage_name}",
            f"Confidence: {confidence_bar}",
        ]

        # Add per-dimension breakdown if available
        if state.stage_confidence:
            breakdown = []
            for s, conf in state.stage_confidence.items():
                breakdown.append(
                    f"{self._get_stage_name(s)}={self._format_percentage(conf)}"
                )
            lines.append(f"Stages: {', '.join(breakdown)}")

        # Add termination status
        if result.should_stop:
            lines.append(f"Status: STOPPING ({result.reason})")
        else:
            lines.append("Status: Continuing...")

        output = "\n".join(lines)

        if self._use_rich and self._console:
            self._console.print(output)
        else:
            print(output)

        return output

    def report_stage_transition(
        self, from_stage: RefinementStage, to_stage: RefinementStage
    ) -> str:
        """
        Announce stage transition.

        Args:
            from_stage: Previous refinement stage
            to_stage: New refinement stage

        Returns:
            Formatted transition announcement string
        """
        from_name = self._get_stage_name(from_stage)
        to_name = self._get_stage_name(to_stage)

        output = f">>> Stage transition: {from_name} -> {to_name}"

        if self._use_rich and self._console:
            self._console.print(f"[bold green]{output}[/bold green]")
        else:
            print(output)

        return output

    def report_final(self, state: LoopState, result: TerminationResult) -> str:
        """
        Display final summary when loop terminates.

        Args:
            state: Final loop state
            result: Final termination result

        Returns:
            Formatted final summary string
        """
        reason_descriptions = {
            "threshold_met": "Confidence threshold reached!",
            "progress_stalled": "Progress stalled (no improvement)",
            "max_iterations": "Maximum iterations reached",
            "continue": "Loop still running",
        }

        reason_desc = reason_descriptions.get(result.reason, result.reason)
        confidence_bar = self.format_confidence_bar(state.confidence)

        lines = [
            "=" * 50,
            "REFINEMENT COMPLETE",
            "=" * 50,
            f"Final confidence: {confidence_bar}",
            f"Iterations: {state.iteration}",
            f"Final stage: {self._get_stage_name(state.stage)}",
            f"Termination reason: {reason_desc}",
            "=" * 50,
        ]

        output = "\n".join(lines)

        if self._use_rich and self._console:
            self._console.print(output)
        else:
            print(output)

        return output


__all__ = ["TerminalReporter"]
