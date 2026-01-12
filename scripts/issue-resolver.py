#!/usr/bin/env python3
"""
Auto-resolution pipeline for Claude Code drift issues.

This script analyzes drift-detector output and generates resolution plans
that can be automatically executed after user approval.

Usage:
    python issue-resolver.py                    # Analyze and print resolution plans
    python issue-resolver.py --json             # Output as JSON
    python issue-resolver.py --dry-run          # Show what would be done
    python issue-resolver.py --create-issues    # Create GitHub issues
    python issue-resolver.py --execute ISSUE_ID # Execute approved resolution
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class FixCommand:
    """A single fix command with description."""

    command: str
    description: str
    risk_level: str = "low"  # low, medium, high
    reversible: bool = True


@dataclass
class ResolutionPlan:
    """Complete resolution plan for an issue."""

    issue_id: str
    category: str
    description: str
    severity: str
    auto_resolvable: bool
    fix_commands: list[FixCommand] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)
    estimated_risk: str = "low"
    requires_restart: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "category": self.category,
            "description": self.description,
            "severity": self.severity,
            "auto_resolvable": self.auto_resolvable,
            "fix_commands": [
                {
                    "command": c.command,
                    "description": c.description,
                    "risk": c.risk_level,
                }
                for c in self.fix_commands
            ],
            "manual_steps": self.manual_steps,
            "estimated_risk": self.estimated_risk,
            "requires_restart": self.requires_restart,
        }


class IssueResolver:
    """Analyzes drift issues and generates resolution plans."""

    # Categories that can be auto-resolved
    AUTO_RESOLVABLE_CATEGORIES = {
        "duplicate_skill",
        "duplicate_command",
        "obsolete_file",
        "missing_file",
        "settings_drift",
    }

    def __init__(self, drift_detector_path: str | None = None):
        self.drift_detector = drift_detector_path or str(
            Path.home() / ".claude" / "scripts" / "drift-detector.py"
        )
        self.plans: list[ResolutionPlan] = []

    def get_drift_report(self) -> dict[str, Any]:
        """Run drift-detector and get JSON report."""
        try:
            result = subprocess.run(
                ["python3", self.drift_detector, "--json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # Extract JSON from output (drift-detector prints header before JSON)
            # Find the opening brace and extract everything from there
            output = result.stdout
            json_start = output.find("{")
            if json_start != -1:
                json_str = output[json_start:]
                return json.loads(json_str)
            return {"score": 100, "issues": []}
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print(f"Error running drift-detector: {e}", file=sys.stderr)
            return {"score": 100, "issues": []}

    def generate_fix_commands(self, issue: dict[str, Any]) -> list[FixCommand]:
        """Generate fix commands for an issue based on its category."""
        category = issue.get("category", "")
        details = issue.get("details", {})
        commands = []

        if category == "duplicate_skill":
            # Remove duplicate skill from repository
            if "path" in details:
                dup_path = details["path"]
                commands.append(
                    FixCommand(
                        command=f"rm -rf {dup_path}",
                        description=f"Remove duplicate skill at {dup_path}",
                        risk_level="low",
                        reversible=False,  # git can recover
                    )
                )

        elif category == "duplicate_command":
            # Remove duplicate command from repository
            if "path" in details:
                dup_path = details["path"]
                commands.append(
                    FixCommand(
                        command=f"rm -f {dup_path}",
                        description=f"Remove duplicate command at {dup_path}",
                        risk_level="low",
                        reversible=False,
                    )
                )

        elif category == "obsolete_file":
            # Remove obsolete file
            if "path" in details:
                obs_path = details["path"]
                commands.append(
                    FixCommand(
                        command=f"rm -f {obs_path}",
                        description=f"Remove obsolete file at {obs_path}",
                        risk_level="low",
                        reversible=False,
                    )
                )

        elif category == "missing_file":
            # Copy from canonical source
            if "expected" in details and "source" in details:
                commands.append(
                    FixCommand(
                        command=f"cp {details['source']} {details['expected']}",
                        description="Copy missing file from canonical source",
                        risk_level="low",
                        reversible=True,
                    )
                )

        elif category == "settings_drift":
            # Update settings file
            if "key" in details and "expected" in details and "file" in details:
                # This is complex - need jq or Python to update JSON
                commands.append(
                    FixCommand(
                        command=f"# Manual: Update {details['file']} - set {details['key']} to {details['expected']}",
                        description=f"Update settings drift for {details['key']}",
                        risk_level="medium",
                        reversible=True,
                    )
                )

        elif category == "port_conflict":
            # Can't auto-resolve port conflicts safely
            pass

        elif category == "service_down":
            # Restart service
            if "service" in details:
                service = details["service"]
                if details.get("type") == "docker":
                    commands.append(
                        FixCommand(
                            command=f"docker start {service}",
                            description=f"Start Docker container {service}",
                            risk_level="medium",
                            reversible=True,
                        )
                    )
                elif details.get("type") == "systemd":
                    commands.append(
                        FixCommand(
                            command=f"sudo systemctl start {service}",
                            description=f"Start systemd service {service}",
                            risk_level="medium",
                            reversible=True,
                        )
                    )

        return commands

    def analyze_issue(self, issue: dict[str, Any], index: int) -> ResolutionPlan:
        """Generate a resolution plan for a single issue."""
        category = issue.get("category", "unknown")
        severity = issue.get("severity", "low")
        description = issue.get("description", "Unknown issue")

        # Generate fix commands
        fix_commands = self.generate_fix_commands(issue)

        # Determine if auto-resolvable
        auto_resolvable = (
            category in self.AUTO_RESOLVABLE_CATEGORIES
            and len(fix_commands) > 0
            and all(c.risk_level in ("low", "medium") for c in fix_commands)
        )

        # Generate manual steps if not auto-resolvable
        manual_steps = []
        if not auto_resolvable:
            if category == "port_conflict":
                manual_steps.append("Identify which service should use the port")
                manual_steps.append("Stop or reconfigure the conflicting service")
            elif category == "cron_missing":
                manual_steps.append("Verify cron job is still needed")
                manual_steps.append("Re-add to crontab if required")
            else:
                manual_steps.append("Review the issue details")
                manual_steps.append("Apply appropriate fix based on context")

        # Calculate risk
        if fix_commands:
            max_risk = max(c.risk_level for c in fix_commands)
            estimated_risk = max_risk
        else:
            estimated_risk = "low" if severity == "low" else "medium"

        return ResolutionPlan(
            issue_id=f"DRIFT-{index + 1:03d}",
            category=category,
            description=description,
            severity=severity,
            auto_resolvable=auto_resolvable,
            fix_commands=fix_commands,
            manual_steps=manual_steps,
            estimated_risk=estimated_risk,
            requires_restart=category in ("service_down", "settings_drift"),
        )

    def analyze_all(self) -> list[ResolutionPlan]:
        """Analyze all issues from drift-detector."""
        report = self.get_drift_report()
        issues = report.get("issues", [])

        self.plans = [self.analyze_issue(issue, i) for i, issue in enumerate(issues)]
        return self.plans

    def create_github_issue(
        self, plan: ResolutionPlan, repo: str = "nautechsystems/nautilus_trader"
    ) -> str | None:
        """Create a GitHub issue with the resolution plan."""
        # Build issue body
        body_parts = [
            f"## Issue: {plan.description}",
            "",
            f"**Category:** {plan.category}",
            f"**Severity:** {plan.severity}",
            f"**Auto-Resolvable:** {'Yes' if plan.auto_resolvable else 'No'}",
            f"**Risk:** {plan.estimated_risk}",
            "",
        ]

        if plan.fix_commands:
            body_parts.append("## Fix Commands")
            body_parts.append("```bash")
            for cmd in plan.fix_commands:
                body_parts.append(f"# {cmd.description}")
                body_parts.append(cmd.command)
            body_parts.append("```")
            body_parts.append("")

        if plan.manual_steps:
            body_parts.append("## Manual Steps")
            for step in plan.manual_steps:
                body_parts.append(f"- [ ] {step}")
            body_parts.append("")

        if plan.auto_resolvable:
            body_parts.append("---")
            body_parts.append("**To approve auto-resolution, comment:** `/approve`")

        body = "\n".join(body_parts)

        # Create labels
        labels = [
            f"severity:{plan.severity}",
            f"category:{plan.category}",
        ]
        if plan.auto_resolvable:
            labels.append("auto-resolvable")

        # Build gh command
        title = f"[{plan.issue_id}] {plan.description[:80]}"

        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    repo,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    ",".join(labels),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # gh issue create returns the URL
                return result.stdout.strip()
            else:
                print(f"Failed to create issue: {result.stderr}", file=sys.stderr)
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Error creating GitHub issue: {e}", file=sys.stderr)
            return None

    def execute_plan(self, plan: ResolutionPlan, dry_run: bool = True) -> bool:
        """Execute a resolution plan."""
        if not plan.auto_resolvable:
            print(f"Plan {plan.issue_id} is not auto-resolvable")
            return False

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Executing plan {plan.issue_id}:")
        print(f"  Description: {plan.description}")

        success = True
        for cmd in plan.fix_commands:
            print(f"\n  Command: {cmd.command}")
            print(f"  Description: {cmd.description}")

            if not dry_run:
                try:
                    result = subprocess.run(
                        cmd.command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode != 0:
                        print(f"  ERROR: {result.stderr}")
                        success = False
                    else:
                        print("  OK")
                except subprocess.TimeoutExpired:
                    print("  ERROR: Command timed out")
                    success = False

        return success


def main():
    parser = argparse.ArgumentParser(
        description="Auto-resolution pipeline for drift issues"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument(
        "--create-issues", action="store_true", help="Create GitHub issues"
    )
    parser.add_argument(
        "--execute", metavar="ISSUE_ID", help="Execute a specific resolution plan"
    )
    parser.add_argument(
        "--repo",
        default="nautechsystems/nautilus_trader",
        help="GitHub repo for issues",
    )
    args = parser.parse_args()

    resolver = IssueResolver()
    plans = resolver.analyze_all()

    if args.execute:
        # Find and execute specific plan
        plan = next((p for p in plans if p.issue_id == args.execute), None)
        if plan:
            success = resolver.execute_plan(plan, dry_run=args.dry_run)
            sys.exit(0 if success else 1)
        else:
            print(f"Plan {args.execute} not found")
            sys.exit(1)

    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "total_issues": len(plans),
            "auto_resolvable": sum(1 for p in plans if p.auto_resolvable),
            "plans": [p.to_dict() for p in plans],
        }
        print(json.dumps(output, indent=2))
    else:
        print("Issue Resolution Analysis")
        print("=" * 50)
        print(f"Total Issues: {len(plans)}")
        print(f"Auto-Resolvable: {sum(1 for p in plans if p.auto_resolvable)}")
        print()

        for plan in plans:
            status = "[AUTO]" if plan.auto_resolvable else "[MANUAL]"
            print(f"\n{plan.issue_id} {status} [{plan.severity.upper()}]")
            print(f"  {plan.description}")

            if plan.fix_commands:
                print("  Fix Commands:")
                for cmd in plan.fix_commands:
                    print(f"    - {cmd.command}")

            if plan.manual_steps:
                print("  Manual Steps:")
                for step in plan.manual_steps:
                    print(f"    - {step}")

    if args.create_issues:
        print("\nCreating GitHub issues...")
        for plan in plans:
            url = resolver.create_github_issue(plan, repo=args.repo)
            if url:
                print(f"  {plan.issue_id}: {url}")
            else:
                print(f"  {plan.issue_id}: FAILED")


if __name__ == "__main__":
    main()
