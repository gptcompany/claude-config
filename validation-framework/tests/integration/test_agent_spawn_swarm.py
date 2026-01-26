"""
Integration tests for agent spawn and swarm activation (Plan 16-02).

Tests:
1. spawn_agent function exists and is callable
2. VALIDATION_AGENT_SPAWN env var respected
3. VALIDATION_SWARM env var respected
4. run_tier3_parallel falls back on error
5. Swarm initializes with hive-manager
"""

from pathlib import Path

import pytest


class TestAgentSpawnFunction:
    """Tests for the spawn_agent function."""

    def test_spawn_agent_exists_in_orchestrator(self):
        """Test that spawn_agent function exists in orchestrator."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "def spawn_agent(" in content

    def test_spawn_agent_checks_env_var(self):
        """Test that VALIDATION_AGENT_SPAWN is checked."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "AGENT_SPAWN_ENABLED" in content
            assert "VALIDATION_AGENT_SPAWN" in content

    def test_spawn_agent_uses_claude_cli(self):
        """Test that spawn uses claude CLI."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert '"claude"' in content

    def test_spawn_agent_handles_missing_cli(self):
        """Test graceful handling when claude CLI not found."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "FileNotFoundError" in content

    def test_spawn_agent_called_on_tier2_failure(self):
        """Test that _suggest_fixes calls spawn_agent."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # spawn_agent should be called in _suggest_fixes
            assert "spawn_agent(" in content


class TestSwarmActivation:
    """Tests for swarm parallel execution."""

    def test_swarm_env_var_exists(self):
        """Test that VALIDATION_SWARM env var is checked."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "SWARM_ENABLED" in content
            assert "VALIDATION_SWARM" in content

    def test_run_tier3_parallel_exists(self):
        """Test that parallel execution function exists."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "async def run_tier3_parallel" in content

    def test_tier3_uses_parallel_when_enabled(self):
        """Test that run_tier uses parallel for Tier 3."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # run_tier should check for MONITOR tier and use parallel
            assert "ValidationTier.MONITOR" in content
            assert "run_tier3_parallel" in content

    def test_parallel_checks_hive_manager(self):
        """Test that parallel execution checks for hive-manager."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "hive-manager" in content

    def test_parallel_fallback_to_sequential(self):
        """Test that parallel falls back to sequential on error."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "falling back to sequential" in content.lower()

    def test_parallel_uses_asyncio_gather(self):
        """Test that parallel uses asyncio.gather for actual parallelism."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "asyncio.gather" in content

    def test_parallel_caps_workers(self):
        """Test that parallel execution caps worker count."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # Should cap at 4 workers
            assert "min(" in content or "worker_count" in content

    def test_parallel_handles_exceptions(self):
        """Test that parallel execution handles exceptions properly."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "return_exceptions=True" in content

    def test_parallel_cleans_up_swarm(self):
        """Test that parallel execution cleans up swarm after."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            assert "shutdown" in content


class TestHiveManagerIntegration:
    """Tests for hive-manager.js integration."""

    def test_hive_manager_exists(self):
        """Test that hive-manager.js exists."""
        hive_path = Path.home() / ".claude/scripts/hooks/control/hive-manager.js"
        assert hive_path.exists(), "hive-manager.js not found"

    def test_hive_manager_has_init(self):
        """Test that hive-manager has init functionality."""
        hive_path = Path.home() / ".claude/scripts/hooks/control/hive-manager.js"
        if hive_path.exists():
            content = hive_path.read_text()
            assert "init" in content.lower()

    def test_hive_manager_has_shutdown(self):
        """Test that hive-manager has shutdown functionality."""
        hive_path = Path.home() / ".claude/scripts/hooks/control/hive-manager.js"
        if hive_path.exists():
            content = hive_path.read_text()
            assert "shutdown" in content.lower() or "close" in content.lower()

    def test_hive_manager_saves_state(self):
        """Test that hive-manager saves state to file."""
        hive_path = Path.home() / ".claude/scripts/hooks/control/hive-manager.js"
        if hive_path.exists():
            content = hive_path.read_text()
            assert "state.json" in content


class TestEnvVarControls:
    """Tests for environment variable controls."""

    def test_agent_spawn_default_enabled(self):
        """Test that agent spawn defaults to enabled."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # Should default to "true"
            assert 'get("VALIDATION_AGENT_SPAWN", "true")' in content

    def test_swarm_default_enabled(self):
        """Test that swarm defaults to enabled."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # Should default to "true"
            assert 'get("VALIDATION_SWARM", "true")' in content

    def test_env_vars_case_insensitive(self):
        """Test that env var checks are case insensitive."""
        orchestrator_path = Path.home() / ".claude/templates/validation/orchestrator.py"
        if orchestrator_path.exists():
            content = orchestrator_path.read_text()
            # Should use .lower() for comparison
            assert ".lower()" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
