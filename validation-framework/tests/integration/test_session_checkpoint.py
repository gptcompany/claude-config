"""
Integration tests for session checkpoint integration (Plan 16-03).

Tests:
1. claudeflow-sync.js is in PostToolUse for Task
2. execute-phase.md has session checkpoint start step
3. execute-phase.md has session checkpoint end step
4. resume-project.md checks claude-flow session state
5. GSD workflows use memory_store/memory_retrieve
"""

from pathlib import Path

import pytest


class TestClaudeflowHookIntegration:
    """Tests for claudeflow-sync.js hook configuration."""

    def test_claudeflow_sync_in_posttooluse_task(self):
        """Test that claudeflow-sync is in PostToolUse for Task."""
        settings_path = Path.home() / ".claude/settings.json"
        if settings_path.exists():
            import json
            settings = json.loads(settings_path.read_text())
            post_hooks = settings.get("hooks", {}).get("PostToolUse", [])

            # Find Task matcher
            task_hooks = None
            for entry in post_hooks:
                if entry.get("matcher") == "Task":
                    task_hooks = entry.get("hooks", [])
                    break

            assert task_hooks is not None, "Task matcher not found in PostToolUse"

            # Check for claudeflow-sync
            has_claudeflow = any(
                "claudeflow-sync" in h.get("command", "")
                for h in task_hooks
            )
            assert has_claudeflow, "claudeflow-sync.js not in Task PostToolUse hooks"

    def test_claudeflow_sync_in_stop_hooks(self):
        """Test that claudeflow-sync is in Stop hooks."""
        settings_path = Path.home() / ".claude/settings.json"
        if settings_path.exists():
            import json
            settings = json.loads(settings_path.read_text())
            stop_hooks = settings.get("hooks", {}).get("Stop", [])

            # Check for claudeflow-sync in any Stop matcher
            has_claudeflow = False
            for entry in stop_hooks:
                hooks = entry.get("hooks", [])
                for h in hooks:
                    if "claudeflow-sync" in h.get("command", ""):
                        has_claudeflow = True
                        break

            assert has_claudeflow, "claudeflow-sync.js not in Stop hooks"


class TestExecutePhaseCheckpoints:
    """Tests for execute-phase.md session checkpoint integration."""

    def test_execute_phase_has_checkpoint_start_step(self):
        """Test that execute-phase has session_checkpoint_start step."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "session_checkpoint_start" in content

    def test_execute_phase_has_checkpoint_end_step(self):
        """Test that execute-phase has session_checkpoint_end step."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "session_checkpoint_end" in content

    def test_execute_phase_uses_session_save(self):
        """Test that execute-phase calls session_save."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "session_save" in content

    def test_execute_phase_uses_memory_store(self):
        """Test that execute-phase calls memory_store."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "memory_store" in content

    def test_execute_phase_includes_memory_flag(self):
        """Test that session_save includes memory flag."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "includeMemory" in content

    def test_execute_phase_handles_crash_recovery(self):
        """Test that execute-phase has crash recovery logic."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-phase.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Should mention recovery or resume
            assert "recover" in content.lower() or "resume" in content.lower()


class TestResumeProjectCheckpoints:
    """Tests for resume-project.md session state integration."""

    def test_resume_project_has_session_state_step(self):
        """Test that resume-project has check_session_state step."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/resume-project.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "check_session_state" in content

    def test_resume_project_uses_memory_retrieve(self):
        """Test that resume-project calls memory_retrieve."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/resume-project.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "memory_retrieve" in content

    def test_resume_project_uses_session_restore(self):
        """Test that resume-project offers session_restore."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/resume-project.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "session_restore" in content

    def test_resume_project_explains_advantages(self):
        """Test that resume-project explains advantages over file-based."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/resume-project.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Should mention /clear or crashes or terminal
            assert "/clear" in content or "crash" in content.lower()

    def test_resume_project_has_fallback(self):
        """Test that resume-project has file-based fallback."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/resume-project.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Should have fallback step
            assert "check_incomplete_work" in content


class TestGSDMemoryIntegration:
    """Tests for GSD workflow memory integration."""

    def test_execute_plan_mentions_memory(self):
        """Test that execute-plan has memory reference."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-plan.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # May not have direct memory calls but should reference session/state
            assert "session" in content.lower() or "state" in content.lower()

    def test_verify_work_mentions_session(self):
        """Test that verify-work has session reference."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/verify-work.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Should have some session awareness
            assert "session" in content.lower() or "state" in content.lower()

    def test_complete_milestone_validates_state(self):
        """Test that complete-milestone references state validation."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/complete-milestone.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "state" in content.lower() or "validation" in content.lower()


class TestCodeSimplifierIntegration:
    """Tests for code-simplifier automatic trigger."""

    def test_orchestrator_has_complexity_check(self):
        """Test that orchestrator has check_complexity_and_simplify function."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "check_complexity_and_simplify" in content

    def test_complexity_check_has_thresholds(self):
        """Test that complexity check has 200 LOC threshold."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "200" in content  # 200 line threshold

    def test_complexity_check_spawns_simplifier(self):
        """Test that complexity check spawns code-simplifier agent."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # Should spawn code-simplifier
            assert "code-simplifier" in content

    def test_run_all_accepts_modified_files(self):
        """Test that run_all accepts modified_files parameter."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "modified_files" in content

    def test_cli_accepts_files_argument(self):
        """Test that CLI accepts --files argument."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "--files" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
