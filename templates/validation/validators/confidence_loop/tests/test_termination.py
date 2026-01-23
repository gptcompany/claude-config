#!/usr/bin/env python3
"""Tests for TerminationEvaluator."""

import pytest

from validators.confidence_loop.termination import (
    TerminationEvaluator,
    TerminationResult,
)


class TestTerminationResult:
    """Tests for TerminationResult dataclass."""

    def test_dataclass_fields(self):
        """Test TerminationResult has expected fields."""
        result = TerminationResult(
            should_stop=True,
            reason="threshold_met",
            confidence=0.95,
            iterations=5,
            history=[0.5, 0.7, 0.85, 0.92, 0.95],
        )
        assert result.should_stop is True
        assert result.reason == "threshold_met"
        assert result.confidence == 0.95
        assert result.iterations == 5
        assert len(result.history) == 5

    def test_default_history(self):
        """Test TerminationResult default empty history."""
        result = TerminationResult(
            should_stop=False,
            reason="continue",
            confidence=0.5,
            iterations=1,
        )
        assert result.history == []


class TestTerminationEvaluator:
    """Tests for TerminationEvaluator."""

    def test_default_config(self):
        """Test default configuration values."""
        evaluator = TerminationEvaluator()
        assert evaluator.confidence_threshold == 0.95
        assert evaluator.max_iterations == 10
        assert evaluator.stall_epsilon == 0.01
        assert evaluator.stall_count_limit == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.90,
            max_iterations=5,
            stall_epsilon=0.05,
            stall_count_limit=2,
        )
        assert evaluator.confidence_threshold == 0.90
        assert evaluator.max_iterations == 5
        assert evaluator.stall_epsilon == 0.05
        assert evaluator.stall_count_limit == 2

    def test_invalid_confidence_threshold_low(self):
        """Test invalid confidence_threshold below 0."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            TerminationEvaluator(confidence_threshold=-0.1)

    def test_invalid_confidence_threshold_high(self):
        """Test invalid confidence_threshold above 1."""
        with pytest.raises(ValueError, match="confidence_threshold must be between"):
            TerminationEvaluator(confidence_threshold=1.5)

    def test_invalid_max_iterations(self):
        """Test invalid max_iterations."""
        with pytest.raises(ValueError, match="max_iterations must be at least 1"):
            TerminationEvaluator(max_iterations=0)

    def test_invalid_stall_epsilon(self):
        """Test invalid negative stall_epsilon."""
        with pytest.raises(ValueError, match="stall_epsilon must be non-negative"):
            TerminationEvaluator(stall_epsilon=-0.01)

    def test_invalid_stall_count_limit(self):
        """Test invalid stall_count_limit."""
        with pytest.raises(ValueError, match="stall_count_limit must be at least 1"):
            TerminationEvaluator(stall_count_limit=0)


class TestThresholdMet:
    """Tests for threshold_met termination condition."""

    def test_threshold_met_exactly(self):
        """Test termination when confidence equals threshold."""
        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        result = evaluator.evaluate(0.95)
        assert result.should_stop is True
        assert result.reason == "threshold_met"
        assert result.confidence == 0.95

    def test_threshold_exceeded(self):
        """Test termination when confidence exceeds threshold."""
        evaluator = TerminationEvaluator(confidence_threshold=0.90)
        result = evaluator.evaluate(0.95)
        assert result.should_stop is True
        assert result.reason == "threshold_met"

    def test_threshold_met_first_iteration(self):
        """Test termination on first iteration if threshold met."""
        evaluator = TerminationEvaluator(confidence_threshold=0.50)
        result = evaluator.evaluate(0.80)
        assert result.should_stop is True
        assert result.reason == "threshold_met"
        assert result.iterations == 1

    def test_threshold_not_met(self):
        """Test continuation when below threshold."""
        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        result = evaluator.evaluate(0.50)
        assert result.should_stop is False
        assert result.reason == "continue"


class TestProgressStalled:
    """Tests for progress_stalled termination condition."""

    def test_progress_stalled_same_confidence(self):
        """Test termination when confidence stays same for stall_count_limit iterations."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            stall_count_limit=3,
            stall_epsilon=0.01,
        )
        # First evaluation - no stall yet
        result1 = evaluator.evaluate(0.50)
        assert result1.should_stop is False

        # Same confidence - stall count 1
        result2 = evaluator.evaluate(0.50)
        assert result2.should_stop is False

        # Same confidence - stall count 2
        result3 = evaluator.evaluate(0.50)
        assert result3.should_stop is False

        # Same confidence - stall count 3 -> terminate
        result4 = evaluator.evaluate(0.50)
        assert result4.should_stop is True
        assert result4.reason == "progress_stalled"

    def test_progress_stalled_tiny_improvement(self):
        """Test stall detection with improvements below epsilon."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            stall_count_limit=3,
            stall_epsilon=0.02,  # Need >2% improvement
        )
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.51)  # 1% improvement < epsilon -> stall
        evaluator.evaluate(0.515)  # 0.5% improvement < epsilon -> stall
        result = evaluator.evaluate(0.52)  # 0.5% improvement < epsilon -> stall count=3
        assert result.should_stop is True
        assert result.reason == "progress_stalled"

    def test_stall_count_resets_on_progress(self):
        """Test stall count resets when progress resumes."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            stall_count_limit=3,
            stall_epsilon=0.01,
        )
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.50)  # stall 1
        evaluator.evaluate(0.50)  # stall 2

        # Make progress - should reset stall count
        evaluator.evaluate(0.60)
        assert evaluator.stall_count == 0

        # Stall again - should not trigger yet
        result = evaluator.evaluate(0.60)
        assert result.should_stop is False
        assert evaluator.stall_count == 1


