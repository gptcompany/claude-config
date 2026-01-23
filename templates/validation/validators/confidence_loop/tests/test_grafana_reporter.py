#!/usr/bin/env python3
"""Tests for GrafanaReporter - metrics push for confidence loops."""

import urllib.error
from unittest.mock import patch, MagicMock, Mock


from validators.confidence_loop.grafana_reporter import GrafanaReporter
from validators.confidence_loop.loop_controller import LoopState, RefinementStage


class TestGrafanaReporterInit:
    """Test GrafanaReporter initialization."""

    def test_init_with_explicit_values(self):
        """Test initialization with explicit values."""
        reporter = GrafanaReporter(
            grafana_url="http://localhost:3000",
            api_key="test-key",
            timeout=10.0,
        )
        assert reporter.grafana_url == "http://localhost:3000"
        assert reporter.api_key == "test-key"
        assert reporter.timeout == 10.0

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization from environment variables."""
        monkeypatch.setenv("GRAFANA_URL", "http://grafana:3000")
        monkeypatch.setenv("GRAFANA_API_KEY", "env-api-key")

        reporter = GrafanaReporter()
        assert reporter.grafana_url == "http://grafana:3000"
        assert reporter.api_key == "env-api-key"

    def test_init_without_config(self):
        """Test initialization without any configuration."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            assert reporter.grafana_url is None
            assert reporter.api_key is None

    def test_is_configured_true(self):
        """Test is_configured returns True when URL is set."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        assert reporter.is_configured is True

    def test_is_configured_false(self):
        """Test is_configured returns False when URL is not set."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            assert reporter.is_configured is False


class TestGetHeaders:
    """Test header generation."""

    def test_headers_without_api_key(self):
        """Test headers when no API key is set."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        headers = reporter._get_headers()
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_api_key(self):
        """Test headers when API key is set."""
        reporter = GrafanaReporter(
            grafana_url="http://localhost:3000",
            api_key="test-api-key",
        )
        headers = reporter._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-api-key"


class TestPushIterationMetrics:
    """Test pushing iteration metrics."""

    def test_push_iteration_metrics_success(self):
        """Test successful metrics push."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        state = LoopState(
            iteration=3,
            stage=RefinementStage.STYLE,
            confidence=0.85,
        )

        with patch.object(reporter, "_make_request", return_value=(True, "OK")):
            result = reporter.push_iteration_metrics(state)
            assert result is True

    def test_push_iteration_metrics_not_configured(self):
        """Test metrics push when Grafana not configured."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)

            result = reporter.push_iteration_metrics(state)
            assert result is False

    def test_push_iteration_metrics_includes_all_fields(self):
        """Test that push includes all required metrics."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        state = LoopState(
            iteration=5,
            stage=RefinementStage.POLISH,
            confidence=0.95,
        )

        captured_data = {}

        def mock_request(endpoint, data=None):
            captured_data["endpoint"] = endpoint
            captured_data["data"] = data
            return True, "OK"

        with patch.object(reporter, "_make_request", mock_request):
            reporter.push_url = None  # Force annotation fallback
            reporter.push_iteration_metrics(state)

            assert captured_data.get("endpoint") == "/api/annotations"
            assert "5" in str(captured_data.get("data", {}).get("text", ""))

    def test_push_iteration_uses_push_gateway(self):
        """Test that push gateway is used when configured."""
        reporter = GrafanaReporter(
            grafana_url="http://localhost:3000",
            push_url="http://pushgateway:9091",
        )
        state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)

        with patch.object(reporter, "_push_to_gateway", return_value=True) as mock_push:
            result = reporter.push_iteration_metrics(state)
            assert result is True
            mock_push.assert_called_once()


class TestPushDimensionScores:
    """Test pushing dimension scores."""

    def test_push_dimension_scores_success(self):
        """Test successful dimension scores push."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        scores = {"visual": 0.85, "dom": 0.90, "perceptual": 0.88}

        with patch.object(reporter, "_make_request", return_value=(True, "OK")):
            result = reporter.push_dimension_scores(scores)
            assert result is True

    def test_push_dimension_scores_not_configured(self):
        """Test dimension scores push when Grafana not configured."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            result = reporter.push_dimension_scores({"visual": 0.85})
            assert result is False

    def test_push_dimension_scores_empty(self):
        """Test push with empty scores dict."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        result = reporter.push_dimension_scores({})
        assert result is True  # Empty dict is valid, nothing to push

    def test_push_dimension_scores_includes_all_dimensions(self):
        """Test that all dimensions are included in annotation."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        scores = {"visual": 0.80, "dom": 0.90}

        captured_data = {}

        def mock_request(endpoint, data):
            captured_data["data"] = data
            return True, "OK"

        with patch.object(reporter, "_make_request", mock_request):
            reporter.push_dimension_scores(scores)

            text = captured_data.get("data", {}).get("text", "")
            assert "visual" in text
            assert "dom" in text
            assert "80" in text or "0.80" in text  # percentage or decimal


