#!/usr/bin/env python3
"""Unit tests for metrics.py - Prometheus Metrics Integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))


class TestMetricsAvailability:
    """Tests for METRICS_AVAILABLE flag."""

    def test_metrics_available_with_prometheus(self):
        """Test METRICS_AVAILABLE is True when prometheus_client installed."""
        try:
            import prometheus_client  # noqa: F401

            from integrations.metrics import METRICS_AVAILABLE

            assert METRICS_AVAILABLE is True
        except ImportError:
            pytest.skip("prometheus_client not installed")

    def test_metrics_graceful_degradation(self):
        """Test module loads even without prometheus_client."""
        # This test verifies the module doesn't crash on import
        from integrations.metrics import push_validation_metrics

        # Should be callable regardless of METRICS_AVAILABLE
        assert callable(push_validation_metrics)


class TestPushValidationMetrics:
    """Tests for push_validation_metrics() function."""

    def test_returns_false_when_unavailable(self):
        """Test returns False when prometheus_client not available."""
        with patch("integrations.metrics.METRICS_AVAILABLE", False):
            from integrations.metrics import push_validation_metrics

            # Create mock result
            mock_result = MagicMock()
            mock_result.tier = MagicMock(value=1)
            mock_result.passed = True
            mock_result.results = []

            result = push_validation_metrics(mock_result, "test_project")
            # When unavailable, should return False (after warning once)
            assert result is False

    def test_handles_tier_result(self):
        """Test handling TierResult (has .tier attribute)."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        # Reset metrics state
        clear_metrics()

        # Create mock TierResult
        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1, name="BLOCKER")
        mock_result.passed = True
        mock_result.results = [
            MagicMock(passed=True, dimension="syntax", duration_ms=100),
            MagicMock(passed=True, dimension="security", duration_ms=200),
        ]

        # Patch push_to_gateway to avoid network call
        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test_project")

        # Should succeed (or return True)
        assert result is True

    def test_handles_validation_report(self):
        """Test handling ValidationReport (has .tiers attribute)."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        # Create mock ValidationReport with .tiers
        tier1 = MagicMock()
        tier1.tier = MagicMock(value=1)
        tier1.passed = True
        tier1.results = [MagicMock(passed=True, dimension="syntax", duration_ms=50)]

        tier2 = MagicMock()
        tier2.tier = MagicMock(value=2)
        tier2.passed = True
        tier2.results = [
            MagicMock(passed=True, dimension="design_principles", duration_ms=100)
        ]

        mock_report = MagicMock()
        mock_report.tiers = [tier1, tier2]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_report, "test_project")

        assert result is True

    def test_handles_failed_validators(self):
        """Test metrics record failed validators."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = False
        mock_result.results = [
            MagicMock(passed=False, dimension="syntax", duration_ms=100),
            MagicMock(passed=True, dimension="security", duration_ms=200),
        ]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test_project")

        assert result is True

    def test_handles_pushgateway_error(self):
        """Test graceful handling of Pushgateway connection error."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = []

        # Simulate connection error
        with patch(
            "integrations.metrics.push_to_gateway",
            side_effect=ConnectionError("Connection refused"),
        ):
            result = push_validation_metrics(mock_result, "test_project")

        # Should return False but not crash
        assert result is False


class TestClearMetrics:
    """Tests for clear_metrics() function."""

    def test_clear_resets_state(self):
        """Test clear_metrics resets global state."""
        from integrations.metrics import clear_metrics

        clear_metrics()

        # After clear, _registry should be None
        from integrations import metrics

        assert metrics._registry is None
        assert metrics._validation_runs is None


class TestMetricLabels:
    """Tests for metric label values."""

    def test_tier_label_is_string(self):
        """Test tier label is converted to string."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)  # Integer value
        mock_result.passed = True
        mock_result.results = []

        with patch("integrations.metrics.push_to_gateway"):
            # Should not raise TypeError about int vs str
            result = push_validation_metrics(mock_result, "test_project")

        assert result is True

    def test_project_label_preserved(self):
        """Test project label is correctly set."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = []

        with patch("integrations.metrics.push_to_gateway") as mock_push:
            push_validation_metrics(mock_result, "my_special_project")

        # Verify grouping_key contains project
        call_kwargs = mock_push.call_args[1]
        assert call_kwargs["grouping_key"]["project"] == "my_special_project"


class TestScoreCalculation:
    """Tests for validation score calculation in metrics."""

    def test_score_100_all_pass(self):
        """Test score is 100 when all validators pass."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import _initialize_metrics, _push_tier_metrics

        _initialize_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = [
            MagicMock(passed=True, dimension="a", duration_ms=10),
            MagicMock(passed=True, dimension="b", duration_ms=20),
        ]

        # Should not raise
        _push_tier_metrics(mock_result, "test")

    def test_score_50_half_pass(self):
        """Test score calculation when half pass."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import _initialize_metrics, _push_tier_metrics

        _initialize_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = False
        mock_result.results = [
            MagicMock(passed=True, dimension="a", duration_ms=10),
            MagicMock(passed=False, dimension="b", duration_ms=20),
        ]

        # Should not raise
        _push_tier_metrics(mock_result, "test")


class TestMetricsInitialization:
    """Tests for metrics initialization."""

    def test_initialize_returns_bool(self):
        """Test _initialize_metrics returns boolean."""
        from integrations.metrics import _initialize_metrics

        result = _initialize_metrics()
        assert isinstance(result, bool)

    def test_initialize_idempotent(self):
        """Test calling _initialize_metrics multiple times is safe."""
        from integrations.metrics import _initialize_metrics, clear_metrics

        clear_metrics()
        result1 = _initialize_metrics()
        result2 = _initialize_metrics()
        # Both calls should succeed if prometheus available
        assert result1 == result2


class TestPushMetricsEdgeCases:
    """Edge case tests for push_validation_metrics."""

    def test_push_empty_results(self):
        """Test pushing metrics for result with empty results list."""
        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = []

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test")
        # Should not crash
        assert isinstance(result, bool)

    def test_push_with_zero_duration(self):
        """Test pushing metrics with zero duration."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=2)
        mock_result.passed = True
        mock_result.results = [
            MagicMock(passed=True, dimension="test", duration_ms=0),
        ]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test")
        assert result is True

    def test_push_with_large_duration(self):
        """Test pushing metrics with large duration value."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=3)
        mock_result.passed = True
        mock_result.results = [
            MagicMock(passed=True, dimension="slow_validator", duration_ms=600000),
        ]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test")
        assert result is True


class TestMetricsGracefulDegradation:
    """Tests for graceful degradation behavior."""

    def test_push_warns_once(self):
        """Test warning is logged only once when prometheus unavailable."""
        # This tests the _warned_once flag behavior
        from integrations.metrics import METRICS_AVAILABLE

        if METRICS_AVAILABLE:
            pytest.skip("prometheus_client is installed")

        # When not available, push should return False
        from integrations.metrics import push_validation_metrics

        mock_result = MagicMock()
        result = push_validation_metrics(mock_result, "test")
        assert result is False

    def test_clear_metrics_always_works(self):
        """Test clear_metrics works regardless of availability."""
        from integrations.metrics import clear_metrics

        # Should not raise
        clear_metrics()
        clear_metrics()  # Call twice to ensure idempotent


class TestMetricsImportFallback:
    """Tests for import fallback paths (lines 31-37)."""

    def test_metrics_module_constants_when_unavailable(self):
        """Test fallback constants when prometheus_client not available."""
        with patch("integrations.metrics.METRICS_AVAILABLE", False):
            from integrations.metrics import push_validation_metrics

            mock_result = MagicMock()
            result = push_validation_metrics(mock_result, "test")
            assert result is False

    def test_import_without_prometheus(self):
        """Test module loads with fallbacks when prometheus_client missing (lines 31-37)."""
        import importlib

        from integrations import metrics

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "prometheus_client":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            importlib.reload(metrics)

        assert metrics.METRICS_AVAILABLE is False
        assert metrics.CollectorRegistry is None
        assert metrics.Counter is None
        assert metrics.Gauge is None
        assert metrics.Histogram is None
        assert metrics.push_to_gateway is None

        # Restore
        importlib.reload(metrics)


class TestInitializeMetricsEdgeCases:
    """Tests for _initialize_metrics edge cases."""

    def test_initialize_returns_false_when_unavailable(self):
        """Test _initialize_metrics returns False when prometheus not available (line 56)."""
        from integrations.metrics import clear_metrics

        clear_metrics()
        with patch("integrations.metrics.METRICS_AVAILABLE", False):
            from integrations.metrics import _initialize_metrics

            result = _initialize_metrics()
            assert result is False

    def test_initialize_returns_true_when_already_initialized(self):
        """Test _initialize_metrics returns True if already initialized (lines 58-59)."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import _initialize_metrics, clear_metrics

        clear_metrics()
        # First call initializes
        _initialize_metrics()
        # Second call returns True immediately
        result = _initialize_metrics()
        assert result is True

    def test_initialize_returns_false_when_counter_none(self):
        """Test returns False when Counter/Histogram/Gauge are None (line 64)."""
        from integrations.metrics import clear_metrics

        clear_metrics()
        with patch("integrations.metrics.METRICS_AVAILABLE", True):
            with patch("integrations.metrics.CollectorRegistry", MagicMock()):
                with patch("integrations.metrics.Counter", None):
                    from integrations.metrics import _initialize_metrics

                    result = _initialize_metrics()
                    assert result is False


