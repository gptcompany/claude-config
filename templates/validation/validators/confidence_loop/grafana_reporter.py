#!/usr/bin/env python3
"""
Grafana Reporter - Metrics push for confidence loops.

Pushes iteration metrics, dimension scores, and annotations to Grafana
for dashboard visualization of confidence loop progress.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any

from .loop_controller import LoopState

logger = logging.getLogger(__name__)


class GrafanaReporter:
    """
    Grafana metrics reporter for confidence loops.

    Pushes metrics and annotations to Grafana for visualization:
    - confidence_loop_iteration (gauge)
    - confidence_loop_confidence (gauge, 0-1)
    - confidence_loop_stage (labeled gauge)
    - confidence_loop_dimension_score (labeled gauge per dimension)

    Gracefully degrades when Grafana is unavailable.

    Usage:
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        reporter.push_iteration_metrics(state)
        reporter.push_dimension_scores({"visual": 0.85, "dom": 0.90})
        reporter.create_annotation("stage_change", ["confidence-loop"])
    """

    def __init__(
        self,
        grafana_url: str | None = None,
        api_key: str | None = None,
        push_url: str | None = None,
        timeout: float = 5.0,
    ):
        """
        Initialize Grafana reporter.

        Args:
            grafana_url: Grafana base URL (or GRAFANA_URL env var)
            api_key: Grafana API key (or GRAFANA_API_KEY env var)
            push_url: Optional push gateway URL for metrics
            timeout: Request timeout in seconds
        """
        self.grafana_url = grafana_url or os.getenv("GRAFANA_URL")
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY")
        self.push_url = push_url or os.getenv("GRAFANA_PUSH_URL")
        self.timeout = timeout

        # Track connection status
        self._available: bool | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Grafana is configured (URL available)."""
        return bool(self.grafana_url)

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for Grafana API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _make_request(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> tuple[bool, str]:
        """
        Make HTTP request to Grafana API.

        Args:
            endpoint: API endpoint path
            data: JSON data to send
            method: HTTP method

        Returns:
            Tuple of (success, message)
        """
        if not self.grafana_url:
            return False, "Grafana URL not configured"

        url = f"{self.grafana_url.rstrip('/')}{endpoint}"

        try:
            body = json.dumps(data).encode("utf-8") if data else None
            request = urllib.request.Request(
                url,
                data=body,
                headers=self._get_headers(),
                method=method,
            )

            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self._available = True
                return True, response.read().decode("utf-8")

        except urllib.error.HTTPError as e:
            self._available = True  # Server is reachable, just returned an error
            logger.warning(f"Grafana HTTP error {e.code}: {e.reason}")
            return False, f"HTTP {e.code}: {e.reason}"

        except urllib.error.URLError as e:
            self._available = False
            logger.warning(f"Grafana unavailable: {e.reason}")
            return False, f"Connection failed: {e.reason}"

        except TimeoutError:
            self._available = False
            logger.warning("Grafana request timed out")
            return False, "Request timed out"

        except Exception as e:
            self._available = False
            logger.warning(f"Grafana request error: {e}")
            return False, f"Error: {e}"

    def push_iteration_metrics(self, state: LoopState) -> bool:
        """
        Push metrics for current iteration to Grafana.

        Metrics pushed:
        - confidence_loop_iteration: Current iteration number
        - confidence_loop_confidence: Current confidence (0-1)
        - confidence_loop_stage: Current refinement stage

        Args:
            state: Current loop state

        Returns:
            True if push succeeded, False otherwise
        """
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping metrics push")
            return False

        metrics = {
            "confidence_loop_iteration": state.iteration,
            "confidence_loop_confidence": state.confidence,
            "confidence_loop_stage": state.stage.value if state.stage else "unknown",
        }

        # If push gateway is configured, use that
        if self.push_url:
            return self._push_to_gateway(metrics)

        # Otherwise use Grafana's annotation API as a fallback for metrics
        # (annotations can carry structured data)
        return self._push_metrics_as_annotation(metrics)

    def _push_to_gateway(self, metrics: dict[str, Any]) -> bool:
        """Push metrics to Prometheus push gateway."""
        if not self.push_url:
            return False

        try:
            # Format as Prometheus exposition format
            lines = []
            for name, value in metrics.items():
                if isinstance(value, (int, float)):
                    lines.append(f"{name} {value}")

            body = "\n".join(lines).encode("utf-8")
            request = urllib.request.Request(
                self.push_url,
                data=body,
                headers={"Content-Type": "text/plain"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=self.timeout):
                return True

        except Exception as e:
            logger.warning(f"Push gateway error: {e}")
            return False

    def _push_metrics_as_annotation(self, metrics: dict[str, Any]) -> bool:
        """Push metrics as Grafana annotation (fallback method)."""
        annotation_data = {
            "text": f"Iteration {metrics.get('confidence_loop_iteration', 0)}: "
            f"confidence={metrics.get('confidence_loop_confidence', 0):.2%}",
            "tags": ["confidence-loop", "metrics"],
        }

        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def push_dimension_scores(self, scores: dict[str, float]) -> bool:
        """
        Push per-dimension scores to Grafana.

        Args:
            scores: Dict mapping dimension name to score (0-1)

        Returns:
            True if push succeeded, False otherwise
        """
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping dimension scores push")
            return False

        if not scores:
            return True  # Nothing to push

        # Format scores as annotation
        score_lines = [f"{dim}={score:.2%}" for dim, score in scores.items()]
        annotation_data = {
            "text": f"Dimension scores: {', '.join(score_lines)}",
            "tags": ["confidence-loop", "dimensions"],
        }

        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def create_annotation(self, event: str, tags: list[str] | None = None) -> bool:
        """
        Create annotation for significant events.

        Events like stage transitions, termination, errors are recorded
        as Grafana annotations for dashboard visualization.

        Args:
            event: Event description
            tags: Optional list of tags for the annotation

        Returns:
            True if annotation created, False otherwise
        """
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping annotation")
            return False

        annotation_data = {
            "text": event,
            "tags": tags or ["confidence-loop"],
        }

        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def check_availability(self) -> bool:
        """
        Check if Grafana is available and responding.

        Returns:
            True if Grafana is reachable, False otherwise
        """
        if not self.is_configured:
            return False

        # Use health endpoint
        success, _ = self._make_request("/api/health", method="GET")
        return success


__all__ = ["GrafanaReporter"]
