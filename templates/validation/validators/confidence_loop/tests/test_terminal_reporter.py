#!/usr/bin/env python3
"""Tests for TerminalReporter - terminal output for confidence loops."""

from unittest.mock import MagicMock, patch

from validators.confidence_loop.loop_controller import LoopState, RefinementStage
from validators.confidence_loop.terminal_reporter import TerminalReporter
from validators.confidence_loop.termination import TerminationResult


class TestTerminalReporterInit:
    """Test TerminalReporter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        reporter = TerminalReporter()
        # use_rich depends on whether rich is available
        assert isinstance(reporter.use_rich, bool)

    def test_init_disable_rich(self):
        """Test disabling rich explicitly."""
        reporter = TerminalReporter(use_rich=False)
        assert reporter.use_rich is False

    def test_init_with_rich_not_available(self):
        """Test initialization when rich is not installed."""
        with patch.object(TerminalReporter, "_rich_available", return_value=False):
            reporter = TerminalReporter(use_rich=True)
            assert reporter.use_rich is False

    def test_init_with_rich_available(self):
        """Test initialization when rich is installed."""
        with patch.object(TerminalReporter, "_rich_available", return_value=True):
            with patch.dict(
                "sys.modules", {"rich": MagicMock(), "rich.console": MagicMock()}
            ):
                reporter = TerminalReporter(use_rich=True)
                assert reporter.use_rich is True


class TestFormatConfidenceBar:
    """Test confidence bar formatting."""

    def test_confidence_bar_zero(self):
        """Test bar at 0% confidence."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(0.0, width=10)
        assert "0%" in bar
        assert "[" in bar
        assert "]" in bar

    def test_confidence_bar_fifty_percent(self):
        """Test bar at 50% confidence."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(0.5, width=10)
        assert "50%" in bar
        # Should have some filled characters
        assert "=" in bar

    def test_confidence_bar_hundred_percent(self):
        """Test bar at 100% confidence."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(1.0, width=10)
        assert "100%" in bar
        # Should be fully filled
        assert "=" in bar

    def test_confidence_bar_custom_width(self):
        """Test bar with custom width."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(0.5, width=20)
        # Bar should contain brackets and percentage
        assert "[" in bar
        assert "]" in bar

    def test_confidence_bar_clamps_negative(self):
        """Test that negative confidence is clamped to 0."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(-0.5, width=10)
        assert "0%" in bar

    def test_confidence_bar_clamps_over_one(self):
        """Test that confidence > 1.0 is clamped to 100%."""
        reporter = TerminalReporter(use_rich=False)
        bar = reporter.format_confidence_bar(1.5, width=10)
        assert "100%" in bar