class TestCreateAnnotation:
    """Test creating annotations."""

    def test_create_annotation_success(self):
        """Test successful annotation creation."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch.object(reporter, "_make_request", return_value=(True, "OK")):
            result = reporter.create_annotation(
                "Stage transition: LAYOUT -> STYLE",
                ["confidence-loop", "stage-change"],
            )
            assert result is True

    def test_create_annotation_not_configured(self):
        """Test annotation when Grafana not configured."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            result = reporter.create_annotation("test event")
            assert result is False

    def test_create_annotation_includes_event_and_tags(self):
        """Test annotation includes event text and tags."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        captured_data = {}

        def mock_request(endpoint, data):
            captured_data["endpoint"] = endpoint
            captured_data["data"] = data
            return True, "OK"

        with patch.object(reporter, "_make_request", mock_request):
            reporter.create_annotation("Loop terminated", ["termination", "success"])

            assert captured_data["endpoint"] == "/api/annotations"
            assert captured_data["data"]["text"] == "Loop terminated"
            assert "termination" in captured_data["data"]["tags"]

    def test_create_annotation_default_tags(self):
        """Test annotation uses default tags when none provided."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        captured_data = {}

        def mock_request(endpoint, data):
            captured_data["data"] = data
            return True, "OK"

        with patch.object(reporter, "_make_request", mock_request):
            reporter.create_annotation("test event", None)

            assert "confidence-loop" in captured_data["data"]["tags"]


class TestMakeRequest:
    """Test HTTP request handling."""

    def test_make_request_not_configured(self):
        """Test request fails when Grafana not configured."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is False
            assert "not configured" in message

    def test_make_request_success(self):
        """Test successful request."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        mock_response = MagicMock()
        mock_response.read.return_value = b'{"id": 1}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is True
            assert "id" in message

    def test_make_request_http_error(self):
        """Test handling of HTTP errors."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        error = urllib.error.HTTPError(
            url="http://localhost:3000/api/test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is False
            assert "401" in message
            assert reporter._available is True  # Server reachable

    def test_make_request_url_error(self):
        """Test handling of connection errors."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        error = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=error):
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is False
            assert "Connection" in message
            assert reporter._available is False

    def test_make_request_timeout(self):
        """Test handling of timeout errors."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is False
            assert "timed out" in message.lower()
            assert reporter._available is False

    def test_make_request_generic_error(self):
        """Test handling of generic errors."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch("urllib.request.urlopen", side_effect=Exception("Unknown error")):
            success, message = reporter._make_request("/api/test", {"key": "value"})

            assert success is False
            assert "Error" in message
            assert reporter._available is False

    def test_make_request_strips_trailing_slash(self):
        """Test that trailing slash is handled correctly."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000/")

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            reporter._make_request("/api/test", {"key": "value"})

            # Check URL doesn't have double slash
            call_args = mock_open.call_args[0][0]
            assert "//api" not in call_args.full_url

    def test_make_request_get_method(self):
        """Test GET request doesn't include body."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            reporter._make_request("/api/health", method="GET")

            call_args = mock_open.call_args[0][0]
            assert call_args.method == "GET"


class TestGrafanaUnavailable:
    """Test graceful degradation when Grafana is unavailable."""

    def test_graceful_degradation_push_metrics(self):
        """Test push_iteration_metrics handles unavailable Grafana."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)

        with patch.object(
            reporter, "_make_request", return_value=(False, "unavailable")
        ):
            result = reporter.push_iteration_metrics(state)
            # Should return False but not raise
            assert result is False

    def test_graceful_degradation_push_dimension_scores(self):
        """Test push_dimension_scores handles unavailable Grafana."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch.object(
            reporter, "_make_request", return_value=(False, "unavailable")
        ):
            result = reporter.push_dimension_scores({"visual": 0.85})
            assert result is False

    def test_graceful_degradation_create_annotation(self):
        """Test create_annotation handles unavailable Grafana."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch.object(
            reporter, "_make_request", return_value=(False, "unavailable")
        ):
            result = reporter.create_annotation("test event")
            assert result is False


class TestMissingCredentials:
    """Test handling of missing credentials."""

    def test_push_without_api_key(self):
        """Test that push works without API key (if Grafana allows)."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        state = LoopState(iteration=1, stage=RefinementStage.LAYOUT, confidence=0.5)

        # Should not raise, just include basic headers
        with patch.object(reporter, "_make_request", return_value=(True, "OK")):
            result = reporter.push_iteration_metrics(state)
            assert result is True


class TestCheckAvailability:
    """Test availability checking."""

    def test_check_availability_success(self):
        """Test availability check when Grafana is up."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch.object(reporter, "_make_request", return_value=(True, "OK")):
            result = reporter.check_availability()
            assert result is True

    def test_check_availability_failure(self):
        """Test availability check when Grafana is down."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")

        with patch.object(
            reporter, "_make_request", return_value=(False, "unavailable")
        ):
            result = reporter.check_availability()
            assert result is False

    def test_check_availability_not_configured(self):
        """Test availability check when not configured."""
        with patch.dict("os.environ", {}, clear=True):
            reporter = GrafanaReporter()
            result = reporter.check_availability()
            assert result is False


class TestPushGateway:
    """Test Prometheus push gateway integration."""

    def test_push_to_gateway_success(self):
        """Test successful push to gateway."""
        reporter = GrafanaReporter(
            grafana_url="http://localhost:3000",
            push_url="http://pushgateway:9091",
        )

        mock_response = MagicMock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = reporter._push_to_gateway({"metric": 1.0})
            assert result is True

    def test_push_to_gateway_no_url(self):
        """Test push to gateway when not configured."""
        reporter = GrafanaReporter(grafana_url="http://localhost:3000")
        result = reporter._push_to_gateway({"metric": 1.0})
        assert result is False

    def test_push_to_gateway_error(self):
        """Test push to gateway error handling."""
        reporter = GrafanaReporter(
            grafana_url="http://localhost:3000",
            push_url="http://pushgateway:9091",
        )

        with patch(
            "urllib.request.urlopen", side_effect=Exception("Connection refused")
        ):
            result = reporter._push_to_gateway({"metric": 1.0})
            assert result is False