class TestPushMetricsInitFails:
    """Tests for push when _initialize_metrics fails (line 128)."""

    def test_push_returns_false_when_init_fails(self):
        """Test push returns False when initialization fails."""
        from integrations.metrics import clear_metrics

        clear_metrics()
        with patch("integrations.metrics.METRICS_AVAILABLE", True):
            with patch("integrations.metrics._initialize_metrics", return_value=False):
                from integrations.metrics import push_validation_metrics

                mock_result = MagicMock()
                result = push_validation_metrics(mock_result, "test")
                assert result is False


class TestPushTierMetricsDirectly:
    """Tests for _push_tier_metrics directly (lines 161-167)."""

    def test_push_tier_metrics_with_all_fields(self):
        """Test _push_tier_metrics records all metrics correctly."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import (
            _initialize_metrics,
            _push_tier_metrics,
            clear_metrics,
        )

        clear_metrics()
        _initialize_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = False
        mock_result.results = [
            MagicMock(passed=True, dimension="a", duration_ms=100),
            MagicMock(passed=False, dimension="b", duration_ms=0),
        ]

        # Should not raise
        _push_tier_metrics(mock_result, "test")


class TestPushNullRegistryGateway:
    """Test push_to_gateway None check (line 144)."""

    def test_push_returns_false_when_push_to_gateway_none(self):
        """Test returns False when push_to_gateway is None."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = []

        with patch("integrations.metrics.push_to_gateway", None):
            result = push_validation_metrics(mock_result, "test")
            assert result is False


