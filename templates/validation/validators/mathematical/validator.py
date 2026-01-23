#!/usr/bin/env python3
"""
MathematicalValidator - Tier 3 CAS Formula Validator

Validates LaTeX formulas in code via CAS microservice.
Graceful degradation when CAS unavailable.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .cas_client import CASClient, CASResponse
from .formula_extractor import ExtractedFormula, FormulaExtractor


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


@dataclass
class FormulaValidation:
    """Result of validating a single formula."""

    formula: ExtractedFormula
    cas_response: CASResponse
    valid: bool
    error: str | None = None


class MathematicalValidator(BaseValidator):
    """
    Tier 3: Mathematical formula validator.

    Extracts LaTeX formulas from Python code and validates them
    via the CAS microservice at localhost:8769.

    Graceful degradation:
    - If CAS unavailable: passes with warning
    - If no formulas found: passes (nothing to validate)
    - If httpx not installed: passes with warning
    """

    dimension = "mathematical"
    tier = ValidationTier.MONITOR
    agent = None  # Formulas need human review, not auto-fix

    DEFAULT_CONFIG = {
        "cas_url": "http://localhost:8769",
        "cas_timeout": 30.0,
        "cas_engine": "maxima",
        "scan_patterns": ["**/*.py"],
    }

    def __init__(self, config: dict | None = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.cas_client = CASClient(
            base_url=self.config["cas_url"],
            timeout=self.config["cas_timeout"],
        )
        self.extractor = FormulaExtractor()

    async def validate(self) -> ValidationResult:
        """
        Run mathematical formula validation.

        Process:
        1. Extract formulas from project files
        2. Validate each via CAS client
        3. Return aggregated result

        Graceful degradation ensures this never blocks the pipeline.
        """
        start = datetime.now()
        project_root = Path(".")

        # Extract formulas
        formulas: list[ExtractedFormula] = []
        for pattern in self.config["scan_patterns"]:
            formulas.extend(
                self.extractor.extract_from_directory(project_root, pattern)
            )

        if not formulas:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No formulas found in codebase",
                details={
                    "formulas_found": 0,
                    "cas_available": self.cas_client.is_available(),
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Check CAS availability
        if not self.cas_client.is_available():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,  # Graceful degradation - don't block
                message=f"CAS unavailable, {len(formulas)} formulas skipped",
                details={
                    "formulas_found": len(formulas),
                    "validated": 0,
                    "errors": 0,
                    "cas_available": False,
                    "formulas": [
                        {
                            "latex": f.latex,
                            "file": str(f.file),
                            "line": f.line,
                            "context": f.context,
                        }
                        for f in formulas[:20]  # Limit to first 20
                    ],
                },
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Validate each formula
        validations: list[FormulaValidation] = []
        for formula in formulas:
            response = self.cas_client.validate(
                formula.latex,
                cas=self.config["cas_engine"],
            )
            validations.append(
                FormulaValidation(
                    formula=formula,
                    cas_response=response,
                    valid=response.success,
                    error=response.error,
                )
            )

        # Count results
        valid_count = sum(1 for v in validations if v.valid)
        error_count = len(validations) - valid_count

        # Build error details
        errors = [
            {
                "latex": v.formula.latex,
                "file": str(v.formula.file),
                "line": v.formula.line,
                "context": v.formula.context,
                "error": v.error,
            }
            for v in validations
            if not v.valid
        ]

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        # Tier 3 monitors don't block, but report errors
        passed = True  # Tier 3 always passes (monitors only)
        message = (
            f"{valid_count}/{len(validations)} formulas validated"
            if error_count == 0
            else f"{error_count} formula errors detected"
        )

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=message,
            details={
                "formulas_found": len(formulas),
                "validated": valid_count,
                "errors": error_count,
                "cas_available": True,
                "cas_engine": self.config["cas_engine"],
                "error_details": errors[:10],  # Limit to 10
            },
            fix_suggestion=(
                f"Review formulas: {', '.join(e['latex'][:30] for e in errors[:3])}"
                if errors
                else None
            ),
            duration_ms=duration_ms,
        )

    def close(self):
        """Clean up resources."""
        self.cas_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Export for testing
__all__ = ["MathematicalValidator", "FormulaValidation"]