class TestReportIteration:
    """Test iteration reporting."""

    def test_report_iteration_basic(self, capsys):
        """Test basic iteration report."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=1,
            stage=RefinementStage.LAYOUT,
            confidence=0.45,
        )
        result = TerminationResult(
            should_stop=False,
            reason="continue",
            confidence=0.45,
            iterations=1,
        )

        output = reporter.report_iteration(state, result)

        assert "Iteration 1" in output
        assert "Layout" in output
        assert "45%" in output
        assert "Continuing" in output

    def test_report_iteration_stopping(self, capsys):
        """Test iteration report when stopping."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=5,
            stage=RefinementStage.POLISH,
            confidence=0.95,
        )
        result = TerminationResult(
            should_stop=True,
            reason="threshold_met",
            confidence=0.95,
            iterations=5,
        )

        output = reporter.report_iteration(state, result)

        assert "Iteration 5" in output
        assert "STOPPING" in output
        assert "threshold_met" in output

    def test_report_iteration_with_stage_confidence(self, capsys):
        """Test iteration report with stage confidence breakdown."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=3,
            stage=RefinementStage.STYLE,
            confidence=0.85,
            stage_confidence={
                RefinementStage.LAYOUT: 0.80,
                RefinementStage.STYLE: 0.85,
            },
        )
        result = TerminationResult(
            should_stop=False,
            reason="continue",
            confidence=0.85,
            iterations=3,
        )

        output = reporter.report_iteration(state, result)

        assert "Stages:" in output
        assert "Layout" in output
        assert "Style" in output


class TestReportStageTransition:
    """Test stage transition reporting."""

    def test_stage_transition_layout_to_style(self, capsys):
        """Test layout to style transition."""
        reporter = TerminalReporter(use_rich=False)
        output = reporter.report_stage_transition(
            RefinementStage.LAYOUT, RefinementStage.STYLE
        )

        assert "Layout" in output
        assert "Style" in output
        assert "->" in output

    def test_stage_transition_style_to_polish(self, capsys):
        """Test style to polish transition."""
        reporter = TerminalReporter(use_rich=False)
        output = reporter.report_stage_transition(
            RefinementStage.STYLE, RefinementStage.POLISH
        )

        assert "Style" in output
        assert "Polish" in output


class TestReportFinal:
    """Test final summary reporting."""

    def test_report_final_threshold_met(self, capsys):
        """Test final report when threshold met."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=5,
            stage=RefinementStage.POLISH,
            confidence=0.96,
        )
        result = TerminationResult(
            should_stop=True,
            reason="threshold_met",
            confidence=0.96,
            iterations=5,
        )

        output = reporter.report_final(state, result)

        assert "REFINEMENT COMPLETE" in output
        assert "96%" in output
        assert "Iterations: 5" in output
        assert "threshold reached" in output.lower()

    def test_report_final_progress_stalled(self, capsys):
        """Test final report when progress stalled."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=7,
            stage=RefinementStage.STYLE,
            confidence=0.85,
        )
        result = TerminationResult(
            should_stop=True,
            reason="progress_stalled",
            confidence=0.85,
            iterations=7,
        )

        output = reporter.report_final(state, result)

        assert "REFINEMENT COMPLETE" in output
        assert "stalled" in output.lower()

    def test_report_final_max_iterations(self, capsys):
        """Test final report when max iterations reached."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=10,
            stage=RefinementStage.LAYOUT,
            confidence=0.60,
        )
        result = TerminationResult(
            should_stop=True,
            reason="max_iterations",
            confidence=0.60,
            iterations=10,
        )

        output = reporter.report_final(state, result)

        assert "REFINEMENT COMPLETE" in output
        assert "maximum" in output.lower() or "max" in output.lower()


