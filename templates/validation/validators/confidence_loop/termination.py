#!/usr/bin/env python3
"""
Termination Evaluator - Dynamic termination logic for confidence loops.

Evaluates when to stop iterating based on:
1. Confidence threshold met
2. Progress stalled (no improvement)
3. Maximum iterations reached
"""

from dataclasses import dataclass, field


@dataclass
class TerminationResult:
    """Result of termination evaluation."""

    should_stop: bool
    reason: str  # "threshold_met", "progress_stalled", "max_iterations", "continue"
    confidence: float
    iterations: int
    history: list[float] = field(default_factory=list)


class TerminationEvaluator:
    """
    Evaluates when a confidence loop should terminate.

    Supports three termination conditions (evaluated in order):
    1. confidence >= threshold -> "threshold_met"
    2. delta < epsilon for stall_count_limit iterations -> "progress_stalled"
    3. iterations >= max_iterations -> "max_iterations"

    Usage:
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            max_iterations=10,
            stall_epsilon=0.01,
            stall_count_limit=3,
        )

        # Each iteration
        result = evaluator.evaluate(current_confidence)
        if result.should_stop:
            print(f"Stopping: {result.reason}")
    """

    def __init__(
        self,
        confidence_threshold: float = 0.95,
        max_iterations: int = 10,
        stall_epsilon: float = 0.01,
        stall_count_limit: int = 3,
    ):
        """
        Initialize termination evaluator.

        Args:
            confidence_threshold: Stop when confidence reaches this level
            max_iterations: Maximum iterations before forced stop
            stall_epsilon: Minimum improvement to not count as stalled
            stall_count_limit: Number of stalled iterations before stopping
        """
        if confidence_threshold < 0.0 or confidence_threshold > 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if stall_epsilon < 0.0:
            raise ValueError("stall_epsilon must be non-negative")
        if stall_count_limit < 1:
            raise ValueError("stall_count_limit must be at least 1")

        self.confidence_threshold = confidence_threshold
        self.max_iterations = max_iterations
        self.stall_epsilon = stall_epsilon
        self.stall_count_limit = stall_count_limit

        self._history: list[float] = []
        self._stall_count: int = 0

    @property
    def history(self) -> list[float]:
        """Get confidence history (copy)."""
        return self._history.copy()

    @property
    def iterations(self) -> int:
        """Get number of iterations so far."""
        return len(self._history)

    @property
    def stall_count(self) -> int:
        """Get current stall count."""
        return self._stall_count

    def evaluate(self, current_confidence: float) -> TerminationResult:
        """
        Evaluate if loop should terminate.

        Termination conditions (in order of priority):
        1. confidence >= threshold -> "threshold_met"
        2. delta < epsilon for stall_count_limit iterations -> "progress_stalled"
        3. iterations >= max_iterations -> "max_iterations"

        Args:
            current_confidence: Current confidence score (0.0 to 1.0)

        Returns:
            TerminationResult with should_stop, reason, and metadata
        """
        # Clamp confidence to valid range
        current_confidence = max(0.0, min(1.0, current_confidence))

        # Check for progress stall before adding to history
        if self._history:
            delta = current_confidence - self._history[-1]
            if delta < self.stall_epsilon:
                self._stall_count += 1
            else:
                self._stall_count = 0

        # Add to history
        self._history.append(current_confidence)

        # Build result helper
        def result(should_stop: bool, reason: str) -> TerminationResult:
            return TerminationResult(
                should_stop=should_stop,
                reason=reason,
                confidence=current_confidence,
                iterations=len(self._history),
                history=self._history.copy(),
            )

        # Check 1: Threshold met
        if current_confidence >= self.confidence_threshold:
            return result(True, "threshold_met")

        # Check 2: Progress stalled
        if self._stall_count >= self.stall_count_limit:
            return result(True, "progress_stalled")

        # Check 3: Max iterations
        if len(self._history) >= self.max_iterations:
            return result(True, "max_iterations")

        # Continue iterating
        return result(False, "continue")

    def reset(self) -> None:
        """Reset evaluator for new loop."""
        self._history = []
        self._stall_count = 0


__all__ = ["TerminationEvaluator", "TerminationResult"]
