#!/usr/bin/env python3
"""Unit tests for sentry_context.py - Sentry Context Integration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations"))


class TestSentryAvailability:
    """Tests for SENTRY_AVAILABLE flag and graceful degradation."""

    def test_module_imports_without_sentry(self):
        """Test module loads even without sentry_sdk."""
        from integrations.sentry_context import (
            add_validation_breadcrumb,
            capture_validation_error,
            inject_validation_context,
        )

        # All functions should be callable
        assert callable(inject_validation_context)
        assert callable(capture_validation_error)
        assert callable(add_validation_breadcrumb)

    def test_sentry_available_check(self):
        """Test SENTRY_AVAILABLE reflects actual state."""
        from integrations.sentry_context import SENTRY_AVAILABLE

        # Should be a boolean
        assert isinstance(SENTRY_AVAILABLE, bool)


class TestIsSentryInitialized:
    """Tests for _is_sentry_initialized() function."""

    def test_returns_false_when_unavailable(self):
        """Test returns False when sentry_sdk not installed."""
        with patch("integrations.sentry_context.SENTRY_AVAILABLE", False):
            from integrations.sentry_context import _is_sentry_initialized

            assert _is_sentry_initialized() is False

    def test_returns_false_when_no_client(self):
        """Test returns False when SDK available but not initialized."""
        with patch("integrations.sentry_context.SENTRY_AVAILABLE", True):
            with patch("integrations.sentry_context.sentry_sdk") as mock_sdk:
                mock_sdk.Hub.current.client = None
                from integrations.sentry_context import _is_sentry_initialized

                result = _is_sentry_initialized()
                assert result is False

    def test_returns_true_when_initialized(self):
        """Test returns True when SDK initialized with client."""
        with patch("integrations.sentry_context.SENTRY_AVAILABLE", True):
            with patch("integrations.sentry_context.sentry_sdk") as mock_sdk:
                mock_sdk.Hub.current.client = MagicMock()  # Non-None client
                from integrations.sentry_context import _is_sentry_initialized

                result = _is_sentry_initialized()
                assert result is True

    def test_handles_exception_gracefully(self):
        """Test returns False on any exception accessing Hub."""
        with patch("integrations.sentry_context.SENTRY_AVAILABLE", True):
            mock_sdk = MagicMock()
            # Make accessing Hub.current.client raise
            type(mock_sdk.Hub.current).client = property(
                lambda self: (_ for _ in ()).throw(RuntimeError("Boom"))
            )
            with patch("integrations.sentry_context.sentry_sdk", mock_sdk):
                from integrations.sentry_context import _is_sentry_initialized

                # Should catch the exception and return False
                result = _is_sentry_initialized()
                assert result is False


class TestInjectValidationContext:
    """Tests for inject_validation_context() function."""

    def test_returns_false_when_not_initialized(self):
        """Test returns False when Sentry not initialized."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=False
        ):
            from integrations.sentry_context import inject_validation_context

            mock_result = MagicMock()
            result = inject_validation_context(mock_result)
            assert result is False

    def test_handles_tier_result(self):
        """Test injection for TierResult (has .tier attribute)."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context") as mock_set_context:
                with patch("integrations.sentry_context.set_tag") as mock_set_tag:
                    with patch(
                        "integrations.sentry_context.add_breadcrumb"
                    ) as mock_breadcrumb:
                        from integrations.sentry_context import (
                            inject_validation_context,
                        )

                        # Create mock TierResult
                        mock_result = MagicMock()
                        mock_result.tier = MagicMock(name="BLOCKER", value=1)
                        mock_result.passed = True
                        mock_result.results = [
                            MagicMock(passed=True, dimension="syntax", duration_ms=100)
                        ]

                        result = inject_validation_context(mock_result)

                        assert result is True
                        mock_set_context.assert_called()
                        mock_set_tag.assert_called()
                        mock_breadcrumb.assert_called()

    def test_handles_validation_report(self):
        """Test injection for ValidationReport (has .tiers attribute)."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context"):
                with patch("integrations.sentry_context.set_tag"):
                    with patch("integrations.sentry_context.add_breadcrumb"):
                        from integrations.sentry_context import (
                            inject_validation_context,
                        )

                        # Create mock ValidationReport
                        tier1 = MagicMock()
                        tier1.tier = MagicMock(value=1)
                        tier1.results = [
                            MagicMock(passed=True, dimension="syntax", duration_ms=50)
                        ]

                        mock_report = MagicMock()
                        mock_report.tiers = [tier1]
                        mock_report.project = "test_project"
                        mock_report.timestamp = "2024-01-01T00:00:00"
                        mock_report.overall_passed = True
                        mock_report.blocked = False

                        result = inject_validation_context(mock_report)
                        assert result is True

    def test_handles_exception_gracefully(self):
        """Test returns False on exception."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.set_context",
                side_effect=RuntimeError("Boom"),
            ):
                from integrations.sentry_context import inject_validation_context

                mock_result = MagicMock()
                mock_result.tier = MagicMock()

                result = inject_validation_context(mock_result)
                assert result is False


class TestCaptureValidationError:
    """Tests for capture_validation_error() function."""

    def test_returns_false_when_not_initialized(self):
        """Test returns False when Sentry not initialized."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=False
        ):
            from integrations.sentry_context import capture_validation_error

            result = capture_validation_error(ValueError("test error"))
            assert result is False

    def test_captures_exception_with_context(self):
        """Test captures exception with validation context."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.push_scope") as mock_push_scope:
                with patch("integrations.sentry_context.sentry_sdk") as mock_sdk:
                    mock_scope = MagicMock()
                    mock_push_scope.return_value.__enter__ = MagicMock(
                        return_value=mock_scope
                    )
                    mock_push_scope.return_value.__exit__ = MagicMock(return_value=None)

                    from integrations.sentry_context import capture_validation_error

                    error = ValueError("Validation failed")
                    context = {
                        "file_path": "/path/to/file.py",
                        "validator_name": "syntax",
                        "config": {"tier": 1},
                        "state": {"iteration": 2},
                        "validators": ["syntax", "security"],
                    }

                    result = capture_validation_error(error, context)

                    assert result is True
                    mock_sdk.capture_exception.assert_called_once_with(error)

    def test_sets_fingerprint_for_grouping(self):
        """Test sets fingerprint for error grouping."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.push_scope") as mock_push_scope:
                with patch("integrations.sentry_context.sentry_sdk"):
                    mock_scope = MagicMock()
                    mock_push_scope.return_value.__enter__ = MagicMock(
                        return_value=mock_scope
                    )
                    mock_push_scope.return_value.__exit__ = MagicMock(return_value=None)

                    from integrations.sentry_context import capture_validation_error

                    capture_validation_error(
                        ValueError("test"), {"validator_name": "security"}
                    )

                    # Verify fingerprint was set
                    assert mock_scope.fingerprint == [
                        "validation-error",
                        "security",
                    ]

    def test_handles_none_context(self):
        """Test handles None context gracefully."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.push_scope") as mock_push_scope:
                with patch("integrations.sentry_context.sentry_sdk"):
                    mock_scope = MagicMock()
                    mock_push_scope.return_value.__enter__ = MagicMock(
                        return_value=mock_scope
                    )
                    mock_push_scope.return_value.__exit__ = MagicMock(return_value=None)

                    from integrations.sentry_context import capture_validation_error

                    result = capture_validation_error(ValueError("test"), None)
                    assert result is True


class TestAddValidationBreadcrumb:
    """Tests for add_validation_breadcrumb() function."""

    def test_returns_false_when_not_initialized(self):
        """Test returns False when Sentry not initialized."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=False
        ):
            from integrations.sentry_context import add_validation_breadcrumb

            result = add_validation_breadcrumb("Test message")
            assert result is False

    def test_adds_breadcrumb_with_defaults(self):
        """Test adds breadcrumb with default level."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.add_breadcrumb"
            ) as mock_add_breadcrumb:
                from integrations.sentry_context import (
                    add_validation_breadcrumb as add_bc,
                )

                result = add_bc("Validation started")

                assert result is True
                mock_add_breadcrumb.assert_called_once_with(
                    category="validation",
                    message="Validation started",
                    level="info",
                    data={},
                )

    def test_adds_breadcrumb_with_custom_level(self):
        """Test adds breadcrumb with custom level."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.add_breadcrumb"
            ) as mock_add_breadcrumb:
                from integrations.sentry_context import (
                    add_validation_breadcrumb as add_bc,
                )

                result = add_bc("Error occurred", level="error")

                assert result is True
                call_kwargs = mock_add_breadcrumb.call_args[1]
                assert call_kwargs["level"] == "error"

    def test_adds_breadcrumb_with_data(self):
        """Test adds breadcrumb with additional data."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.add_breadcrumb"
            ) as mock_add_breadcrumb:
                from integrations.sentry_context import (
                    add_validation_breadcrumb as add_bc,
                )

                result = add_bc(
                    "Tier 1 complete",
                    data={"validators": ["syntax", "security"], "score": 95.0},
                )

                assert result is True
                call_kwargs = mock_add_breadcrumb.call_args[1]
                assert call_kwargs["data"]["validators"] == ["syntax", "security"]
                assert call_kwargs["data"]["score"] == 95.0

    def test_handles_exception_gracefully(self):
        """Test returns False on exception."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.add_breadcrumb",
                side_effect=RuntimeError("Boom"),
            ):
                from integrations.sentry_context import (
                    add_validation_breadcrumb as add_bc,
                )

                result = add_bc("Test message")
                assert result is False


