#!/usr/bin/env python3
"""Send drift detector metrics to QuestDB for Grafana visualization."""

import json
import socket
import subprocess
import sys
from datetime import datetime


def run_drift_detector() -> dict:
    """Run drift detector and return JSON output."""
    result = subprocess.run(
        ["python3", "/home/sam/.claude/scripts/drift-detector.py", "--json"],
        capture_output=True,
        text=True,
    )
    # Extract JSON from output (skip header lines)
    output = result.stdout
    json_start = output.find("{")
    if json_start == -1:
        return {"score": 0, "issues": [], "repos_checked": 0}
    return json.loads(output[json_start:])


def send_to_questdb(metrics: dict) -> bool:
    """Send metrics to QuestDB via ILP protocol."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", 9009))

        timestamp_ns = int(datetime.now().timestamp() * 1e9)
        score = metrics.get("score", 0)
        repos_checked = metrics.get("repos_checked", 0)
        issues_count = len(metrics.get("issues", []))

        # ILP format: table,tags field=value timestamp
        line = f"config_drift score={score}i,repos_checked={repos_checked}i,issues_count={issues_count}i {timestamp_ns}\n"
        sock.sendall(line.encode())
        sock.close()
        return True
    except Exception as e:
        print(f"Error sending to QuestDB: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    metrics = run_drift_detector()
    print(f"Drift Score: {metrics.get('score', 0)}/100")
    print(f"Repos Checked: {metrics.get('repos_checked', 0)}")
    print(f"Issues Found: {len(metrics.get('issues', []))}")

    if send_to_questdb(metrics):
        print("Metrics sent to QuestDB")
    else:
        print("Failed to send metrics to QuestDB", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
