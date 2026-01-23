#!/usr/bin/env python3
"""
APIContractValidator - Tier 3 OpenAPI Contract Validator

Detects breaking changes in OpenAPI specs via oasdiff.
Graceful degradation when oasdiff not installed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .oasdiff_runner import OasdiffRunner
from .spec_discovery import SpecDiscovery


# Import base types (with fallback for standalone testing)
class ValidationTier(Enum):
    BLOCKER = 1
    WARNING = 2
    MONITOR = 3


@dataclass
class ValidationResult:
    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0


class BaseValidator:
    dimension = "unknown"
    tier = ValidationTier.MONITOR
    agent = None

    async def validate(self) -> ValidationResult:
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


class APIContractValidator(BaseValidator):
    """
    Tier 3: API contract validator.

    Detects breaking changes in OpenAPI specs by comparing
    current spec against a baseline version.

    Graceful degradation:
    - If oasdiff not installed: passes with warning
    - If no specs found: passes (nothing to validate)
    - If no baseline configured: passes (no comparison possible)
    """

    dimension = "api_contract"
    tier = ValidationTier.MONITOR
    agent = None  # Contract changes need human review, not auto-fix

    DEFAULT_CONFIG = {
        "oasdiff_binary": "oasdiff",
        "oasdiff_timeout": 30,
        "baseline_spec": None,  # Path to baseline spec for comparison
        "spec_paths": [],  # Additional paths to check
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.runner = OasdiffRunner(
            binary=self.config["oasdiff_binary"],
            timeout=self.config["oasdiff_timeout"],
        )
        self.discovery = SpecDiscovery(custom_paths=self.config["spec_paths"])

    async def validate(self) -> ValidationResult:
        """
        Run API contract validation.

        Process:
        1. Find OpenAPI specs in project
        2. Check for oasdiff availability
        3. If baseline configured, compare for breaking changes
        4. Return result (Tier 3 never blocks)
        """
        start = datetime.now()
        project_root = Path(".")

        # Find specs
        specs = self.discovery.find_specs(project_root)

        if not specs:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No OpenAPI specs found",
                details={
                    "specs_found": 0,
                    "oasdiff_available": self.runner.is_available(),
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Check oasdiff availability
        if not self.runner.is_available():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Graceful degradation
                message=f"oasdiff not installed, {len(specs)} specs found",
                details={
                    "specs_found": len(specs),
                    "specs": [str(s) for s in specs],
                    "oasdiff_available": False,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Check for baseline
        baseline = self.discovery.find_baseline(project_root, self.config)

        if not baseline:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message=f"{len(specs)} specs found, no baseline configured",
                details={
                    "specs_found": len(specs),
                    "specs": [str(s) for s in specs],
                    "oasdiff_available": True,
                    "baseline_configured": False,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Compare first spec against baseline
        # (In production, might want to support multiple spec comparisons)
        current_spec = specs[0]
        result = self.runner.breaking_changes(baseline, current_spec)

        if not result.success:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Tier 3 never blocks
                message=f"oasdiff error: {result.error}",
                details={
                    "specs_found": len(specs),
                    "oasdiff_available": result.oasdiff_available,
                    "error": result.error,
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        if result.has_breaking_changes:
            # Group changes by level
            by_level: dict[str, int] = {}
            for change in result.changes:
                by_level[change.level] = by_level.get(change.level, 0) + 1

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Tier 3 never blocks
                message=f"{len(result.changes)} breaking changes detected",
                details={
                    "specs_found": len(specs),
                    "oasdiff_available": True,
                    "baseline": str(baseline),
                    "current_spec": str(current_spec),
                    "breaking_changes_count": len(result.changes),
                    "by_level": by_level,
                    "breaking_changes": [
                        {
                            "level": c.level,
                            "code": c.code,
                            "path": c.path,
                            "message": c.message,
                        }
                        for c in result.changes[:20]  # Limit to 20
                    ],
                },
                fix_suggestion=(
                    f"Review breaking changes: {', '.join(c.code for c in result.changes[:3])}"
                ),
                duration_ms=duration_ms,
            )

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No breaking changes detected",
            details={
                "specs_found": len(specs),
                "oasdiff_available": True,
                "baseline": str(baseline),
                "current_spec": str(current_spec),
                "breaking_changes_count": 0,
            },
            duration_ms=duration_ms,
        )


# Export for testing
__all__ = ["APIContractValidator"]
