#!/usr/bin/env python3
"""ODiff CLI wrapper for fast pixel-level image comparison with graceful degradation."""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ODiffResult:
    match: bool
    diff_percentage: float
    diff_count: int
    pixel_score: float
    diff_path: str | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ODiffRunner:
    DEFAULT_THRESHOLD = 0.1
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        antialiasing: bool = True,
        ignore_regions: list[dict[str, int]] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.threshold = threshold
        self.antialiasing = antialiasing
        self.ignore_regions = ignore_regions or []
        self.timeout = timeout
        self._odiff_path: str | None = None

    def is_available(self) -> bool:
        if self._odiff_path is not None:
            return bool(self._odiff_path)

        odiff_path = shutil.which("odiff")
        if odiff_path:
            self._odiff_path = odiff_path
            return True

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
        cmd = (
            ["npx", "--yes", "odiff-bin"]
            if self._odiff_path == "npx"
            else [self._odiff_path or "odiff"]
        )
        cmd.extend([baseline, current, diff_output, "--threshold", str(self.threshold)])

        if self.antialiasing:
            cmd.append("--antialiasing")

        for region in self.ignore_regions:
            cmd.extend(
                [
                    "--ignore",
                    f"{region['x1']}:{region['y1']}-{region['x2']}:{region['y2']}",
                ]
            )

        cmd.append("--parsable-stdout")
        return cmd

    def _parse_output(
        self, stdout: str, stderr: str, returncode: int
    ) -> dict[str, Any]:
        result = {"match": returncode == 0, "diffPercentage": 0.0, "diffCount": 0}
        combined = (stdout + "\n" + stderr).strip()

        parsable = re.search(r"^(\d+);([\d.]+)$", combined, re.MULTILINE)
        if parsable:
            result["diffCount"] = int(parsable.group(1))
            result["diffPercentage"] = float(parsable.group(2))
            return result

        human = re.search(
            r"Found\s+(\d+)\s+different\s+pixels?\s+\(([\d.]+)%\)",
            combined,
            re.IGNORECASE,
        )
        if human:
            result["diffCount"] = int(human.group(1))
            result["diffPercentage"] = float(human.group(2))
            return result

        pct = re.search(r"([\d.]+)\s*%", combined)
        if pct:
            result["diffPercentage"] = float(pct.group(1))

        return result

    def compare(self, baseline: str, current: str, diff_output: str) -> ODiffResult:
        baseline_path, current_path = Path(baseline), Path(current)

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

        if not self.is_available():
            return ODiffResult(
                match=False,
                diff_percentage=100.0,
                diff_count=0,
                pixel_score=0.0,
                error="odiff not installed. Install via: npm install -g odiff-bin",
                details={"odiff_available": False},
            )

        Path(diff_output).parent.mkdir(parents=True, exist_ok=True)
        cmd = self._build_command(baseline, current, diff_output)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
            data = self._parse_output(result.stdout, result.stderr, result.returncode)

            match = data.get("match", result.returncode == 0)
            diff_percentage = data.get("diffPercentage", 0.0)
            diff_count = data.get("diffCount", 0)
            pixel_score = max(0.0, min(1.0, 1.0 - (diff_percentage / 100.0)))

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
