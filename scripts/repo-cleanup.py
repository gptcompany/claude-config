#!/usr/bin/env python3
"""Intelligent Repository Cleanup Tool.

Performs "thoughtful" cleanup by analyzing:
- Obsolete files (.bak, .old, ~, .orig)
- Stale specs (all tasks completed, old dates)
- Stale git branches
- Empty directories
- Large files that shouldn't be in git
- Duplicate files

Usage:
    # Analyze only (no changes)
    python repo-cleanup.py /path/to/repo

    # Analyze all 4 main repos
    python repo-cleanup.py --all

    # Actually clean (with confirmation per category)
    python repo-cleanup.py /path/to/repo --clean

    # Force clean without confirmation
    python repo-cleanup.py /path/to/repo --clean --force
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

MAIN_REPOS = [
    Path("/media/sam/1TB/N8N_dev"),
    Path("/media/sam/1TB/UTXOracle"),
    Path("/media/sam/1TB/LiquidationHeatmap"),
    Path("/media/sam/1TB/nautilus_dev"),
]

# File patterns considered obsolete
OBSOLETE_PATTERNS = [
    "*.bak",
    "*.old",
    "*~",
    "*.orig",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
]

# Directories to always skip
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".nox"}

# Large file threshold (5MB)
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024


@dataclass
class CleanupReport:
    """Report of cleanup analysis."""

    repo: str
    obsolete_files: list[Path] = field(default_factory=list)
    stale_specs: list[dict] = field(default_factory=list)
    stale_branches: list[str] = field(default_factory=list)
    empty_dirs: list[Path] = field(default_factory=list)
    large_files: list[tuple[Path, int]] = field(default_factory=list)
    duplicate_files: list[tuple[str, list[Path]]] = field(default_factory=list)
    pycache_dirs: list[Path] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return (
            len(self.obsolete_files)
            + len(self.stale_specs)
            + len(self.stale_branches)
            + len(self.empty_dirs)
            + len(self.large_files)
            + len(self.duplicate_files)
            + len(self.pycache_dirs)
        )

    @property
    def potential_space_mb(self) -> float:
        """Estimate space that could be freed."""
        space = 0
        for f in self.obsolete_files:
            try:
                space += f.stat().st_size
            except OSError:
                pass
        for f, size in self.large_files:
            space += size
        for d in self.pycache_dirs:
            try:
                space += sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
            except OSError:
                pass
        return space / (1024 * 1024)


def find_obsolete_files(repo_path: Path) -> list[Path]:
    """Find obsolete/backup files."""
    obsolete = []
    for pattern in OBSOLETE_PATTERNS:
        for f in repo_path.rglob(pattern):
            if not any(skip in f.parts for skip in SKIP_DIRS):
                obsolete.append(f)
    return sorted(obsolete)


def find_stale_specs(repo_path: Path) -> list[dict]:
    """Find specs that are completed or abandoned."""
    stale = []
    specs_dir = repo_path / "specs"
    if not specs_dir.exists():
        return stale

    for spec_dir in specs_dir.iterdir():
        if not spec_dir.is_dir():
            continue

        tasks_file = spec_dir / "tasks.md"
        if not tasks_file.exists():
            continue

        content = tasks_file.read_text()

        # Count tasks
        total_tasks = len(re.findall(r"- \[[ xX]\]", content))
        completed_tasks = len(re.findall(r"- \[[xX]\]", content))

        if total_tasks == 0:
            continue

        # Check if all completed
        completion_pct = (completed_tasks / total_tasks) * 100

        # Check last modified date
        mtime = datetime.fromtimestamp(tasks_file.stat().st_mtime)
        days_old = (datetime.now() - mtime).days

        # Stale if: 100% complete OR >90 days old with <50% completion
        is_stale = completion_pct == 100 or (days_old > 90 and completion_pct < 50)

        if is_stale:
            stale.append(
                {
                    "path": spec_dir,
                    "name": spec_dir.name,
                    "total_tasks": total_tasks,
                    "completed": completed_tasks,
                    "completion_pct": completion_pct,
                    "days_old": days_old,
                    "reason": "completed" if completion_pct == 100 else "abandoned",
                }
            )

    return stale


def find_stale_branches(repo_path: Path) -> list[str]:
    """Find git branches not touched in 60+ days."""
    stale = []
    try:
        result = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--sort=-committerdate",
                "--format=%(refname:short) %(committerdate:relative)",
                "refs/heads/",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return stale

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split(" ", 1)
            if len(parts) < 2:
                continue
            branch, date_str = parts
            # Skip main branches
            if branch in ("main", "master", "develop"):
                continue
            # Check if old (contains "months" or "year")
            if "month" in date_str or "year" in date_str:
                stale.append(f"{branch} ({date_str})")
    except Exception:
        pass
    return stale


def find_empty_dirs(repo_path: Path) -> list[Path]:
    """Find empty directories."""
    empty = []
    for d in repo_path.rglob("*"):
        if d.is_dir() and not any(d.iterdir()):
            if not any(skip in d.parts for skip in SKIP_DIRS):
                empty.append(d)
    return sorted(empty)


def find_large_files(repo_path: Path) -> list[tuple[Path, int]]:
    """Find large files that probably shouldn't be in git."""
    large = []
    # Extensions that are probably data files
    data_extensions = {
        ".csv",
        ".parquet",
        ".db",
        ".sqlite",
        ".pkl",
        ".h5",
        ".hdf5",
        ".zip",
        ".tar",
        ".gz",
    }

    for f in repo_path.rglob("*"):
        if f.is_file() and not any(skip in f.parts for skip in SKIP_DIRS):
            try:
                size = f.stat().st_size
                if size > LARGE_FILE_THRESHOLD:
                    # Check if it's a data file or in data directory
                    if f.suffix.lower() in data_extensions or "data" in f.parts:
                        large.append((f, size))
            except OSError:
                pass
    return sorted(large, key=lambda x: x[1], reverse=True)[:20]  # Top 20


