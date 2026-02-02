#!/usr/bin/env python3
"""Tests for ConfidenceLoopOrchestrator - orchestrator integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from validators.confidence_loop.grafana_reporter import GrafanaReporter
from validators.confidence_loop.loop_controller import ProgressiveRefinementLoop
from validators.confidence_loop.orchestrator_integration import (
    ConfidenceLoopOrchestrator,
)
from validators.confidence_loop.terminal_reporter import TerminalReporter
from validators.confidence_loop.termination import TerminationEvaluator


class TestConfidenceLoopOrchestratorInit:
    """Test ConfidenceLoopOrchestrator initialization."""

    def test_init_default(self):
        """Test default initialization."""
        orchestrator = ConfidenceLoopOrchestrator()
        assert orchestrator.loop is not None
        assert orchestrator.terminal is not None
        assert orchestrator.grafana is None
        assert orchestrator.orchestrator is None

    def test_init_with_base_orchestrator(self):
        """Test initialization with base orchestrator."""
        mock_orchestrator = MagicMock()
        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=mock_orchestrator,
        )
        assert orchestrator.orchestrator is mock_orchestrator

    def test_init_with_custom_loop(self):
        """Test initialization with custom loop."""
        custom_loop = ProgressiveRefinementLoop()
        orchestrator = ConfidenceLoopOrchestrator(loop=custom_loop)
        assert orchestrator.loop is custom_loop

    def test_init_with_reporters(self):
        """Test initialization with custom reporters."""
        terminal = TerminalReporter(use_rich=False)
        grafana = GrafanaReporter(grafana_url="http://localhost:3000")

        orchestrator = ConfidenceLoopOrchestrator(
            terminal_reporter=terminal,
            grafana_reporter=grafana,
        )
        assert orchestrator.terminal is terminal
        assert orchestrator.grafana is grafana

    def test_init_with_multimodal_validator(self):
        """Test initialization with multimodal validator."""
        mock_validator = MagicMock()
        orchestrator = ConfidenceLoopOrchestrator(
            multimodal_validator=mock_validator,
        )
        assert orchestrator.multimodal_validator is mock_validator


class TestRunWithConfidence:
    """Test run_with_confidence method."""

    @pytest.mark.asyncio
    async def test_run_with_confidence_meets_threshold(self):
        """Test loop terminates when confidence threshold met."""
        # Create mock validator that returns increasing confidence
        mock_validator = MagicMock()
        call_count = [0]
        confidences = [0.5, 0.7, 0.9, 0.96]

        async def mock_validate(**kwargs):
            result = MagicMock()
            idx = min(call_count[0], len(confidences) - 1)
            result.confidence = confidences[idx]
            call_count[0] += 1
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        state, result = await orchestrator.run_with_confidence(
            confidence_threshold=0.95,
            report_progress=False,
        )

        assert result.should_stop is True
        assert result.reason == "threshold_met"
        assert state.confidence >= 0.95

    @pytest.mark.asyncio
    async def test_run_with_confidence_stalls(self):
        """Test loop terminates when progress stalls."""
        # Create mock validator that returns same confidence
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.5  # Never improves
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
                stall_epsilon=0.01,
                stall_count_limit=3,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        state, result = await orchestrator.run_with_confidence(
            confidence_threshold=0.95,
            report_progress=False,
        )

        assert result.should_stop is True
        assert result.reason == "progress_stalled"

    @pytest.mark.asyncio
    async def test_run_with_confidence_max_iterations(self):
        """Test loop terminates at max iterations."""
        # Create mock validator with slow progress
        mock_validator = MagicMock()
        call_count = [0]

        async def mock_validate(**kwargs):
            result = MagicMock()
            # Slow progress, won't reach 0.95 in 3 iterations
            result.confidence = 0.3 + (call_count[0] * 0.1)
            call_count[0] += 1
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=3,
                stall_epsilon=0.0,  # Disable stall detection
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        state, result = await orchestrator.run_with_confidence(
            confidence_threshold=0.95,
            max_iterations=3,
            report_progress=False,
        )

        assert result.should_stop is True
        assert result.reason == "max_iterations"

    @pytest.mark.asyncio
    async def test_run_with_confidence_reports_called(self):
        """Test that both reporters receive updates."""
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.96
            return result

        mock_validator.validate = mock_validate

        terminal = MagicMock(spec=TerminalReporter)
        grafana = MagicMock(spec=GrafanaReporter)

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=terminal,
            grafana_reporter=grafana,
        )

        await orchestrator.run_with_confidence(
            confidence_threshold=0.95,
            report_progress=True,
        )

        # Terminal should be called
        terminal.report_iteration.assert_called()
        terminal.report_final.assert_called()

        # Grafana should be called
        grafana.push_iteration_metrics.assert_called()
        grafana.create_annotation.assert_called()


class TestGetCurrentConfidence:
    """Test get_current_confidence method."""

    def test_get_current_confidence_no_state(self):
        """Test returns 0 when no state available."""
        orchestrator = ConfidenceLoopOrchestrator()
        assert orchestrator.get_current_confidence() == 0.0

    @pytest.mark.asyncio
    async def test_get_current_confidence_with_state(self):
        """Test returns fused score from state."""
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.85
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=1,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        await orchestrator.run_with_confidence(report_progress=False)

        confidence = orchestrator.get_current_confidence()
        assert confidence > 0


class TestGetDimensionBreakdown:
    """Test get_dimension_breakdown method."""

    def test_get_dimension_breakdown_no_state(self):
        """Test returns empty dict when no state available."""
        orchestrator = ConfidenceLoopOrchestrator()
        assert orchestrator.get_dimension_breakdown() == {}

    @pytest.mark.asyncio
    async def test_get_dimension_breakdown_includes_all_dimensions(self):
        """Test includes all dimensions from state."""
        mock_validator = MagicMock()
        call_count = [0]
        confidences = [0.5, 0.85, 0.96]

        async def mock_validate(**kwargs):
            result = MagicMock()
            idx = min(call_count[0], len(confidences) - 1)
            result.confidence = confidences[idx]
            call_count[0] += 1
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        await orchestrator.run_with_confidence(report_progress=False)

        breakdown = orchestrator.get_dimension_breakdown()
        # Should have at least one dimension
        assert len(breakdown) > 0
        # All values should be strings (stage values)
        assert all(isinstance(k, str) for k in breakdown.keys())


class TestIntegrationWithMockOrchestrator:
    """Test full integration with mock orchestrator."""

    @pytest.mark.asyncio
    async def test_full_integration_flow(self):
        """Test complete integration flow."""
        # Create mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.run_all = AsyncMock(return_value=MagicMock(blocked=False))

        # Create mock validator
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.96
            return result

        mock_validator.validate = mock_validate

        # Create loop
        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        # Create orchestrator
        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=mock_orchestrator,
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        # Run
        state, result = await orchestrator.run_with_confidence(
            validation_input={"file": "test.py"},
            confidence_threshold=0.95,
            report_progress=False,
        )

        # Verify results
        assert result.should_stop is True
        assert state.confidence >= 0.95

        # Verify state accessible
        assert orchestrator.current_state is not None
        assert orchestrator.last_result is not None


class TestRunSingleValidation:
    """Test run_single_validation method."""

    @pytest.mark.asyncio
    async def test_run_single_validation_no_orchestrator(self):
        """Test returns default when no orchestrator."""
        orchestrator = ConfidenceLoopOrchestrator()
        passed, confidence = await orchestrator.run_single_validation()
        assert passed is True
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_run_single_validation_with_file(self):
        """Test file-specific validation."""
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.has_blockers = False
        mock_orchestrator.validate_file = AsyncMock(return_value=mock_result)

        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=mock_orchestrator,
        )

        passed, confidence = await orchestrator.run_single_validation(
            file_path="test.py"
        )

        assert passed is True
        assert confidence == 1.0
        mock_orchestrator.validate_file.assert_called_once_with("test.py")

    @pytest.mark.asyncio
    async def test_run_single_validation_with_blockers(self):
        """Test validation with blockers."""
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.has_blockers = True
        mock_orchestrator.validate_file = AsyncMock(return_value=mock_result)

        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=mock_orchestrator,
        )

        passed, confidence = await orchestrator.run_single_validation(
            file_path="test.py"
        )

        assert passed is False
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_run_single_validation_full_run(self):
        """Test full validation run without file."""
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.blocked = False
        mock_orchestrator.run_all = AsyncMock(return_value=mock_result)

        orchestrator = ConfidenceLoopOrchestrator(
            base_orchestrator=mock_orchestrator,
        )

        passed, confidence = await orchestrator.run_single_validation()

        assert passed is True
        assert confidence == 1.0
        mock_orchestrator.run_all.assert_called_once()


class TestStageTransitionReporting:
    """Test stage transition reporting."""

    @pytest.mark.asyncio
    async def test_reports_stage_transition(self):
        """Test that stage transitions are reported."""
        mock_validator = MagicMock()
        call_count = [0]
        # Confidence progresses through stages
        confidences = [0.5, 0.85, 0.92, 0.96]

        async def mock_validate(**kwargs):
            result = MagicMock()
            idx = min(call_count[0], len(confidences) - 1)
            result.confidence = confidences[idx]
            call_count[0] += 1
            return result

        mock_validator.validate = mock_validate

        terminal = MagicMock(spec=TerminalReporter)
        grafana = MagicMock(spec=GrafanaReporter)

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=terminal,
            grafana_reporter=grafana,
        )

        await orchestrator.run_with_confidence(report_progress=True)

        # Stage transition should have been reported
        terminal.report_stage_transition.assert_called()
        # Grafana annotation for stage change
        grafana.create_annotation.assert_called()


class TestTerminationConfiguration:
    """Test termination evaluator configuration."""

    @pytest.mark.asyncio
    async def test_reuses_evaluator_when_threshold_matches(self):
        """Test that evaluator is reused when threshold matches."""
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.96
            return result

        mock_validator.validate = mock_validate

        # Create evaluator with specific threshold
        evaluator = TerminationEvaluator(
            confidence_threshold=0.95,
            max_iterations=10,
        )

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=evaluator,
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        # Run with same threshold - should reuse evaluator
        await orchestrator.run_with_confidence(
            confidence_threshold=0.95,  # Same as evaluator
            report_progress=False,
        )

        # Evaluator should still be the same instance
        assert orchestrator.loop.termination is evaluator


class TestProperties:
    """Test property accessors."""

    def test_current_state_property(self):
        """Test current_state property."""
        orchestrator = ConfidenceLoopOrchestrator()
        assert orchestrator.current_state is None

    def test_last_result_property(self):
        """Test last_result property."""
        orchestrator = ConfidenceLoopOrchestrator()
        assert orchestrator.last_result is None

    @pytest.mark.asyncio
    async def test_properties_after_run(self):
        """Test properties are set after run."""
        mock_validator = MagicMock()

        async def mock_validate(**kwargs):
            result = MagicMock()
            result.confidence = 0.96
            return result

        mock_validator.validate = mock_validate

        loop = ProgressiveRefinementLoop(
            multimodal_validator=mock_validator,
            termination_evaluator=TerminationEvaluator(
                confidence_threshold=0.95,
                max_iterations=10,
            ),
        )

        orchestrator = ConfidenceLoopOrchestrator(
            loop=loop,
            terminal_reporter=TerminalReporter(use_rich=False),
        )

        await orchestrator.run_with_confidence(report_progress=False)

        assert orchestrator.current_state is not None
        assert orchestrator.last_result is not None
        assert orchestrator.last_result.should_stop is True
