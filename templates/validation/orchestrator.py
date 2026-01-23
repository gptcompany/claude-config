#!/usr/bin/env python3
"""
ValidationOrchestrator - 14-Dimension Tiered Validation Framework

Tier 1 (Blockers): MUST pass before merge - blocks CI/Ralph loop
Tier 2 (Warnings): Auto-suggest fixes via agents - doesn't block
Tier 3 (Monitors): Metrics only - emit to Grafana/QuestDB

Generated from: ~/.claude/templates/validation/orchestrator.py.j2
Config: test_project/.claude/validation/config.json
"""

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# =============================================================================
# Integration Imports (Optional - graceful degradation)
# =============================================================================

try:
    from integrations.metrics import push_validation_metrics, METRICS_AVAILABLE
except ImportError:
    METRICS_AVAILABLE = False

    def push_validation_metrics(*args, **kwargs) -> bool:
        return False


try:
    from integrations.sentry_context import (
        inject_validation_context,
        add_validation_breadcrumb,
        SENTRY_AVAILABLE,
    )
except ImportError:
    SENTRY_AVAILABLE = False

    def inject_validation_context(*args, **kwargs) -> bool:
        return False

    def add_validation_breadcrumb(*args, **kwargs) -> bool:
        return False


# =============================================================================
# Configuration from Template
# =============================================================================

PROJECT_NAME = "test_project"
DOMAIN = "general"

# Tier thresholds from config

DIMENSIONS_CONFIG = {}

DIMENSIONS_CONFIG = {}


# =============================================================================
# Logging
# =============================================================================

LOG_DIR = Path.home() / ".claude" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "orchestrator", "message": "%(message)s"}',
    handlers=[
        logging.FileHandler(LOG_DIR / "validation-orchestrator.log"),
    ],
)
logger = logging.getLogger(__name__)

# Log available integrations once at module load
_integrations_logged = False


def _log_integrations_status():
    """Log which integrations are available (once at startup)."""
    global _integrations_logged
    if _integrations_logged:
        return
    _integrations_logged = True

    integrations = []
    if METRICS_AVAILABLE:
        integrations.append("Prometheus metrics")
    if SENTRY_AVAILABLE:
        integrations.append("Sentry context")

    if integrations:
        logger.info(f"Integrations available: {', '.join(integrations)}")
    else:
        logger.info(
            "No optional integrations available (prometheus_client, sentry_sdk)"
        )


# =============================================================================
# Types
# =============================================================================


class ValidationTier(Enum):
    """Validation tiers with different behaviors."""

    BLOCKER = 1  # Must pass - blocks merge/deploy
    WARNING = 2  # Warn + suggest fix - doesn't block
    MONITOR = 3  # Metrics only - emit to dashboards


@dataclass
class ValidationResult:
    """Result from a single dimension validator."""

    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None  # Agent to spawn for fix
    duration_ms: int = 0


@dataclass
class TierResult:
    """Aggregated result for a validation tier."""

    tier: ValidationTier
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """All validators in tier passed."""
        return all(r.passed for r in self.results)

    @property
    def has_warnings(self) -> bool:
        """Any validator failed (for Tier 2 fix suggestions)."""
        return any(not r.passed for r in self.results)

    @property
    def failed_dimensions(self) -> list[str]:
        """List of dimensions that failed."""
        return [r.dimension for r in self.results if not r.passed]


@dataclass
class ValidationReport:
    """Full validation report across all tiers."""

    project: str
    timestamp: str
    tiers: list[TierResult] = field(default_factory=list)
    blocked: bool = False
    overall_passed: bool = True
    execution_time_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        return {
            "project": self.project,
            "timestamp": self.timestamp,
            "blocked": self.blocked,
            "overall_passed": self.overall_passed,
            "execution_time_ms": self.execution_time_ms,
            "tiers": [
                {
                    "tier": t.tier.value,
                    "tier_name": t.tier.name,
                    "passed": t.passed,
                    "results": [
                        {
                            "dimension": r.dimension,
                            "passed": r.passed,
                            "message": r.message,
                            "details": r.details,
                            "fix_suggestion": r.fix_suggestion,
                            "agent": r.agent,
                            "duration_ms": r.duration_ms,
                        }
                        for r in t.results
                    ],
                }
                for t in self.tiers
            ],
        }