def find_duplicate_files(repo_path: Path) -> list[tuple[str, list[Path]]]:
    """Find duplicate files by content hash."""
    hashes = defaultdict(list)

    for f in repo_path.rglob("*"):
        if f.is_file() and not any(skip in f.parts for skip in SKIP_DIRS):
            try:
                if (
                    f.stat().st_size > 1024 and f.stat().st_size < 10_000_000
                ):  # 1KB-10MB
                    # Only check certain extensions
                    if f.suffix in (".py", ".md", ".json", ".yaml", ".yml", ".txt"):
                        hash_val = hashlib.md5(f.read_bytes()).hexdigest()
                        hashes[hash_val].append(f)
            except OSError:
                pass

    # Return only actual duplicates
    duplicates = [(h, paths) for h, paths in hashes.items() if len(paths) > 1]
    return sorted(duplicates, key=lambda x: len(x[1]), reverse=True)[:10]  # Top 10


def find_pycache_dirs(repo_path: Path) -> list[Path]:
    """Find __pycache__ directories."""
    return sorted(repo_path.rglob("__pycache__"))


def analyze_repo(repo_path: Path) -> CleanupReport:
    """Analyze repo for cleanup opportunities."""
    report = CleanupReport(repo=repo_path.name)

    print(f"Analyzing {repo_path.name}...")

    report.obsolete_files = find_obsolete_files(repo_path)
    report.stale_specs = find_stale_specs(repo_path)
    report.stale_branches = find_stale_branches(repo_path)
    report.empty_dirs = find_empty_dirs(repo_path)
    report.large_files = find_large_files(repo_path)
    report.duplicate_files = find_duplicate_files(repo_path)
    report.pycache_dirs = find_pycache_dirs(repo_path)

    return report


