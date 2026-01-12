#!/usr/bin/env python3
"""
E2E Tests for Spec Pipeline Orchestrator

Run with:
    pytest test_spec_pipeline.py -v
    pytest test_spec_pipeline.py -v -m "not slow"  # Skip slow tests
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from spec_pipeline import (
    CIRCUITS,
    CheckpointManager,
    CircuitBreaker,
    FatalError,
    PipelineRun,
    PipelineState,
    SpecPipelineOrchestrator,
    StepResult,
    retry,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Temporary directory for checkpoint files."""
    checkpoint_dir = tmp_path / ".claude" / "metrics"
    checkpoint_dir.mkdir(parents=True)
    return checkpoint_dir


@pytest.fixture
def mock_checkpoint(temp_checkpoint_dir, monkeypatch):
    """Mock checkpoint manager to use file-based storage."""
    monkeypatch.setattr(
        "spec_pipeline.CheckpointManager._file_path",
        temp_checkpoint_dir / "pipeline_runs.json",
    )
    return CheckpointManager()


@pytest.fixture
def orchestrator():
    """Create orchestrator instance."""
    return SpecPipelineOrchestrator(project="test-project", dry_run=False)


@pytest.fixture
def reset_circuits():
    """Reset all circuit breakers before each test."""
    for cb in CIRCUITS.values():
        cb._state.state = "closed"
        cb._state.failure_count = 0
        cb._state.opened_at = None
    yield
    # Reset again after
    for cb in CIRCUITS.values():
        cb._state.state = "closed"
        cb._state.failure_count = 0
        cb._state.opened_at = None


# =============================================================================
# Unit Tests: State Machine
# =============================================================================


class TestPipelineState:
    """Test state machine."""

    def test_state_values(self):
        """States have string values for DB storage."""
        assert PipelineState.NOT_STARTED.value == "not_started"
        assert PipelineState.COMPLETED.value == "completed"
        assert PipelineState.FAILED.value == "failed"

    def test_state_from_string(self):
        """Can create state from string."""
        state = PipelineState("spec_created")
        assert state == PipelineState.SPEC_CREATED

    def test_invalid_state(self):
        """Invalid state raises error."""
        with pytest.raises(ValueError):
            PipelineState("invalid_state")


# =============================================================================
# Unit Tests: Retry Decorator
# =============================================================================


class TestRetryDecorator:
    """Test retry with exponential backoff."""

    def test_success_no_retry(self):
        """Successful call doesn't retry."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_connection_error(self):
        """Retries on connection error."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Failed")
            return "success"

        result = failing_func()
        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Raises after max retries."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            always_fail()

        assert call_count == 3

    def test_fatal_error_no_retry(self):
        """Fatal errors are not retried."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def fatal_func():
            nonlocal call_count
            call_count += 1
            raise FatalError("Fatal")

        with pytest.raises(FatalError):
            fatal_func()

        assert call_count == 1


# =============================================================================
# Unit Tests: Circuit Breaker
# =============================================================================


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_starts_closed(self):
        """Circuit starts in closed state."""
        cb = CircuitBreaker("test", failure_threshold=3)
        assert not cb.is_open()

    def test_opens_after_threshold(self):
        """Circuit opens after failure threshold."""
        cb = CircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            cb.record_failure("error")

        assert cb.is_open()

    def test_success_resets_failures(self):
        """Success resets failure count."""
        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure("error")
        cb.record_failure("error")
        cb.record_success()

        assert cb._state.failure_count == 0
        assert not cb.is_open()

    def test_half_open_after_timeout(self):
        """Circuit becomes half-open after reset timeout."""
        cb = CircuitBreaker("test", failure_threshold=2, reset_timeout=1)

        cb.record_failure("error")
        cb.record_failure("error")
        # Circuit should be open now
        assert cb._state.state == "open"

        # Simulate timeout by setting opened_at in the past
        from datetime import timedelta

        cb._state.opened_at = datetime.now() - timedelta(seconds=2)

        # After timeout, should transition to half-open
        assert not cb.is_open()  # This triggers the transition
        assert cb._state.state == "half_open"

    def test_context_manager_success(self):
        """Context manager records success."""
        cb = CircuitBreaker("test", failure_threshold=3)

        with cb:
            pass

        assert cb._state.failure_count == 0

    def test_context_manager_failure(self):
        """Context manager records failure."""
        cb = CircuitBreaker("test", failure_threshold=3)

        with pytest.raises(ValueError):
            with cb:
                raise ValueError("test error")

        assert cb._state.failure_count == 1


# =============================================================================
# Unit Tests: Checkpoint Manager
# =============================================================================


class TestCheckpointManager:
    """Test checkpoint persistence."""

    def test_save_and_load_file(self, temp_checkpoint_dir):
        """Save and load from file."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        run = PipelineRun(
            run_id="test-123",
            project="test-project",
            feature_description="Test feature",
            current_state=PipelineState.SPEC_CREATED,
            metadata={"key": "value"},
        )

        manager.save(run)
        loaded = manager.load("test-123")

        assert loaded is not None
        assert loaded.run_id == "test-123"
        assert loaded.project == "test-project"
        assert loaded.current_state == PipelineState.SPEC_CREATED
        assert loaded.metadata == {"key": "value"}

    def test_load_nonexistent(self, temp_checkpoint_dir):
        """Loading nonexistent run returns None."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        loaded = manager.load("nonexistent")
        assert loaded is None

    def test_update_existing(self, temp_checkpoint_dir):
        """Update existing run."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        run = PipelineRun(
            run_id="test-123",
            project="test-project",
            feature_description="Test feature",
            current_state=PipelineState.NOT_STARTED,
        )

        manager.save(run)

        run.current_state = PipelineState.COMPLETED
        manager.save(run)

        loaded = manager.load("test-123")
        assert loaded.current_state == PipelineState.COMPLETED


