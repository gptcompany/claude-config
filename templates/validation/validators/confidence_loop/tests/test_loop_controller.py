#!/usr/bin/env python3
"""Tests for ProgressiveRefinementLoop."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from validators.confidence_loop.loop_controller import (
    LoopState,
    ProgressiveRefinementLoop,
    RefinementStage,
)
from validators.confidence_loop.termination import TerminationEvaluator


class TestRefinementStage:
    """Tests for RefinementStage enum."""

    def test_stage_values(self):
        """Test stage enum values."""
        assert RefinementStage.LAYOUT.value == "layout"
        assert RefinementStage.STYLE.value == "style"
        assert RefinementStage.POLISH.value == "polish"

    def test_all_stages(self):
        """Test all stages are present."""
        stages = list(RefinementStage)
        assert len(stages) == 3
        assert RefinementStage.LAYOUT in stages
        assert RefinementStage.STYLE in stages
        assert RefinementStage.POLISH in stages


class TestLoopState:
    """Tests for LoopState dataclass."""

    def test_default_state(self):
        """Test default state initialization."""
        state = LoopState()
        assert state.iteration == 0
        assert state.stage == RefinementStage.LAYOUT
        assert state.confidence == 0.0
        assert state.stage_confidence == {}
        assert state.history == []
        assert state.started_at is None
        assert state.last_update is None

    def test_custom_state(self):
        """Test custom state initialization."""
        now = datetime.now()
        state = LoopState(
            iteration=5,
            stage=RefinementStage.STYLE,
            confidence=0.85,
            stage_confidence={RefinementStage.LAYOUT: 0.80},
            history=[{"iteration": 1, "confidence": 0.50}],
            started_at=now,
            last_update=now,
        )
        assert state.iteration == 5
        assert state.stage == RefinementStage.STYLE
        assert state.confidence == 0.85
        assert RefinementStage.LAYOUT in state.stage_confidence
        assert len(state.history) == 1


class TestProgressiveRefinementLoopInit:
    """Tests for ProgressiveRefinementLoop initialization."""

    def test_default_init(self):
        """Test default initialization."""
        loop = ProgressiveRefinementLoop()
        assert loop.validator is None
        assert loop.termination is not None
        assert loop.stage_thresholds == {
            RefinementStage.LAYOUT: 0.80,
            RefinementStage.STYLE: 0.90,
            RefinementStage.POLISH: 0.95,
        }

    def test_custom_termination_evaluator(self):
        """Test with custom termination evaluator."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=5,
        )
        loop = ProgressiveRefinementLoop(termination_evaluator=evaluator)
        assert loop.termination is evaluator

    def test_custom_stage_thresholds(self):
        """Test with custom stage thresholds."""
        custom_thresholds = {
            RefinementStage.LAYOUT: 0.70,
            RefinementStage.STYLE: 0.85,
            RefinementStage.POLISH: 0.99,
        }
        loop = ProgressiveRefinementLoop(stage_thresholds=custom_thresholds)
        assert loop.stage_thresholds[RefinementStage.LAYOUT] == 0.70
        assert loop.stage_thresholds[RefinementStage.STYLE] == 0.85
        assert loop.stage_thresholds[RefinementStage.POLISH] == 0.99

    def test_partial_custom_thresholds(self):
        """Test partial custom thresholds merge with defaults."""
        custom_thresholds = {RefinementStage.POLISH: 0.99}
        loop = ProgressiveRefinementLoop(stage_thresholds=custom_thresholds)
        assert loop.stage_thresholds[RefinementStage.LAYOUT] == 0.80  # default
        assert loop.stage_thresholds[RefinementStage.STYLE] == 0.90  # default
        assert loop.stage_thresholds[RefinementStage.POLISH] == 0.99  # custom


class TestGetCurrentStage:
    """Tests for get_current_stage method."""

    def test_layout_stage_low_confidence(self):
        """Test LAYOUT stage for low confidence."""
        loop = ProgressiveRefinementLoop()
        assert loop.get_current_stage(0.0) == RefinementStage.LAYOUT
        assert loop.get_current_stage(0.50) == RefinementStage.LAYOUT
        assert loop.get_current_stage(0.79) == RefinementStage.LAYOUT

    def test_style_stage_mid_confidence(self):
        """Test STYLE stage for mid confidence."""
        loop = ProgressiveRefinementLoop()
        assert loop.get_current_stage(0.80) == RefinementStage.STYLE
        assert loop.get_current_stage(0.85) == RefinementStage.STYLE
        assert loop.get_current_stage(0.89) == RefinementStage.STYLE

    def test_polish_stage_high_confidence(self):
        """Test POLISH stage for high confidence."""
        loop = ProgressiveRefinementLoop()
        assert loop.get_current_stage(0.90) == RefinementStage.POLISH
        assert loop.get_current_stage(0.95) == RefinementStage.POLISH
        assert loop.get_current_stage(1.0) == RefinementStage.POLISH

    def test_custom_thresholds_affect_staging(self):
        """Test custom thresholds change stage boundaries."""
        loop = ProgressiveRefinementLoop(
            stage_thresholds={
                RefinementStage.LAYOUT: 0.50,
                RefinementStage.STYLE: 0.70,
                RefinementStage.POLISH: 0.90,
            }
        )
        assert loop.get_current_stage(0.49) == RefinementStage.LAYOUT
        assert loop.get_current_stage(0.50) == RefinementStage.STYLE
        assert loop.get_current_stage(0.70) == RefinementStage.POLISH


