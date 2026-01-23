#!/usr/bin/env python3
"""
Ralph Loop - Iterative Validation State Machine

Runs validation in a loop until quality threshold is met or blocked.

State machine:
  IDLE -> VALIDATING -> (BLOCKED | COMPLETE)

  - Tier 1 blocks immediately on failure
  - Tier 2+3 run in parallel (informational)
  - Loop continues if score < threshold (up to max iterations)

Usage:
  python3 ralph_loop.py --files "file1.py,file2.py" --project myproject
  python3 ralph_loop.py --files "file1.py" --json
  echo "file1.py,file2.py" | python3 ralph_loop.py --project myproject
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# =============================================================================
# Logging
# =============================================================================

LOG_DIR = Path.home() / ".claude" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "ralph_loop", "message": "%(message)s"}',
    handlers=[
        logging.FileHandler(LOG_DIR / "ralph-loop.log"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class LoopState(Enum):
    """Ralph loop state machine states."""

    IDLE = "idle"
    VALIDATING = "validating"
    BLOCKED = "blocked"
    FIX_REQUESTED = "fix_requested"
    COMPLETE = "complete"


@dataclass
class RalphLoopConfig:
    """Configuration for Ralph loop behavior."""

    max_iterations: int = 5
    min_score_threshold: float = 70.0
    tier1_timeout_seconds: float = 30.0
    tier2_timeout_seconds: float = 120.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RalphLoopConfig":
        """Create config from dict."""
        return cls(
            max_iterations=data.get("max_iterations", 5),
            min_score_threshold=data.get("min_score_threshold", 70.0),
            tier1_timeout_seconds=data.get("tier1_timeout_seconds", 30.0),
            tier2_timeout_seconds=data.get("tier2_timeout_seconds", 120.0),
        )

    @classmethod
    def from_file(cls, path: Path) -> "RalphLoopConfig":
        """Load config from JSON file."""
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            return cls.from_dict(data.get("ralph_loop", data))
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
            return cls()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "max_iterations": self.max_iterations,
            "min_score_threshold": self.min_score_threshold,
            "tier1_timeout_seconds": self.tier1_timeout_seconds,
            "tier2_timeout_seconds": self.tier2_timeout_seconds,
        }


@dataclass
class IterationHistory:
    """Record of a single iteration in the loop."""

    iteration: int
    score: float
    tier1_passed: bool
    tier2_warnings: int = 0
    tier3_monitors: int = 0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LoopResult:
    """Final result from Ralph loop execution."""

    state: LoopState
    iteration: int
    score: float | None
    blockers: list[str]
    message: str
    history: list[IterationHistory] = field(default_factory=list)
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "state": self.state.value,
            "iteration": self.iteration,
            "score": self.score,
            "blockers": self.blockers,
            "message": self.message,
            "execution_time_ms": self.execution_time_ms,
            "history": [
                {
                    "iteration": h.iteration,
                    "score": h.score,
                    "tier1_passed": h.tier1_passed,
                    "tier2_warnings": h.tier2_warnings,
                    "tier3_monitors": h.tier3_monitors,
                    "duration_ms": h.duration_ms,
                    "timestamp": h.timestamp,
                }
                for h in self.history
            ],
        }


# =============================================================================
# Integration imports (optional)
# =============================================================================

try:
    from integrations.metrics import push_validation_metrics, METRICS_AVAILABLE
except ImportError:
    METRICS_AVAILABLE = False

    def push_validation_metrics(*args, **kwargs):
        pass


try:
    from integrations.sentry_context import (
        inject_validation_context,
        add_validation_breadcrumb,
        SENTRY_AVAILABLE,
    )
except ImportError:
    SENTRY_AVAILABLE = False

    def inject_validation_context(*args, **kwargs):
        pass

    def add_validation_breadcrumb(*args, **kwargs):
        pass


# =============================================================================
# Ralph Loop
# =============================================================================


class RalphLoop:
    """
    Iterative validation loop with state machine.

    Runs validation tiers until quality threshold is met or blocked.

    Usage:
        orchestrator = ValidationOrchestrator()
        loop = RalphLoop(orchestrator, RalphLoopConfig())
        result = await loop.run(["file1.py", "file2.py"])

        if result.state == LoopState.BLOCKED:
            print(f"Blocked: {result.blockers}")
        elif result.state == LoopState.COMPLETE:
            print(f"Complete with score: {result.score}")
    """

    def __init__(self, orchestrator: Any, config: RalphLoopConfig):
        """
        Initialize Ralph loop.

        Args:
            orchestrator: ValidationOrchestrator instance
            config: Loop configuration
        """
        self.orchestrator = orchestrator
        self.config = config
        self.state = LoopState.IDLE
        self.iteration = 0
        self.history: list[IterationHistory] = []
        self.project_name = "unknown"

    def _get_project_name(self) -> str:
        """Get project name from git or fallback to cwd."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip()).name
        except Exception:
            pass
        return Path.cwd().name

    def _calculate_score(
        self,
        tier1_result: Any,
        tier2_result: Any,
        tier3_result: Any,
    ) -> float:
        """
        Calculate combined validation score.

        Weights:
        - Tier 1 (blockers): 50%
        - Tier 2 (warnings): 30%
        - Tier 3 (monitors): 20%
        """

        def tier_score(tier_result: Any) -> float:
            if not hasattr(tier_result, "results") or not tier_result.results:
                return 100.0
            passed = sum(1 for r in tier_result.results if r.passed)
            total = len(tier_result.results)
            return (passed / total * 100) if total > 0 else 100.0

        t1_score = tier_score(tier1_result)
        t2_score = tier_score(tier2_result)
        t3_score = tier_score(tier3_result)

        # Weighted average
        return t1_score * 0.5 + t2_score * 0.3 + t3_score * 0.2

    async def run(self, changed_files: list[str]) -> LoopResult:
        """
        Run validation loop until quality threshold met or blocked.

        Args:
            changed_files: List of file paths to validate

        Returns:
            LoopResult with final state, score, and history
        """
        start_time = datetime.now()
        self.state = LoopState.VALIDATING
        self.iteration = 0
        self.history = []
        self.project_name = self._get_project_name()

        logger.info(
            f"Starting Ralph loop for {len(changed_files)} files "
            f"(max_iterations={self.config.max_iterations}, "
            f"threshold={self.config.min_score_threshold})"
        )

        combined_score = 0.0

        while self.iteration < self.config.max_iterations:
            self.iteration += 1
            iteration_start = datetime.now()

            logger.info(f"Iteration {self.iteration}/{self.config.max_iterations}")

            # Phase 1: Tier 1 blockers (fail-fast)
            try:
                tier1_result = await asyncio.wait_for(
                    self.orchestrator.run_tier(
                        self.orchestrator.validators[
                            next(iter(self.orchestrator.validators))
                        ].tier.__class__(1)
                    ),
                    timeout=self.config.tier1_timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Tier 1 timeout after {self.config.tier1_timeout_seconds}s"
                )
                self.state = LoopState.BLOCKED
                return LoopResult(
                    state=self.state,
                    iteration=self.iteration,
                    score=None,
                    blockers=["Tier 1 timeout"],
                    message=f"Tier 1 timed out after {self.config.tier1_timeout_seconds}s",
                    history=self.history,
                    execution_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

            # Push metrics and inject context after Tier 1
            push_validation_metrics(tier1_result, self.project_name)
            inject_validation_context(tier1_result)

            # Check for blockers
            if not tier1_result.passed:
                self.state = LoopState.BLOCKED
                blockers = tier1_result.failed_dimensions

                add_validation_breadcrumb(
                    message=f"Blocked at iteration {self.iteration}: {blockers}",
                    level="error",
                    data={"blockers": blockers, "iteration": self.iteration},
                )

                logger.warning(f"Tier 1 blockers found: {blockers}")

                return LoopResult(
                    state=self.state,
                    iteration=self.iteration,
                    score=None,
                    blockers=blockers,
                    message=f"Tier 1 blockers - fix required: {', '.join(blockers)}",
                    history=self.history,
                    execution_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

            logger.info("Tier 1 passed - running Tier 2+3 in parallel")

            # Phase 2: Tier 2+3 in parallel (informational)
            try:
                tier2_result, tier3_result = await asyncio.gather(
                    asyncio.wait_for(
                        self.orchestrator.run_tier(
                            self.orchestrator.validators[
                                next(iter(self.orchestrator.validators))
                            ].tier.__class__(2)
                        ),
                        timeout=self.config.tier2_timeout_seconds,
                    ),
                    asyncio.wait_for(
                        self.orchestrator.run_tier(
                            self.orchestrator.validators[
                                next(iter(self.orchestrator.validators))
                            ].tier.__class__(3)
                        ),
                        timeout=self.config.tier2_timeout_seconds,
                    ),
                    return_exceptions=True,
                )

                # Handle timeout exceptions
                if isinstance(tier2_result, Exception):
                    logger.warning(f"Tier 2 error: {tier2_result}")
                    tier2_result = _create_empty_tier_result(2)
                if isinstance(tier3_result, Exception):
                    logger.warning(f"Tier 3 error: {tier3_result}")
                    tier3_result = _create_empty_tier_result(3)

            except Exception as e:
                logger.error(f"Error running Tier 2+3: {e}")
                tier2_result = _create_empty_tier_result(2)
                tier3_result = _create_empty_tier_result(3)

            # Push metrics for Tier 2 and 3
            push_validation_metrics(tier2_result, self.project_name)
            push_validation_metrics(tier3_result, self.project_name)
            inject_validation_context(tier2_result)
            inject_validation_context(tier3_result)

            # Calculate combined score
            combined_score = self._calculate_score(
                tier1_result, tier2_result, tier3_result
            )

            # Record iteration history
            iteration_duration = int(
                (datetime.now() - iteration_start).total_seconds() * 1000
            )
            self.history.append(
                IterationHistory(
                    iteration=self.iteration,
                    score=combined_score,
                    tier1_passed=tier1_result.passed,
                    tier2_warnings=len(
                        [r for r in tier2_result.results if not r.passed]
                    )
                    if hasattr(tier2_result, "results")
                    else 0,
                    tier3_monitors=len(tier3_result.results)
                    if hasattr(tier3_result, "results")
                    else 0,
                    duration_ms=iteration_duration,
                )
            )

            logger.info(
                f"Iteration {self.iteration} complete: score={combined_score:.1f}"
            )

            # Check if threshold met
            if combined_score >= self.config.min_score_threshold:
                self.state = LoopState.COMPLETE

                add_validation_breadcrumb(
                    message=f"Validation complete: score {combined_score:.1f}",
                    level="info",
                    data={"score": combined_score, "iteration": self.iteration},
                )

                return LoopResult(
                    state=self.state,
                    iteration=self.iteration,
                    score=combined_score,
                    blockers=[],
                    message=f"Validation passed (score: {combined_score:.1f})",
                    history=self.history,
                    execution_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                )

            # Log that we're continuing
            logger.info(
                f"Score {combined_score:.1f} < threshold {self.config.min_score_threshold}, "
                f"continuing..."
            )

        # Max iterations reached
        self.state = LoopState.COMPLETE

        add_validation_breadcrumb(
            message=f"Max iterations reached: score {combined_score:.1f}",
            level="warning",
            data={
                "score": combined_score,
                "max_iterations": self.config.max_iterations,
            },
        )

        return LoopResult(
            state=self.state,
            iteration=self.iteration,
            score=combined_score,
            blockers=[],
            message=f"Max iterations ({self.config.max_iterations}) reached, score: {combined_score:.1f}",
            history=self.history,
            execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
        )


def _create_empty_tier_result(tier: int) -> Any:
    """Create an empty tier result for error cases."""
    # Import here to avoid circular imports
    try:
        from orchestrator import TierResult, ValidationTier

        return TierResult(tier=ValidationTier(tier), results=[])
    except ImportError:
        # Fallback: create a simple object
        class EmptyTierResult:
            def __init__(self, tier_value: int):
                self.tier = type("Tier", (), {"value": tier_value})()
                self.results = []
                self.passed = True
                self.failed_dimensions = []

        return EmptyTierResult(tier)


# =============================================================================
# CLI
# =============================================================================


def _get_project_from_git() -> str:
    """Auto-detect project name from git."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    return Path.cwd().name


def parse_files(files_arg: str | None) -> list[str]:
    """Parse files from argument or stdin."""
    if files_arg:
        # Comma-separated or space-separated
        files = []
        for f in files_arg.replace(",", " ").split():
            f = f.strip()
            if f:
                files.append(f)
        return files

    # Read from stdin if not a tty
    if not sys.stdin.isatty():
        content = sys.stdin.read().strip()
        files = []
        for f in content.replace(",", " ").replace("\n", " ").split():
            f = f.strip()
            if f:
                files.append(f)
        return files

    return []


async def async_main():
    """Async CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ralph Loop - Iterative validation state machine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ralph_loop.py --files "file1.py,file2.py" --project myproject
  python3 ralph_loop.py --files "file1.py" --json
  echo "file1.py,file2.py" | python3 ralph_loop.py --project myproject

Config file format (JSON):
  {
    "ralph_loop": {
      "max_iterations": 5,
      "min_score_threshold": 70.0,
      "tier1_timeout_seconds": 30.0,
      "tier2_timeout_seconds": 120.0
    }
  }
""",
    )
    parser.add_argument(
        "--files",
        "-f",
        help="Comma-separated list of files to validate (or read from stdin)",
    )
    parser.add_argument(
        "--project",
        "-p",
        help="Project name (default: auto-detect from git)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        help="Path to config file (JSON)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        help="Override max iterations from config",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        help="Override min score threshold from config",
    )

    args = parser.parse_args()

    # Parse files
    files = parse_files(args.files)
    if not files:
        if args.json:
            print(json.dumps({"error": "No files specified", "state": "idle"}))
        else:
            parser.print_help()
            print("\nError: No files specified. Use --files or pipe to stdin.")
        sys.exit(1)

    # Load config
    config = RalphLoopConfig()
    if args.config:
        config = RalphLoopConfig.from_file(args.config)

    # Apply CLI overrides
    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations
    if args.threshold is not None:
        config.min_score_threshold = args.threshold

    # Get project name
    project = args.project or _get_project_from_git()

    # Import orchestrator
    try:
        from orchestrator import ValidationOrchestrator

        orchestrator = ValidationOrchestrator()
    except ImportError as e:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": f"Failed to import orchestrator: {e}",
                        "state": "idle",
                    }
                )
            )
        else:
            print(f"Error: Failed to import orchestrator: {e}")
            print("Make sure you're running from the validation templates directory.")
        sys.exit(1)

    # Run loop
    loop = RalphLoop(orchestrator, config)
    loop.project_name = project

    result = await loop.run(files)

    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'=' * 60}")
        print("RALPH LOOP RESULT")
        print(f"{'=' * 60}")
        print(f"State:       {result.state.value}")
        print(f"Iterations:  {result.iteration}")
        print(f"Score:       {result.score:.1f if result.score else 'N/A'}")
        print(f"Duration:    {result.execution_time_ms}ms")

        if result.blockers:
            print(f"Blockers:    {', '.join(result.blockers)}")

        print(f"\nMessage: {result.message}")

        if result.history:
            print(f"\n{'=' * 60}")
            print("HISTORY")
            print(f"{'=' * 60}")
            for h in result.history:
                print(
                    f"  Iteration {h.iteration}: score={h.score:.1f}, "
                    f"t1={'PASS' if h.tier1_passed else 'FAIL'}, "
                    f"t2_warnings={h.tier2_warnings}, "
                    f"duration={h.duration_ms}ms"
                )

    # Exit code
    if result.state == LoopState.BLOCKED:
        sys.exit(1)
    elif result.score and result.score < config.min_score_threshold:
        sys.exit(2)  # Threshold not met but not blocked
    else:
        sys.exit(0)


def main():
    """Sync wrapper for CLI."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
