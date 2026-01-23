#!/usr/bin/env python3
"""
ODiffRunner - Fast pixel-level image comparison using ODiff CLI.

ODiff is a blazing fast image comparison library using SIMD.
This module wraps the CLI tool for Python usage.

Graceful degradation: Returns match=False with explanatory message
when odiff is not installed or other errors occur.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ODiffResult:
    """Result from ODiff comparison."""

    match: bool
    diff_percentage: float
    diff_count: int
    pixel_score: float  # 1.0 - (diff_percentage / 100.0)
    diff_path: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ODiffRunner:
    """
    Wrapper for ODiff CLI for fast pixel-level image comparison.

    ODiff uses SIMD instructions for 2000+ images/sec comparison.
    Handles anti-aliasing, threshold tolerance, and region masking.

    Usage:
        runner = ODiffRunner(threshold=0.1, antialiasing=True)
        result = runner.compare("baseline.png", "current.png", "diff.png")

        if result.match:
            print("Images match!")
        else:
            print(f"Difference: {result.diff_percentage:.2f}%")
    """

    DEFAULT_THRESHOLD = 0.1  # 10% tolerance
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        antialiasing: bool = True,
        ignore_regions: list[dict[str, int]] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize ODiff runner.

        Args:
            threshold: Pixel difference tolerance (0.0 to 1.0)
            antialiasing: Ignore anti-aliasing differences
            ignore_regions: List of regions to ignore, each with x1, y1, x2, y2
            timeout: Command timeout in seconds
        """
        self.threshold = threshold
        self.antialiasing = antialiasing
        self.ignore_regions = ignore_regions or []
        self.timeout = timeout
        self._odiff_path: str | None = None

    def is_available(self) -> bool:
        """Check if odiff CLI is installed and accessible."""
        if self._odiff_path is not None:
            return bool(self._odiff_path)

        # Try to find odiff in PATH or common locations
        odiff_path = shutil.which("odiff")
        if odiff_path:
            self._odiff_path = odiff_path
            return True

        # Try npx odiff (if installed via npm)
        try:
            result = subprocess.run(
                ["npx", "--yes", "odiff-bin", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self._odiff_path = "npx"
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        self._odiff_path = ""
        return False

    def _build_command(
        self, baseline: str, current: str, diff_output: str
    ) -> list[str]:
        """Build the odiff command with all options."""
        if self._odiff_path == "npx":
            cmd = ["npx", "--yes", "odiff-bin"]
        else:
            cmd = [self._odiff_path or "odiff"]

        cmd.extend([baseline, current, diff_output])

        # Add options
        cmd.extend(["--threshold", str(self.threshold)])

        if self.antialiasing:
            cmd.append("--antialiasing")

        # Add ignore regions (format: x1:y1-x2:y2)
        for region in self.ignore_regions:
            cmd.extend(
                [
                    "--ignore",
                    f"{region['x1']}:{region['y1']}-{region['x2']}:{region['y2']}",
                ]
            )

        # Request parsable stdout for machine-readable output
        cmd.append("--parsable-stdout")

        return cmd

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> dict:
        """
        Parse ODiff output into structured data.

        ODiff output formats:
        - Exit code 0: "Images are identical" (match)
        - Exit code 22: "Found N different pixels (X.XX%)" (mismatch)
        - With --parsable-stdout: "diffCount;diffPercentage" e.g. "10000;100.00"
        """
        import re

        # Default result based on return code
        # 0 = match, 22 = pixel differences found
        result = {
            "match": returncode == 0,
            "diffPercentage": 0.0,
            "diffCount": 0,
        }

        combined_output = (stdout + "\n" + stderr).strip()

        # Try parsable format first: "diffCount;diffPercentage"
        parsable_match = re.search(r"^(\d+);([\d.]+)$", combined_output, re.MULTILINE)
        if parsable_match:
            result["diffCount"] = int(parsable_match.group(1))
            result["diffPercentage"] = float(parsable_match.group(2))
            result["match"] = returncode == 0
            return result

        # Try human-readable format: "Found N different pixels (X.XX%)"
        human_match = re.search(
            r"Found\s+(\d+)\s+different\s+pixels?\s+\(([\d.]+)%\)",
            combined_output,
            re.IGNORECASE,
        )
        if human_match:
            result["diffCount"] = int(human_match.group(1))
            result["diffPercentage"] = float(human_match.group(2))
            result["match"] = returncode == 0
            return result

        # Try extracting just percentage: "X.XX%"
        pct_match = re.search(r"([\d.]+)\s*%", combined_output)
        if pct_match:
            result["diffPercentage"] = float(pct_match.group(1))
            result["match"] = returncode == 0

        return result

    def compare(self, baseline: str, current: str, diff_output: str) -> ODiffResult:
        """
        Compare two images and generate diff output.

        Args:
            baseline: Path to baseline/expected image
            current: Path to current/actual image
            diff_output: Path to save diff visualization

        Returns:
            ODiffResult with match status, scores, and any errors
        """
        # Validate inputs
        baseline_path = Path(baseline)
        current_path = Path(current)
        diff_output_path = Path(diff_output)

        if not baseline_path.exists():
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error=f"Baseline image not found: {baseline}",
            )

        if not current_path.exists():
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error=f"Current image not found: {current}",
            )

        # Check odiff availability
        if not self.is_available():
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error="odiff not installed. Install via: npm install -g odiff-bin",
                details={"odiff_available": False},
            )

        # Ensure diff output directory exists
        diff_output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build and run command
        cmd = self._build_command(baseline, current, diff_output)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Parse output
            data = self._parse_output(result.stdout, result.stderr, result.returncode)

            match = data.get("match", result.returncode == 0)
            diff_percentage = data.get("diffPercentage", 0.0)
            diff_count = data.get("diffCount", 0)

            # Calculate pixel score (1.0 = identical, 0.0 = completely different)
            pixel_score = 1.0 - (diff_percentage / 100.0)
            pixel_score = max(0.0, min(1.0, pixel_score))  # Clamp to [0, 1]

            return ODiffResult(
                match=match,
                diff_percentage=diff_percentage,
                diff_count=diff_count,
                pixel_score=pixel_score,
                diff_path=diff_output if not match else None,
                details={
                    "odiff_available": True,
                    "threshold": self.threshold,
                    "antialiasing": self.antialiasing,
                    "returncode": result.returncode,
                },
            )

        except subprocess.TimeoutExpired:
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error=f"ODiff comparison timed out after {self.timeout}s",
                details={"odiff_available": True, "timeout": True},
            )

        except Exception as e:
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error=f"ODiff comparison failed: {str(e)}",
                details={"odiff_available": True, "exception": str(type(e).__name__)},
            )


__all__ = ["ODiffRunner", "ODiffResult"]
