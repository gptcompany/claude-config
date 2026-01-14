#!/usr/bin/env python3
"""Repository Compliance Checker for SpecKit Standard.

Checks and optionally fixes repo structure compliance.
Designed to be run by Claude Code non-interactively.

Usage:
    # Check single repo
    python repo-compliance.py /path/to/repo

    # Check and auto-fix
    python repo-compliance.py /path/to/repo --fix

    # Check all 4 main repos
    python repo-compliance.py --all

    # JSON output for Claude
    python repo-compliance.py /path/to/repo --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Global Claude home
CLAUDE_HOME = Path.home() / ".claude"

# Template reference (for consistency checks)
TEMPLATE_PATH = CLAUDE_HOME / "templates/gptprojectmanager-standard.md"

# Main repos to check with --all
MAIN_REPOS = [
    Path("/media/sam/1TB/N8N_dev"),
    Path("/media/sam/1TB/UTXOracle"),
    Path("/media/sam/1TB/LiquidationHeatmap"),
    Path("/media/sam/1TB/nautilus_dev"),
]

# Required structure
REQUIRED_FILES = [
    (".claude/CLAUDE.md", "CLAUDE.md"),  # Either location
    ".specify/memory/constitution.md",
    ".claude/validation/config.json",
    "catalog-info.yaml",
]

REQUIRED_DIRS = [
    "specs",
    "tests",
    "docs",
]

RECOMMENDED_FILES = [
    "docs/ARCHITECTURE.md",
    "pyproject.toml",
    "README.md",
]


@dataclass
class ComplianceResult:
    """Result of compliance check."""

    repo: str
    score: int = 0
    max_score: int = 0
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        return len(self.missing_required) == 0

    @property
    def status(self) -> str:
        if self.compliant:
            return "✅ COMPLIANT"
        return "❌ NON-COMPLIANT"


def check_file_exists(repo_path: Path, file_spec) -> bool:
    """Check if file exists (supports tuple for alternatives)."""
    if isinstance(file_spec, tuple):
        return any((repo_path / f).exists() for f in file_spec)
    return (repo_path / file_spec).exists()


def get_file_path(repo_path: Path, file_spec) -> str:
    """Get the actual file path string."""
    if isinstance(file_spec, tuple):
        return " or ".join(file_spec)
    return file_spec


def check_repo(repo_path: Path, fix: bool = False) -> ComplianceResult:
    """Check repo compliance and optionally fix issues."""
    result = ComplianceResult(repo=repo_path.name)

    # Check required files
    for file_spec in REQUIRED_FILES:
        result.max_score += 1
        if check_file_exists(repo_path, file_spec):
            result.score += 1
        else:
            path_str = get_file_path(repo_path, file_spec)
            result.missing_required.append(path_str)

    # Check required directories
    for dir_name in REQUIRED_DIRS:
        result.max_score += 1
        if (repo_path / dir_name).is_dir():
            result.score += 1
        else:
            result.missing_required.append(f"{dir_name}/")

    # Check recommended files
    for file_path in RECOMMENDED_FILES:
        if not (repo_path / file_path).exists():
            result.missing_recommended.append(file_path)

    # Check for common issues
    check_common_issues(repo_path, result)

    # Apply fixes if requested
    if fix and result.missing_required:
        apply_fixes(repo_path, result)

    return result


def check_common_issues(repo_path: Path, result: ComplianceResult):
    """Check for common compliance issues."""
    # Check for .env files that shouldn't be committed
    env_files = list(repo_path.glob("**/.env"))
    gitignore = repo_path / ".gitignore"
    if env_files and gitignore.exists():
        content = gitignore.read_text()
        if ".env" not in content:
            result.issues.append(".env files found but not in .gitignore")

    # Check for __pycache__ directories
    pycache_dirs = list(repo_path.glob("**/__pycache__"))
    if len(pycache_dirs) > 10:
        result.issues.append(
            f"{len(pycache_dirs)} __pycache__ directories (consider cleanup)"
        )

    # Check for large log files
    log_files = list(repo_path.glob("**/*.log"))
    large_logs = [f for f in log_files if f.stat().st_size > 10_000_000]  # 10MB
    if large_logs:
        result.issues.append(f"{len(large_logs)} large log files (>10MB)")

    # Check constitution version and core principles
    constitution = repo_path / ".specify/memory/constitution.md"
    if constitution.exists():
        content = constitution.read_text()
        if "Version:" not in content and "Version**:" not in content:
            result.issues.append("Constitution missing version number")
        # Check for required principles (from global template)
        if "KISS" not in content and "Keep It Simple" not in content:
            result.issues.append("Constitution missing KISS principle")
        if "YAGNI" not in content:
            result.issues.append("Constitution missing YAGNI principle")

    # Check CLAUDE.md has key sections
    claude_md = repo_path / ".claude/CLAUDE.md"
    if not claude_md.exists():
        claude_md = repo_path / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        if "## Project Overview" not in content and "Project Overview" not in content:
            result.issues.append("CLAUDE.md missing Project Overview section")
        if "KISS" not in content and "YAGNI" not in content:
            result.issues.append("CLAUDE.md missing development principles")

    # Check if repo is registered in global canonical.yaml
    canonical = CLAUDE_HOME / "canonical.yaml"
    if canonical.exists():
        canonical_content = canonical.read_text()
        repo_key = repo_path.name.lower().replace("-", "_")
        if (
            repo_key not in canonical_content
            and repo_path.name not in canonical_content
        ):
            result.issues.append("Repo not registered in global canonical.yaml")


def apply_fixes(repo_path: Path, result: ComplianceResult):
    """Apply automatic fixes for missing structure."""
    # Create missing directories
    for missing in result.missing_required[:]:
        if missing.endswith("/"):
            dir_path = repo_path / missing.rstrip("/")
            dir_path.mkdir(parents=True, exist_ok=True)
            result.fixes_applied.append(f"Created {missing}")
            result.missing_required.remove(missing)

    # Create validation config if missing
    if ".claude/validation/config.json" in result.missing_required:
        validation_dir = repo_path / ".claude/validation"
        validation_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "domain": repo_path.name.lower().replace("-", "_"),
            "anti_patterns": ["hardcoded_api_keys"],
            "research_keywords": {"trigger": [], "skip": []},
        }
        config_path = validation_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2))
        result.fixes_applied.append("Created validation/config.json")
        result.missing_required.remove(".claude/validation/config.json")

    # Create basic constitution if missing
    if ".specify/memory/constitution.md" in result.missing_required:
        specify_dir = repo_path / ".specify/memory"
        specify_dir.mkdir(parents=True, exist_ok=True)
        constitution = f"""# Project Constitution: {repo_path.name}

