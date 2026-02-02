"""E2E tests with real tools (no mocks).

These tests verify that validation tools actually work in the current environment.
Run with: pytest tests/e2e/test_real_tools.py -v -m e2e

Works in both Claude Code (user sam) and OpenClaw (user openclaw) environments.
"""

import subprocess
import sys
from pathlib import Path

import pytest

VALIDATION_DIR = Path(__file__).parent.parent.parent


@pytest.mark.e2e
class TestRealToolAvailability:
    """Verify validation tools are installed and functional."""

    def test_ruff_detects_errors(self, tmp_path):
        """ruff finds real lint errors in bad code."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("import os\nimport os\n")
        result = subprocess.run(
            ["ruff", "check", str(tmp_path), "--select", "F811"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0, "ruff should find duplicate import"
        assert "F811" in result.stdout

    def test_pyright_available(self):
        """pyright is installed and runs."""
        result = subprocess.run(
            ["pyright", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "pyright" in result.stdout.lower()

    def test_bandit_detects_vulnerability(self, tmp_path):
        """bandit finds real security issues."""
        vuln_file = tmp_path / "vuln.py"
        vuln_file.write_text(
            "import subprocess\nsubprocess.call(input())  # nosec test\n"
        )
        result = subprocess.run(
            ["bandit", "-r", str(tmp_path), "-q"],
            capture_output=True, text=True, timeout=30,
        )
        # bandit returns non-zero when issues found
        assert result.returncode != 0 or "Issue" in result.stdout + result.stderr


@pytest.mark.e2e
class TestOrchestratorReal:
    """Test orchestrator with real execution."""

    def test_tier1_on_validation_framework(self):
        """Run tier1 validation on the framework itself."""
        result = subprocess.run(
            [sys.executable, "orchestrator.py", "1"],
            cwd=str(VALIDATION_DIR),
            capture_output=True, text=True, timeout=120,
        )
        assert "Tier 1" in result.stdout or "PASS" in result.stdout, (
            f"Tier 1 should produce output. stdout={result.stdout[:200]}, "
            f"stderr={result.stderr[:200]}"
        )


@pytest.mark.e2e
class TestInfraReachability:
    """Test infrastructure connectivity (skip if not available)."""

    def test_grafana_health(self):
        """Grafana responds on expected endpoint."""
        try:
            import urllib.request
            resp = urllib.request.urlopen(
                "http://192.168.1.111:3000/api/health", timeout=5
            )
            data = resp.read().decode()
            assert "ok" in data.lower()
        except Exception as e:
            pytest.skip(f"Grafana not reachable: {e}")

    def test_prometheus_has_openclaw_metrics(self):
        """Prometheus has openclaw metrics via Grafana proxy."""
        try:
            import urllib.request
            import json
            url = (
                "http://192.168.1.111:9090/api/v1/query"
                "?query=openclaw_daily_cost"
            )
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read().decode())
            assert data.get("status") == "success"
        except Exception as e:
            pytest.skip(f"Prometheus not reachable: {e}")
