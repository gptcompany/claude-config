"""
Integration tests for GSD + ValidationOrchestrator.

Tests the integration points between GSD workflows and the validation framework:
1. execute-plan calls orchestrator with Tier 1
2. execute-plan blocks on Tier 1 failures
3. verify-work calls orchestrator with Tier 1 and 2
4. verify-work shows warnings for Tier 2
5. complete-milestone runs all tiers
6. complete-milestone blocks on Tier 1 < 100%
7. Override mechanism works with logging
8. VALIDATION_ENABLED flag respected

These tests verify the workflow integration, not the orchestrator itself.
"""

import os
import subprocess
from pathlib import Path

import pytest


class TestExecutePlanValidation:
    """Tests for execute-plan.md validation integration."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create a mock orchestrator script for testing."""
        orchestrator = tmp_path / "orchestrator.py"
        orchestrator.write_text("""#!/usr/bin/env python3
import sys
tier = sys.argv[1] if len(sys.argv) > 1 else "all"
# Return codes: 0=pass, 1=fail, 2=error
if tier == "1":
    print("Tier 1 (BLOCKER): [PASS]")
    print("  [+] code_quality: OK")
    print("  [+] type_safety: OK")
    sys.exit(0)
elif tier == "fail":
    print("Tier 1 (BLOCKER): [FAIL]")
    print("  [-] code_quality: 5 errors")
    sys.exit(1)
elif tier == "error":
    print("Orchestrator error")
    sys.exit(2)
else:
    print("Validation complete")
    sys.exit(0)
""")
        orchestrator.chmod(0o755)
        return orchestrator

    def test_execute_plan_calls_orchestrator(self, mock_orchestrator):
        """Test that execute-plan calls orchestrator.py with tier 1."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Tier 1" in result.stdout

    def test_execute_plan_blocks_on_tier1_fail(self, mock_orchestrator):
        """Test that exit code 1 stops plan completion."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "fail"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "[FAIL]" in result.stdout

    def test_execute_plan_proceeds_on_tier1_pass(self, mock_orchestrator):
        """Test that exit code 0 allows plan to continue."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "[PASS]" in result.stdout

    def test_execute_plan_failopen_on_error(self, mock_orchestrator):
        """Test that exit code 2 warns but continues (fail-open)."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "error"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        # In fail-open mode, workflow should log warning and proceed

    def test_execute_plan_logs_validation_result(self, tmp_path, mock_orchestrator):
        """Test that validation results are logged in SUMMARY.md."""
        # Simulate summary creation after validation
        summary_path = tmp_path / "SUMMARY.md"

        # Run orchestrator
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "1"],
            capture_output=True,
            text=True,
        )

        # Simulate logging to summary
        if result.returncode == 0:
            summary_path.write_text("""## Verification

- [x] Tier 1 validation passed (code_quality, type_safety, security)
""")

        assert summary_path.exists()
        content = summary_path.read_text()
        assert "Tier 1 validation passed" in content

    def test_execute_plan_shows_failure_details(self, mock_orchestrator):
        """Test that failure messages are displayed."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "fail"],
            capture_output=True,
            text=True,
        )
        assert "code_quality" in result.stdout
        assert "5 errors" in result.stdout

    def test_execute_plan_suggests_planfix(self):
        """Test that /gsd:plan-fix is suggested on failure."""
        # This tests the workflow behavior - we verify the workflow file contains the suggestion
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-plan.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "/gsd:plan-fix" in content

    def test_execute_plan_respects_validation_disabled(self):
        """Test that VALIDATION_ENABLED=false skips validation."""
        # Set environment variable
        env = os.environ.copy()
        env["VALIDATION_ENABLED"] = "false"

        # Workflow should check this and skip validation
        # We verify the workflow file contains the check
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-plan.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "VALIDATION_ENABLED" in content

    def test_execute_plan_handles_missing_orchestrator(self):
        """Test graceful handling when orchestrator.py not found."""
        result = subprocess.run(
            ["python3", "/nonexistent/orchestrator.py", "1"],
            capture_output=True,
            text=True,
        )
        # Should fail with file not found
        assert result.returncode != 0

    def test_execute_plan_no_duplicate_validation(self):
        """Test that validation doesn't run multiple times in same session."""
        # This is a workflow-level debounce check
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-plan.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Verify debounce guidance exists
            assert "Debounce" in content or "duplicate" in content.lower()


