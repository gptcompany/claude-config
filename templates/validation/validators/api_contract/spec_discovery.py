#!/usr/bin/env python3
"""
Spec Discovery - Auto-find OpenAPI specs in a project.

Searches standard locations and glob patterns.
"""

from pathlib import Path


class SpecDiscovery:
    """
    Auto-discover OpenAPI specs in a project.

    Usage:
        discovery = SpecDiscovery()
        specs = discovery.find_specs(Path("."))
        for spec in specs:
            print(spec)
    """

    STANDARD_PATHS = [
        "openapi.yaml",
        "openapi.json",
        "openapi.yml",
        "api/openapi.yaml",
        "api/openapi.json",
        "api/openapi.yml",
        "docs/openapi.yaml",
        "docs/openapi.json",
        "docs/openapi.yml",
        "swagger.yaml",
        "swagger.json",
        "swagger.yml",
        "spec/openapi.yaml",
        "spec/openapi.json",
    ]

    GLOB_PATTERNS = [
        "**/openapi*.yaml",
        "**/openapi*.yml",
        "**/openapi*.json",
        "**/swagger*.yaml",
        "**/swagger*.yml",
        "**/swagger*.json",
    ]

    def __init__(self, custom_paths: list[str] | None = None):
        """
        Initialize spec discovery.

        Args:
            custom_paths: Additional paths to check (from config)
        """
        self.custom_paths = custom_paths or []

    def find_specs(self, project_root: Path) -> list[Path]:
        """
        Find all OpenAPI specs in project.

        Args:
            project_root: Root directory to search

        Returns:
            List of paths to OpenAPI spec files
        """
        specs: set[Path] = set()

        # Check standard paths
        for rel_path in self.STANDARD_PATHS:
            spec_path = project_root / rel_path
            if spec_path.exists() and spec_path.is_file():
                specs.add(spec_path.resolve())

        # Check custom paths from config
        for rel_path in self.custom_paths:
            spec_path = project_root / rel_path
            if spec_path.exists() and spec_path.is_file():
                specs.add(spec_path.resolve())

        # Glob patterns
        for pattern in self.GLOB_PATTERNS:
            for match in project_root.glob(pattern):
                if match.is_file():
                    # Skip common non-spec directories
                    if any(
                        part in ("node_modules", ".git", "venv", "__pycache__")
                        for part in match.parts
                    ):
                        continue
                    specs.add(match.resolve())

        return sorted(specs)

    def find_baseline(self, project_root: Path, config: dict) -> Path | None:
        """
        Find baseline spec for comparison.

        Args:
            project_root: Root directory
            config: Validation config with optional baseline_spec path

        Returns:
            Path to baseline spec or None
        """
        baseline_path = config.get("baseline_spec")
        if baseline_path:
            full_path = project_root / baseline_path
            if full_path.exists():
                return full_path.resolve()
        return None


# Export for testing
__all__ = ["SpecDiscovery"]
