#!/usr/bin/env python3
"""
Sync canonical.yaml to Backstage catalog entities.
Generates catalog-info.yaml files from canonical.yaml SSOT.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List

CANONICAL_PATH = Path.home() / ".claude" / "canonical.yaml"
BACKSTAGE_CATALOG_DIR = Path("/media/sam/1TB/backstage-portal/catalog")


def load_canonical() -> Dict[str, Any]:
    """Load canonical.yaml if it exists."""
    if not CANONICAL_PATH.exists():
        print(f"Warning: {CANONICAL_PATH} not found")
        return {}

    with open(CANONICAL_PATH) as f:
        return yaml.safe_load(f) or {}


def generate_catalog_entity(
    repo_name: str, repo_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate a Backstage Component entity from repo config."""
    # Convert repo name to backstage-compatible name
    entity_name = repo_name.lower().replace("_", "-")

    annotations = {"backstage.io/techdocs-ref": "dir:."}

    # Add GitHub slug if available
    if "github" in repo_config:
        github_config = repo_config["github"]
        if (
            isinstance(github_config, dict)
            and "org" in github_config
            and "repo" in github_config
        ):
            annotations["github.com/project-slug"] = (
                f"{github_config['org']}/{github_config['repo']}"
            )
        elif isinstance(github_config, str):
            annotations["github.com/project-slug"] = github_config

    # Add Grafana selector if available
    if "grafana" in repo_config:
        annotations["grafana/dashboard-selector"] = repo_config["grafana"]

    entity = {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {
            "name": entity_name,
            "description": repo_config.get("description", f"{repo_name} repository"),
            "annotations": annotations,
            "tags": repo_config.get("tags", []),
        },
        "spec": {
            "type": repo_config.get("type", "service"),
            "lifecycle": repo_config.get("lifecycle", "production"),
            "owner": "user:default/sam",
            "system": "claude-infrastructure",
        },
    }

    return entity


def sync_repos(canonical: Dict[str, Any]) -> List[str]:
    """Sync repository definitions to catalog entities."""
    synced = []

    repos = canonical.get("repositories", {})
    for repo_name, repo_config in repos.items():
        if not isinstance(repo_config, dict):
            continue

        # Get repo path from canonical or construct default
        repo_path = repo_config.get("path", f"/media/sam/1TB/{repo_name}")
        catalog_file = Path(repo_path) / "catalog-info.yaml"

        # Skip if directory doesn't exist
        if not Path(repo_path).exists():
            print(f"Skipping {repo_name}: directory not found at {repo_path}")
            continue

        # Generate and write entity
        entity = generate_catalog_entity(repo_name, repo_config)

        with open(catalog_file, "w") as f:
            yaml.dump(entity, f, default_flow_style=False, sort_keys=False)

        synced.append(repo_name)
        print(f"Synced: {repo_name} -> {catalog_file}")

    return synced


def main():
    print("=== Backstage Catalog Sync ===")
    print(f"Source: {CANONICAL_PATH}")
    print()

    canonical = load_canonical()

    if not canonical:
        print("No canonical configuration found. Creating sample entries...")
        return 0

    synced = sync_repos(canonical)

    print()
    print(f"Synced {len(synced)} repositories to Backstage catalog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
