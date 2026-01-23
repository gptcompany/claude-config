#!/usr/bin/env python3
"""Unit tests for post_tool_hook.py - PostToolUse Hook."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hooks.post_tool_hook import (
    TIMEOUT_SECONDS,
    TOOLS_TO_VALIDATE,
    approve,
    block,
    run_validation,
)


class TestConstants:
    """Tests for module constants."""

    def test_timeout_reasonable(self):
        """Ensure timeout is reasonable (not too long, not too short)."""
        assert 10 <= TIMEOUT_SECONDS <= 60

    def test_tools_to_validate(self):
        """Ensure correct tools are validated."""
        assert "Write" in TOOLS_TO_VALIDATE
        assert "Edit" in TOOLS_TO_VALIDATE
        assert "MultiEdit" in TOOLS_TO_VALIDATE
        # Read should NOT be validated
        assert "Read" not in TOOLS_TO_VALIDATE
        assert "Bash" not in TOOLS_TO_VALIDATE


class TestApproveFunction:
    """Tests for approve() function."""

    def test_approve_outputs_json(self, capsys):
        """Test approve outputs correct JSON."""
        with pytest.raises(SystemExit) as exc_info:
            approve()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["decision"] == "approve"

    def test_approve_exits_zero(self):
        """Test approve exits with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            approve()
        assert exc_info.value.code == 0


class TestBlockFunction:
    """Tests for block() function."""

    def test_block_outputs_json_with_reason(self, capsys):
        """Test block outputs JSON with reason."""
        with pytest.raises(SystemExit):
            block("Syntax error in file.py")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["decision"] == "block"
        assert output["reason"] == "Syntax error in file.py"

    def test_block_exits_zero(self):
        """Test block exits with code 0 (not error code)."""
        with pytest.raises(SystemExit) as exc_info:
            block("any reason")
        assert exc_info.value.code == 0

    def test_block_preserves_special_chars(self, capsys):
        """Test block preserves special characters in reason."""
        with pytest.raises(SystemExit):
            block("Error: \"quotes\" and 'apostrophes' in <message>")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "quotes" in output["reason"]
        assert "apostrophes" in output["reason"]


class TestRunValidation:
    """Tests for run_validation() async function."""

    @pytest.mark.asyncio
    async def test_run_validation_returns_tuple(self):
        """Test run_validation returns (bool, str) tuple."""
        # Test with actual orchestrator (may pass or fail depending on environment)
        has_blockers, summary = await run_validation("test.py")

        # Always returns a tuple regardless of success/failure
        assert isinstance(has_blockers, bool)
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_run_validation_nonexistent_file(self):
        """Test validation handles non-existent file gracefully."""
        has_blockers, summary = await run_validation("/nonexistent/path/file.py")

        # Should not crash, returns tuple
        assert isinstance(has_blockers, bool)
        assert isinstance(summary, str)


class TestMainFunction:
    """Tests for main() entry point via stdin simulation."""

    @pytest.fixture
    def mock_stdin(self):
        """Fixture to mock stdin."""

        def _mock_stdin(content):
            return patch("sys.stdin", StringIO(content))

        return _mock_stdin

    def test_empty_stdin_approves(self, mock_stdin, capsys):
        """Test empty stdin results in approve."""
        with mock_stdin(""):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_invalid_json_approves(self, mock_stdin, capsys):
        """Test invalid JSON results in approve (fail-open)."""
        with mock_stdin("not valid json {{{"):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_read_tool_approves(self, mock_stdin, capsys):
        """Test Read tool (not in validation list) approves immediately."""
        hook_input = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": "test.py"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_bash_tool_approves(self, mock_stdin, capsys):
        """Test Bash tool approves immediately."""
        hook_input = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_write_non_python_approves(self, mock_stdin, capsys):
        """Test Write to non-Python file approves."""
        hook_input = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": "readme.md"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_write_no_filepath_approves(self, mock_stdin, capsys):
        """Test Write with no file_path approves."""
        hook_input = json.dumps({"tool_name": "Write", "tool_input": {}})
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out


