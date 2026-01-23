"""
Grafana dashboard templates for validation orchestrator.

Templates:
- validation-dashboard.json: Main validation metrics dashboard
"""

from pathlib import Path

DASHBOARD_DIR = Path(__file__).parent


def get_dashboard_path(name: str = "validation-dashboard") -> Path:
    """Get path to a dashboard template."""
    return DASHBOARD_DIR / f"{name}.json"


def load_dashboard(name: str = "validation-dashboard") -> dict:
    """Load a dashboard template as dict."""
    import json

    path = get_dashboard_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Dashboard template not found: {path}")
    return json.loads(path.read_text())
