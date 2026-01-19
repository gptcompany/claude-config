#!/usr/bin/env python3
"""
Claude Code Drift Detector

Validates configuration consistency across repositories based on canonical.yaml.
Detects duplicates, missing files, and configuration drift.

Usage:
    python drift-detector.py          # Check for drift
    python drift-detector.py --fix    # Auto-fix where possible
    python drift-detector.py --report # Generate markdown report

Based on:
- Anthropic best practices: CLAUDE.md as living documentation
- FAANG patterns: SSOT (Single Source of Truth)
"""

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# SSOT location
CANONICAL_PATH = Path.home() / ".claude" / "canonical.yaml"
REPORT_DIR = Path.home() / ".claude" / "reports"


@dataclass
class Issue:
    """Detected drift issue."""
    severity: str  # critical, high, medium, low
    category: str  # duplicate, missing, drift, obsolete
    repo: str
    path: str
    message: str
    fix_available: bool = False
    fix_command: str = ""


@dataclass
class HealthReport:
    """Cross-repo health report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    issues: list[Issue] = field(default_factory=list)
    repos_checked: int = 0
    files_checked: int = 0

    @property
    def score(self) -> int:
        """Calculate health score 0-100."""
        if not self.issues:
            return 100

        deductions = {
            "critical": 25,
            "high": 10,
            "medium": 5,
            "low": 2,
        }

        total_deduction = sum(
            deductions.get(issue.severity, 0)
            for issue in self.issues
        )

        return max(0, 100 - total_deduction)


def load_canonical() -> dict:
    """Load canonical configuration."""
    if not CANONICAL_PATH.exists():
        print(f"ERROR: Canonical config not found: {CANONICAL_PATH}")
        sys.exit(1)

    with open(CANONICAL_PATH) as f:
        return yaml.safe_load(f)


def file_hash(path: Path) -> Optional[str]:
    """Calculate MD5 hash of file."""
    if not path.exists():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def check_duplicates(canonical: dict) -> list[Issue]:
    """Find duplicate files across repos that should be global."""
    issues = []
    global_artifacts = canonical.get("global", {})
    repos = canonical.get("repositories", {})

    global_skills = set(global_artifacts.get("skills", []))
    global_commands = set(global_artifacts.get("commands", []))

    for repo_name, repo_config in repos.items():
        repo_path = Path(repo_config.get("path", ""))
        if not repo_path.exists():
            continue

        # Check for duplicate skills
        skills_dir = repo_path / ".claude" / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir() and skill_dir.name in global_skills:
                    # Compare with global version
                    global_skill = Path.home() / ".claude" / "skills" / skill_dir.name / "SKILL.md"
                    local_skill = skill_dir / "SKILL.md"

                    if global_skill.exists() and local_skill.exists():
                        if file_hash(global_skill) != file_hash(local_skill):
                            issues.append(Issue(
                                severity="medium",
                                category="duplicate",
                                repo=repo_name,
                                path=str(local_skill),
                                message=f"Skill '{skill_dir.name}' differs from global version",
                                fix_available=True,
                                fix_command=f"rm -rf {skill_dir}"
                            ))
                        else:
                            issues.append(Issue(
                                severity="low",
                                category="duplicate",
                                repo=repo_name,
                                path=str(local_skill),
                                message=f"Skill '{skill_dir.name}' is identical to global (can remove)",
                                fix_available=True,
                                fix_command=f"rm -rf {skill_dir}"
                            ))

        # Check for duplicate commands
        commands_dir = repo_path / ".claude" / "commands"
        if commands_dir.exists():
            for cmd_path in commands_dir.iterdir():
                cmd_name = cmd_path.name
                if cmd_name.endswith(".md"):
                    base_name = cmd_name.replace(".md", "")
                    if any(base_name.startswith(gc.replace("/", "")) for gc in global_commands if not gc.endswith("/")):
                        global_cmd = Path.home() / ".claude" / "commands" / cmd_name
                        if global_cmd.exists():
                            if file_hash(global_cmd) != file_hash(cmd_path):
                                issues.append(Issue(
                                    severity="medium",
                                    category="duplicate",
                                    repo=repo_name,
                                    path=str(cmd_path),
                                    message=f"Command '{cmd_name}' differs from global version",
                                    fix_available=True,
                                    fix_command=f"rm {cmd_path}"
                                ))

    return issues


def check_missing_global(canonical: dict) -> list[Issue]:
    """Check if global artifacts exist."""
    issues = []
    global_artifacts = canonical.get("global", {})

    # Check global skills
    for skill in global_artifacts.get("skills", []):
        skill_path = Path.home() / ".claude" / "skills" / skill / "SKILL.md"
        if not skill_path.exists():
            issues.append(Issue(
                severity="high",
                category="missing",
                repo="global",
                path=str(skill_path),
                message=f"Global skill '{skill}' not found",
                fix_available=False,
            ))

    # Check global commands
    for cmd in global_artifacts.get("commands", []):
        if cmd.endswith("/"):
            # Directory
            cmd_dir = Path.home() / ".claude" / "commands" / cmd.rstrip("/")
            if not cmd_dir.exists():
                issues.append(Issue(
                    severity="high",
                    category="missing",
                    repo="global",
                    path=str(cmd_dir),
                    message=f"Global command directory '{cmd}' not found",
                    fix_available=False,
                ))
        else:
            cmd_path = Path.home() / ".claude" / "commands" / f"{cmd}.md"
            if not cmd_path.exists():
                issues.append(Issue(
                    severity="high",
                    category="missing",
                    repo="global",
                    path=str(cmd_path),
                    message=f"Global command '{cmd}' not found",
                    fix_available=False,
                ))

    return issues


def check_settings_drift(canonical: dict) -> list[Issue]:
    """Check for settings.json drift across repos."""
    issues = []
    repos = canonical.get("repositories", {})
    infra = canonical.get("infrastructure", {})

    expected_env = {
        "QUESTDB_HOST": infra.get("questdb", {}).get("host", "localhost"),
        "QUESTDB_ILP_PORT": str(infra.get("questdb", {}).get("ilp_port", 9009)),
    }

    for repo_name, repo_config in repos.items():
        repo_path = Path(repo_config.get("path", ""))
        settings_path = repo_path / ".claude" / "settings.local.json"

        if not settings_path.exists():
            continue

        try:
            with open(settings_path) as f:
                settings = json.load(f)

            env = settings.get("env", {})
            for key, expected_value in expected_env.items():
                actual_value = env.get(key)
                if actual_value and actual_value != expected_value:
                    issues.append(Issue(
                        severity="medium",
                        category="drift",
                        repo=repo_name,
                        path=str(settings_path),
                        message=f"Env {key}={actual_value}, expected {expected_value}",
                        fix_available=True,
                        fix_command=f"Update {settings_path} env.{key} to {expected_value}"
                    ))
        except (json.JSONDecodeError, OSError) as e:
            issues.append(Issue(
                severity="high",
                category="drift",
                repo=repo_name,
                path=str(settings_path),
                message=f"Cannot parse settings: {e}",
                fix_available=False,
            ))

    return issues


def check_obsolete(canonical: dict) -> list[Issue]:
    """Check for obsolete files not in canonical."""
    issues = []
    repos = canonical.get("repositories", {})
    project_specific = canonical.get("project_specific", {})
    global_artifacts = canonical.get("global", {})

    all_global_skills = set(global_artifacts.get("skills", []))

    for repo_name, repo_config in repos.items():
        repo_path = Path(repo_config.get("path", ""))
        if not repo_path.exists():
            continue

        # Get project-specific allowed items
        proj_skills = set(project_specific.get(repo_name, {}).get("skills", []))

        # Check skills
        skills_dir = repo_path / ".claude" / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name
                    # Check if it's global, project-specific, or obsolete
                    if skill_name not in all_global_skills and skill_name not in proj_skills:
                        # Check if it's a backup
                        if not skill_name.startswith("."):
                            issues.append(Issue(
                                severity="low",
                                category="obsolete",
                                repo=repo_name,
                                path=str(skill_dir),
                                message=f"Skill '{skill_name}' not in canonical.yaml",
                                fix_available=True,
                                fix_command=f"rm -rf {skill_dir}  # or add to canonical.yaml"
                            ))

    return issues


def generate_report(report: HealthReport, canonical: dict) -> str:
    """Generate markdown report."""
    repos = canonical.get("repositories", {})

    lines = [
        f"# Claude Code Health Report",
        f"",
        f"Generated: {report.timestamp}",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Health Score | **{report.score}/100** |",
        f"| Repos Checked | {report.repos_checked} |",
        f"| Files Checked | {report.files_checked} |",
        f"| Issues Found | {len(report.issues)} |",
        f"",
    ]

    if report.issues:
        # Group by severity
        by_severity = {}
        for issue in report.issues:
            by_severity.setdefault(issue.severity, []).append(issue)

        lines.extend([
            f"## Issues by Severity",
            f"",
        ])

        for severity in ["critical", "high", "medium", "low"]:
            issues = by_severity.get(severity, [])
            if issues:
                lines.extend([
                    f"### {severity.upper()} ({len(issues)})",
                    f"",
                ])
                for issue in issues:
                    fix_note = " [auto-fixable]" if issue.fix_available else ""
                    lines.append(f"- **{issue.repo}**: {issue.message}{fix_note}")
                    lines.append(f"  - Path: `{issue.path}`")
                    if issue.fix_command:
                        lines.append(f"  - Fix: `{issue.fix_command}`")
                lines.append("")
    else:
        lines.extend([
            f"## Status",
            f"",
            f"All checks passed. No drift detected.",
            f"",
        ])

    lines.extend([
        f"## Recommendations",
        f"",
    ])

    if report.score == 100:
        lines.append("- System is healthy. No action required.")
    elif report.score >= 80:
        lines.append("- Address HIGH severity issues this week.")
        lines.append("- MEDIUM issues can wait for next sprint.")
    elif report.score >= 60:
        lines.append("- Multiple issues detected. Schedule cleanup session.")
        lines.append("- Run `drift-detector.py --fix` for auto-fixable issues.")
    else:
        lines.append("- CRITICAL: System health is degraded.")
        lines.append("- Immediate attention required.")
        lines.append("- Consider reverting recent changes.")

    return "\n".join(lines)


def apply_fixes(issues: list[Issue], dry_run: bool = True) -> int:
    """Apply auto-fixes for fixable issues."""
    fixed = 0

    for issue in issues:
        if not issue.fix_available:
            continue

        if dry_run:
            print(f"[DRY-RUN] Would fix: {issue.message}")
            print(f"          Command: {issue.fix_command}")
        else:
            # Only handle safe operations
            if issue.fix_command.startswith("rm -rf "):
                path = Path(issue.fix_command.replace("rm -rf ", "").strip())
                if path.exists():
                    import shutil
                    shutil.rmtree(path)
                    print(f"[FIXED] Removed: {path}")
                    fixed += 1
            elif issue.fix_command.startswith("rm "):
                path = Path(issue.fix_command.replace("rm ", "").strip())
                if path.exists():
                    path.unlink()
                    print(f"[FIXED] Removed: {path}")
                    fixed += 1
            else:
                print(f"[SKIP] Manual fix required: {issue.fix_command}")

    return fixed


def main():
    parser = argparse.ArgumentParser(description="Claude Code Drift Detector")
    parser.add_argument("--fix", action="store_true", help="Apply auto-fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    canonical = load_canonical()
    repos = canonical.get("repositories", {})

    print("Claude Code Drift Detector")
    print("=" * 40)
    print(f"Checking {len(repos)} repositories...")
    print()

    # Run all checks
    all_issues = []
    all_issues.extend(check_duplicates(canonical))
    all_issues.extend(check_missing_global(canonical))
    all_issues.extend(check_settings_drift(canonical))
    all_issues.extend(check_obsolete(canonical))

    # Create report
    report = HealthReport(
        issues=all_issues,
        repos_checked=len(repos),
        files_checked=sum(1 for _ in all_issues),  # Approximate
    )

    if args.json:
        output = {
            "timestamp": report.timestamp,
            "score": report.score,
            "repos_checked": report.repos_checked,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "repo": i.repo,
                    "path": i.path,
                    "message": i.message,
                    "fix_available": i.fix_available,
                }
                for i in report.issues
            ]
        }
        print(json.dumps(output, indent=2))
        return

    if args.report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"drift-report-{datetime.now().strftime('%Y%m%d')}.md"
        report_content = generate_report(report, canonical)
        report_path.write_text(report_content)
        print(f"Report saved to: {report_path}")
        print()
        print(report_content)
        return

    # Default: show summary
    print(f"Health Score: {report.score}/100")
    print()

    if not all_issues:
        print("No drift detected. All systems healthy.")
        return

    # Show issues by severity
    by_severity = {}
    for issue in all_issues:
        by_severity.setdefault(issue.severity, []).append(issue)

    for severity in ["critical", "high", "medium", "low"]:
        issues = by_severity.get(severity, [])
        if issues:
            print(f"{severity.upper()}: {len(issues)} issues")
            for issue in issues[:3]:  # Show first 3
                fix_marker = " [fixable]" if issue.fix_available else ""
                print(f"  - [{issue.repo}] {issue.message}{fix_marker}")
            if len(issues) > 3:
                print(f"  ... and {len(issues) - 3} more")
            print()

    # Handle fixes
    fixable = [i for i in all_issues if i.fix_available]
    if fixable:
        print(f"{len(fixable)} issues can be auto-fixed.")

        if args.dry_run:
            print("\nDry run (no changes made):")
            apply_fixes(fixable, dry_run=True)
        elif args.fix:
            print("\nApplying fixes...")
            fixed = apply_fixes(fixable, dry_run=False)
            print(f"\nFixed {fixed} issues.")
        else:
            print("Run with --fix to apply, or --dry-run to preview.")


if __name__ == "__main__":
    main()