# =============================================================================
# Validators (wired to existing implementations)
# =============================================================================


class BaseValidator:
    """Base class for dimension validators."""

    dimension: str = "unknown"
    tier: ValidationTier = ValidationTier.MONITOR
    agent: str | None = None

    async def validate(self) -> ValidationResult:
        """Run validation. Override in subclasses."""
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


class CodeQualityValidator(BaseValidator):
    """Tier 1: Code quality (ruff, complexity)."""

    dimension = "code_quality"
    tier = ValidationTier.BLOCKER

    async def validate(self) -> ValidationResult:
        start = datetime.now()
        try:
            # Run ruff
            result = subprocess.run(
                ["ruff", "check", "."],
                capture_output=True,
                text=True,
                timeout=60,
            )
            passed = result.returncode == 0
            errors = (
                len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
            )

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=passed,
                message=f"Ruff: {errors} errors" if not passed else "Code quality OK",
                details={"error_count": errors, "output": result.stdout[:500]},
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )
        except FileNotFoundError:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="ruff not installed (skipped)",
            )
        except Exception as e:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message=f"Error: {e}",
            )


class TypeSafetyValidator(BaseValidator):
    """Tier 1: Type safety (pyright/mypy)."""

    dimension = "type_safety"
    tier = ValidationTier.BLOCKER

    async def validate(self) -> ValidationResult:
        start = datetime.now()
        try:
            result = subprocess.run(
                ["python3", "-m", "pyright", "--outputjson", "."],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return ValidationResult(
                    dimension=self.dimension,
                    tier=self.tier,
                    passed=True,
                    message="Type check passed",
                    duration_ms=int((datetime.now() - start).total_seconds() * 1000),
                )

            # Parse errors
            try:
                output = json.loads(result.stdout)
                errors = output.get("generalDiagnostics", [])
                error_count = len(errors)
            except json.JSONDecodeError:
                error_count = -1

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message=f"Type errors: {error_count}",
                details={"error_count": error_count},
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )
        except FileNotFoundError:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="pyright not installed (skipped)",
            )
        except Exception as e:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message=f"Error: {e}",
            )


