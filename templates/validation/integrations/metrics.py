"""
Prometheus metrics integration for validation orchestrator.

Pushes validation metrics to Prometheus Pushgateway for Grafana visualization.
Gracefully degrades if prometheus_client is not installed.

Environment variables:
- PUSHGATEWAY_URL: Pushgateway URL (default: localhost:9091)
"""

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator import ValidationReport, TierResult

logger = logging.getLogger(__name__)

# Check if prometheus_client is available
try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        push_to_gateway,
    )

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    CollectorRegistry = None
    Counter = None
    Gauge = None
    Histogram = None
    push_to_gateway = None

# Configuration
PUSHGATEWAY_URL = os.environ.get("PUSHGATEWAY_URL", "localhost:9091")

# Isolated registry for validation metrics (don't pollute global)
_registry = None
_validation_runs = None
_validation_duration = None
_validation_score = None
_validation_blockers = None
_warned_once = False


def _initialize_metrics():
    """Initialize metrics on first use (lazy initialization)."""
    global \
        _registry, \
        _validation_runs, \
        _validation_duration, \
        _validation_score, \
        _validation_blockers

    if not METRICS_AVAILABLE:
        return False

    if _registry is not None:
        return True

    _registry = CollectorRegistry()

    _validation_runs = Counter(
        "validation_runs_total",
        "Total validation runs",
        ["tier", "result", "project"],
        registry=_registry,
    )

    _validation_duration = Histogram(
        "validation_duration_seconds",
        "Validation duration per validator",
        ["tier", "validator"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        registry=_registry,
    )

    _validation_score = Gauge(
        "validation_score",
        "Current validation score (pass rate)",
        ["tier", "project"],
        registry=_registry,
    )

    _validation_blockers = Gauge(
        "validation_blockers_count",
        "Number of blockers found",
        ["project", "validator"],
        registry=_registry,
    )

    return True


def push_validation_metrics(
    result: "TierResult | ValidationReport",
    project: str,
) -> bool:
    """
    Push validation metrics to Prometheus Pushgateway.

    Args:
        result: TierResult or ValidationReport from validation run
        project: Project name for metric labels

    Returns:
        True if metrics were pushed successfully, False otherwise

    Note:
        - No-op if prometheus_client is not installed
        - Catches connection errors and logs warning (doesn't crash)
    """
    global _warned_once

    if not METRICS_AVAILABLE:
        if not _warned_once:
            logger.warning(
                "prometheus_client not installed - metrics will not be pushed. "
                "Install with: pip install prometheus_client"
            )
            _warned_once = True
        return False

    if not _initialize_metrics():
        return False

    try:
        # Handle both TierResult and ValidationReport
        # TierResult has .tier and .results
        # ValidationReport has .tiers list
        if hasattr(result, "tiers"):
            # ValidationReport - push metrics for all tiers
            for tier_result in result.tiers:
                _push_tier_metrics(tier_result, project)
        else:
            # Single TierResult
            _push_tier_metrics(result, project)

        # Push to gateway
        push_to_gateway(
            gateway=PUSHGATEWAY_URL,
            job="validation_orchestrator",
            grouping_key={"project": project},
            registry=_registry,
        )

        logger.debug(f"Metrics pushed to {PUSHGATEWAY_URL} for project {project}")
        return True

    except Exception as e:
        # Log warning but don't crash - metrics are optional
        logger.warning(f"Failed to push metrics to Pushgateway: {e}")
        return False


def _push_tier_metrics(tier_result: "TierResult", project: str) -> None:
    """Push metrics for a single tier result."""
    tier_name = tier_result.tier.name.lower()
    tier_value = str(tier_result.tier.value)

    # Increment run counter
    result_label = "pass" if tier_result.passed else "fail"
    _validation_runs.labels(
        tier=tier_value,
        result=result_label,
        project=project,
    ).inc()

    # Track blockers and duration per validator
    passed_count = 0
    total_count = len(tier_result.results)

    for validator_result in tier_result.results:
        # Record duration
        if validator_result.duration_ms > 0:
            _validation_duration.labels(
                tier=tier_value,
                validator=validator_result.dimension,
            ).observe(validator_result.duration_ms / 1000.0)  # Convert to seconds

        # Track blockers (only for failed validators)
        if not validator_result.passed:
            _validation_blockers.labels(
                project=project,
                validator=validator_result.dimension,
            ).set(1)
        else:
            passed_count += 1
            # Reset blocker count for passing validators
            _validation_blockers.labels(
                project=project,
                validator=validator_result.dimension,
            ).set(0)

    # Calculate and set score (percentage of passed validators)
    score = (passed_count / total_count * 100) if total_count > 0 else 100.0
    _validation_score.labels(
        tier=tier_value,
        project=project,
    ).set(score)


def clear_metrics() -> None:
    """Clear all metrics (useful for testing)."""
    global \
        _registry, \
        _validation_runs, \
        _validation_duration, \
        _validation_score, \
        _validation_blockers
    _registry = None
    _validation_runs = None
    _validation_duration = None
    _validation_score = None
    _validation_blockers = None
