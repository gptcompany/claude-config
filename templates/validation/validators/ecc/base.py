"""
ECC Validator Base Class

Base class for validators ported from ECC (everything-claude-code) agents.
Provides common helpers for running CLI tools and parsing output.

Source: /media/sam/1TB/everything-claude-code/agents/
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Import from parent orchestrator using relative import
# validators/ecc/ -> validators/ -> validation/orchestrator.py
try:
    from ...orchestrator import BaseValidator, ValidationResult, ValidationTier
except ImportError:
    # Fallback for when running standalone or in different contexts
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from orchestrator import (
        BaseValidator,
        ValidationResult,  # noqa: F401
        ValidationTier,
    )

# Re-export for subclasses
__all__ = ["ECCValidatorBase", "ValidationResult", "ValidationTier"]


class ECCValidatorBase(BaseValidator):
    """
    Base class for validators ported from ECC agents.

    ECC agents are markdown prompt files that orchestrate CLI tools.
    This base class provides helpers to run those same tools programmatically.

    Attributes:
        agent: ECC agent name (e.g., "e2e-runner", "security-reviewer")
        timeout: Default timeout in seconds for CLI tool execution

    Example:
        class E2EValidator(ECCValidatorBase):
            dimension = "e2e_validation"
            tier = ValidationTier.BLOCKER
            agent = "e2e-runner"

            async def validate(self) -> ValidationResult:
                result = await self._run_tool(["npx", "playwright", "test"])
                ...
    """

    agent: str = ""  # ECC agent name for reference
    timeout: int = 300  # 5 min default (same as ECC agents)

    async def _run_tool(
        self,
        cmd: list[str],
        *,
        timeout: int | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Run CLI tool with timeout and capture output.

        This is the primary helper for invoking external tools that ECC agents
        would invoke. Handles timeouts, captures stdout/stderr, and returns
        the CompletedProcess for parsing.

        Args:
            cmd: Command and arguments as list (e.g., ["npx", "playwright", "test"])
            timeout: Override default timeout in seconds
            cwd: Working directory for command execution
            env: Additional environment variables

        Returns:
            subprocess.CompletedProcess with stdout, stderr, returncode

        Raises:
            subprocess.TimeoutExpired: If command exceeds timeout
            FileNotFoundError: If command binary not found
        """
        effective_timeout = timeout or self.timeout

        # Run in thread pool to not block async loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=cwd,
                env=env,
            ),
        )

    def _parse_json_output(self, stdout: str) -> dict:
        """
        Parse JSON output from CLI tool.

        Many tools (Playwright, ESLint, bandit) support JSON output.
        This helper handles common parsing with error fallback.

        Args:
            stdout: Raw stdout from CLI tool

        Returns:
            Parsed dict, or empty dict if parsing fails
        """
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {}

    def _format_duration(self, start: datetime) -> int:
        """
        Calculate duration in milliseconds from start time.

        Args:
            start: Start datetime

        Returns:
            Duration in milliseconds
        """
        return int((datetime.now() - start).total_seconds() * 1000)

    def _check_tool_installed(self, cmd: str) -> bool:
        """
        Check if a CLI tool is installed and accessible.

        Args:
            cmd: Command name to check (e.g., "npx", "bandit")

        Returns:
            True if tool is accessible, False otherwise
        """
        try:
            result = subprocess.run(
                ["which", cmd],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _skip_result(self, reason: str) -> ValidationResult:
        """
        Create a skip result when validation cannot run.

        Use this when preconditions aren't met (tool not installed,
        config file missing, etc.).

        Args:
            reason: Human-readable reason for skipping

        Returns:
            ValidationResult with passed=True and skip message
        """
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message=f"{reason} (skipped)",
            details={"skipped": True, "reason": reason},
        )

    def _error_result(self, error: str, duration_ms: int = 0) -> ValidationResult:
        """
        Create an error result when validation fails unexpectedly.

        Args:
            error: Error message
            duration_ms: How long the validation ran before failing

        Returns:
            ValidationResult with passed=False and error details
        """
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=False,
            message=f"Error: {error}",
            details={"error": str(error)},
            agent=self.agent if self.agent else None,
            duration_ms=duration_ms,
        )
