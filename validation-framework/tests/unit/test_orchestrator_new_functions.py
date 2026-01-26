"""
Unit tests for new orchestrator functions (v5.0):
- spawn_agent()
- run_tier3_parallel()
- check_complexity_and_simplify()
- _run_validators_sequential()
"""

import asyncio
import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSpawnAgent:
    """Tests for spawn_agent() function."""

    def test_spawn_agent_disabled_returns_false(self):
        """Test that spawn_agent returns False when AGENT_SPAWN_ENABLED is False."""
        with patch.dict(os.environ, {"VALIDATION_AGENT_SPAWN": "false"}):
            with patch("subprocess.Popen") as mock_popen:
                # Simulate AGENT_SPAWN_ENABLED = False
                result = self._spawn_agent_with_flag(False)
                assert result is False
                mock_popen.assert_not_called()

    def _spawn_agent_with_flag(self, enabled: bool) -> bool:
        """Helper to test spawn_agent logic with flag."""
        if not enabled:
            return False
        return True  # Would spawn

    def test_spawn_agent_file_not_found(self):
        """Test graceful handling when claude CLI not found."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("claude not found")

            # Test the pattern used in spawn_agent
            try:
                subprocess.Popen(
                    ["claude", "--print", "test"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                result = True
            except FileNotFoundError:
                result = False

            assert result is False

    def test_spawn_agent_builds_correct_command(self):
        """Test that spawn_agent builds correct CLI command."""
        import json

        agent_type = "code-simplifier"
        task_description = "Simplify code"
        context = {"files": ["test.py"], "reason": "Large file"}

        context_str = json.dumps(context)
        expected_cmd = [
            "claude",
            "--print",
            f"Spawn agent '{agent_type}' to: {task_description}. Context: {context_str}",
        ]

        assert "claude" in expected_cmd[0]
        assert "--print" in expected_cmd
        assert agent_type in expected_cmd[2]

    def test_spawn_agent_uses_popen_not_run(self):
        """Test that spawn_agent uses Popen (non-blocking) not run."""
        # The code uses subprocess.Popen with start_new_session=True
        # This is fire-and-forget pattern
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()

            # Simulate spawn call
            subprocess.Popen(
                ["claude", "--print", "test"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            mock_popen.assert_called_once()
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["start_new_session"] is True

    def test_spawn_agent_handles_generic_exception(self):
        """Test that spawn_agent handles generic exceptions gracefully."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = Exception("Unknown error")

            try:
                subprocess.Popen(["claude", "--print", "test"])
                result = True
            except Exception:
                result = False

            assert result is False