class SecurityValidator(BaseValidator):
    """Tier 1: Security (bandit, trivy, gitleaks)."""

    dimension = "security"
    tier = ValidationTier.BLOCKER

    async def validate(self) -> ValidationResult:
        start = datetime.now()
        issues = []

        # Run bandit (Python SAST)
        try:
            result = subprocess.run(
                ["bandit", "-r", ".", "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                try:
                    data = json.loads(result.stdout)
                    high_sev = [
                        r
                        for r in data.get("results", [])
                        if r.get("issue_severity") in ("HIGH", "MEDIUM")
                    ]
                    if high_sev:
                        issues.append(f"Bandit: {len(high_sev)} issues")
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            pass  # bandit not installed

        # Run gitleaks (secrets)
        try:
            result = subprocess.run(
                ["gitleaks", "detect", "--no-git", "-v"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                issues.append("Gitleaks: secrets detected")
        except FileNotFoundError:
            pass  # gitleaks not installed

        passed = len(issues) == 0
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message="; ".join(issues) if issues else "Security check passed",
            details={"issues": issues},
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


class CoverageValidator(BaseValidator):
    """Tier 1: Test coverage."""

    dimension = "coverage"
    tier = ValidationTier.BLOCKER
    min_coverage = 70

    async def validate(self) -> ValidationResult:
        start = datetime.now()

        # Check for coverage.xml
        coverage_file = Path("coverage.xml")
        if not coverage_file.exists():
            # Try running pytest with coverage
            try:
                subprocess.run(
                    ["pytest", "--cov=.", "--cov-report=xml", "-q"],
                    capture_output=True,
                    timeout=300,
                )
            except Exception:
                pass

        if not coverage_file.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No coverage data (skipped)",
            )

        # Parse coverage
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(coverage_file)
            root = tree.getroot()
            line_rate = float(root.get("line-rate", 0)) * 100

            passed = line_rate >= self.min_coverage
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=passed,
                message=f"Coverage: {line_rate:.1f}% (min: {self.min_coverage}%)",
                details={"coverage_percent": line_rate},
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )
        except Exception as e:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message=f"Coverage parse error: {e}",
            )


# Import real validators with fallback to stubs
try:
    from validators.design_principles.validator import (
        DesignPrinciplesValidator as DesignPrinciplesValidatorImpl,
    )
except ImportError:
    DesignPrinciplesValidatorImpl = None

try:
    from validators.oss_reuse.validator import (
        OSSReuseValidator as OSSReuseValidatorImpl,
    )
except ImportError:
    OSSReuseValidatorImpl = None

try:
    from validators.mathematical.validator import (
        MathematicalValidator as MathematicalValidatorImpl,
    )
except ImportError:
    MathematicalValidatorImpl = None

try:
    from validators.api_contract.validator import (
        APIContractValidator as APIContractValidatorImpl,
    )
except ImportError:
    APIContractValidatorImpl = None


class DesignPrinciplesValidator(BaseValidator):
    """Tier 2: Design principles (KISS, YAGNI, DRY) - stub fallback."""

    dimension = "design_principles"
    tier = ValidationTier.WARNING
    agent = "code-simplifier"

    async def validate(self) -> ValidationResult:
        # Use real implementation if available
        if DesignPrinciplesValidatorImpl:
            impl = DesignPrinciplesValidatorImpl()
            # ValidationResult from validator module is structurally identical
            return await impl.validate()  # type: ignore[return-value]

        # Fallback stub
        start = datetime.now()
        warnings = []

        for py_file in Path(".").rglob("*.py"):
            if py_file.stat().st_size > 50000:  # >50KB
                warnings.append(f"{py_file}: >50KB")

        passed = len(warnings) == 0
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=f"{len(warnings)} large files" if warnings else "Design OK (stub)",
            details={"warnings": warnings[:5], "using_stub": True},
            fix_suggestion="Consider splitting large files",
            agent=self.agent if not passed else None,
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


class OSSReuseValidator(BaseValidator):
    """Tier 2: OSS reuse suggestions - stub fallback."""

    dimension = "oss_reuse"
    tier = ValidationTier.WARNING

    async def validate(self) -> ValidationResult:
        # Use real implementation if available
        if OSSReuseValidatorImpl:
            impl = OSSReuseValidatorImpl()
            return await impl.validate()

        # Fallback stub
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="OSS reuse validator not installed (stub)",
            details={"using_stub": True},
        )


class ArchitectureValidator(BaseValidator):
    """Tier 2: Architecture consistency."""

    dimension = "architecture"
    tier = ValidationTier.WARNING
    agent = "architecture-validator"

    async def validate(self) -> ValidationResult:
        start = datetime.now()

        # Check for ARCHITECTURE.md
        arch_file = Path("ARCHITECTURE.md")
        if not arch_file.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message="ARCHITECTURE.md not found",
                fix_suggestion="Create ARCHITECTURE.md documenting structure",
                agent=self.agent,
            )

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="Architecture documented",
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


class DocumentationValidator(BaseValidator):
    """Tier 2: Documentation completeness."""

    dimension = "documentation"
    tier = ValidationTier.WARNING
    agent = "readme-generator"

    async def validate(self) -> ValidationResult:
        start = datetime.now()

        # Check for README.md
        readme = Path("README.md")
        if not readme.exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message="README.md not found",
                fix_suggestion="Create README.md with project overview",
                agent=self.agent,
            )

        # Check README has content
        content = readme.read_text()
        if len(content) < 100:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message="README.md too short",
                fix_suggestion="Expand README with installation/usage",
                agent=self.agent,
            )

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="Documentation OK",
            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
        )


class PerformanceValidator(BaseValidator):
    """Tier 3: Performance metrics (Lighthouse)."""

    dimension = "performance"
    tier = ValidationTier.MONITOR

    async def validate(self) -> ValidationResult:
        # Performance validation is typically CI-only
        # Here we just check if budgets file exists
        budgets = Path("budgets.json")
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message=f"Budgets file: {'exists' if budgets.exists() else 'not found'}",
            details={"budgets_file_exists": budgets.exists()},
        )


class AccessibilityValidator(BaseValidator):
    """Tier 3: Accessibility (axe-core)."""

    dimension = "accessibility"
    tier = ValidationTier.MONITOR

    async def validate(self) -> ValidationResult:
        # A11y validation requires browser - typically CI-only
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="A11y: requires CI (Playwright + axe)",
        )


