#!/usr/bin/env python3
"""
Pre-Push Bug Hunter v3 - Optimized Design

Flow:
1. ClaudeFlow CLI local analysis (FREE, ~2s)
2. Only escalate to Claude AI if risk > threshold (Max subscription)

This saves Max subscription tokens for 90%+ of pushes.
"""

import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Skip in CI
if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
    sys.exit(0)

# Configuration
RISK_THRESHOLD = 40  # Escalate to AI review if risk score > this
METRICS_DIR = Path.home() / ".claude" / "metrics"
REVIEW_LOG = METRICS_DIR / "pre_push_reviews.jsonl"
QUESTDB_HOST = "localhost"
QUESTDB_PORT = 9009

# Risk level mappings
RISK_LEVELS = {
    "critical": 90,
    "high": 70,
    "medium": 40,
    "low": 20,
    "minimal": 5,
    "unknown": 0,
}


def get_changed_files() -> list[str]:
    """Get list of changed code files to be pushed."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "@{push}.."],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
            )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        code_extensions = {".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go", ".sh"}
        return [f for f in files if Path(f).suffix in code_extensions]
    except Exception:
        return []


def run_local_analysis() -> dict:
    """
    Run ClaudeFlow CLI local analysis (FREE, no API tokens).
    Returns parsed risk assessment.
    """
    try:
        result = subprocess.run(
            ["npx", "claude-flow@alpha", "analyze", "diff", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Try to parse JSON output
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

        # Fallback: parse text output
        output = result.stdout + result.stderr
        risk_match = re.search(r"Risk:\s*(\w+)\s*\((\d+)/100\)", output)
        files_match = re.search(r"Files:\s*(\d+)", output)
        category_match = re.search(r"Category\s*\|\s*(\w+)", output)

        risk_level = risk_match.group(1) if risk_match else "unknown"
        risk_score = int(risk_match.group(2)) if risk_match else 0
        files_count = int(files_match.group(1)) if files_match else 0
        category = category_match.group(1) if category_match else "unknown"

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "files_changed": files_count,
            "category": category,
            "raw_output": output[:500],
        }

    except subprocess.TimeoutExpired:
        return {"risk_level": "unknown", "risk_score": 0, "error": "timeout"}
    except Exception as e:
        return {"risk_level": "unknown", "risk_score": 0, "error": str(e)}


def run_ai_review(files: list[str], local_analysis: dict) -> str:
    """
    Run Claude AI review (Max subscription) for high-risk changes.
    Only called when risk > threshold.
    """
    risk_info = f"Risk: {local_analysis.get('risk_level', 'unknown')} ({local_analysis.get('risk_score', 0)}/100)"

    prompt = f"""Review these high-risk git changes:

Local Analysis: {risk_info}
Category: {local_analysis.get("category", "unknown")}
Files: {", ".join(files[:10])}

Run `git diff HEAD~1` to see the actual changes, then report:
- CRITICAL: [issue] - blocking issues (security, data loss)
- HIGH: [issue] - serious issues
- MEDIUM: [issue] - minor issues
- OK - if no real issues found

Be concise (max 10 lines). Focus on real bugs, not style."""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Bash"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        return (
            result.stdout.strip()
            if result.returncode == 0
            else f"ERROR: {result.stderr}"
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def send_to_questdb(entry: dict) -> bool:
    """Send metrics to QuestDB via ILP."""
    try:
        ts_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1e9)

        # Escape tag values
        def escape_tag(v):
            return str(v).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

        result = escape_tag(entry.get("result", "unknown"))
        risk_level = escape_tag(entry.get("risk_level", "unknown"))
        category = escape_tag(entry.get("category", "unknown"))

        line = (
            f"claude_prepush_reviews,"
            f"result={result},"
            f"risk_level={risk_level},"
            f"category={category} "
            f"risk_score={entry.get('risk_score', 0)}i,"
            f"files_count={entry.get('files_count', 0)}i,"
            f"duration_ms={entry.get('duration_ms', 0)}i,"
            f"used_ai={'t' if entry.get('used_ai') else 'f'} "
            f"{ts_ns}"
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((QUESTDB_HOST, QUESTDB_PORT))
            s.sendall((line + "\n").encode())
        return True
    except Exception:
        return False


def log_review(entry: dict):
    """Log review to local JSONL and QuestDB."""
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        entry["timestamp"] = datetime.now().isoformat()

        with open(REVIEW_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Also send to QuestDB
        send_to_questdb(entry)
    except Exception:
        pass


def main():
    start = datetime.now()

    files = get_changed_files()
    if not files:
        print("No code files to review")
        sys.exit(0)

    print("=" * 50)
    print("Pre-Push Review v3 (ClaudeFlow + AI escalation)")
    print("=" * 50)
    print(f"Files: {len(files)}")
    for f in files[:5]:
        print(f"  {f}")
    if len(files) > 5:
        print(f"  +{len(files) - 5} more")
    print("-" * 50)

    # Step 1: Local analysis (FREE, fast)
    print("Running local analysis...")
    local_analysis = run_local_analysis()
    risk_score = local_analysis.get("risk_score", 0)
    risk_level = local_analysis.get("risk_level", "unknown")

    print(f"Local Risk: {risk_level} ({risk_score}/100)")

    # Step 2: Decide if AI review needed
    used_ai = False
    ai_review = None

    if risk_score > RISK_THRESHOLD:
        print("-" * 50)
        print(f"Risk > {RISK_THRESHOLD}, escalating to AI review...")
        ai_review = run_ai_review(files, local_analysis)
        used_ai = True
        print()
        print("AI Review Results:")
        print("-" * 50)
        print(ai_review)
    else:
        print(f"Risk ≤ {RISK_THRESHOLD}, skipping AI review")

    duration_ms = int((datetime.now() - start).total_seconds() * 1000)

    # Determine final result
    has_critical = ai_review and "CRITICAL:" in ai_review
    has_high = ai_review and "HIGH:" in ai_review
    result = "blocked" if has_critical else ("warning" if has_high else "passed")

    # Log metrics
    log_review(
        {
            "files_count": len(files),
            "files": files[:10],
            "risk_score": risk_score,
            "risk_level": risk_level,
            "category": local_analysis.get("category", "unknown"),
            "duration_ms": duration_ms,
            "used_ai": used_ai,
            "has_critical": has_critical,
            "has_high": has_high,
            "result": result,
        }
    )

    print("-" * 50)
    print(f"Duration: {duration_ms}ms | AI used: {used_ai}")

    # Exit codes
    if has_critical:
        print()
        print("CRITICAL issues found! Push blocked.")
        sys.exit(1)

    if has_high:
        print()
        print("HIGH severity issues. Review recommended.")
        try:
            r = input("Continue push? (y/N) ")
            if r.lower() != "y":
                print("Push cancelled.")
                sys.exit(1)
        except EOFError:
            pass

    print()
    print("Pre-push review passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
