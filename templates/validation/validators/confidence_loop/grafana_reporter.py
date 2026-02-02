#!/usr/bin/env python3
"""Grafana Reporter - Metrics push for confidence loops."""

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from .loop_controller import LoopState

logger = logging.getLogger(__name__)


class GrafanaReporter:
    def __init__(
        self,
        grafana_url: str | None = None,
        api_key: str | None = None,
        push_url: str | None = None,
        timeout: float = 5.0,
    ):
        self.grafana_url = grafana_url or os.getenv("GRAFANA_URL")
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY")
        self.push_url = push_url or os.getenv("GRAFANA_PUSH_URL")
        self.timeout = timeout
        self._available: bool | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.grafana_url)

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _make_request(
        self, endpoint: str, data: dict[str, Any] | None = None, method: str = "POST"
    ) -> tuple[bool, str]:
        if not self.grafana_url:
            return False, "Grafana URL not configured"

        url = f"{self.grafana_url.rstrip('/')}{endpoint}"

        try:
            body = json.dumps(data).encode("utf-8") if data else None
            request = urllib.request.Request(
                url, data=body, headers=self._get_headers(), method=method
            )

            with urllib.request.urlopen(
                request, timeout=self.timeout
            ) as response:  # nosec B310 - internal Grafana API, not user input
                self._available = True
                return True, response.read().decode("utf-8")

        except urllib.error.HTTPError as e:
            self._available = True
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
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping metrics push")
            return False

        metrics = {
            "confidence_loop_iteration": state.iteration,
            "confidence_loop_confidence": state.confidence,
            "confidence_loop_stage": state.stage.value if state.stage else "unknown",
        }

        if self.push_url:
            return self._push_to_gateway(metrics)

        return self._push_metrics_as_annotation(metrics)

    def _push_to_gateway(self, metrics: dict[str, Any]) -> bool:
        if not self.push_url:
            return False

        try:
            lines = [
                f"{name} {value}"
                for name, value in metrics.items()
                if isinstance(value, (int, float))
            ]
            body = "\n".join(lines).encode("utf-8")
            request = urllib.request.Request(
                self.push_url,
                data=body,
                headers={"Content-Type": "text/plain"},
                method="POST",
            )

            with urllib.request.urlopen(
                request, timeout=self.timeout
            ):  # nosec B310 - internal push gateway, not user input
                return True

        except Exception as e:
            logger.warning(f"Push gateway error: {e}")
            return False

    def _push_metrics_as_annotation(self, metrics: dict[str, Any]) -> bool:
        annotation_data = {
            "text": f"Iteration {metrics.get('confidence_loop_iteration', 0)}: "
            f"confidence={metrics.get('confidence_loop_confidence', 0):.2%}",
            "tags": ["confidence-loop", "metrics"],
        }
        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def push_dimension_scores(self, scores: dict[str, float]) -> bool:
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping dimension scores push")
            return False

        if not scores:
            return True

        score_lines = [f"{dim}={score:.2%}" for dim, score in scores.items()]
        annotation_data = {
            "text": f"Dimension scores: {', '.join(score_lines)}",
            "tags": ["confidence-loop", "dimensions"],
        }

        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def create_annotation(self, event: str, tags: list[str] | None = None) -> bool:
        if not self.is_configured:
            logger.debug("Grafana not configured, skipping annotation")
            return False

        annotation_data = {"text": event, "tags": tags or ["confidence-loop"]}
        success, _ = self._make_request("/api/annotations", annotation_data)
        return success

    def check_availability(self) -> bool:
        if not self.is_configured:
            return False
        success, _ = self._make_request("/api/health", method="GET")
        return success


__all__ = ["GrafanaReporter"]