**Created**: {datetime.now().strftime("%Y-%m-%d")}
**Version**: 1.0.0

## Core Principles

### I. KISS + YAGNI (MUST)
- Keep It Simple, Stupid
- You Ain't Gonna Need It

### II. Documentation-First (MUST)
- README.md required for modules

## Quality Gates
- [ ] All tests pass
- [ ] No secrets in code
"""
        (specify_dir / "constitution.md").write_text(constitution)
        result.fixes_applied.append("Created constitution.md")
        result.missing_required.remove(".specify/memory/constitution.md")


def clean_repo(repo_path: Path) -> dict:
    """Clean __pycache__, .pyc files, and large logs."""
    import shutil

    cleaned = {"pycache": 0, "pyc": 0, "logs": 0}

    # Remove __pycache__ directories
    for pycache in repo_path.glob("**/__pycache__"):
        try:
            shutil.rmtree(pycache)
            cleaned["pycache"] += 1
        except OSError:
            pass

    # Remove .pyc files
    for pyc in repo_path.glob("**/*.pyc"):
        try:
            pyc.unlink()
            cleaned["pyc"] += 1
        except OSError:
            pass

    # Remove large log files (>10MB)
    for log in repo_path.glob("**/*.log"):
        try:
            if log.stat().st_size > 10_000_000:
                log.unlink()
                cleaned["logs"] += 1
        except OSError:
            pass

    return cleaned


def print_result(result: ComplianceResult, json_output: bool = False):
    """Print compliance result."""
    if json_output:
        print(
            json.dumps(
                {
                    "repo": result.repo,
                    "compliant": result.compliant,
                    "score": f"{result.score}/{result.max_score}",
                    "missing_required": result.missing_required,
                    "missing_recommended": result.missing_recommended,
                    "issues": result.issues,
                    "fixes_applied": result.fixes_applied,
                },
                indent=2,
            )
        )
        return

    print(f"\n{'=' * 50}")
    print(f"📁 {result.repo}")
    print(f"{'=' * 50}")
    print(f"Status: {result.status}")
    print(f"Score: {result.score}/{result.max_score}")

    if result.missing_required:
        print("\n❌ Missing Required:")
        for item in result.missing_required:
            print(f"   - {item}")

    if result.missing_recommended:
        print("\n⚠️  Missing Recommended:")
        for item in result.missing_recommended:
            print(f"   - {item}")

    if result.issues:
        print("\n🔍 Issues Found:")
        for issue in result.issues:
            print(f"   - {issue}")

    if result.fixes_applied:
        print("\n🔧 Fixes Applied:")
        for fix in result.fixes_applied:
            print(f"   - {fix}")


def main():
    parser = argparse.ArgumentParser(
        description="Check repo compliance with SpecKit standard"
    )
    parser.add_argument("repo", nargs="?", type=Path, help="Repository path to check")
    parser.add_argument("--all", action="store_true", help="Check all 4 main repos")
    parser.add_argument("--fix", action="store_true", help="Auto-fix missing structure")
    parser.add_argument(
        "--clean", action="store_true", help="Clean __pycache__, .pyc, logs"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.all:
        repos = MAIN_REPOS
    elif args.repo:
        repos = [args.repo]
    else:
        parser.print_help()
        sys.exit(1)

    results = []
    for repo_path in repos:
        if not repo_path.exists():
            print(f"Warning: {repo_path} does not exist", file=sys.stderr)
            continue
        result = check_repo(repo_path, fix=args.fix)
        results.append(result)
        print_result(result, json_output=args.json)

    # Summary for --all
    if args.all and not args.json:
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        compliant = sum(1 for r in results if r.compliant)
        print(f"Compliant: {compliant}/{len(results)}")
        total_issues = sum(len(r.issues) for r in results)
        if total_issues:
            print(f"Total Issues: {total_issues}")


if __name__ == "__main__":
    main()
