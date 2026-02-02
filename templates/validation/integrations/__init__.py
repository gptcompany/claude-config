"""
Validation Framework Integrations

Provides optional integrations for observability:
- metrics: Prometheus metrics to Pushgateway
- sentry_context: Sentry context injection for debugging

All integrations gracefully degrade if dependencies are unavailable.
"""

from .metrics import METRICS_AVAILABLE, push_validation_metrics
from .sentry_context import (
    SENTRY_AVAILABLE,
    capture_validation_error,
    inject_validation_context,
)

__all__ = [
    "push_validation_metrics",
    "inject_validation_context",
    "capture_validation_error",
    "METRICS_AVAILABLE",
    "SENTRY_AVAILABLE",
]