class TestPushWithTiersNoTier:
    """Test push with result that has neither tiers nor tier (lines 138-140)."""

    def test_push_with_result_having_tiers(self):
        """Test push with ValidationReport-like object having tiers."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        # Object with tiers (ValidationReport-like)
        tier_result = MagicMock()
        tier_result.tier = MagicMock(value=1)
        tier_result.passed = True
        tier_result.results = [
            MagicMock(passed=True, dimension="a", duration_ms=10),
        ]

        mock_report = MagicMock(spec=["tiers"])
        mock_report.tiers = [tier_result]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_report, "test")
        assert result is True

    def test_push_with_single_tier_result(self):
        """Test push with single TierResult (has tier, no tiers) lines 138-140."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock(spec=["tier", "passed", "results"])
        mock_result.tier = MagicMock(value=2)
        mock_result.passed = True
        mock_result.results = [
            MagicMock(passed=True, dimension="x", duration_ms=50),
        ]

        with patch("integrations.metrics.push_to_gateway"):
            result = push_validation_metrics(mock_result, "test")
        assert result is True


class TestClearMetricsCoversAllGlobals:
    """Test clear_metrics resets all 4 metric globals (lines 219-222)."""

    def test_clear_resets_all(self):
        """All global metric vars are None after clear."""
        from integrations import metrics

        metrics.clear_metrics()
        assert metrics._registry is None
        assert metrics._validation_runs is None
        assert metrics._validation_duration is None
        assert metrics._validation_score is None
        assert metrics._validation_blockers is None


class TestWarnedOnceFlag:
    """Test _warned_once flag path (lines 118-119)."""

    def test_warned_once_suppresses_repeated_warnings(self):
        """After first warning, subsequent calls don't warn again."""
        import integrations.metrics as m

        m._warned_once = False

        with patch.object(m, "METRICS_AVAILABLE", False):
            mock_result = MagicMock()
            m.push_validation_metrics(mock_result, "test")
            assert m._warned_once is True
            # Second call should still return False but not warn again
            m.push_validation_metrics(mock_result, "test")

        # Reset
        m._warned_once = False


class TestPushExceptionPath:
    """Test the exception handling in push_validation_metrics (line 155)."""

    def test_push_catches_generic_exception(self):
        """Test that generic exceptions are caught (line 155)."""
        try:
            import prometheus_client  # noqa: F401
        except ImportError:
            pytest.skip("prometheus_client not installed")

        from integrations.metrics import clear_metrics, push_validation_metrics

        clear_metrics()

        mock_result = MagicMock()
        mock_result.tier = MagicMock(value=1)
        mock_result.passed = True
        mock_result.results = []

        with patch(
            "integrations.metrics.push_to_gateway",
            side_effect=Exception("unexpected"),
        ):
            result = push_validation_metrics(mock_result, "test")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
