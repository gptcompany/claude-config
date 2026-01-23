#!/usr/bin/env python3
"""
Oasdiff Runner - Wrapper for oasdiff CLI.

Detects breaking changes between OpenAPI specs.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BreakingChange:
    """A single breaking change detected by oasdiff."""

    level: str  # ERR, WARN, INFO
    code: str  # e.g., PATH_ITEM_DELETED
    path: str  # API path affected
    message: str = ""


@dataclass
class OasdiffResult:
    """Result from oasdiff comparison."""

    success: bool
    has_breaking_changes: bool
    changes: list[BreakingChange] = field(default_factory=list)
    error: str | None = None
    oasdiff_available: bool = True
    raw_output: str = ""


class OasdiffRunner:
    """
    Wrapper for oasdiff CLI tool.

    Usage:
        runner = OasdiffRunner()
        if runner.is_available():
            result = runner.breaking_changes(base_spec, revision_spec)
            if result.has_breaking_changes:
                for change in result.changes:
                    print(f"{change.level}: {change.code} - {change.path}")
    """

    DEFAULT_BINARY = "oasdiff"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        binary: str = DEFAULT_BINARY,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.binary = binary
        self.timeout = timeout
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if oasdiff binary is available."""
        if self._available is not None:
            return self._available

        # Check with shutil.which first
        if shutil.which(self.binary):
            self._available = True
            return True

        # Try running --version
        try:
            result = subprocess.run(
                [self.binary, "--version"],
                capture_output=True,
                timeout=5,
            )
            self._available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False

        return self._available

    def breaking_changes(
        self,
        base_spec: Path,
        revision_spec: Path,
    ) -> OasdiffResult:
        """
        Detect breaking changes between two OpenAPI specs.

        Args:
            base_spec: Path to the baseline/original spec
            revision_spec: Path to the current/revised spec

        Returns:
            OasdiffResult with breaking changes list
        """
        if not self.is_available():
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error="oasdiff not installed",
                oasdiff_available=False,
            )

        if not base_spec.exists():
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error=f"Base spec not found: {base_spec}",
            )

        if not revision_spec.exists():
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error=f"Revision spec not found: {revision_spec}",
            )

        try:
            result = subprocess.run(
                [
                    self.binary,
                    "breaking",
                    str(base_spec),
                    str(revision_spec),
                    "-f",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Return code 0 = no breaking changes
            # Return code 1 = breaking changes found
            # Return code 2+ = error
            if result.returncode == 0:
                return OasdiffResult(
                    success=True,
                    has_breaking_changes=False,
                    raw_output=result.stdout,
                )

            if result.returncode == 1:
                # Parse breaking changes from JSON output
                changes = self._parse_breaking_changes(result.stdout)
                return OasdiffResult(
                    success=True,
                    has_breaking_changes=True,
                    changes=changes,
                    raw_output=result.stdout,
                )

            # Error case
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error=result.stderr or f"oasdiff exit code {result.returncode}",
                raw_output=result.stdout + result.stderr,
            )

        except subprocess.TimeoutExpired:
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error=f"oasdiff timeout ({self.timeout}s)",
            )
        except FileNotFoundError:
            self._available = False
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error="oasdiff not found",
                oasdiff_available=False,
            )
        except Exception as e:
            return OasdiffResult(
                success=False,
                has_breaking_changes=False,
                error=str(e),
            )

    def diff(self, base_spec: Path, revision_spec: Path) -> dict:
        """
        Get full diff between two specs (not just breaking changes).

        Args:
            base_spec: Path to the baseline/original spec
            revision_spec: Path to the current/revised spec

        Returns:
            Dict with diff information or error
        """
        if not self.is_available():
            return {"error": "oasdiff not installed", "oasdiff_available": False}

        try:
            result = subprocess.run(
                [
                    self.binary,
                    "diff",
                    str(base_spec),
                    str(revision_spec),
                    "-f",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.stdout:
                return json.loads(result.stdout)
            return {"changes": [], "raw_output": result.stderr}

        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            return {"error": str(e)}

    def _parse_breaking_changes(self, output: str) -> list[BreakingChange]:
        """Parse JSON output from oasdiff breaking."""
        changes: list[BreakingChange] = []

        if not output.strip():
            return changes

        try:
            data = json.loads(output)

            # oasdiff returns different formats depending on version
            # Try common formats
            if isinstance(data, dict):
                # Format: {"messages": [...]}
                messages = data.get("messages", [])
                if not messages:
                    # Format: {"breaking-changes": [...]}
                    messages = data.get("breaking-changes", [])

                for msg in messages:
                    changes.append(
                        BreakingChange(
                            level=msg.get("level", "ERR"),
                            code=msg.get("code", msg.get("id", "UNKNOWN")),
                            path=msg.get("path", msg.get("api-path", "")),
                            message=msg.get("message", msg.get("text", "")),
                        )
                    )

            elif isinstance(data, list):
                # Format: [{"level": ..., "code": ...}, ...]
                for item in data:
                    changes.append(
                        BreakingChange(
                            level=item.get("level", "ERR"),
                            code=item.get("code", item.get("id", "UNKNOWN")),
                            path=item.get("path", item.get("api-path", "")),
                            message=item.get("message", item.get("text", "")),
                        )
                    )

        except json.JSONDecodeError:
            # If JSON parsing fails, return empty
            pass

        return changes


# Export for testing
__all__ = ["OasdiffRunner", "OasdiffResult", "BreakingChange"]