# =============================================================================
# Integration Tests: Orchestrator
# =============================================================================


class TestOrchestratorDryRun:
    """Test orchestrator dry run mode."""

    def test_dry_run_shows_steps(self, capsys):
        """Dry run shows steps without executing."""
        orchestrator = SpecPipelineOrchestrator(project="test", dry_run=True)

        run = orchestrator.run("Test feature")

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "Test feature" in captured.out
        assert run.current_state == PipelineState.NOT_STARTED

    def test_dry_run_from_checkpoint(self, temp_checkpoint_dir, capsys):
        """Dry run from checkpoint shows remaining steps."""
        # Create a checkpoint
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        run = PipelineRun(
            run_id="test-resume",
            project="test",
            feature_description="Test feature",
            current_state=PipelineState.PLAN_CREATED,
        )
        manager.save(run)

        # Dry run with resume
        orchestrator = SpecPipelineOrchestrator(project="test", dry_run=True)
        orchestrator.checkpoint = manager

        result = orchestrator.run(None, run_id="test-resume")

        captured = capsys.readouterr()
        assert "plan_created" in captured.out.lower()


class TestOrchestratorStatus:
    """Test orchestrator status queries."""

    def test_get_status(self, temp_checkpoint_dir):
        """Get status of a run."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        run = PipelineRun(
            run_id="status-test",
            project="test",
            feature_description="Test feature",
            current_state=PipelineState.TASKS_CREATED,
            steps={"spec_created": {"status": "success", "duration_ms": 100}},
        )
        manager.save(run)

        orchestrator = SpecPipelineOrchestrator(project="test")
        orchestrator.checkpoint = manager

        status = orchestrator.get_status("status-test")

        assert status is not None
        assert status["state"] == "tasks_created"
        assert "steps" in status

    def test_get_status_not_found(self, temp_checkpoint_dir):
        """Status of nonexistent run returns None."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        orchestrator = SpecPipelineOrchestrator(project="test")
        orchestrator.checkpoint = manager

        status = orchestrator.get_status("nonexistent")
        assert status is None


# =============================================================================
# E2E Tests (with mocked skills)
# =============================================================================


class TestE2EPipeline:
    """End-to-end pipeline tests with mocked skill execution."""

    @pytest.mark.slow
    def test_full_pipeline_success(self, temp_checkpoint_dir, reset_circuits):
        """Full pipeline execution with all steps succeeding."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        # Mock skill execution
        with patch("spec_pipeline._run_skill") as mock_skill:
            mock_skill.return_value = StepResult(success=True, output="done")

            # Mock constitution check
            with patch("spec_pipeline.SPECKIT_DIR", temp_checkpoint_dir):
                orchestrator = SpecPipelineOrchestrator(project="test")
                orchestrator.checkpoint = manager

                run = orchestrator.run("Test feature")

                assert run.current_state == PipelineState.COMPLETED
                assert mock_skill.called

    @pytest.mark.slow
    def test_pipeline_resume_after_failure(self, temp_checkpoint_dir, reset_circuits):
        """Pipeline can resume from checkpoint after failure."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        # Create a checkpoint at PLAN_CREATED
        run = PipelineRun(
            run_id="resume-test",
            project="test",
            feature_description="Test feature",
            current_state=PipelineState.PLAN_CREATED,
        )
        manager.save(run)

        # Resume and complete
        with patch("spec_pipeline._run_skill") as mock_skill:
            mock_skill.return_value = StepResult(success=True, output="done")

            with patch("spec_pipeline.SPECKIT_DIR", temp_checkpoint_dir):
                orchestrator = SpecPipelineOrchestrator(project="test")
                orchestrator.checkpoint = manager

                result = orchestrator.run(None, run_id="resume-test")

                assert result.current_state == PipelineState.COMPLETED

    @pytest.mark.slow
    def test_circuit_breaker_fallback(self, temp_checkpoint_dir, reset_circuits):
        """Pipeline continues with fallback when circuit is open."""
        manager = CheckpointManager()
        manager._use_file = True
        manager._file_path = temp_checkpoint_dir / "pipeline_runs.json"

        # Open the GitHub circuit
        CIRCUITS["github"]._state.state = "open"
        CIRCUITS["github"]._state.opened_at = datetime.now()

        with patch("spec_pipeline._run_skill") as mock_skill:
            mock_skill.return_value = StepResult(success=True, output="done")

            with patch("spec_pipeline.SPECKIT_DIR", temp_checkpoint_dir):
                orchestrator = SpecPipelineOrchestrator(project="test")
                orchestrator.checkpoint = manager

                run = orchestrator.run("Test feature")

                # Should complete despite GitHub being down
                assert run.current_state == PipelineState.COMPLETED

                # Check that issues step was skipped
                assert run.steps.get("issues_created", {}).get("status") == "skipped"


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
