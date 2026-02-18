#!/usr/bin/env python3
"""
Pre-Push Bug Hunter v4 - Multi-CLI Fallback

Flow:
1. Local heuristic analysis (FREE, ~2s)
2. If risk > threshold, escalate to AI review with configurable fallback chain

Environment variables:
  PREPUSH_REVIEWERS    Comma-separated reviewer chain (default: "gemini,codex,claude")
                       Available: gemini, codex, claude
                       Examples:
                         "gemini"             - Gemini only, no fallback
                         "codex,claude"       - Skip Gemini, try Codex then Claude
                         "claude"             - Claude only
  PREPUSH_THRESHOLD    Risk score to trigger AI review (default: 40, range: 0-100)
  PREPUSH_TIMEOUT      Timeout per reviewer in seconds (default: 120)
  PREPUSH_METRICS_DIR  Where to write review logs (default: ~/.claude/metrics)
  QUESTDB_HOST         QuestDB host for ILP metrics (default: localhost)
  QUESTDB_PORT         QuestDB ILP port (default: 9009)
  GEMINI_MODEL         Gemini model to use (default: gemini-3-flash-preview)
  CODEX_MODEL          Codex model to use (default: o3-mini)

Portable: works as standard git pre-push hook, independent of any specific agent.
Install: cp pre-push-review.py /path/to/repo/.git/hooks/pre-push && chmod +x ...
"""

import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Skip in CI
if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
    sys.exit(0)

