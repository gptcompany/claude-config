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
    Run local diff analysis with git + heuristics.
    ClaudeFlow analyze diff has bugs, so we use git directly.
    """
    try:
        # Get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]

        # Get diff stats
        stat_result = subprocess.run(
            ["git", "diff", "--stat", "HEAD~1..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Count lines changed
        lines_added = 0
        lines_removed = 0
        for line in stat_result.stdout.split("\n"):
            if "|" in line:
                parts = line.split("|")
                if len(parts) > 1:
                    changes = parts[1].strip()
                    lines_added += changes.count("+")
                    lines_removed += changes.count("-")

        # Calculate risk score based on heuristics
        risk_score = 0
        risk_factors = []

        # File count risk
        if len(files) > 20:
            risk_score += 30
            risk_factors.append("many_files")
        elif len(files) > 10:
            risk_score += 15
            risk_factors.append("moderate_files")

        # Lines changed risk
        total_lines = lines_added + lines_removed
        if total_lines > 1000:
            risk_score += 25
            risk_factors.append("large_diff")
        elif total_lines > 500:
            risk_score += 15
            risk_factors.append("medium_diff")

        # Sensitive files risk
        sensitive_patterns = ["secret", "password", "key", "token", "auth", ".env"]
        for f in files:
            if any(p in f.lower() for p in sensitive_patterns):
                risk_score += 20
                risk_factors.append("sensitive_file")
                break

        # Config/infra risk
        infra_patterns = ["docker", "k8s", "terraform", "ci", "workflow"]
        for f in files:
            if any(p in f.lower() for p in infra_patterns):
                risk_score += 15
                risk_factors.append("infra_change")
                break

        # Determine risk level
        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        elif risk_score >= 20:
            risk_level = "low"
        else:
            risk_level = "minimal"

        # Categorize based on files
        category = "unknown"
        if any("test" in f.lower() for f in files):
            category = "test"
        elif any(f.endswith(".md") for f in files):
            category = "docs"
        elif any(f.startswith("src/") for f in files):
            category = "feature"

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "files_changed": len(files),
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "category": category,
            "risk_factors": risk_factors,
        }

    except subprocess.TimeoutExpired:
        return {"risk_level": "unknown", "risk_score": 0, "error": "timeout"}
    except Exception as e:
        return {"risk_level": "unknown", "risk_score": 0, "error": str(e)}


def _get_diff_context(files: list[str]) -> str:
    """Get git diff for context (used by Gemini which can't run commands)."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--", *files[:10]],
            capture_output=True, text=True, timeout=15,
        )
        diff = result.stdout.strip()
        # Truncate to avoid exceeding model context
        return diff[:30000] if len(diff) > 30000 else diff
    except Exception:
        return ""


def run_ai_review(files: list[str], local_analysis: dict) -> str:
    """
    AI review chain: Gemini 3 CLI (free, 300/day) → Claude CLI (Max subscription).
    Only called when risk > threshold.
    """
    risk_info = f"Risk: {local_analysis.get('risk_level', 'unknown')} ({local_analysis.get('risk_score', 0)}/100)"

    # Try Gemini 3 CLI first (free with AI Pro subscription)
    gemini_result = _run_gemini_review(files, risk_info, local_analysis)
    if gemini_result and gemini_result != "SKIP":
        return gemini_result

    # Fallback to Claude CLI (Max subscription tokens)
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


def _run_gemini_review(files: list[str], risk_info: str, local_analysis: dict) -> str | None:
    """Run review via Gemini 3 CLI (AI Pro, 300 thinking prompts/day)."""
    import shutil
    gemini_bin = shutil.which("gemini")
    if not gemini_bin:
        return None

    diff_context = _get_diff_context(files)
    if not diff_context:
        return None

    prompt = f"""You are a code reviewer. Review this git diff for bugs and security issues.

Risk assessment: {risk_info}
Category: {local_analysis.get("category", "unknown")}
Files: {", ".join(files[:10])}

Diff:
```
{diff_context}
```

Report ONLY real issues (not style):
- CRITICAL: [issue] - blocking (security, data loss)
- HIGH: [issue] - serious bugs
- MEDIUM: [issue] - minor issues
- OK - if no real issues

Be concise (max 10 lines)."""

    try:
        result = subprocess.run(
            [gemini_bin, "-m", "gemini-3-flash-preview", "-p", prompt],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "NO_COLOR": "1"},
        )
        if result.returncode == 0:
            # Filter hook/dotenvx lines
            lines = [l for l in result.stdout.split("\n")
                     if not l.startswith("Hook registry") and not l.startswith("[dotenvx")]
            output = "\n".join(lines).strip()
            if output:
                return f"[gemini-3-flash] {output}"
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


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
