"""
Eval Validator - pass@k metrics monitoring.

Checks for eval results in .claude/evals/ directory and extracts
pass@k metrics for Grafana integration.

Source: /media/sam/1TB/everything-claude-code/skills/eval-harness/
"""

import json
from datetime import datetime
from pathlib import Path

from .base import ECCValidatorBase, ValidationResult, ValidationTier

__all__ = ["EvalValidator"]


class EvalValidator(ECCValidatorBase):
    """
    Eval metrics monitor.

    Checks for .claude/evals/ directory with eval results.
    Extracts pass@k metrics for monitoring dashboards.

    Tier: MONITOR (Tier 3) - Metrics only, never fails
    Agent: eval-harness

    Metrics emitted:
    - pass_at_1: Pass@1 success rate
    - pass_at_5: Pass@5 success rate (if available)
    - pass_at_10: Pass@10 success rate (if available)
    - total_evals: Total number of evaluations
    """

    dimension = "eval_metrics"
    tier = ValidationTier.MONITOR
    agent = "eval-harness"
    timeout = 30  # Reading JSON is fast

    def __init__(self, project_path: str | Path = "."):
        """
        Initialize EvalValidator.

        Args:
            project_path: Path to project root
        """
        self.project_path = Path(project_path)

    async def validate(self) -> ValidationResult:
        """
        Read eval results and emit pass@k metrics.

        Always passes (Tier 3 monitoring only).

        Returns:
            ValidationResult with:
            - passed: Always True (monitoring tier)
            - message: Summary of eval metrics
            - details: Dict with pass@k values
        """
        start = datetime.now()

        # Check for evals directory
        evals_dir = self.project_path / ".claude" / "evals"

        if not evals_dir.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Always pass for monitoring
                message="No evals directory (monitoring skipped)",
                details={"has_evals": False},
                duration_ms=self._format_duration(start),
            )

        # Find latest eval results
        results = self._find_eval_results(evals_dir)

        if not results:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No eval results found",
                details={"has_evals": True, "results_found": 0},
                duration_ms=self._format_duration(start),
            )

        # Parse metrics from results
        metrics = self._extract_metrics(results)

        message = self._format_metrics_message(metrics)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,  # Always pass for monitoring
            message=message,
            details=metrics,
            duration_ms=self._format_duration(start),
        )

    def _find_eval_results(self, evals_dir: Path) -> list[dict]:
        """
        Find and load eval result files.

        Looks for JSON files in evals directory and returns
        the most recent results.
        """
        results = []
        seen_files: set[Path] = set()

        # Common eval result file patterns
        patterns = ["*.json", "results*.json", "eval*.json"]

        for pattern in patterns:
            for json_file in evals_dir.glob(pattern):
                if json_file in seen_files:
                    continue
                seen_files.add(json_file)
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            data["_source_file"] = str(json_file)
                            results.append(data)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    item["_source_file"] = str(json_file)
                                    results.append(item)
                except (json.JSONDecodeError, IOError):
                    continue

        return results

    def _extract_metrics(self, results: list[dict]) -> dict:
        """
        Extract pass@k metrics from eval results.

        Looks for common metric field names:
        - pass_at_k, pass@k, passAtK
        - success_rate, accuracy
        - passed/total counts
        """
        metrics: dict = {
            "total_evals": len(results),
            "pass_at_1": None,
            "pass_at_5": None,
            "pass_at_10": None,
        }

        # Aggregate pass@k from all results
        pass_counts = {"1": 0, "5": 0, "10": 0}
        total_counts = {"1": 0, "5": 0, "10": 0}

        for result in results:
            # Try to extract pass@k values
            for k in ["1", "5", "10"]:
                # Common field patterns
                patterns = [
                    f"pass_at_{k}",
                    f"pass@{k}",
                    f"passAt{k}",
                    f"pass_{k}",
                ]

                for pattern in patterns:
                    if pattern in result:
                        value = result[pattern]
                        if isinstance(value, (int, float)):
                            if 0 <= value <= 1:
                                # It's a ratio
                                pass_counts[k] += value
                                total_counts[k] += 1
                            elif value > 1:
                                # It's a count, need total
                                total = result.get("total", result.get("n_samples", 1))
                                pass_counts[k] += value / total if total else 0
                                total_counts[k] += 1
                        break

            # Also check for passed/total structure
            if "passed" in result and "total" in result:
                passed = result["passed"]
                total = result["total"]
                if total > 0:
                    pass_counts["1"] += passed / total
                    total_counts["1"] += 1

        # Calculate averages
        for k in ["1", "5", "10"]:
            if total_counts[k] > 0:
                metrics[f"pass_at_{k}"] = round(pass_counts[k] / total_counts[k], 3)

        return metrics

    def _format_metrics_message(self, metrics: dict) -> str:
        """
        Format metrics as a readable message.
        """
        parts = [f"Evals: {metrics['total_evals']} results"]

        if metrics.get("pass_at_1") is not None:
            parts.append(f"pass@1={metrics['pass_at_1']:.0%}")

        if metrics.get("pass_at_5") is not None:
            parts.append(f"pass@5={metrics['pass_at_5']:.0%}")

        if metrics.get("pass_at_10") is not None:
            parts.append(f"pass@10={metrics['pass_at_10']:.0%}")

        return ", ".join(parts)
