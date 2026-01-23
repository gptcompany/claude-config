"""
Sentry context injection for validation orchestrator.

Injects validation context into Sentry for debugging and error tracking.
Gracefully degrades if sentry_sdk is not installed or not initialized.

All functions are no-ops if Sentry is unavailable - no warnings, no crashes.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orchestrator import ValidationReport, TierResult

logger = logging.getLogger(__name__)

# Check if sentry_sdk is available
try:
    import sentry_sdk
    from sentry_sdk import set_context, set_tag, add_breadcrumb, push_scope

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None
    set_context = None
    set_tag = None
    add_breadcrumb = None
    push_scope = None


def _is_sentry_initialized() -> bool:
    """Check if Sentry SDK is initialized (has a valid client)."""
    if not SENTRY_AVAILABLE:
        return False
    try:
        # Get the current hub's client - if None, SDK not initialized
        hub = sentry_sdk.Hub.current
        return hub.client is not None
    except Exception:
        return False


def inject_validation_context(
    result: "TierResult | ValidationReport",
) -> bool:
    """
    Inject validation context into Sentry for debugging.

    Adds:
    - Structured context (appears in "Additional Data" section)
    - Searchable tags (tier, passed, score)
    - Breadcrumb for timeline

    Args:
        result: TierResult or ValidationReport from validation run

    Returns:
        True if context was injected, False otherwise (Sentry unavailable)
    """
    if not _is_sentry_initialized():
        return False

    try:
        # Handle both TierResult and ValidationReport
        if hasattr(result, "tiers"):
            # ValidationReport - inject aggregate context
            _inject_report_context(result)
        else:
            # Single TierResult
            _inject_tier_context(result)

        return True

    except Exception as e:
        # Silently fail - Sentry context is optional
        logger.debug(f"Failed to inject Sentry context: {e}")
        return False


def _inject_tier_context(tier_result: "TierResult") -> None:
    """Inject context for a single tier result."""
    tier_name = tier_result.tier.name
    tier_value = tier_result.tier.value

    # Calculate metrics
    total_validators = len(tier_result.results)
    passed_validators = sum(1 for r in tier_result.results if r.passed)
    failed_validators = [r.dimension for r in tier_result.results if not r.passed]
    validators_run = [r.dimension for r in tier_result.results]
    total_duration_ms = sum(r.duration_ms for r in tier_result.results)

    # Set structured context
    set_context(
        "validation",
        {
            "tier": tier_value,
            "tier_name": tier_name,
            "passed": tier_result.passed,
            "score": (passed_validators / total_validators * 100)
            if total_validators > 0
            else 100.0,
            "blockers": len(failed_validators) if tier_value == 1 else 0,
            "warnings": len(failed_validators) if tier_value == 2 else 0,
            "validators_run": validators_run,
            "failed_validators": failed_validators,
            "duration_ms": total_duration_ms,
        },
    )

    # Set searchable tags
    set_tag("validation.tier", str(tier_value))
    set_tag("validation.passed", str(tier_result.passed).lower())
    set_tag(
        "validation.score",
        f"{(passed_validators / total_validators * 100) if total_validators > 0 else 100:.1f}",
    )

    # Add breadcrumb for timeline
    add_breadcrumb(
        category="validation",
        message=f"Tier {tier_value} ({tier_name}): {'PASSED' if tier_result.passed else 'FAILED'}",
        level="info" if tier_result.passed else "warning",
        data={
            "validators": validators_run,
            "failed": failed_validators,
            "duration_ms": total_duration_ms,
        },
    )


def _inject_report_context(report: "ValidationReport") -> None:
    """Inject context for a full validation report."""
    # Aggregate metrics across all tiers
    all_validators = []
    all_failed = []
    total_duration_ms = 0

    for tier_result in report.tiers:
        for r in tier_result.results:
            all_validators.append(r.dimension)
            if not r.passed:
                all_failed.append(r.dimension)
            total_duration_ms += r.duration_ms

    passed_count = len(all_validators) - len(all_failed)
    score = (passed_count / len(all_validators) * 100) if all_validators else 100.0

    # Set structured context
    set_context(
        "validation",
        {
            "project": report.project,
            "timestamp": report.timestamp,
            "passed": report.overall_passed,
            "blocked": report.blocked,
            "score": score,
            "blockers": len(
                [
                    r
                    for t in report.tiers
                    if t.tier.value == 1
                    for r in t.results
                    if not r.passed
                ]
            ),
            "warnings": len(
                [
                    r
                    for t in report.tiers
                    if t.tier.value == 2
                    for r in t.results
                    if not r.passed
                ]
            ),
            "validators_run": all_validators,
            "failed_validators": all_failed,
            "duration_ms": total_duration_ms,
        },
    )

    # Set searchable tags
    set_tag("validation.passed", str(report.overall_passed).lower())
    set_tag("validation.blocked", str(report.blocked).lower())
    set_tag("validation.score", f"{score:.1f}")
    set_tag("validation.project", report.project)

    # Add breadcrumb for timeline
    status = (
        "BLOCKED"
        if report.blocked
        else ("PASSED" if report.overall_passed else "FAILED")
    )
    add_breadcrumb(
        category="validation",
        message=f"Validation {status}: {report.project}",
        level="error"
        if report.blocked
        else ("info" if report.overall_passed else "warning"),
        data={
            "tiers_run": len(report.tiers),
            "validators": all_validators,
            "failed": all_failed,
            "duration_ms": total_duration_ms,
        },
    )


def capture_validation_error(
    error: Exception,
    context: dict[str, Any] | None = None,
) -> bool:
    """
    Capture validation error with full context.

    Uses isolated scope to avoid polluting global context.
    Sets fingerprint for proper error grouping.

    Args:
        error: The exception to capture
        context: Optional additional context dict with keys:
            - file_path: Path being validated
            - validator_name: Name of validator that failed
            - config: Validation configuration
            - state: Current validation state

    Returns:
        True if error was captured, False otherwise (Sentry unavailable)
    """
    if not _is_sentry_initialized():
        return False

    if context is None:
        context = {}

    try:
        with push_scope() as scope:
            # Add validation-specific context
            if "config" in context:
                scope.set_context("validation_config", context["config"])

            if "state" in context:
                scope.set_context("validation_state", context["state"])

            # Add extras
            if "file_path" in context:
                scope.set_extra("file_path", context["file_path"])

            if "validators" in context:
                scope.set_extra("validators_attempted", context["validators"])

            # Set fingerprint for grouping
            validator_name = context.get("validator_name", "unknown")
            scope.fingerprint = ["validation-error", validator_name]

            # Set tags for searchability
            scope.set_tag("validation.error", "true")
            scope.set_tag("validation.validator", validator_name)

            # Capture the exception
            sentry_sdk.capture_exception(error)

        return True

    except Exception as e:
        # Silently fail - error capture is best-effort
        logger.debug(f"Failed to capture validation error to Sentry: {e}")
        return False


def add_validation_breadcrumb(
    message: str,
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> bool:
    """
    Add a validation breadcrumb to the Sentry timeline.

    Useful for tracking validation progress without full context injection.

    Args:
        message: Breadcrumb message
        level: Severity level (debug, info, warning, error)
        data: Optional additional data dict

    Returns:
        True if breadcrumb was added, False otherwise
    """
    if not _is_sentry_initialized():
        return False

    try:
        add_breadcrumb(
            category="validation",
            message=message,
            level=level,
            data=data or {},
        )
        return True
    except Exception:
        return False
