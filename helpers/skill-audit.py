#!/usr/bin/env python3
"""
Skill Audit Trail - Tracks skill execution order and timing.
Used for debugging skill execution issues and performance analysis.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

AUDIT_FILE = Path(os.environ.get("HOME", "~")) / ".claude" / ".skill-audit.jsonl"


def log_skill_execution(
    skill_name: str,
    phase: str,
    success: bool = True,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """
    Log a skill execution to the audit trail.

    Args:
        skill_name: Name of the skill executed
        phase: Pipeline phase (e.g., "plan", "execute", "validate")
        success: Whether execution succeeded
        duration_ms: Optional execution duration in milliseconds
        error: Optional error message if failed
    """
    entry = {
        "ts": time.time(),
        "datetime": datetime.now().isoformat(),
        "skill": skill_name,
        "phase": phase,
        "success": success,
    }
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    if error:
        entry["error"] = error

    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_recent_executions(limit: int = 10) -> list[dict]:
    """Get the most recent skill executions."""
    if not AUDIT_FILE.exists():
        return []

    entries = []
    with open(AUDIT_FILE) as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return entries[-limit:]


def get_skill_stats(skill_name: Optional[str] = None) -> dict:
    """Get execution statistics for skills."""
    if not AUDIT_FILE.exists():
        return {"total": 0, "success": 0, "failed": 0}

    stats = {"total": 0, "success": 0, "failed": 0, "avg_duration_ms": 0}
    durations = []

    with open(AUDIT_FILE) as f:
        for line in f:
            if line.strip():
                try:
                    entry = json.loads(line)
                    if skill_name and entry.get("skill") != skill_name:
                        continue
                    stats["total"] += 1
                    if entry.get("success"):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                    if "duration_ms" in entry:
                        durations.append(entry["duration_ms"])
                except json.JSONDecodeError:
                    pass

    if durations:
        stats["avg_duration_ms"] = int(sum(durations) / len(durations))

    return stats


def clear_audit_trail() -> None:
    """Clear the audit trail."""
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Skill Audit Trail")
    parser.add_argument("--recent", "-r", type=int, default=10, help="Show N recent executions")
    parser.add_argument("--stats", "-s", action="store_true", help="Show statistics")
    parser.add_argument("--skill", help="Filter by skill name")
    parser.add_argument("--clear", action="store_true", help="Clear audit trail")
    args = parser.parse_args()

    if args.clear:
        clear_audit_trail()
        print("Audit trail cleared")
    elif args.stats:
        stats = get_skill_stats(args.skill)
        print(json.dumps(stats, indent=2))
    else:
        recent = get_recent_executions(args.recent)
        for entry in recent:
            status = "✅" if entry.get("success") else "❌"
            print(f"{status} [{entry.get('datetime', 'unknown')}] {entry.get('skill')} ({entry.get('phase')})")
