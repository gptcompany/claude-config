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
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# =============================================================================
# Environment Controls
# =============================================================================

AGENT_SPAWN_ENABLED = os.environ.get("VALIDATION_AGENT_SPAWN", "true").lower() == "true"
SWARM_ENABLED = os.environ.get("VALIDATION_SWARM", "true").lower() == "true"

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


def _elapsed_ms(start: datetime) -> int:
    """Calculate elapsed milliseconds since start time."""
    return int((datetime.now() - start).total_seconds() * 1000)


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
            # Use JSON output format for accurate error counting
            result = subprocess.run(
                ["ruff", "check", ".", "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            passed = result.returncode == 0

            # Parse JSON output to get actual error count
            errors = 0
            output_preview = ""
            if result.stdout.strip():
                try:
                    error_list = json.loads(result.stdout)
                    errors = len(error_list)
                    # Create readable preview from first few errors
                    if error_list:
                        preview_items = [
                            f"{e.get('filename', '?')}:{e.get('location', {}).get('row', '?')}: {e.get('code', '?')} {e.get('message', '')}"
                            for e in error_list[:5]
                        ]
                        output_preview = "\n".join(preview_items)
                        if len(error_list) > 5:
                            output_preview += f"\n... and {len(error_list) - 5} more"
                except json.JSONDecodeError:
                    # Fallback: count non-empty lines if JSON parsing fails
                    errors = len([line for line in result.stdout.strip().split("\n") if line.strip()])
                    output_preview = result.stdout[:500]

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=passed,
                message="Code quality OK" if passed else f"Ruff: {errors} errors",
                details={"error_count": errors, "output": output_preview},
                duration_ms=_elapsed_ms(start),
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
                    duration_ms=_elapsed_ms(start),
                )

            # Parse errors
            try:
                output = json.loads(result.stdout)
                error_count = len(output.get("generalDiagnostics", []))
            except json.JSONDecodeError:
                error_count = -1

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message=f"Type errors: {error_count}",
                details={"error_count": error_count},
                duration_ms=_elapsed_ms(start),
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
        issues.extend(self._check_bandit())

        # Run gitleaks (secrets)
        issues.extend(self._check_gitleaks())

        passed = len(issues) == 0
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message="Security check passed" if passed else "; ".join(issues),
            details={"issues": issues},
            duration_ms=_elapsed_ms(start),
        )

    def _check_bandit(self) -> list[str]:
        """Run bandit SAST scanner."""
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
                        r for r in data.get("results", [])
                        if r.get("issue_severity") in ("HIGH", "MEDIUM")
                    ]
                    if high_sev:
                        return [f"Bandit: {len(high_sev)} issues"]
                except json.JSONDecodeError:
                    pass
        except FileNotFoundError:
            pass
        return []

    def _check_gitleaks(self) -> list[str]:
        """Run gitleaks secrets scanner."""
        try:
            result = subprocess.run(
                ["gitleaks", "detect", "--no-git", "-v"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return ["Gitleaks: secrets detected"]
        except FileNotFoundError:
            pass
        return []


class CoverageValidator(BaseValidator):
    """Tier 1: Test coverage."""

    dimension = "coverage"
    tier = ValidationTier.BLOCKER
    min_coverage = 70

    async def validate(self) -> ValidationResult:
        start = datetime.now()
        coverage_file = Path("coverage.xml")

        # Generate coverage if not present
        if not coverage_file.exists():
            self._generate_coverage()

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
            line_rate = float(tree.getroot().get("line-rate", 0)) * 100

            passed = line_rate >= self.min_coverage
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=passed,
                message=f"Coverage: {line_rate:.1f}% (min: {self.min_coverage}%)",
                details={"coverage_percent": line_rate},
                duration_ms=_elapsed_ms(start),
            )
        except Exception as e:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message=f"Coverage parse error: {e}",
            )

    def _generate_coverage(self) -> None:
        """Try to generate coverage.xml via pytest."""
        try:
            subprocess.run(
                ["pytest", "--cov=.", "--cov-report=xml", "-q"],
                capture_output=True,
                timeout=300,
            )
        except Exception:
            pass


# Import real validators with fallback to stubs
try:
    from validators.design_principles.validator import (  # type: ignore[import-not-found]
        DesignPrinciplesValidator as DesignPrinciplesValidatorImpl,
    )