class TestGetFeedback:
    """Tests for get_feedback method."""

    def test_basic_feedback(self):
        """Test basic feedback generation."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(
            iteration=3,
            stage=RefinementStage.LAYOUT,
            confidence=0.65,
        )
        feedback = loop.get_feedback(state)

        assert "Iteration 3" in feedback
        assert "Layout" in feedback
        assert "65.0%" in feedback
        assert "80.0%" in feedback  # target threshold

    def test_feedback_with_stage_confidence(self):
        """Test feedback includes stage progress."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(
            iteration=5,
            stage=RefinementStage.STYLE,
            confidence=0.85,
            stage_confidence={
                RefinementStage.LAYOUT: 0.80,
                RefinementStage.STYLE: 0.85,
            },
        )
        feedback = loop.get_feedback(state)

        assert "Stages:" in feedback
        assert "layout=" in feedback
        assert "style=" in feedback

    def test_feedback_polish_stage(self):
        """Test feedback for POLISH stage."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(
            iteration=8,
            stage=RefinementStage.POLISH,
            confidence=0.92,
        )
        feedback = loop.get_feedback(state)

        assert "Polish" in feedback
        assert "95.0%" in feedback  # target for polish


class TestRunIteration:
    """Tests for run_iteration method."""

    @pytest.mark.asyncio
    async def test_iteration_increments(self):
        """Test iteration counter increments."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(iteration=0, confidence=0.50)

        new_state, _ = await loop.run_iteration(state)
        assert new_state.iteration == 1

    @pytest.mark.asyncio
    async def test_state_immutable(self):
        """Test original state is not modified."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(iteration=0, confidence=0.50)

        new_state, _ = await loop.run_iteration(state)
        assert state.iteration == 0  # original unchanged
        assert new_state.iteration == 1

    @pytest.mark.asyncio
    async def test_history_recorded(self):
        """Test history is recorded."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(confidence=0.50)

        new_state, _ = await loop.run_iteration(state)
        assert len(new_state.history) == 1
        assert new_state.history[0]["iteration"] == 1
        assert new_state.history[0]["confidence"] == 0.50
        assert "timestamp" in new_state.history[0]

    @pytest.mark.asyncio
    async def test_stage_confidence_updated(self):
        """Test stage confidence is tracked."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(confidence=0.85)

        new_state, _ = await loop.run_iteration(state)
        assert RefinementStage.STYLE in new_state.stage_confidence
        assert new_state.stage_confidence[RefinementStage.STYLE] == 0.85

    @pytest.mark.asyncio
    async def test_timestamps_set(self):
        """Test timestamps are set."""
        loop = ProgressiveRefinementLoop()
        state = LoopState()

        new_state, _ = await loop.run_iteration(state)
        assert new_state.started_at is not None
        assert new_state.last_update is not None

    @pytest.mark.asyncio
    async def test_with_validator(self):
        """Test iteration with validator."""
        # Create mock validator
        mock_result = MagicMock()
        mock_result.confidence = 0.75

        mock_validator = AsyncMock()
        mock_validator.validate.return_value = mock_result

        loop = ProgressiveRefinementLoop(multimodal_validator=mock_validator)
        state = LoopState(confidence=0.50)

        new_state, _ = await loop.run_iteration(state)
        assert new_state.confidence == 0.75
        mock_validator.validate.assert_called_once()


class TestRunToCompletion:
    """Tests for run method (complete loop)."""

    @pytest.mark.asyncio
    async def test_terminates_on_threshold(self):
        """Test loop terminates when threshold met."""
        # Mock validator that returns increasing confidence
        confidences = [0.50, 0.70, 0.85, 0.95, 0.98]
        confidence_iter = iter(confidences)

        mock_result = MagicMock()

        def get_confidence():
            try:
                return next(confidence_iter)
            except StopIteration:
                return 0.98

        mock_result.confidence = property(lambda self: get_confidence())

        mock_validator = AsyncMock()
        mock_validator.validate.side_effect = lambda: MagicMock(
            confidence=confidences[
                min(mock_validator.validate.call_count, len(confidences) - 1)
            ]
        )

        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, result = await loop.run()
        assert result.should_stop is True
        assert result.reason == "threshold_met"

    @pytest.mark.asyncio
    async def test_terminates_on_max_iterations(self):
        """Test loop terminates on max iterations."""
        # Mock validator that returns constant confidence
        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(confidence=0.50)

        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=3,
            stall_epsilon=0.0,  # Disable stall detection
        )
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, result = await loop.run()
        assert result.should_stop is True
        assert result.reason == "max_iterations"
        assert state.iteration == 3

    @pytest.mark.asyncio
    async def test_terminates_on_stall(self):
        """Test loop terminates when progress stalls."""
        # Mock validator that returns same confidence
        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(confidence=0.50)

        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=10,
            stall_epsilon=0.01,
            stall_count_limit=3,
        )
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, result = await loop.run()
        assert result.should_stop is True
        assert result.reason == "progress_stalled"

    @pytest.mark.asyncio
    async def test_initial_state_preserved(self):
        """Test custom initial state is used."""
        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(confidence=0.99)

        evaluator = TerminationEvaluator(confidence_threshold=0.95)
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        initial = LoopState(iteration=5, confidence=0.90)
        state, result = await loop.run(initial_state=initial)

        # Should start from iteration 5, end at 6
        assert state.iteration == 6
        assert result.reason == "threshold_met"


class TestStageProgression:
    """Tests for stage progression."""

    @pytest.mark.asyncio
    async def test_layout_to_style_to_polish(self):
        """Test progression through all stages."""
        # Confidences that progress through stages
        confidences = [0.50, 0.65, 0.80, 0.88, 0.92, 0.96]
        call_count = [0]

        mock_validator = AsyncMock()

        def make_result():
            idx = min(call_count[0], len(confidences) - 1)
            call_count[0] += 1
            return MagicMock(confidence=confidences[idx])

        mock_validator.validate.side_effect = make_result

        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            max_iterations=10,
        )
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, result = await loop.run()

        # Should have progressed through all stages
        assert RefinementStage.LAYOUT in state.stage_confidence
        assert RefinementStage.STYLE in state.stage_confidence
        assert RefinementStage.POLISH in state.stage_confidence
        assert result.reason == "threshold_met"


class TestCreateInitialState:
    """Tests for create_initial_state method."""

    def test_creates_fresh_state(self):
        """Test creates fresh initial state."""
        loop = ProgressiveRefinementLoop()
        state = loop.create_initial_state()

        assert state.iteration == 0
        assert state.stage == RefinementStage.LAYOUT
        assert state.confidence == 0.0
        assert state.stage_confidence == {}
        assert state.history == []
        assert state.started_at is not None  # Should be set


class TestValidatorIntegration:
    """Tests for validator integration."""

    @pytest.mark.asyncio
    async def test_validator_with_details(self):
        """Test validator with fused_confidence in details."""
        mock_result = MagicMock()
        mock_result.confidence = None
        mock_result.details = {"fused_confidence": 0.88}

        mock_validator = AsyncMock()
        mock_validator.validate.return_value = mock_result

        loop = ProgressiveRefinementLoop(multimodal_validator=mock_validator)
        state = LoopState()

        new_state, _ = await loop.run_iteration(state)
        assert new_state.confidence == 0.88

    @pytest.mark.asyncio
    async def test_validator_with_passed_fallback(self):
        """Test fallback to passed=True/False."""
        mock_result = MagicMock(spec=["passed"])
        mock_result.passed = True

        mock_validator = AsyncMock()
        mock_validator.validate.return_value = mock_result

        loop = ProgressiveRefinementLoop(multimodal_validator=mock_validator)
        state = LoopState()

        new_state, _ = await loop.run_iteration(state)
        assert new_state.confidence == 1.0

    @pytest.mark.asyncio
    async def test_validator_error_graceful(self):
        """Test graceful handling of validator errors."""
        mock_validator = AsyncMock()
        mock_validator.validate.side_effect = Exception("Validator failed")

        loop = ProgressiveRefinementLoop(multimodal_validator=mock_validator)
        state = LoopState(confidence=0.75)

        new_state, _ = await loop.run_iteration(state)
        # Should keep previous confidence on error
        assert new_state.confidence == 0.75


class TestNoValidator:
    """Tests without a validator."""

    @pytest.mark.asyncio
    async def test_no_validator_uses_state_confidence(self):
        """Test without validator uses state confidence."""
        loop = ProgressiveRefinementLoop()
        state = LoopState(confidence=0.60)

        new_state, _ = await loop.run_iteration(state)
        assert new_state.confidence == 0.60

    @pytest.mark.asyncio
    async def test_no_validator_complete_run(self):
        """Test complete run without validator."""
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            max_iterations=3,
        )
        loop = ProgressiveRefinementLoop(termination_evaluator=evaluator)

        state, result = await loop.run()
        assert result.should_stop is True
        assert result.reason == "max_iterations"
        assert state.iteration == 3


class TestHistoryTracking:
    """Tests for history tracking."""

    @pytest.mark.asyncio
    async def test_history_accumulates(self):
        """Test history accumulates across iterations."""
        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(confidence=0.50)

        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=3,
        )
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, _ = await loop.run()
        assert len(state.history) == 3
        assert state.history[0]["iteration"] == 1
        assert state.history[1]["iteration"] == 2
        assert state.history[2]["iteration"] == 3

    @pytest.mark.asyncio
    async def test_history_includes_stage(self):
        """Test history includes stage information."""
        mock_validator = AsyncMock()
        mock_validator.validate.return_value = MagicMock(confidence=0.85)

        evaluator = TerminationEvaluator(
            confidence_threshold=0.99,
            max_iterations=1,
        )
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        state, _ = await loop.run()
        assert state.history[0]["stage"] == "style"