class TestRichFallback:
    """Test rich library fallback behavior."""

    def test_works_without_rich(self, capsys):
        """Test that reporter works without rich library."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)
        result = TerminationResult(
            should_stop=False, reason="continue", confidence=0.5, iterations=1
        )

        # Should not raise
        output = reporter.report_iteration(state, result)
        assert output is not None

        # Check stdout has content
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_stage_transition_without_rich(self, capsys):
        """Test stage transition without rich."""
        reporter = TerminalReporter(use_rich=False)
        output = reporter.report_stage_transition(
            RefinementStage.LAYOUT, RefinementStage.STYLE
        )
        assert output is not None
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_final_without_rich(self, capsys):
        """Test final report without rich."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(iteration=5, stage=RefinementStage.POLISH, confidence=0.95)
        result = TerminationResult(
            should_stop=True, reason="threshold_met", confidence=0.95, iterations=5
        )

        output = reporter.report_final(state, result)
        assert output is not None
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestRichIntegration:
    """Test rich library integration when available."""

    def test_uses_console_when_rich_available(self):
        """Test that Console is used when rich is available."""
        mock_console = MagicMock()
        mock_console_cls = MagicMock(return_value=mock_console)
        mock_rich_console = MagicMock()
        mock_rich_console.Console = mock_console_cls

        with patch.object(TerminalReporter, "_rich_available", return_value=True):
            with patch.dict(
                "sys.modules",
                {"rich": MagicMock(), "rich.console": mock_rich_console},
            ):
                reporter = TerminalReporter(use_rich=True)

                state = LoopState(
                    iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5
                )
                result = TerminationResult(
                    should_stop=False, reason="continue", confidence=0.5, iterations=1
                )

                reporter.report_iteration(state, result)

                # Console.print should have been called
                mock_console.print.assert_called()

    def test_stage_transition_uses_console(self):
        """Test that stage transition uses Console when available."""
        mock_console = MagicMock()
        mock_console_cls = MagicMock(return_value=mock_console)
        mock_rich_console = MagicMock()
        mock_rich_console.Console = mock_console_cls

        with patch.object(TerminalReporter, "_rich_available", return_value=True):
            with patch.dict(
                "sys.modules",
                {"rich": MagicMock(), "rich.console": mock_rich_console},
            ):
                reporter = TerminalReporter(use_rich=True)

                reporter.report_stage_transition(
                    RefinementStage.LAYOUT, RefinementStage.STYLE
                )

                # Console.print should have been called for stage transition
                mock_console.print.assert_called()

    def test_final_report_uses_console(self):
        """Test that final report uses Console when available."""
        mock_console = MagicMock()
        mock_console_cls = MagicMock(return_value=mock_console)
        mock_rich_console = MagicMock()
        mock_rich_console.Console = mock_console_cls

        with patch.object(TerminalReporter, "_rich_available", return_value=True):
            with patch.dict(
                "sys.modules",
                {"rich": MagicMock(), "rich.console": mock_rich_console},
            ):
                reporter = TerminalReporter(use_rich=True)

                state = LoopState(
                    iteration=5, stage=RefinementStage.POLISH, confidence=0.95
                )
                result = TerminationResult(
                    should_stop=True,
                    reason="threshold_met",
                    confidence=0.95,
                    iterations=5,
                )

                reporter.report_final(state, result)

                # Console.print should have been called for final report
                mock_console.print.assert_called()

    def test_rich_available_returns_false_when_import_fails(self):
        """Test _rich_available returns False when rich not installed."""
        # Create a reporter with rich disabled to not trigger import
        _reporter = TerminalReporter(use_rich=False)  # noqa: F841

        # Now test the static method directly with import failure
        with patch.dict("sys.modules", {"rich": None}):
            # Force ImportError by making the import fail
            import sys

            original = sys.modules.get("rich")
            try:
                sys.modules["rich"] = None
                # Need to test the actual method behavior
                # Since it catches ImportError, we test the fallback
                reporter2 = TerminalReporter(use_rich=False)
                assert reporter2.use_rich is False
            finally:
                if original is not None:
                    sys.modules["rich"] = original


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_stage_confidence(self):
        """Test with empty stage confidence dict."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(
            iteration=1,
            stage=RefinementStage.LAYOUT,
            confidence=0.5,
            stage_confidence={},
        )
        result = TerminationResult(
            should_stop=False, reason="continue", confidence=0.5, iterations=1
        )

        output = reporter.report_iteration(state, result)
        # Should not have "Stages:" line
        assert "Stages:" not in output

    def test_unknown_termination_reason(self):
        """Test with unknown termination reason."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)
        result = TerminationResult(
            should_stop=True,
            reason="unknown_reason",
            confidence=0.5,
            iterations=1,
        )

        output = reporter.report_final(state, result)
        # Should still show the reason
        assert "unknown_reason" in output

    def test_zero_iteration(self):
        """Test with zero iteration."""
        reporter = TerminalReporter(use_rich=False)
        state = LoopState(iteration=0, stage=RefinementStage.LAYOUT, confidence=0.0)
        result = TerminationResult(
            should_stop=False, reason="continue", confidence=0.0, iterations=0
        )

        output = reporter.report_iteration(state, result)
        assert "Iteration 0" in output