def print_report(report: CleanupReport):
    """Print cleanup report."""
    print(f"\n{'=' * 60}")
    print(f"📁 {report.repo}")
    print(f"{'=' * 60}")
    print(f"Total issues: {report.total_issues}")
    print(f"Potential space savings: {report.potential_space_mb:.1f} MB")

    if report.pycache_dirs:
        print(f"\n🗑️  __pycache__ directories: {len(report.pycache_dirs)}")

    if report.obsolete_files:
        print(f"\n📄 Obsolete files ({len(report.obsolete_files)}):")
        for f in report.obsolete_files[:10]:
            print(f"   - {f.relative_to(f.parents[len(f.parts) - 2])}")
        if len(report.obsolete_files) > 10:
            print(f"   ... and {len(report.obsolete_files) - 10} more")

    if report.stale_specs:
        print(f"\n📋 Stale specs ({len(report.stale_specs)}):")
        for spec in report.stale_specs:
            status = (
                "✅ 100%"
                if spec["reason"] == "completed"
                else f"⚠️ {spec['completion_pct']:.0f}%"
            )
            print(f"   - {spec['name']}: {status}, {spec['days_old']}d old")

    if report.stale_branches:
        print(f"\n🌿 Stale branches ({len(report.stale_branches)}):")
        for branch in report.stale_branches[:5]:
            print(f"   - {branch}")
        if len(report.stale_branches) > 5:
            print(f"   ... and {len(report.stale_branches) - 5} more")

    if report.large_files:
        print(f"\n📦 Large files ({len(report.large_files)}):")
        for f, size in report.large_files[:5]:
            size_mb = size / (1024 * 1024)
            print(f"   - {f.name}: {size_mb:.1f} MB")

    if report.duplicate_files:
        print(f"\n🔄 Duplicate files ({len(report.duplicate_files)} groups):")
        for _, paths in report.duplicate_files[:3]:
            print(f"   - {paths[0].name} ({len(paths)} copies)")

    if report.empty_dirs:
        print(f"\n📂 Empty directories: {len(report.empty_dirs)}")


def clean_repo(repo_path: Path, report: CleanupReport, force: bool = False):
    """Perform cleanup based on report."""
    cleaned = {"pycache": 0, "obsolete": 0, "empty_dirs": 0}

    # Clean __pycache__
    if report.pycache_dirs:
        if (
            force
            or input(
                f"\nRemove {len(report.pycache_dirs)} __pycache__ dirs? [y/N] "
            ).lower()
            == "y"
        ):
            for d in report.pycache_dirs:
                try:
                    shutil.rmtree(d)
                    cleaned["pycache"] += 1
                except OSError:
                    pass
            print(f"   Removed {cleaned['pycache']} __pycache__ directories")

    # Clean obsolete files
    if report.obsolete_files:
        if (
            force
            or input(
                f"\nRemove {len(report.obsolete_files)} obsolete files? [y/N] "
            ).lower()
            == "y"
        ):
            for f in report.obsolete_files:
                try:
                    f.unlink()
                    cleaned["obsolete"] += 1
                except OSError:
                    pass
            print(f"   Removed {cleaned['obsolete']} obsolete files")

    # Clean empty directories
    if report.empty_dirs:
        if (
            force
            or input(
                f"\nRemove {len(report.empty_dirs)} empty directories? [y/N] "
            ).lower()
            == "y"
        ):
            for d in sorted(report.empty_dirs, reverse=True):  # Delete deepest first
                try:
                    d.rmdir()
                    cleaned["empty_dirs"] += 1
                except OSError:
                    pass
            print(f"   Removed {cleaned['empty_dirs']} empty directories")

    # Stale specs and branches require manual review
    if report.stale_specs:
        print("\n⚠️  Stale specs require manual review:")
        for spec in report.stale_specs:
            print(f"   - {spec['name']}: Consider archiving or deleting")

    if report.stale_branches:
        print("\n⚠️  Stale branches require manual deletion:")
        print("   git branch -d <branch_name>")

    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Intelligent repo cleanup")
    parser.add_argument("repo", nargs="?", type=Path, help="Repository path")
    parser.add_argument("--all", action="store_true", help="Analyze all 4 main repos")
    parser.add_argument("--clean", action="store_true", help="Perform cleanup")
    parser.add_argument("--force", action="store_true", help="Skip confirmations")
    args = parser.parse_args()

    if args.all:
        repos = MAIN_REPOS
    elif args.repo:
        repos = [args.repo]
    else:
        parser.print_help()
        sys.exit(1)

    total_space = 0
    for repo_path in repos:
        if not repo_path.exists():
            print(f"Warning: {repo_path} does not exist", file=sys.stderr)
            continue

        report = analyze_repo(repo_path)
        print_report(report)
        total_space += report.potential_space_mb

        if args.clean:
            clean_repo(repo_path, report, force=args.force)

    if len(repos) > 1:
        print(f"\n{'=' * 60}")
        print(f"TOTAL potential space savings: {total_space:.1f} MB")


if __name__ == "__main__":
    main()
