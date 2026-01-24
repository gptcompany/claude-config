"""
E2E Validator - Playwright E2E testing validation.

Wraps ECC e2e-runner agent patterns for Playwright E2E test execution.
Checks for Playwright config, runs tests, and parses results.

Source: /media/sam/1TB/everything-claude-code/agents/e2e-runner.md
"""

import subprocess
from datetime import datetime
from pathlib import Path

from .base import ECCValidatorBase, ValidationResult, ValidationTier

__all__ = ["E2EValidator"]


class E2EValidator(ECCValidatorBase):
    """
    Playwright E2E test validator.

    Runs Playwright tests via npx and parses JSON output.
    Fails if any non-flaky tests fail. Flaky tests are allowed to pass.

    Tier: BLOCKER (Tier 1) - E2E failures block CI/CD
    Agent: e2e-runner

    Usage:
        validator = E2EValidator(project_path="/path/to/project")
        result = await validator.validate()
    """

    dimension = "e2e_validation"
    tier = ValidationTier.BLOCKER
    agent = "e2e-runner"
    timeout = 300  # 5 minutes for E2E tests

    def __init__(self, project_path: str | Path = "."):
        """
        Initialize E2EValidator.

        Args:
            project_path: Path to project root containing playwright.config.ts
        """
        self.project_path = Path(project_path)

    async def validate(self) -> ValidationResult:
        """
        Run Playwright E2E tests and return validation result.

        Returns:
            ValidationResult with:
            - passed: True if no tests failed (flaky tests allowed)
            - message: Summary of test results
            - details: Dict with total, passed, failed, flaky counts
            - fix_suggestion: Debug command if tests failed
        """
        start = datetime.now()

        # Check if Playwright is configured
        config_patterns = [
            "playwright.config.ts",
            "playwright.config.js",
            "playwright.config.mjs",
        ]
        if not any(
            (self.project_path / pattern).exists() for pattern in config_patterns
        ):
            return self._skip_result("No Playwright config found")

        try:
            # Run Playwright tests with JSON reporter
            result = await self._run_tool(
                ["npx", "playwright", "test", "--reporter=json"],
                cwd=self.project_path,
            )

            # Parse JSON output
            report = self._parse_json_output(result.stdout)

            if not report:
                # If JSON parsing failed, check return code
                if result.returncode == 0:
                    return ValidationResult(
                        dimension=self.dimension,
                        tier=self.tier,
                        passed=True,
                        message="E2E tests passed (no JSON output)",
                        details={
                            "stdout": result.stdout[:500] if result.stdout else ""
                        },
                        duration_ms=self._format_duration(start),
                    )
                else:
                    return ValidationResult(
                        dimension=self.dimension,
                        tier=self.tier,
                        passed=False,
                        message=f"E2E tests failed (exit code {result.returncode})",
                        details={
                            "stdout": result.stdout[:1000] if result.stdout else "",
                            "stderr": result.stderr[:1000] if result.stderr else "",
                        },
                        fix_suggestion="Run: npx playwright test --debug",
                        agent=self.agent,
                        duration_ms=self._format_duration(start),
                    )

            # Extract stats from Playwright JSON report
            stats = report.get("stats", {})
            passed = stats.get("expected", 0)
            failed = stats.get("unexpected", 0)
            flaky = stats.get("flaky", 0)
            skipped = stats.get("skipped", 0)
            total = passed + failed + flaky

            duration_s = stats.get("duration", 0) / 1000 if stats.get("duration") else 0
            is_passed = failed == 0

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=is_passed,
                message=f"E2E: {passed}/{total} passed, {failed} failed, {flaky} flaky",
                details={
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "flaky": flaky,
                    "skipped": skipped,
                    "duration_s": duration_s,
                },
                fix_suggestion="Run: npx playwright test --debug"
                if not is_passed
                else None,
                agent=self.agent if not is_passed else None,
                duration_ms=self._format_duration(start),
            )

        except FileNotFoundError:
            return self._skip_result("npx/Playwright not installed")

        except subprocess.TimeoutExpired:
            return self._error_result(
                f"E2E tests timed out ({self.timeout}s)",
                duration_ms=self._format_duration(start),
            )

        except Exception as e:
            return self._error_result(str(e), duration_ms=self._format_duration(start))
