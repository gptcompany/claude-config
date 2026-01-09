#!/usr/bin/env python3
"""
New Project Setup Script

Creates Claude Code skeleton for a new repository based on canonical.yaml.

Usage:
    python new-project.py                    # Auto-detect
    python new-project.py python             # With language
    python new-project.py python fastapi     # With framework
    python new-project.py --path /path/to/repo

Based on canonical.yaml SSOT pattern.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

CANONICAL_PATH = Path.home() / ".claude" / "canonical.yaml"

# Language detection patterns
LANGUAGE_PATTERNS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "typescript": ["package.json", "tsconfig.json"],
    "javascript": ["package.json"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
}

# Framework detection patterns (file → framework)
FRAMEWORK_PATTERNS = {
    "python": {
        "fastapi": ["from fastapi", "FastAPI("],
        "flask": ["from flask", "Flask("],
        "django": ["django", "DJANGO_SETTINGS"],
        "nautilus": ["nautilus_trader", "NautilusTrader"],
    },
    "typescript": {
        "n8n": ["n8n", "@n8n"],
        "react": ["react", "React"],
        "next": ["next", "Next"],
    },
}

# Default commands per language
DEFAULT_COMMANDS = {
    "python": {
        "test": "uv run pytest tests/ -x",
        "lint": "uv run ruff check .",
        "format": "uv run ruff format .",
    },
    "typescript": {
        "test": "npm test",
        "lint": "npm run lint",
        "format": "npm run format",
    },
    "rust": {
        "test": "cargo test",
        "lint": "cargo clippy",
        "format": "cargo fmt",
    },
    "go": {
        "test": "go test ./...",
        "lint": "golangci-lint run",
        "format": "go fmt ./...",
    },
}


def load_canonical() -> dict:
    """Load canonical configuration."""
    if CANONICAL_PATH.exists():
        with open(CANONICAL_PATH) as f:
            return yaml.safe_load(f)
    return {}


def detect_language(repo_path: Path) -> str:
    """Detect project language from files."""
    for lang, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            if (repo_path / pattern).exists():
                return lang
    return "unknown"


def detect_framework(repo_path: Path, language: str) -> str:
    """Detect framework from source files."""
    patterns = FRAMEWORK_PATTERNS.get(language, {})
    if not patterns:
        return "none"

    # Search in source files
    source_dirs = ["src", "app", "lib", "."]
    extensions = {
        "python": "*.py",
        "typescript": "*.ts",
        "javascript": "*.js",
    }

    ext = extensions.get(language, "*.*")

    for source_dir in source_dirs:
        source_path = repo_path / source_dir
        if not source_path.exists():
            continue

        for file_path in source_path.glob(ext):
            try:
                content = file_path.read_text()
                for framework, keywords in patterns.items():
                    if any(kw in content for kw in keywords):
                        return framework
            except (OSError, UnicodeDecodeError):
                continue

    return "none"


def generate_claude_md(project_name: str, language: str, framework: str, commands: dict) -> str:
    """Generate CLAUDE.md content."""
    framework_note = f" with {framework}" if framework != "none" else ""

    return f'''# CLAUDE.md

## Project Overview
**{project_name}** - {language.capitalize()}{framework_note} project.

## Tech Stack
- **Language**: {language}
- **Framework**: {framework if framework != "none" else "N/A"}
- **Test Command**: `{commands.get("test", "N/A")}`
- **Lint Command**: `{commands.get("lint", "N/A")}`

## Development Rules

### Code Style
- Follow existing patterns in the codebase
- Use type hints (Python) / strict types (TypeScript)
- Keep functions focused and testable

### Testing
- Write tests before implementation (TDD)
- Maintain >80% coverage for critical paths
- Run tests before committing

### Git Workflow
- Atomic commits with clear messages
- Use feature branches
- Reference issues in commits

## Quick Commands

| Command | Description |
|---------|-------------|
| `/health` | Check system health |
| `/tdd:cycle` | Full TDD cycle |
| `/undo:checkpoint` | Create rollback point |
| `/insight` | View metrics summary |

## Project-Specific Notes

*Add project-specific instructions here.*

---
Generated: {datetime.now().strftime("%Y-%m-%d")}
'''


def generate_settings_local(canonical: dict) -> dict:
    """Generate settings.local.json content."""
    infra = canonical.get("infrastructure", {})
    questdb = infra.get("questdb", {})

    return {
        "env": {
            "QUESTDB_HOST": questdb.get("host", "localhost"),
            "QUESTDB_ILP_PORT": str(questdb.get("ilp_port", 9009)),
        }
    }


def update_canonical(canonical: dict, repo_path: Path, language: str, framework: str, commands: dict):
    """Add new repo to canonical.yaml."""
    repo_name = repo_path.name.lower().replace("-", "_").replace(" ", "_")

    new_repo = {
        "path": str(repo_path),
        "language": language,
        "framework": framework if framework != "none" else language,
        "test_command": commands.get("test", ""),
        "lint_command": commands.get("lint", ""),
        "features": [],
    }

    repos = canonical.setdefault("repositories", {})
    if repo_name not in repos:
        repos[repo_name] = new_repo
        with open(CANONICAL_PATH, "w") as f:
            yaml.dump(canonical, f, default_flow_style=False, sort_keys=False)
        print(f"Added {repo_name} to canonical.yaml")
    else:
        print(f"Repository {repo_name} already in canonical.yaml")


def setup_project(repo_path: Path, language: str = None, framework: str = None):
    """Set up Claude Code skeleton for project."""
    print(f"Setting up Claude Code for: {repo_path}")
    print("=" * 50)

    # Load canonical
    canonical = load_canonical()

    # Detect or use provided values
    if not language:
        language = detect_language(repo_path)
        print(f"Detected language: {language}")
    else:
        print(f"Using language: {language}")

    if not framework:
        framework = detect_framework(repo_path, language)
        print(f"Detected framework: {framework}")
    else:
        print(f"Using framework: {framework}")

    # Get commands
    commands = DEFAULT_COMMANDS.get(language, {})
    print(f"Test command: {commands.get('test', 'N/A')}")
    print(f"Lint command: {commands.get('lint', 'N/A')}")
    print()

    # Create directory structure
    claude_dir = repo_path / ".claude"
    dirs_to_create = [
        claude_dir,
        claude_dir / "agents",
        claude_dir / "commands",
        claude_dir / "skills",
    ]

    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Created: {dir_path.relative_to(repo_path)}/")

    # Generate CLAUDE.md
    claude_md_path = claude_dir / "CLAUDE.md"
    if not claude_md_path.exists():
        project_name = repo_path.name
        content = generate_claude_md(project_name, language, framework, commands)
        claude_md_path.write_text(content)
        print(f"Generated: .claude/CLAUDE.md")
    else:
        print(f"Skipped: .claude/CLAUDE.md (already exists)")

    # Generate settings.local.json
    settings_path = claude_dir / "settings.local.json"
    if not settings_path.exists():
        settings = generate_settings_local(canonical)
        settings_path.write_text(json.dumps(settings, indent=2))
        print(f"Generated: .claude/settings.local.json")
    else:
        print(f"Skipped: .claude/settings.local.json (already exists)")

    # Update canonical.yaml
    print()
    update_canonical(canonical, repo_path, language, framework, commands)

    # Summary
    print()
    print("Setup complete!")
    print()
    print("Next steps:")
    print("  1. Review .claude/CLAUDE.md and customize")
    print("  2. Run /health to verify integration")
    print("  3. Commit .claude/ directory")
    print()
    print("Available commands:")
    print("  /health         - Check system health")
    print("  /tdd:cycle      - TDD workflow")
    print("  /undo:checkpoint - Create rollback point")


def main():
    parser = argparse.ArgumentParser(description="Set up Claude Code for new project")
    parser.add_argument("language", nargs="?", help="Project language (python, typescript, etc.)")
    parser.add_argument("framework", nargs="?", help="Framework (fastapi, react, etc.)")
    parser.add_argument("--path", type=Path, default=Path.cwd(), help="Project path")
    args = parser.parse_args()

    repo_path = args.path.resolve()

    if not repo_path.exists():
        print(f"ERROR: Path does not exist: {repo_path}")
        sys.exit(1)

    setup_project(repo_path, args.language, args.framework)


if __name__ == "__main__":
    main()