# Configuration (all overridable via env)
RISK_THRESHOLD = int(os.environ.get("PREPUSH_THRESHOLD", "40"))
REVIEWER_CHAIN = os.environ.get("PREPUSH_REVIEWERS", "gemini,codex,claude").split(",")
REVIEWER_TIMEOUT = int(os.environ.get("PREPUSH_TIMEOUT", "120"))
METRICS_DIR = Path(os.environ.get("PREPUSH_METRICS_DIR", str(Path.home() / ".claude" / "metrics")))
REVIEW_LOG = METRICS_DIR / "pre_push_reviews.jsonl"
QUESTDB_HOST = os.environ.get("QUESTDB_HOST", "localhost")
QUESTDB_PORT = int(os.environ.get("QUESTDB_PORT", "9009"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
CODEX_MODEL = os.environ.get("CODEX_MODEL", "o3-mini")

REVIEW_PROMPT = """You are a code reviewer. Review this git diff for bugs and security issues.

Risk assessment: {risk_info}
Category: {category}
Files: {files}

Diff:
```
{diff}
```

Report ONLY real issues (not style):
- CRITICAL: [issue] - blocking (security, data loss)
- HIGH: [issue] - serious bugs
- MEDIUM: [issue] - minor issues
- OK - if no real issues

Be concise (max 10 lines)."""


def _git(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _get_base_ref() -> str | None:
    """Best-effort base for the upcoming push."""
    for ref in ("@{push}", "@{upstream}"):
        result = _git(["rev-parse", "--verify", "--quiet", ref], timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return ref
    return None


def _get_diff_range() -> str | None:
    base = _get_base_ref()
    return f"{base}...HEAD" if base else None


def get_changed_files() -> list[str]:
    """Get list of changed code files to be pushed."""
    try:
        diff_range = _get_diff_range()
        if diff_range:
            result = _git(["diff", "--name-only", diff_range])
        else:
            # No upstream/push target yet: include root diff against empty tree.
            result = _git(["diff", "--name-only", "--root", "HEAD"])

        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        code_extensions = {".py", ".ts", ".js", ".tsx", ".jsx", ".rs", ".go", ".sh"}
        return [f for f in files if Path(f).suffix in code_extensions]
    except Exception:
        return []


def get_diff_context(files: list[str]) -> str:
    """Get git diff for context."""
    try:
        diff_range = _get_diff_range()
        if diff_range:
            result = _git(["diff", diff_range, "--", *files[:10]], timeout=15)
        else:
            result = _git(["diff", "--root", "HEAD", "--", *files[:10]], timeout=15)
        diff = result.stdout.strip()
        return diff[:30000] if len(diff) > 30000 else diff
    except Exception:
        return ""


def run_local_analysis() -> dict:
    """Run local diff analysis with git + heuristics."""
    try:
        diff_range = _get_diff_range()
        if diff_range:
            result = _git(["diff", "--name-only", diff_range], timeout=10)
            stat_result = _git(["diff", "--stat", diff_range], timeout=10)
        else:
            result = _git(["diff", "--name-only", "--root", "HEAD"], timeout=10)
            stat_result = _git(["diff", "--stat", "--root", "HEAD"], timeout=10)

        files = [f for f in result.stdout.strip().split("\n") if f]

        lines_added = 0
        lines_removed = 0
        for line in stat_result.stdout.split("\n"):
            if "|" in line:
                parts = line.split("|")
                if len(parts) > 1:
                    changes = parts[1].strip()
                    lines_added += changes.count("+")
                    lines_removed += changes.count("-")

        risk_score = 0
        risk_factors = []

        if len(files) > 20:
            risk_score += 30
            risk_factors.append("many_files")
        elif len(files) > 10:
            risk_score += 15
            risk_factors.append("moderate_files")

        total_lines = lines_added + lines_removed
        if total_lines > 1000:
            risk_score += 25
            risk_factors.append("large_diff")
        elif total_lines > 500:
            risk_score += 15
            risk_factors.append("medium_diff")

        sensitive_patterns = ["secret", "password", "key", "token", "auth", ".env"]
        for f in files:
            if any(p in f.lower() for p in sensitive_patterns):
                risk_score += 20
                risk_factors.append("sensitive_file")
                break

        infra_patterns = ["docker", "k8s", "terraform", "ci", "workflow"]
        for f in files:
            if any(p in f.lower() for p in infra_patterns):
                risk_score += 15
                risk_factors.append("infra_change")
                break

        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        elif risk_score >= 20:
            risk_level = "low"
        else:
            risk_level = "minimal"

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


# --- AI Review Fallback Chain ---


def _review_gemini(prompt: str) -> str | None:
    """Tier 1: Gemini CLI (free with Google AI Pro, OAuth)."""
    gemini_bin = shutil.which("gemini")
    if not gemini_bin:
        return None
    try:
        result = subprocess.run(
            [gemini_bin, "-m", GEMINI_MODEL, "-p", prompt],
            capture_output=True, text=True, timeout=REVIEWER_TIMEOUT,
            env={**os.environ, "NO_COLOR": "1"},
        )
        if result.returncode == 0:
            lines = [
                line for line in result.stdout.split("\n")
                if not line.startswith("Hook registry")
                and not line.startswith("[dotenvx")
            ]
            output = "\n".join(lines).strip()
            if output:
                return f"[gemini-3-flash] {output}"
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def _review_codex(prompt: str) -> str | None:
    """Tier 2: Codex CLI (OpenAI subscription)."""
    codex_bin = shutil.which("codex")
    if not codex_bin:
        return None
    try:
        result = subprocess.run(
            [codex_bin, "-q", "--full-auto", "-m", CODEX_MODEL, prompt],
            capture_output=True, text=True, timeout=REVIEWER_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"[codex/o3-mini] {result.stdout.strip()}"
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def _review_claude(prompt: str, files: list[str]) -> str | None:
    """Tier 3: Claude CLI (Anthropic Max subscription). Can run git commands."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None

    # Claude can run commands, so give it a simpler prompt
    claude_prompt = f"""Review these high-risk git changes:

{prompt}

Run `git diff HEAD~1` to see the actual changes, then report:
- CRITICAL: [issue] - blocking issues (security, data loss)
- HIGH: [issue] - serious issues
- MEDIUM: [issue] - minor issues
- OK - if no real issues found

Be concise (max 10 lines). Focus on real bugs, not style."""

    try:
        result = subprocess.run(
            [claude_bin, "-p", claude_prompt, "--allowedTools", "Bash"],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"[claude] {result.stdout.strip()}"
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def run_ai_review(files: list[str], local_analysis: dict) -> str:
    """
    AI review with fallback chain:
    Gemini CLI (free) → Codex CLI (OpenAI) → Claude CLI (Anthropic)

    Tries each in order, returns first successful result.
    """
    risk_info = (
        f"{local_analysis.get('risk_level', 'unknown')} "
        f"({local_analysis.get('risk_score', 0)}/100)"
    )
    category = local_analysis.get("category", "unknown")
    files_str = ", ".join(files[:10])
    diff = get_diff_context(files)

    if not diff:
        return "NO_DIFF: could not retrieve diff context"

    prompt = REVIEW_PROMPT.format(
        risk_info=risk_info,
        category=category,
        files=files_str,
        diff=diff,
    )

    # Configurable fallback chain via PREPUSH_REVIEWERS env
    available = {
        "gemini": lambda: _review_gemini(prompt),
        "codex": lambda: _review_codex(prompt),
        "claude": lambda: _review_claude(prompt, files),
    }
    reviewers = [(name.strip(), available[name.strip()]) for name in REVIEWER_CHAIN if name.strip() in available]

    for name, reviewer in reviewers:
        print(f"  Trying {name}...", end=" ", flush=True)
        result = reviewer()
        if result:
            print("OK")
            return result
        print("skip")

    return "NO_REVIEWER: all AI reviewers unavailable"


# --- Metrics ---


def send_to_questdb(entry: dict) -> bool:
    """Send metrics to QuestDB via ILP."""
    try:
        ts_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1e9)

        def escape_tag(v):
            return str(v).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

        result = escape_tag(entry.get("result", "unknown"))
        risk_level = escape_tag(entry.get("risk_level", "unknown"))
        category = escape_tag(entry.get("category", "unknown"))
        reviewer = escape_tag(entry.get("reviewer", "none"))

        line = (
            f"prepush_reviews,"
            f"result={result},"
            f"risk_level={risk_level},"
            f"category={category},"
            f"reviewer={reviewer} "
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
        send_to_questdb(entry)
    except Exception:
        pass


# --- Main ---


def main():
    start = datetime.now()

    files = get_changed_files()
    if not files:
        print("No code files to review")
        sys.exit(0)

    chain_str = " > ".join(r.strip() for r in REVIEWER_CHAIN if r.strip())
    print("=" * 50)
    print(f"Pre-Push Review v4 ({chain_str})")
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

    # Step 2: AI review if risk > threshold
    used_ai = False
    ai_review = None
    reviewer = "none"

    if risk_score > RISK_THRESHOLD:
        print("-" * 50)
        print(f"Risk > {RISK_THRESHOLD}, escalating to AI review...")
        ai_review = run_ai_review(files, local_analysis)
        used_ai = True

        # Extract which reviewer was used
        if ai_review.startswith("[gemini"):
            reviewer = "gemini"
        elif ai_review.startswith("[codex"):
            reviewer = "codex"
        elif ai_review.startswith("[claude"):
            reviewer = "claude"

        print()
        print("AI Review Results:")
        print("-" * 50)
        print(ai_review)
    else:
        print(f"Risk <= {RISK_THRESHOLD}, skipping AI review")

    duration_ms = int((datetime.now() - start).total_seconds() * 1000)

    has_critical = ai_review and "CRITICAL:" in ai_review
    has_high = ai_review and "HIGH:" in ai_review
    result = "blocked" if has_critical else ("warning" if has_high else "passed")

    log_review({
        "files_count": len(files),
        "files": files[:10],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "category": local_analysis.get("category", "unknown"),
        "duration_ms": duration_ms,
        "used_ai": used_ai,
        "reviewer": reviewer,
        "has_critical": has_critical,
        "has_high": has_high,
        "result": result,
    })

    print("-" * 50)
    print(f"Duration: {duration_ms}ms | AI: {reviewer if used_ai else 'no'}")

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