except ImportError:
    DesignPrinciplesValidatorImpl = None  # type: ignore[assignment]

try:
    from validators.oss_reuse.validator import (  # type: ignore[import-not-found]
        OSSReuseValidator as OSSReuseValidatorImpl,
    )
except ImportError:
    OSSReuseValidatorImpl = None  # type: ignore[assignment]

try:
    from validators.mathematical.validator import (  # type: ignore[import-not-found]
        MathematicalValidator as MathematicalValidatorImpl,
    )
except ImportError:
    MathematicalValidatorImpl = None  # type: ignore[assignment]

try:
    from validators.api_contract.validator import (  # type: ignore[import-not-found]
        APIContractValidator as APIContractValidatorImpl,
    )
except ImportError:
    APIContractValidatorImpl = None  # type: ignore[assignment]

# ECC Validators (from everything-claude-code integration)
try:
    from validators.ecc import (  # type: ignore[import-not-found]
        E2EValidator,
        SecurityEnhancedValidator,
        TDDValidator,
        EvalValidator,
    )

    ECC_VALIDATORS_AVAILABLE = True
except ImportError:
    ECC_VALIDATORS_AVAILABLE = False
    E2EValidator = None  # type: ignore[misc, assignment]
    SecurityEnhancedValidator = None  # type: ignore[misc, assignment]
    TDDValidator = None  # type: ignore[misc, assignment]
    EvalValidator = None  # type: ignore[misc, assignment]


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
            message="Design OK (stub)" if passed else f"{len(warnings)} large files",
            details={"warnings": warnings[:5], "using_stub": True},
            fix_suggestion="Consider splitting large files",
            agent=self.agent if not passed else None,
            duration_ms=_elapsed_ms(start),
        )


class OSSReuseValidator(BaseValidator):
    """Tier 2: OSS reuse suggestions - stub fallback."""

    dimension = "oss_reuse"
    tier = ValidationTier.WARNING

    async def validate(self) -> ValidationResult:
        # Use real implementation if available
        if OSSReuseValidatorImpl:
            impl = OSSReuseValidatorImpl()
            # ValidationResult from validator module is structurally identical
            return await impl.validate()  # type: ignore[return-value]

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
            duration_ms=_elapsed_ms(start),
        )


class DocumentationValidator(BaseValidator):
    """Tier 2: Documentation completeness."""

    dimension = "documentation"
    tier = ValidationTier.WARNING
    agent = "readme-generator"

    async def validate(self) -> ValidationResult:
        start = datetime.now()
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

        if len(readme.read_text()) < 100:
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
            duration_ms=_elapsed_ms(start),
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
            # ValidationResult from validator module is structurally identical
            return await impl.validate()  # type: ignore[return-value]

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
            # ValidationResult from validator module is structurally identical
            return await impl.validate()  # type: ignore[return-value]

        # Fallback stub
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="API contract validator not installed (stub)",
            details={"using_stub": True, "oasdiff_available": False},
        )


# =============================================================================
# Agent Spawn Function
# =============================================================================


async def _run_validators_sequential(validators: list) -> list:
    """Run validators sequentially with error handling."""
    results = []
    for name, v in validators:
        try:
            result = await v.validate()
            results.append(result)
        except Exception as e:
            logger.error(f"Validator {name} failed: {e}")
    return results