class TestToolFiltering:
    """Tests for tool filtering logic."""

    def test_write_in_validation_list(self):
        """Write should trigger validation."""
        assert "Write" in TOOLS_TO_VALIDATE

    def test_edit_in_validation_list(self):
        """Edit should trigger validation."""
        assert "Edit" in TOOLS_TO_VALIDATE

    def test_multiedit_in_validation_list(self):
        """MultiEdit should trigger validation."""
        assert "MultiEdit" in TOOLS_TO_VALIDATE

    def test_glob_not_in_validation_list(self):
        """Glob should NOT trigger validation."""
        assert "Glob" not in TOOLS_TO_VALIDATE

    def test_grep_not_in_validation_list(self):
        """Grep should NOT trigger validation."""
        assert "Grep" not in TOOLS_TO_VALIDATE


class TestMainEdgeCases:
    """Additional edge case tests for main() function."""

    @pytest.fixture
    def mock_stdin(self):
        """Fixture to mock stdin."""

        def _mock_stdin(content):
            return patch("sys.stdin", StringIO(content))

        return _mock_stdin

    def test_edit_tool_non_python(self, mock_stdin, capsys):
        """Test Edit to non-Python file approves."""
        hook_input = json.dumps(
            {"tool_name": "Edit", "tool_input": {"file_path": "style.css"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_multiedit_tool_non_python(self, mock_stdin, capsys):
        """Test MultiEdit to non-Python file approves."""
        hook_input = json.dumps(
            {"tool_name": "MultiEdit", "tool_input": {"file_path": "data.json"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_tool_input_with_path_key(self, mock_stdin, capsys):
        """Test tool_input with 'path' instead of 'file_path'."""
        hook_input = json.dumps(
            {"tool_name": "Write", "tool_input": {"path": "readme.txt"}}
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_session_id_logged(self, mock_stdin, capsys):
        """Test session_id is processed (even if just logged)."""
        hook_input = json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "test.txt"},
                "session_id": "test-session-123",
            }
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_whitespace_only_stdin(self, mock_stdin, capsys):
        """Test stdin with only whitespace approves."""
        with mock_stdin("   \n\t  "):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out

    def test_nested_json_input(self, mock_stdin, capsys):
        """Test handling of nested JSON in tool_input."""
        hook_input = json.dumps(
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "echo test",
                    "options": {"timeout": 30, "env": {"PATH": "/usr/bin"}},
                },
            }
        )
        with mock_stdin(hook_input):
            with pytest.raises(SystemExit) as exc_info:
                from hooks.post_tool_hook import main

                main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "approve" in captured.out


class TestApproveBlockOutput:
    """Tests for JSON output format of approve/block."""

    def test_approve_json_structure(self, capsys):
        """Test approve outputs valid JSON with correct structure."""
        with pytest.raises(SystemExit):
            approve()

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "decision" in output
        assert output["decision"] == "approve"
        # Should not have reason key
        assert "reason" not in output

    def test_block_json_structure(self, capsys):
        """Test block outputs valid JSON with correct structure."""
        with pytest.raises(SystemExit):
            block("Test reason message")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "decision" in output
        assert "reason" in output
        assert output["decision"] == "block"
        assert output["reason"] == "Test reason message"

    def test_block_empty_reason(self, capsys):
        """Test block with empty reason."""
        with pytest.raises(SystemExit):
            block("")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["reason"] == ""

    def test_block_multiline_reason(self, capsys):
        """Test block with multiline reason."""
        with pytest.raises(SystemExit):
            block("Line 1\nLine 2\nLine 3")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "\n" in output["reason"]

    def test_block_unicode_reason(self, capsys):
        """Test block with unicode in reason."""
        with pytest.raises(SystemExit):
            block("Error: 文件不存在 🚫")

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "文件" in output["reason"]
        assert "🚫" in output["reason"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