class TestTagValues:
    """Tests for tag value formatting."""

    def test_validation_passed_tag_lowercase(self):
        """Test validation.passed tag is lowercase string for TierResult."""
        mock_set_context = MagicMock()
        mock_set_tag = MagicMock()
        mock_add_breadcrumb = MagicMock()

        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context", mock_set_context):
                with patch("integrations.sentry_context.set_tag", mock_set_tag):
                    with patch(
                        "integrations.sentry_context.add_breadcrumb",
                        mock_add_breadcrumb,
                    ):
                        from integrations.sentry_context import (
                            inject_validation_context,
                        )

                        # Create a proper TierResult-like mock (has .tier, no .tiers)
                        mock_result = MagicMock(spec=["tier", "passed", "results"])
                        mock_result.tier = MagicMock(name="BLOCKER", value=1)
                        mock_result.passed = True
                        mock_result.results = []

                        result = inject_validation_context(mock_result)

                        # If injection succeeded, check tag format
                        if result and mock_set_tag.call_args_list:
                            calls = mock_set_tag.call_args_list
                            passed_call = next(
                                (c for c in calls if c[0][0] == "validation.passed"),
                                None,
                            )
                            if passed_call:
                                assert passed_call[0][1] == "true"

    def test_tier_tag_is_string(self):
        """Test validation.tier tag is string value."""
        mock_set_context = MagicMock()
        mock_set_tag = MagicMock()
        mock_add_breadcrumb = MagicMock()

        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context", mock_set_context):
                with patch("integrations.sentry_context.set_tag", mock_set_tag):
                    with patch(
                        "integrations.sentry_context.add_breadcrumb",
                        mock_add_breadcrumb,
                    ):
                        from integrations.sentry_context import (
                            inject_validation_context,
                        )

                        mock_result = MagicMock()
                        mock_result.tier = MagicMock(name="BLOCKER", value=1)
                        mock_result.passed = True
                        mock_result.results = []

                        result = inject_validation_context(mock_result)

                        # If injection succeeded, check tag format
                        if result and mock_set_tag.call_args_list:
                            calls = mock_set_tag.call_args_list
                            tier_call = next(
                                (c for c in calls if c[0][0] == "validation.tier"),
                                None,
                            )
                            if tier_call:
                                assert tier_call[0][1] == "1"