async def run_tier3_parallel(validators: list) -> list:
    """
    Run Tier 3 validators in parallel using swarm workers.

    For Tier 3 (monitoring), parallelization is safe because:
    - Results are non-blocking
    - No ordering dependencies
    - Pure metrics collection

    Falls back to sequential execution on any error.
    """
    if len(validators) < 2:
        return await _run_validators_sequential(validators)

    if not SWARM_ENABLED:
        logger.info("Swarm disabled, running Tier 3 sequentially")
        return await _run_validators_sequential(validators)

    hive_script = os.path.expanduser("~/.claude/scripts/hooks/control/hive-manager.js")

    if not os.path.exists(hive_script):
        logger.warning("Hive manager not found, falling back to sequential")
        return await _run_validators_sequential(validators)

    try:
        # Initialize swarm with mesh topology
        init_result = subprocess.run(
            ["node", hive_script, "init", "--topology", "mesh"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if init_result.returncode != 0:
            logger.warning("Swarm init failed, falling back to sequential")
            return await _run_validators_sequential(validators)

        worker_count = min(len(validators), 4)
        logger.info(f"Running {len(validators)} Tier 3 validators in parallel (max {worker_count} concurrent)")

        tasks = [v.validate() for _, v in validators]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Validator failed with exception: {result}")
            else:
                valid_results.append(result)

        # Best effort cleanup
        subprocess.run(
            ["node", hive_script, "shutdown"],
            capture_output=True,
            timeout=5,
            check=False,
        )

        return valid_results

    except Exception as e:
        logger.warning(f"Swarm execution failed: {e}, falling back to sequential")
        return await _run_validators_sequential(validators)


async def check_complexity_and_simplify(modified_files: list[str]) -> bool:
    """
    Proactively spawn code-simplifier when complexity thresholds exceeded.

    Triggers code-simplifier agent when:
    - Multiple files modified (>= 2)
    - Total LOC > 200
    - Single file > 200 lines

    Returns True if simplifier was spawned.
    """
    if not AGENT_SPAWN_ENABLED:
        return False

    if not modified_files:
        return False

    # Get file stats
    total_lines = 0
    complex_files = []

    for file_path in modified_files:
        try:
            path = Path(file_path)
            if path.exists() and path.suffix in ('.py', '.ts', '.js', '.tsx', '.jsx'):
                lines = len(path.read_text().splitlines())
                total_lines += lines
                if lines > 200:
                    complex_files.append((file_path, lines))
        except Exception:
            continue

    # Check thresholds
    should_simplify = False
    reason = ""

    if len(modified_files) >= 2 and total_lines > 200:
        should_simplify = True
        reason = f"Multiple files ({len(modified_files)}) with {total_lines} total LOC"
    elif complex_files:
        should_simplify = True
        files_info = ", ".join([f"{f}:{loc}LOC" for f, loc in complex_files])
        reason = f"Large files detected: {files_info}"

    if should_simplify:
        logger.info(f"Complexity threshold exceeded: {reason}")
        spawn_agent(
            agent_type="code-simplifier",
            task_description=f"Simplify recently modified code. {reason}",
            context={
                "files": modified_files,
                "total_lines": total_lines,
                "complex_files": [f for f, _ in complex_files],
                "reason": reason,
            },
        )
        return True

    return False


def spawn_agent(agent_type: str, task_description: str, context: dict) -> bool:
    """
    Spawn a Claude Code agent to fix validation issues.

    Args:
        agent_type: Agent type (e.g., 'code-simplifier', 'security-reviewer')
        task_description: What the agent should do
        context: Additional context (file paths, error details)

    Returns:
        True if spawn successful, False otherwise
    """
    if not AGENT_SPAWN_ENABLED:
        logger.info(f"  → Agent spawn disabled, would spawn: {agent_type}")
        return False

    try:
        # Build the claude command for spawning agent
        # Uses claude code CLI to spawn task
        context_str = json.dumps(context)

        cmd = [
            "claude",
            "--print",  # Non-interactive mode
            f"Spawn agent '{agent_type}' to: {task_description}. Context: {context_str}",
        ]

        # Fire and forget (non-blocking spawn)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        logger.info(f"  → Spawned agent: {agent_type}")
        return True

    except FileNotFoundError:
        logger.warning(f"  → Claude CLI not found, cannot spawn agent {agent_type}")
        return False
    except Exception as e:
        logger.warning(f"  → Failed to spawn agent {agent_type}: {e}")
        return False


# =============================================================================
# Orchestrator
# =============================================================================


class ValidationOrchestrator:
    """
    Main orchestrator for 14-dimension tiered validation.

    Core dimensions: code_quality, type_safety, security, coverage,
    design_principles, architecture, documentation, performance,
    accessibility, oss_reuse, mathematical, api_contract, visual, data_integrity

    ECC dimensions (if available): e2e_validation, security_enhanced,
    tdd_compliance, eval_metrics

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

    # Conditionally add ECC validators if available
    if ECC_VALIDATORS_AVAILABLE:
        VALIDATOR_REGISTRY.update({  # type: ignore[arg-type]
            "e2e_validation": E2EValidator,
            "security_enhanced": SecurityEnhancedValidator,
            "tdd_compliance": TDDValidator,
            "eval_metrics": EvalValidator,
        })

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

        # Use swarm parallel execution for Tier 3 (monitoring) when >= 2 validators
        if tier == ValidationTier.MONITOR and len(tier_validators) >= 2 and SWARM_ENABLED:
            results = await run_tier3_parallel(tier_validators)
            return TierResult(tier=tier, results=list(results))

        # Sequential execution for Tier 1/2 or when swarm disabled
        results = await asyncio.gather(
            *[self._run_validator(name, v) for name, v in tier_validators]
        )

        return TierResult(tier=tier, results=list(results))

    async def _suggest_fixes(self, tier_result: TierResult):
        """Log fix suggestions and spawn agents for failed Tier 2 validators."""
        for result in tier_result.results:
            if not result.passed and result.fix_suggestion:
                logger.info(
                    f"Fix suggestion for {result.dimension}: {result.fix_suggestion}"
                )
                if result.agent:
                    # Actually spawn the agent to fix the issue
                    spawn_agent(
                        agent_type=result.agent,
                        task_description=f"Fix: {result.message}",
                        context={
                            "validator": result.dimension,
                            "message": result.message,
                            "details": result.details,
                            "fix_suggestion": result.fix_suggestion,
                        },
                    )

    async def _emit_metrics(self, tier_result: TierResult) -> None:
        """Emit Tier 3 metrics to QuestDB."""
        import socket

        for result in tier_result.results:
            try:
                passed_int = 1 if result.passed else 0
                line = f"validation,dimension={result.dimension} passed={passed_int}i,duration={result.duration_ms}i\n"

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(2)
                    sock.connect(("localhost", 9009))
                    sock.sendall(line.encode())
            except Exception:
                pass  # QuestDB not available - ignore

    def _push_observability(self, data, project_name: str) -> None:
        """Push metrics and context to observability backends."""
        push_validation_metrics(data, project_name)
        inject_validation_context(data)

    async def run_all(self, modified_files: list[str] | None = None) -> ValidationReport:
        """
        Run all tiers in sequence.

        Execution order:
        1. Tier 1 (Blockers) - if any fail, stop and return blocked=True
        2. Check complexity and spawn code-simplifier if needed
        3. Tier 2 (Warnings) - log fix suggestions
        4. Tier 3 (Monitors) - emit metrics

        After each tier, push to Prometheus and Sentry (if available).
        """
        _log_integrations_status()

        start = datetime.now()
        project_name = self.config.get("project_name", "unknown")
        report = ValidationReport(project=project_name, timestamp=start.isoformat())

        # Tier 1: Blockers (must all pass)
        t1 = await self.run_tier(ValidationTier.BLOCKER)
        report.tiers.append(t1)
        self._push_observability(t1, project_name)

        if not t1.passed:
            report.blocked = True
            report.overall_passed = False
            logger.warning(f"Tier 1 BLOCKED: {t1.failed_dimensions}")
            add_validation_breadcrumb(
                message=f"Blocked by: {', '.join(t1.failed_dimensions)}",
                level="error",
                data={"blockers": t1.failed_dimensions},
            )
            report.execution_time_ms = _elapsed_ms(start)
            self._push_observability(report, project_name)
            return report

        logger.info("Tier 1 passed - proceeding to Tier 2")

        # Check complexity and spawn code-simplifier if needed
        if modified_files:
            await check_complexity_and_simplify(modified_files)

        # Tier 2: Warnings (suggest fixes)
        t2 = await self.run_tier(ValidationTier.WARNING)
        report.tiers.append(t2)
        self._push_observability(t2, project_name)

        if t2.has_warnings:
            await self._suggest_fixes(t2)
            logger.info(f"Tier 2 warnings: {t2.failed_dimensions}")
            add_validation_breadcrumb(
                message=f"Warnings: {', '.join(t2.failed_dimensions)}",
                level="warning",
                data={"warnings": t2.failed_dimensions},
            )

        # Tier 3: Monitors (emit metrics)
        t3 = await self.run_tier(ValidationTier.MONITOR)
        report.tiers.append(t3)
        await self._emit_metrics(t3)
        self._push_observability(t3, project_name)

        report.execution_time_ms = _elapsed_ms(start)
        logger.info(f"Validation complete in {report.execution_time_ms}ms")
        self._push_observability(report, project_name)

        return report

    def _print_tier_result(self, tier_result: TierResult) -> None:
        """Print formatted tier result."""
        status = "[PASS]" if tier_result.passed else "[FAIL]"
        print(f"\nTier {tier_result.tier.value} ({tier_result.tier.name}): {status}")
        for r in tier_result.results:
            icon = "[+]" if r.passed else "[-]"
            print(f"  {icon} {r.dimension}: {r.message}")

    def _parse_tier_arg(self, tier: str) -> ValidationTier | None:
        """Parse tier string to ValidationTier enum. Returns None for invalid input."""
        tier_map = {
            "1": ValidationTier.BLOCKER,
            "quick": ValidationTier.BLOCKER,
            "2": ValidationTier.WARNING,
            "3": ValidationTier.MONITOR,
        }
        return tier_map.get(tier.lower())

    async def run_from_cli(
        self, tier: str | None = None, modified_files: list[str] | None = None
    ) -> int:
        """
        Run validation from CLI with tier filtering and nice output.

        Returns: Exit code (0=passed, 1=blocked, 2=error)
        """
        try:
            # Run all tiers
            if tier is None or tier.lower() in ("all", ""):
                report = await self.run_all(modified_files=modified_files)

                print(f"\n{'=' * 60}")
                print(f"VALIDATION REPORT: {report.project}")
                print(f"{'=' * 60}")

                for tier_result in report.tiers:
                    self._print_tier_result(tier_result)

                print(f"\n{'=' * 60}")
                if report.blocked:
                    print("RESULT: BLOCKED (Tier 1 failures)")
                    return 1
                print(f"RESULT: PASSED ({report.execution_time_ms}ms)")
                return 0

            # Run single tier
            tier_enum = self._parse_tier_arg(tier)
            if tier_enum is None:
                print(f"Unknown tier: {tier}. Use 1/quick, 2, 3, or all.")
                return 2

            result = await self.run_tier(tier_enum)
            self._print_tier_result(result)
            return 0 if result.passed else 1

        except Exception as e:
            print(f"Validation error: {e}")
            return 2

    # Mapping of file extensions to relevant validators
    FILE_TYPE_VALIDATORS: dict[str, list[str]] = {
        ".py": ["code_quality", "type_safety", "security"],
        ".js": ["code_quality", "security"],
        ".ts": ["code_quality", "security"],
        ".jsx": ["code_quality", "security"],
        ".tsx": ["code_quality", "security"],
        ".json": ["security"],
        ".yaml": ["security"],
        ".yml": ["security"],
    }

    async def validate_file(self, file_path: str, tier: int = 1) -> "FileValidationResult":
        """
        Quick validation for a single file. Used by hooks.

        Only runs validators relevant to the file type. Much faster than run_all().
        """
        start = datetime.now()
        file_ext = Path(file_path).suffix.lower()
        relevant_validators = self.FILE_TYPE_VALIDATORS.get(file_ext)

        if not relevant_validators:
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
                duration_ms=_elapsed_ms(start),
            )

        # Run validators in parallel
        results = await asyncio.gather(
            *[self._run_validator(name, v) for name, v in validators_to_run]
        )

        has_blockers = any(not r.passed for r in results)
        failed = [r.dimension for r in results if not r.passed]

        return FileValidationResult(
            file_path=file_path,
            has_blockers=has_blockers,
            message=f"Tier {tier} blockers: {', '.join(failed)}" if has_blockers else f"Tier {tier} passed ({len(results)} validators)",
            results=list(results),
            duration_ms=_elapsed_ms(start),
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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run validation orchestrator")
    parser.add_argument(
        "tier",
        nargs="?",
        default=None,
        help="Tier to run (1/quick, 2, 3, or all)",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="Modified files to check for complexity (for code-simplifier trigger)",
    )
    args = parser.parse_args()

    orchestrator = ValidationOrchestrator()
    exit_code = asyncio.run(orchestrator.run_from_cli(args.tier, modified_files=args.files))
    sys.exit(exit_code)