class TestMaxIterations:
    """Tests for max_iterations termination condition."""

    def test_max_iterations_reached(self):
        """Test termination when max iterations reached."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,  # Very high, won't be met
            max_iterations=5,
            stall_epsilon=0.0,  # Disable stall detection
        )
        for i in range(4):
            result = evaluator.evaluate(0.10 + i * 0.10)
            assert result.should_stop is False

        # 5th iteration should terminate
        result = evaluator.evaluate(0.50)
        assert result.should_stop is True
        assert result.reason == "max_iterations"
        assert result.iterations == 5

    def test_max_iterations_priority(self):
        """Test max_iterations is lower priority than threshold."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.50,
            max_iterations=3,
        )
        evaluator.evaluate(0.20)
        evaluator.evaluate(0.30)

        # 3rd iteration meets both max_iterations and threshold
        result = evaluator.evaluate(0.60)
        assert result.should_stop is True
        assert result.reason == "threshold_met"  # Threshold checked first


class TestNormalProgress:
    """Tests for normal loop continuation."""

    def test_normal_increasing_confidence(self):
        """Test loop continues with increasing confidence below threshold."""
        evaluator = TerminationEvaluator(confidence_threshold=0.95)

        confidences = [0.50, 0.60, 0.70, 0.80, 0.85, 0.90]
        for conf in confidences:
            result = evaluator.evaluate(conf)
            assert result.should_stop is False
            assert result.reason == "continue"

    def test_iterations_tracked(self):
        """Test iteration count is tracked correctly."""
        evaluator = TerminationEvaluator()

        for i in range(5):
            result = evaluator.evaluate(0.50 + i * 0.05)
            assert result.iterations == i + 1
            assert evaluator.iterations == i + 1


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_history(self):
        """Test reset clears history."""
        evaluator = TerminationEvaluator()
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.60)
        assert evaluator.iterations == 2

        evaluator.reset()
        assert evaluator.iterations == 0
        assert evaluator.history == []

    def test_reset_clears_stall_count(self):
        """Test reset clears stall count."""
        evaluator = TerminationEvaluator()
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.50)
        assert evaluator.stall_count == 1

        evaluator.reset()
        assert evaluator.stall_count == 0

    def test_reset_allows_reuse(self):
        """Test evaluator can be reused after reset."""
        evaluator = TerminationEvaluator(max_iterations=3)

        # First loop
        for _ in range(3):
            evaluator.evaluate(0.50)
        assert evaluator.iterations == 3

        # Reset and second loop
        evaluator.reset()
        result = evaluator.evaluate(0.99)
        assert result.iterations == 1
        assert result.should_stop is True
        assert result.reason == "threshold_met"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_confidence(self):
        """Test handling of 0.0 confidence."""
        evaluator = TerminationEvaluator()
        result = evaluator.evaluate(0.0)
        assert result.confidence == 0.0
        assert result.should_stop is False

    def test_full_confidence(self):
        """Test handling of 1.0 confidence."""
        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        result = evaluator.evaluate(1.0)
        assert result.confidence == 1.0
        assert result.should_stop is True
        assert result.reason == "threshold_met"

    def test_negative_confidence_clamped(self):
        """Test negative confidence is clamped to 0."""
        evaluator = TerminationEvaluator()
        result = evaluator.evaluate(-0.5)
        assert result.confidence == 0.0

    def test_over_one_confidence_clamped(self):
        """Test confidence over 1.0 is clamped to 1.0."""
        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        result = evaluator.evaluate(1.5)
        assert result.confidence == 1.0
        assert result.should_stop is True

    def test_history_copy(self):
        """Test history property returns copy."""
        evaluator = TerminationEvaluator()
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.60)

        history = evaluator.history
        history.append(0.99)  # Modify returned copy

        assert len(evaluator.history) == 2  # Original unchanged

    def test_result_history_copy(self):
        """Test result history is a copy."""
        evaluator = TerminationEvaluator()
        result = evaluator.evaluate(0.50)
        result.history.append(0.99)

        assert len(evaluator.history) == 1  # Original unchanged

    def test_single_iteration_max(self):
        """Test max_iterations=1 terminates immediately."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=1,
        )
        result = evaluator.evaluate(0.50)
        assert result.should_stop is True
        assert result.reason == "max_iterations"

    def test_zero_epsilon_strict_stall(self):
        """Test stall_epsilon=0 requires exact same value."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            stall_epsilon=0.0,
            stall_count_limit=2,
        )
        evaluator.evaluate(0.50)
        # Tiny improvement > 0, not stalled
        result = evaluator.evaluate(0.500001)
        assert evaluator.stall_count == 0

    def test_boundary_epsilon(self):
        """Test exactly at epsilon boundary."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            stall_epsilon=0.01,
            stall_count_limit=2,
        )
        evaluator.evaluate(0.50)
        # Exactly epsilon improvement - counts as stall (< epsilon, not <=)
        evaluator.evaluate(0.50 + 0.01)
        # Wait, let's check: delta = 0.01, stall_epsilon = 0.01
        # delta < epsilon? 0.01 < 0.01 is False
        # So this should NOT be a stall
        assert evaluator.stall_count == 0


class TestHistoryAndState:
    """Tests for history tracking and state management."""

    def test_history_grows(self):
        """Test history accumulates values."""
        evaluator = TerminationEvaluator()
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.60)
        evaluator.evaluate(0.70)

        assert evaluator.history == [0.50, 0.60, 0.70]

    def test_result_contains_full_history(self):
        """Test result contains complete history."""
        evaluator = TerminationEvaluator()
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.60)
        result = evaluator.evaluate(0.70)

        assert result.history == [0.50, 0.60, 0.70]

    def test_stall_count_access(self):
        """Test stall_count property."""
        evaluator = TerminationEvaluator(stall_epsilon=0.1)
        evaluator.evaluate(0.50)
        evaluator.evaluate(0.51)  # +0.01 < 0.1 epsilon -> stall

        assert evaluator.stall_count == 1