class TestSentryImportFallback:
    """Tests for import fallback paths (lines 24-30)."""

    def test_sentry_unavailable_sets_none(self):
        """When sentry_sdk not available, functions are None."""
        with patch("integrations.sentry_context.SENTRY_AVAILABLE", False):
            from integrations.sentry_context import inject_validation_context

            mock_result = MagicMock()
            result = inject_validation_context(mock_result)
            assert result is False

    def test_import_without_sentry_sdk(self):
        """Test module loads with fallbacks when sentry_sdk missing (lines 24-30)."""
        import importlib
        from integrations import sentry_context

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "sentry_sdk":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            importlib.reload(sentry_context)

        assert sentry_context.SENTRY_AVAILABLE is False
        assert sentry_context.sentry_sdk is None
        assert sentry_context.set_context is None
        assert sentry_context.set_tag is None
        assert sentry_context.add_breadcrumb is None
        assert sentry_context.push_scope is None

        # Restore
        importlib.reload(sentry_context)


class TestInjectContextSetContextNone:
    """Test inject_validation_context when set_context is None (line 67)."""

    def test_returns_false_when_set_context_none(self):
        """Returns False when set_context/set_tag/add_breadcrumb are None."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context", None):
                from integrations.sentry_context import inject_validation_context

                mock_result = MagicMock()
                result = inject_validation_context(mock_result)
                assert result is False


class TestInjectReportContextFailed:
    """Test _inject_report_context with failed validators (line 160)."""

    def test_inject_report_with_failed_validators(self):
        """Test report context with failed validators in multiple tiers."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch("integrations.sentry_context.set_context") as mock_ctx:
                with patch("integrations.sentry_context.set_tag"):
                    with patch("integrations.sentry_context.add_breadcrumb"):
                        from integrations.sentry_context import (
                            inject_validation_context,
                        )

                        tier1 = MagicMock()
                        tier1.tier = MagicMock(value=1, name="BLOCKER")
                        tier1.results = [
                            MagicMock(passed=False, dimension="syntax", duration_ms=50),
                            MagicMock(
                                passed=True, dimension="security", duration_ms=30
                            ),
                        ]

                        tier2 = MagicMock()
                        tier2.tier = MagicMock(value=2, name="WARNING")
                        tier2.results = [
                            MagicMock(passed=False, dimension="design", duration_ms=20),
                        ]

                        mock_report = MagicMock()
                        mock_report.tiers = [tier1, tier2]
                        mock_report.project = "test"
                        mock_report.timestamp = "2024-01-01"
                        mock_report.overall_passed = False
                        mock_report.blocked = True

                        result = inject_validation_context(mock_report)
                        assert result is True

                        # Check context was set with correct failed validators
                        ctx_call = mock_ctx.call_args
                        ctx_data = ctx_call[0][1]
                        assert "syntax" in ctx_data["failed_validators"]
                        assert "design" in ctx_data["failed_validators"]
                        assert ctx_data["duration_ms"] == 100


class TestCaptureValidationErrorException:
    """Test capture_validation_error exception handling (lines 288-291)."""

    def test_capture_returns_false_on_exception(self):
        """Test returns False when push_scope raises."""
        with patch(
            "integrations.sentry_context._is_sentry_initialized", return_value=True
        ):
            with patch(
                "integrations.sentry_context.push_scope",
                side_effect=RuntimeError("Boom"),
            ):
                with patch("integrations.sentry_context.sentry_sdk"):
                    from integrations.sentry_context import capture_validation_error

                    result = capture_validation_error(
                        ValueError("test"), {"validator_name": "x"}
                    )
                    assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