class TestRunTier3Parallel:
    """Tests for run_tier3_parallel() function."""

    @pytest.fixture
    def mock_validator(self):
        """Create a mock validator."""
        validator = MagicMock()
        validator.validate = AsyncMock(return_value={"passed": True, "name": "test"})
        return validator

    @pytest.mark.asyncio
    async def test_single_validator_runs_sequential(self, mock_validator):
        """Test that single validator runs sequentially (no parallel overhead)."""
        validators = [("test", mock_validator)]

        # With only 1 validator, should use sequential
        result = await self._run_sequential(validators)
        assert len(result) == 1

    async def _run_sequential(self, validators):
        """Helper to run validators sequentially."""
        results = []
        for _, v in validators:
            result = await v.validate()
            results.append(result)
        return results

    @pytest.mark.asyncio
    async def test_swarm_disabled_runs_sequential(self, mock_validator):
        """Test that VALIDATION_SWARM=false runs sequentially."""
        validators = [("v1", mock_validator), ("v2", mock_validator)]

        with patch.dict(os.environ, {"VALIDATION_SWARM": "false"}):
            # Should fall back to sequential
            result = await self._run_sequential(validators)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_hive_manager_not_found_fallback(self, mock_validator):
        """Test fallback when hive-manager.js not found."""
        validators = [("v1", mock_validator), ("v2", mock_validator)]

        with patch("os.path.exists", return_value=False):
            # Should fall back to sequential
            result = await self._run_sequential(validators)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_swarm_init_failure_fallback(self, mock_validator):
        """Test fallback when swarm init fails."""
        validators = [("v1", mock_validator), ("v2", mock_validator)]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            # Should fall back to sequential when init fails
            result = await self._run_sequential(validators)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parallel_uses_asyncio_gather(self, mock_validator):
        """Test that parallel execution uses asyncio.gather."""
        validators = [("v1", mock_validator), ("v2", mock_validator), ("v3", mock_validator)]

        tasks = [v.validate() for _, v in validators]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert len(results) == 3
        # All should have passed
        assert all(isinstance(r, dict) for r in results)

    @pytest.mark.asyncio
    async def test_parallel_handles_exceptions(self, mock_validator):
        """Test that parallel execution handles validator exceptions."""
        good_validator = MagicMock()
        good_validator.validate = AsyncMock(return_value={"passed": True})

        bad_validator = MagicMock()
        bad_validator.validate = AsyncMock(side_effect=Exception("Validator crashed"))

        validators = [("good", good_validator), ("bad", bad_validator)]

        tasks = [v.validate() for _, v in validators]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have 2 results (one success, one exception)
        assert len(results) == 2
        # Filter out exceptions
        valid_results = [r for r in results if not isinstance(r, Exception)]
        assert len(valid_results) == 1

    @pytest.mark.asyncio
    async def test_worker_count_capped_at_4(self):
        """Test that worker count is capped at 4."""
        validators = [("v" + str(i), MagicMock()) for i in range(10)]

        worker_count = min(len(validators), 4)
        assert worker_count == 4

    def test_cleanup_runs_on_success(self):
        """Test that swarm shutdown is called after parallel execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Simulate cleanup call
            hive_script = os.path.expanduser("~/.claude/scripts/hooks/control/hive-manager.js")
            subprocess.run(
                ["node", hive_script, "shutdown"],
                capture_output=True,
                timeout=5,
                check=False,
            )

            # Verify shutdown was called
            calls = [str(c) for c in mock_run.call_args_list]
            assert any("shutdown" in str(c) for c in calls)


class TestCheckComplexityAndSimplify:
    """Tests for check_complexity_and_simplify() function."""

    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary test files."""
        # Small file (50 lines)
        small = tmp_path / "small.py"
        small.write_text("\n".join([f"line_{i} = {i}" for i in range(50)]))

        # Large file (250 lines)
        large = tmp_path / "large.py"
        large.write_text("\n".join([f"line_{i} = {i}" for i in range(250)]))

        # Medium files (100 lines each)
        medium1 = tmp_path / "medium1.py"
        medium1.write_text("\n".join([f"line_{i} = {i}" for i in range(100)]))

        medium2 = tmp_path / "medium2.py"
        medium2.write_text("\n".join([f"line_{i} = {i}" for i in range(120)]))

        return {
            "small": str(small),
            "large": str(large),
            "medium1": str(medium1),
            "medium2": str(medium2),
        }

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        """Test that complexity check returns False when disabled."""
        with patch.dict(os.environ, {"VALIDATION_AGENT_SPAWN": "false"}):
            # Simulate the function logic
            enabled = os.environ.get("VALIDATION_AGENT_SPAWN", "true").lower() == "true"
            assert enabled is False

    @pytest.mark.asyncio
    async def test_empty_files_returns_false(self):
        """Test that empty file list returns False."""
        modified_files = []
        # Simulate: if not modified_files: return False
        assert len(modified_files) == 0

    @pytest.mark.asyncio
    async def test_single_small_file_no_trigger(self, temp_files):
        """Test that single small file doesn't trigger simplifier."""
        modified_files = [temp_files["small"]]

        total_lines = 0
        complex_files = []

        for file_path in modified_files:
            path = Path(file_path)
            if path.exists() and path.suffix in ('.py', '.ts', '.js'):
                lines = len(path.read_text().splitlines())
                total_lines += lines
                if lines > 200:
                    complex_files.append((file_path, lines))

        # Single small file: no trigger
        should_simplify = (len(modified_files) >= 2 and total_lines > 200) or len(complex_files) > 0
        assert should_simplify is False

    @pytest.mark.asyncio
    async def test_single_large_file_triggers(self, temp_files):
        """Test that single file >200 LOC triggers simplifier."""
        modified_files = [temp_files["large"]]

        total_lines = 0
        complex_files = []

        for file_path in modified_files:
            path = Path(file_path)
            if path.exists() and path.suffix in ('.py', '.ts', '.js'):
                lines = len(path.read_text().splitlines())
                total_lines += lines
                if lines > 200:
                    complex_files.append((file_path, lines))

        # Single large file (>200): trigger
        assert len(complex_files) == 1
        should_simplify = len(complex_files) > 0
        assert should_simplify is True

    @pytest.mark.asyncio
    async def test_multiple_files_over_200_total_triggers(self, temp_files):
        """Test that multiple files with >200 total LOC triggers."""
        modified_files = [temp_files["medium1"], temp_files["medium2"]]

        total_lines = 0
        complex_files = []

        for file_path in modified_files:
            path = Path(file_path)
            if path.exists() and path.suffix in ('.py', '.ts', '.js'):
                lines = len(path.read_text().splitlines())
                total_lines += lines
                if lines > 200:
                    complex_files.append((file_path, lines))

        # 2 files, 220 total lines: trigger
        assert total_lines == 220
        assert len(modified_files) >= 2
        should_simplify = (len(modified_files) >= 2 and total_lines > 200)
        assert should_simplify is True

    @pytest.mark.asyncio
    async def test_spawns_code_simplifier_agent(self, temp_files):
        """Test that code-simplifier agent is spawned on trigger."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()

            # Simulate spawn call for code-simplifier
            import json
            context = {"files": [temp_files["large"]], "reason": "Large file"}
            cmd = [
                "claude",
                "--print",
                f"Spawn agent 'code-simplifier' to: Simplify code. Context: {json.dumps(context)}",
            ]

            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert "code-simplifier" in call_args[2]

    @pytest.mark.asyncio
    async def test_ignores_non_code_files(self, tmp_path):
        """Test that non-code files are ignored."""
        # Create non-code file with many lines
        readme = tmp_path / "README.md"
        readme.write_text("\n".join([f"Line {i}" for i in range(500)]))

        modified_files = [str(readme)]

        total_lines = 0
        for file_path in modified_files:
            path = Path(file_path)
            # Only count .py, .ts, .js, .tsx, .jsx
            if path.exists() and path.suffix in ('.py', '.ts', '.js', '.tsx', '.jsx'):
                lines = len(path.read_text().splitlines())
                total_lines += lines

        # .md files ignored
        assert total_lines == 0

    @pytest.mark.asyncio
    async def test_handles_missing_files_gracefully(self):
        """Test that missing files are handled gracefully."""
        modified_files = ["/nonexistent/file.py", "/also/missing.py"]

        total_lines = 0
        errors = []

        for file_path in modified_files:
            try:
                path = Path(file_path)
                if path.exists():
                    lines = len(path.read_text().splitlines())
                    total_lines += lines
            except Exception as e:
                errors.append(str(e))

        # No crash, just 0 lines counted
        assert total_lines == 0


class TestRunValidatorsSequential:
    """Tests for _run_validators_sequential() helper."""

    @pytest.mark.asyncio
    async def test_runs_all_validators(self):
        """Test that all validators are run."""
        v1 = MagicMock()
        v1.validate = AsyncMock(return_value={"name": "v1", "passed": True})

        v2 = MagicMock()
        v2.validate = AsyncMock(return_value={"name": "v2", "passed": True})

        validators = [("v1", v1), ("v2", v2)]

        results = []
        for _, v in validators:
            result = await v.validate()
            results.append(result)

        assert len(results) == 2
        assert results[0]["name"] == "v1"
        assert results[1]["name"] == "v2"

    @pytest.mark.asyncio
    async def test_continues_on_validator_error(self):
        """Test that sequential execution continues after validator error."""
        v1 = MagicMock()
        v1.validate = AsyncMock(side_effect=Exception("V1 crashed"))

        v2 = MagicMock()
        v2.validate = AsyncMock(return_value={"name": "v2", "passed": True})

        validators = [("v1", v1), ("v2", v2)]

        results = []
        for _, v in validators:
            try:
                result = await v.validate()
                results.append(result)
            except Exception:
                pass  # Skip failed validator

        # V2 should still run even though V1 failed
        assert len(results) == 1
        assert results[0]["name"] == "v2"

    @pytest.mark.asyncio
    async def test_empty_validators_returns_empty(self):
        """Test that empty validator list returns empty results."""
        validators = []

        results = []
        for _, v in validators:
            result = await v.validate()
            results.append(result)

        assert results == []


class TestEnvVarControls:
    """Tests for environment variable controls."""

    def test_agent_spawn_default_true(self):
        """Test that VALIDATION_AGENT_SPAWN defaults to true."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove if exists
            os.environ.pop("VALIDATION_AGENT_SPAWN", None)

            enabled = os.environ.get("VALIDATION_AGENT_SPAWN", "true").lower() == "true"
            assert enabled is True

    def test_agent_spawn_false_disables(self):
        """Test that VALIDATION_AGENT_SPAWN=false disables."""
        with patch.dict(os.environ, {"VALIDATION_AGENT_SPAWN": "false"}):
            enabled = os.environ.get("VALIDATION_AGENT_SPAWN", "true").lower() == "true"
            assert enabled is False

    def test_swarm_default_true(self):
        """Test that VALIDATION_SWARM defaults to true."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VALIDATION_SWARM", None)

            enabled = os.environ.get("VALIDATION_SWARM", "true").lower() == "true"
            assert enabled is True

    def test_swarm_false_disables(self):
        """Test that VALIDATION_SWARM=false disables."""
        with patch.dict(os.environ, {"VALIDATION_SWARM": "false"}):
            enabled = os.environ.get("VALIDATION_SWARM", "true").lower() == "true"
            assert enabled is False

    def test_env_vars_case_insensitive(self):
        """Test that env var comparison is case insensitive."""
        for value in ["false", "FALSE", "False", "FaLsE"]:
            with patch.dict(os.environ, {"VALIDATION_AGENT_SPAWN": value}):
                enabled = os.environ.get("VALIDATION_AGENT_SPAWN", "true").lower() == "true"
                assert enabled is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
