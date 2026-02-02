#!/usr/bin/env python3
"""Unit tests for dashboards/__init__.py - Dashboard utilities."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboards import DASHBOARD_DIR, get_dashboard_path, load_dashboard


class TestGetDashboardPath:
    """Tests for get_dashboard_path() function."""

    def test_default_dashboard_name(self):
        """Test getting default dashboard path."""
        path = get_dashboard_path()
        assert path.name == "validation-dashboard.json"
        assert path.parent == DASHBOARD_DIR

    def test_custom_dashboard_name(self):
        """Test getting custom dashboard path."""
        path = get_dashboard_path("custom-dashboard")
        assert path.name == "custom-dashboard.json"
        assert path.parent == DASHBOARD_DIR

    def test_returns_path_object(self):
        """Test that return type is Path."""
        path = get_dashboard_path()
        assert isinstance(path, Path)


class TestLoadDashboard:
    """Tests for load_dashboard() function."""

    def test_load_existing_dashboard(self):
        """Test loading an existing dashboard."""
        # Create a temp dashboard file
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_content = {
                "title": "Test Dashboard",
                "panels": [{"id": 1, "type": "graph"}],
            }
            dashboard_path = Path(tmpdir) / "test-dashboard.json"
            dashboard_path.write_text(json.dumps(dashboard_content))

            with patch("dashboards.DASHBOARD_DIR", Path(tmpdir)):
                result = load_dashboard("test-dashboard")

            assert result == dashboard_content
            assert result["title"] == "Test Dashboard"

    def test_load_nonexistent_dashboard(self):
        """Test loading a non-existent dashboard raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("dashboards.DASHBOARD_DIR", Path(tmpdir)):
                with pytest.raises(FileNotFoundError) as exc_info:
                    load_dashboard("nonexistent")

            assert "Dashboard template not found" in str(exc_info.value)

    def test_load_default_dashboard(self):
        """Test loading default dashboard if it exists."""
        # Try to load real dashboard if it exists
        try:
            result = load_dashboard()
            assert isinstance(result, dict)
            # Grafana dashboards typically have these fields
            assert "title" in result or "panels" in result or "uid" in result
        except FileNotFoundError:
            pytest.skip("Default dashboard not found")

    def test_load_returns_dict(self):
        """Test that load_dashboard returns a dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "test.json"
            dashboard_path.write_text('{"test": true}')

            with patch("dashboards.DASHBOARD_DIR", Path(tmpdir)):
                result = load_dashboard("test")

            assert isinstance(result, dict)
            assert result["test"] is True


class TestDashboardDir:
    """Tests for DASHBOARD_DIR constant."""

    def test_dashboard_dir_is_path(self):
        """Test DASHBOARD_DIR is a Path object."""
        assert isinstance(DASHBOARD_DIR, Path)

    def test_dashboard_dir_exists(self):
        """Test DASHBOARD_DIR points to existing directory."""
        assert DASHBOARD_DIR.exists()
        assert DASHBOARD_DIR.is_dir()

    def test_dashboard_dir_relative_to_module(self):
        """Test DASHBOARD_DIR is relative to module location."""
        # DASHBOARD_DIR should be the dashboards directory
        assert DASHBOARD_DIR.name == "dashboards"


class TestDashboardIntegration:
    """Integration tests for dashboard utilities."""

    def test_get_and_load_workflow(self):
        """Test getting path and loading dashboard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create dashboard
            dashboard_data = {"uid": "test-123", "title": "Integration Test"}
            dashboard_path = Path(tmpdir) / "my-dashboard.json"
            dashboard_path.write_text(json.dumps(dashboard_data))

            with patch("dashboards.DASHBOARD_DIR", Path(tmpdir)):
                # Get path
                path = get_dashboard_path("my-dashboard")
                assert path.exists()

                # Load dashboard
                loaded = load_dashboard("my-dashboard")
                assert loaded["uid"] == "test-123"

    def test_real_validation_dashboard_structure(self):
        """Test that real validation dashboard has expected structure."""
        try:
            dashboard = load_dashboard("validation-dashboard")

            # Common Grafana dashboard fields
            assert "title" in dashboard
            # Should have panels for validation metrics
            if "panels" in dashboard:
                assert len(dashboard["panels"]) > 0
        except FileNotFoundError:
            pytest.skip("Validation dashboard not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