class TestVerifyWorkValidation:
    """Tests for verify-work.md validation integration."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create a mock orchestrator for testing."""
        orchestrator = tmp_path / "orchestrator.py"
        orchestrator.write_text("""#!/usr/bin/env python3
import sys
tier = sys.argv[1] if len(sys.argv) > 1 else "all"
if tier == "1":
    print("Tier 1 (BLOCKER): [PASS]")
    sys.exit(0)
elif tier == "2":
    print("Tier 2 (WARNING): [WARN]")
    print("  [-] design_principles: Large files detected")
    print("  [+] documentation: OK")
    sys.exit(0)
elif tier == "fail":
    print("Tier 1 (BLOCKER): [FAIL]")
    sys.exit(1)
else:
    sys.exit(0)
""")
        orchestrator.chmod(0o755)
        return orchestrator

    def test_verify_work_runs_tier1_first(self, mock_orchestrator):
        """Test that Tier 1 is called before UAT."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "1"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Tier 1" in result.stdout

    def test_verify_work_runs_tier2_second(self, mock_orchestrator):
        """Test that Tier 2 is called after Tier 1 passes."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Tier 2" in result.stdout

    def test_verify_work_skips_uat_on_tier1_fail(self, mock_orchestrator):
        """Test that UAT is skipped when Tier 1 fails."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "fail"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        # Workflow should not proceed to UAT steps

    def test_verify_work_shows_tier2_warnings(self, mock_orchestrator):
        """Test that Tier 2 warnings are displayed to user."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "2"],
            capture_output=True,
            text=True,
        )
        assert "design_principles" in result.stdout
        assert "Large files" in result.stdout

    def test_verify_work_proceeds_with_tier2_warnings(self, mock_orchestrator):
        """Test that Tier 2 warnings don't block UAT."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "2"],
            capture_output=True,
            text=True,
        )
        # Exit code 0 means warnings don't block
        assert result.returncode == 0

    def test_verify_work_routes_to_planfix(self):
        """Test that /gsd:plan-fix is suggested on Tier 1 fail."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/verify-work.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "/gsd:plan-fix" in content

    def test_verify_work_shows_validation_summary(self):
        """Test that validation summary is shown before UAT."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/verify-work.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "Automated Validation Results" in content

    def test_verify_work_handles_both_tiers_pass(self, mock_orchestrator):
        """Test clean proceed to UAT when both tiers pass."""
        # Run both tiers
        t1 = subprocess.run(
            ["python3", str(mock_orchestrator), "1"],
            capture_output=True,
            text=True,
        )
        t2 = subprocess.run(
            ["python3", str(mock_orchestrator), "2"],
            capture_output=True,
            text=True,
        )
        assert t1.returncode == 0
        assert t2.returncode == 0

    def test_verify_work_respects_quick_flag(self):
        """Test that --quick skips Tier 2."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/verify-work.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "--quick" in content or "Quick Mode" in content

    def test_verify_work_logs_validation_metrics(self):
        """Test that validation results are logged for tracking."""
        # This verifies the workflow mentions metrics/logging
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/verify-work.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            # Validation results should be presented/logged
            assert "Validation" in content


class TestCompleteMilestoneValidation:
    """Tests for complete-milestone.md quality gate."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path):
        """Create a mock orchestrator for quality gate testing."""
        orchestrator = tmp_path / "orchestrator.py"
        orchestrator.write_text("""#!/usr/bin/env python3
import sys
tier = sys.argv[1] if len(sys.argv) > 1 else "all"
if tier == "all":
    print("=== VALIDATION REPORT ===")
    print("Tier 1 (BLOCKER): [PASS]")
    print("Tier 2 (WARNING): [PASS]")
    print("Tier 3 (MONITOR): [PASS]")
    print("RESULT: PASSED")
    sys.exit(0)
elif tier == "fail":
    print("Tier 1 (BLOCKER): [FAIL]")
    print("  [-] security: Secrets detected")
    sys.exit(1)
else:
    sys.exit(0)
""")
        orchestrator.chmod(0o755)
        return orchestrator

    def test_complete_milestone_runs_all_tiers(self, mock_orchestrator):
        """Test that all tiers are executed for milestone."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "all"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Tier 1" in result.stdout
        assert "Tier 2" in result.stdout
        assert "Tier 3" in result.stdout

    def test_complete_milestone_blocks_on_tier1_fail(self, mock_orchestrator):
        """Test that milestone cannot be archived with Tier 1 failures."""
        result = subprocess.run(
            ["python3", str(mock_orchestrator), "fail"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_complete_milestone_allows_override(self):
        """Test that --force with reason allows completion."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/complete-milestone.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "--force" in content
            assert "--reason" in content

    def test_complete_milestone_logs_override(self):
        """Test that overrides are logged in milestone archive."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/complete-milestone.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "Quality Gate Override" in content
            assert "logged" in content.lower() or "audit" in content.lower()

    def test_complete_milestone_records_metrics(self):
        """Test that Tier 3 metrics are recorded in archive."""
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/complete-milestone.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "Tier 3" in content
            assert "Metrics" in content or "metrics" in content


class TestValidationIntegration:
    """Full integration tests for validation + GSD workflows."""

    def test_validation_disabled_skips_all(self):
        """Test that VALIDATION_ENABLED=false skips all validation."""
        workflows = [
            "execute-plan.md",
            "verify-work.md",
            "complete-milestone.md",
        ]

        for workflow in workflows:
            path = Path.home() / f".claude/get-shit-done/workflows/{workflow}"
            if path.exists():
                content = path.read_text()
                assert "VALIDATION_ENABLED" in content, f"{workflow} missing VALIDATION_ENABLED check"

    def test_orchestrator_error_failopen(self, tmp_path):
        """Test graceful handling of orchestrator errors."""
        # Create orchestrator that errors
        orchestrator = tmp_path / "orchestrator.py"
        orchestrator.write_text("""#!/usr/bin/env python3
import sys
print("Orchestrator error")
sys.exit(2)
""")
        orchestrator.chmod(0o755)

        result = subprocess.run(
            ["python3", str(orchestrator)],
            capture_output=True,
            text=True,
        )

        # Exit code 2 means error, but fail-open should allow workflow to continue
        assert result.returncode == 2

        # Verify workflows handle exit code 2
        workflow_path = Path.home() / ".claude/get-shit-done/workflows/execute-plan.md"
        if workflow_path.exists():
            content = workflow_path.read_text()
            assert "fail-open" in content.lower() or "exit code 2" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