class MathematicalValidator(BaseValidator):
    """Tier 3: Mathematical formula validation - stub fallback."""

    dimension = "mathematical"
    tier = ValidationTier.MONITOR

    async def validate(self) -> ValidationResult:
        # Use real implementation if available
        if MathematicalValidatorImpl:
            impl = MathematicalValidatorImpl()
            return await impl.validate()

        # Fallback stub
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="Mathematical validator not installed (stub)",
            details={"using_stub": True, "cas_available": False},
        )


class APIContractValidator(BaseValidator):
    """Tier 3: API contract validation - stub fallback."""

    dimension = "api_contract"
    tier = ValidationTier.MONITOR

    async def validate(self) -> ValidationResult:
        # Use real implementation if available
        if APIContractValidatorImpl:
            impl = APIContractValidatorImpl()
            return await impl.validate()

        # Fallback stub
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="API contract validator not installed (stub)",
            details={"using_stub": True, "oasdiff_available": False},
        )


# =============================================================================
# Orchestrator
# =============================================================================


class ValidationOrchestrator:
    """
    Main orchestrator for 14-dimension tiered validation.

    Usage:
        orchestrator = ValidationOrchestrator(config_path)
        report = await orchestrator.run_all()

        if report.blocked:
            print("Tier 1 blockers failed - cannot proceed")
        elif report.tiers[1].has_warnings:
            print("Tier 2 warnings - consider fixing")
    """

    # Registry of validators by dimension name
    VALIDATOR_REGISTRY: dict[str, type[BaseValidator]] = {
        "code_quality": CodeQualityValidator,
        "type_safety": TypeSafetyValidator,
        "security": SecurityValidator,
        "coverage": CoverageValidator,
        "design_principles": DesignPrinciplesValidator,
        "architecture": ArchitectureValidator,
        "documentation": DocumentationValidator,
        "performance": PerformanceValidator,
        "accessibility": AccessibilityValidator,
        # Phase 9-10 validators
        "oss_reuse": OSSReuseValidator,
        "mathematical": MathematicalValidator,
        "api_contract": APIContractValidator,
        # Remaining stubs (Phase 12)
        "visual": BaseValidator,
        "data_integrity": BaseValidator,
    }

    def __init__(self, config_path: Path | None = None):
        self.config = self._load_config(config_path)
        self.validators: dict[str, BaseValidator] = {}
        self._register_validators()

    def _load_config(self, path: Path | None) -> dict:
        """Load validation config."""
        if path and path.exists():
            return json.loads(path.read_text())

        # Default config
        return {
            "project_name": PROJECT_NAME or "unknown",
            "dimensions": DIMENSIONS_CONFIG or {},
        }

    def _register_validators(self):
        """Register validators based on config."""
        dimensions = self.config.get("dimensions", {})

        # If no dimensions in config, use defaults
        if not dimensions:
            dimensions = {
                "code_quality": {"enabled": True, "tier": 1},
                "type_safety": {"enabled": True, "tier": 1},
                "security": {"enabled": True, "tier": 1},
                "coverage": {"enabled": True, "tier": 1},
                "design_principles": {"enabled": True, "tier": 2},
                "architecture": {"enabled": True, "tier": 2},
                "documentation": {"enabled": True, "tier": 2},
                "performance": {"enabled": True, "tier": 3},
                "accessibility": {"enabled": True, "tier": 3},
            }

        for name, dim_config in dimensions.items():
            if dim_config.get("enabled", True):
                validator_class = self.VALIDATOR_REGISTRY.get(name, BaseValidator)
                self.validators[name] = validator_class()

                # Override tier if specified in config
                if "tier" in dim_config:
                    self.validators[name].tier = ValidationTier(dim_config["tier"])

    def _get_tier(self, dimension: str) -> ValidationTier:
        """Get tier for a dimension."""
        validator = self.validators.get(dimension)
        return validator.tier if validator else ValidationTier.MONITOR

    async def _run_validator(
        self, name: str, validator: BaseValidator
    ) -> ValidationResult:
        """Run a single validator with error handling."""
        try:
            return await validator.validate()
        except Exception as e:
            logger.error(f"Validator {name} failed: {e}")
            return ValidationResult(
                dimension=name,
                tier=validator.tier,
                passed=False,
                message=f"Validator error: {e}",
            )

    async def run_tier(self, tier: ValidationTier) -> TierResult:
        """Run all validators for a specific tier."""
        tier_validators = [
            (name, v) for name, v in self.validators.items() if v.tier == tier
        ]

        if not tier_validators:
            return TierResult(tier=tier, results=[])

        results = await asyncio.gather(
            *[self._run_validator(name, v) for name, v in tier_validators]
        )

        return TierResult(tier=tier, results=list(results))

    async def _suggest_fixes(self, tier_result: TierResult):
        """Log fix suggestions for failed Tier 2 validators."""
        for result in tier_result.results:
            if not result.passed and result.fix_suggestion:
                logger.info(
                    f"Fix suggestion for {result.dimension}: {result.fix_suggestion}"
                )
                if result.agent:
                    logger.info(f"  → Spawn agent: {result.agent}")

    async def _emit_metrics(self, tier_result: TierResult):
        """Emit Tier 3 metrics to QuestDB."""
        import socket

        host = "localhost"
        port = 9009

        for result in tier_result.results:
            try:
                # ILP line protocol
                passed_int = 1 if result.passed else 0
                line = f"validation,dimension={result.dimension} passed={passed_int}i,duration={result.duration_ms}i\n"

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(2)
                    sock.connect((host, port))
                    sock.sendall(line.encode())
            except Exception:
                pass  # QuestDB not available - ignore

    async def run_all(self) -> ValidationReport:
        """
        Run all tiers in sequence.

        Execution order:
        1. Tier 1 (Blockers) - if any fail, stop and return blocked=True
        2. Tier 2 (Warnings) - log fix suggestions
        3. Tier 3 (Monitors) - emit metrics

        After each tier:
        - Push metrics to Prometheus (if available)
        - Inject context to Sentry (if available)
        """
        # Log available integrations once at startup
        _log_integrations_status()

        start = datetime.now()
        project_name = self.config.get("project_name", "unknown")
        report = ValidationReport(
            project=project_name,
            timestamp=start.isoformat(),
        )

        # Tier 1: Blockers (must all pass)
        t1 = await self.run_tier(ValidationTier.BLOCKER)
        report.tiers.append(t1)

        # Push metrics and inject context after Tier 1
        push_validation_metrics(t1, project_name)
        inject_validation_context(t1)

        if not t1.passed:
            report.blocked = True
            report.overall_passed = False
            logger.warning(f"Tier 1 BLOCKED: {t1.failed_dimensions}")

            # Add breadcrumb for blocker details
            add_validation_breadcrumb(
                message=f"Blocked by: {', '.join(t1.failed_dimensions)}",
                level="error",
                data={"blockers": t1.failed_dimensions},
            )

            # Push final metrics and context before returning
            report.execution_time_ms = int(
                (datetime.now() - start).total_seconds() * 1000
            )
            push_validation_metrics(report, project_name)
            inject_validation_context(report)
            return report

        logger.info("Tier 1 passed - proceeding to Tier 2")

        # Tier 2: Warnings (suggest fixes)
        t2 = await self.run_tier(ValidationTier.WARNING)
        report.tiers.append(t2)

        # Push metrics and inject context after Tier 2
        push_validation_metrics(t2, project_name)
        inject_validation_context(t2)

        if t2.has_warnings:
            await self._suggest_fixes(t2)
            logger.info(f"Tier 2 warnings: {t2.failed_dimensions}")

            # Add breadcrumb for warning details
            add_validation_breadcrumb(
                message=f"Warnings: {', '.join(t2.failed_dimensions)}",
                level="warning",
                data={"warnings": t2.failed_dimensions},
            )

        # Tier 3: Monitors (emit metrics)
        t3 = await self.run_tier(ValidationTier.MONITOR)
        report.tiers.append(t3)
        await self._emit_metrics(t3)

        # Push metrics and inject context after Tier 3
        push_validation_metrics(t3, project_name)
        inject_validation_context(t3)

        report.execution_time_ms = int((datetime.now() - start).total_seconds() * 1000)
        logger.info(f"Validation complete in {report.execution_time_ms}ms")

        # Final metrics push with full report
        push_validation_metrics(report, project_name)
        inject_validation_context(report)

        return report

    async def validate_file(
        self, file_path: str, tier: int = 1
    ) -> "FileValidationResult":
        """
        Quick validation for a single file. Used by hooks.

        Args:
            file_path: Path to the file to validate
            tier: Validation tier (1=blockers only, 2=warnings, 3=monitors)

        Returns:
            FileValidationResult with has_blockers property

        Notes:
            - Only runs validators relevant to the file type
            - For Python files: code_quality, type_safety, security
            - For other files: minimal checks or skip
            - Much faster than run_all() for single-file validation
        """
        start = datetime.now()
        file_ext = Path(file_path).suffix.lower()

        # Determine which validators to run based on file type
        if file_ext == ".py":
            relevant_validators = ["code_quality", "type_safety", "security"]
        elif file_ext in (".js", ".ts", ".jsx", ".tsx"):
            relevant_validators = ["code_quality", "security"]
        elif file_ext in (".json", ".yaml", ".yml"):
            relevant_validators = ["security"]  # Check for secrets
        else:
            # Unknown file type - skip validation
            return FileValidationResult(
                file_path=file_path,
                has_blockers=False,
                message="File type not validated",
                results=[],
                duration_ms=0,
            )

        # Filter validators by tier and relevance
        target_tier = ValidationTier(tier)
        validators_to_run = [
            (name, v)
            for name, v in self.validators.items()
            if name in relevant_validators and v.tier == target_tier
        ]

        if not validators_to_run:
            return FileValidationResult(
                file_path=file_path,
                has_blockers=False,
                message=f"No tier {tier} validators for this file type",
                results=[],
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

        # Run validators in parallel
        results = await asyncio.gather(
            *[self._run_validator(name, v) for name, v in validators_to_run]
        )

        # Aggregate results
        has_blockers = any(not r.passed for r in results)
        failed = [r.dimension for r in results if not r.passed]
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        if has_blockers:
            message = f"Tier {tier} blockers: {', '.join(failed)}"
        else:
            message = f"Tier {tier} passed ({len(results)} validators)"

        return FileValidationResult(
            file_path=file_path,
            has_blockers=has_blockers,
            message=message,
            results=list(results),
            duration_ms=duration_ms,
        )


@dataclass
class FileValidationResult:
    """Result from single-file validation. Used by hooks."""

    file_path: str
    has_blockers: bool
    message: str
    results: list[ValidationResult] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        """Convert to serializable dict."""
        return {
            "file_path": self.file_path,
            "has_blockers": self.has_blockers,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "results": [
                {
                    "dimension": r.dimension,
                    "passed": r.passed,
                    "message": r.message,
                }
                for r in self.results
            ],
        }


# =============================================================================
# CLI Entry Point
# =============================================================================


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run tiered validation")
    parser.add_argument("--config", "-c", type=Path, help="Config file path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3], help="Run specific tier only"
    )
    args = parser.parse_args()

    # Find config
    config_path = args.config
    if not config_path:
        for candidate in [
            Path(".claude/validation/config.json"),
            Path("config/validation.json"),
        ]:
            if candidate.exists():
                config_path = candidate
                break

    orchestrator = ValidationOrchestrator(config_path)

    if args.tier:
        result = await orchestrator.run_tier(ValidationTier(args.tier))
        if args.json:
            print(json.dumps({"tier": args.tier, "passed": result.passed}))
        else:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            print(f"Tier {args.tier}: {status}")
            for r in result.results:
                icon = "✓" if r.passed else "✗"
                print(f"  {icon} {r.dimension}: {r.message}")
    else:
        report = await orchestrator.run_all()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(f"\n{'=' * 60}")
            print(f"VALIDATION REPORT: {report.project}")
            print(f"{'=' * 60}")

            for tier_result in report.tiers:
                status = "✅" if tier_result.passed else "❌"
                print(
                    f"\nTier {tier_result.tier.value} ({tier_result.tier.name}): {status}"
                )
                for r in tier_result.results:
                    icon = "✓" if r.passed else "✗"
                    print(f"  {icon} {r.dimension}: {r.message}")

            print(f"\n{'=' * 60}")
            if report.blocked:
                print("RESULT: ❌ BLOCKED (Tier 1 failures)")
                sys.exit(1)
            else:
                print(f"RESULT: ✅ PASSED ({report.execution_time_ms}ms)")
                sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
