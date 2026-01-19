#!/usr/bin/env python3
"""
Research Budget Guard - Token and iteration limits

Prevents runaway research by enforcing:
- Token budget (default: 200K)
- Iteration limits (default: 5)
- Time limits (default: 30 minutes)

USAGE:
    from research_budget import BudgetGuard

    budget = BudgetGuard(max_tokens=200000, max_iterations=5)
    while budget.can_continue():
        result = do_research_step()
        budget.record(tokens_used=len(result), iteration=True)

CLI:
    python research_budget.py start --tokens 200000 --iterations 5
    python research_budget.py check <session_id>
    python research_budget.py record <session_id> --tokens 5000
    python research_budget.py status <session_id>
    python research_budget.py list
"""

import argparse
import json
import os
import socket
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any


# =============================================================================
# Configuration
# =============================================================================

BUDGET_DIR = Path.home() / ".claude" / "metrics" / "research_budgets"
DEFAULT_MAX_TOKENS = 200_000
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_TIME_MINUTES = 30

QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", 9009))


# =============================================================================
# Budget Session
# =============================================================================


@dataclass
class BudgetSession:
    """Research budget session."""

    session_id: str
    query: str
    max_tokens: int
    max_iterations: int
    max_time_minutes: int
    tokens_used: int = 0
    iterations: int = 0
    started_at: str = ""
    last_activity: str = ""
    status: str = "active"  # active, completed, exceeded, timeout
    history: list = field(default_factory=list)


class BudgetGuard:
    """
    Token and iteration budget guard.

    Tracks resource usage for a research session and prevents
    exceeding configured limits.
    """

    def __init__(
        self,
        session_id: str = None,
        query: str = "",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_time_minutes: int = DEFAULT_MAX_TIME_MINUTES,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._session = BudgetSession(
            session_id=self.session_id,
            query=query,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            max_time_minutes=max_time_minutes,
            started_at=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat(),
        )
        self._ensure_dir()
        self._load_or_create()

    def _ensure_dir(self):
        """Ensure budget directory exists."""
        BUDGET_DIR.mkdir(parents=True, exist_ok=True)

    def _get_path(self) -> Path:
        """Get session file path."""
        return BUDGET_DIR / f"{self.session_id}.json"

    def _load_or_create(self):
        """Load existing session or create new one."""
        path = self._get_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._session = BudgetSession(**data)
            except (json.JSONDecodeError, TypeError):
                self._save()
        else:
            self._save()

    def _save(self):
        """Persist session state."""
        path = self._get_path()
        data = {
            "session_id": self._session.session_id,
            "query": self._session.query,
            "max_tokens": self._session.max_tokens,
            "max_iterations": self._session.max_iterations,
            "max_time_minutes": self._session.max_time_minutes,
            "tokens_used": self._session.tokens_used,
            "iterations": self._session.iterations,
            "started_at": self._session.started_at,
            "last_activity": self._session.last_activity,
            "status": self._session.status,
            "history": self._session.history,
        }
        path.write_text(json.dumps(data, indent=2))

    def can_continue(self) -> bool:
        """
        Check if research can continue.

        Returns False if any limit is exceeded.
        """
        # Check status
        if self._session.status != "active":
            return False

        # Check tokens
        if self._session.tokens_used >= self._session.max_tokens:
            self._session.status = "exceeded"
            self._save()
            print(
                f"  Budget EXCEEDED: tokens ({self._session.tokens_used}/{self._session.max_tokens})",
                file=sys.stderr,
            )
            return False

        # Check iterations
        if self._session.iterations >= self._session.max_iterations:
            self._session.status = "exceeded"
            self._save()
            print(
                f"  Budget EXCEEDED: iterations ({self._session.iterations}/{self._session.max_iterations})",
                file=sys.stderr,
            )
            return False

        # Check time
        started = datetime.fromisoformat(self._session.started_at)
        elapsed = datetime.now() - started
        if elapsed > timedelta(minutes=self._session.max_time_minutes):
            self._session.status = "timeout"
            self._save()
            print(
                f"  Budget TIMEOUT: {elapsed.total_seconds() / 60:.1f} minutes",
                file=sys.stderr,
            )
            return False

        return True

    def record(self, tokens: int = 0, iteration: bool = False, step_name: str = None):
        """
        Record resource usage.

        Args:
            tokens: Tokens used in this step
            iteration: Whether this counts as an iteration
            step_name: Optional step name for history
        """
        self._session.tokens_used += tokens
        if iteration:
            self._session.iterations += 1
        self._session.last_activity = datetime.now().isoformat()

        # Record in history
        self._session.history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "tokens": tokens,
                "iteration": iteration,
                "step": step_name,
                "total_tokens": self._session.tokens_used,
                "total_iterations": self._session.iterations,
            }
        )

        self._save()
        self._log_metric(tokens, iteration, step_name)

    def complete(self):
        """Mark session as completed."""
        self._session.status = "completed"
        self._session.last_activity = datetime.now().isoformat()
        self._save()

    def get_remaining(self) -> Dict[str, Any]:
        """Get remaining budget."""
        started = datetime.fromisoformat(self._session.started_at)
        elapsed = datetime.now() - started
        remaining_time = max(
            0, self._session.max_time_minutes - elapsed.total_seconds() / 60
        )

        return {
            "tokens": self._session.max_tokens - self._session.tokens_used,
            "iterations": self._session.max_iterations - self._session.iterations,
            "time_minutes": round(remaining_time, 1),
            "percent_tokens": round(
                (1 - self._session.tokens_used / self._session.max_tokens) * 100, 1
            ),
            "percent_iterations": round(
                (1 - self._session.iterations / self._session.max_iterations) * 100, 1
            ),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get full session status."""
        started = datetime.fromisoformat(self._session.started_at)
        elapsed = datetime.now() - started

        return {
            "session_id": self._session.session_id,
            "query": self._session.query,
            "status": self._session.status,
            "tokens_used": self._session.tokens_used,
            "max_tokens": self._session.max_tokens,
            "iterations": self._session.iterations,
            "max_iterations": self._session.max_iterations,
            "elapsed_minutes": round(elapsed.total_seconds() / 60, 1),
            "max_time_minutes": self._session.max_time_minutes,
            "remaining": self.get_remaining(),
            "history_count": len(self._session.history),
            "started_at": self._session.started_at,
            "last_activity": self._session.last_activity,
        }

    def _log_metric(self, tokens: int, iteration: bool, step_name: str = None):
        """Log metric to QuestDB."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((QUESTDB_HOST, QUESTDB_ILP_PORT))
            sock.settimeout(2.0)

            session_id = self._session.session_id.replace(" ", "\\ ")
            tags = f"session_id={session_id}"
            fields = (
                f"tokens_used={self._session.tokens_used}i,"
                f"iterations={self._session.iterations}i,"
                f"step_tokens={tokens}i,"
                f'status="{self._session.status}"'
            )
            if step_name:
                fields += f',step_name="{step_name}"'

            timestamp_ns = int(datetime.now().timestamp() * 1e9)
            line = f"research_budget,{tags} {fields} {timestamp_ns}\n"

            sock.sendall(line.encode())
            sock.close()
        except (socket.error, OSError):
            pass  # Best effort


# =============================================================================
# Helper Functions
# =============================================================================


def load_session(session_id: str) -> Optional[BudgetGuard]:
    """Load existing session by ID."""
    path = BUDGET_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    return BudgetGuard(session_id=session_id)


def list_sessions() -> list:
    """List all budget sessions."""
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    sessions = []

    for path in BUDGET_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            sessions.append(
                {
                    "session_id": data.get("session_id"),
                    "query": data.get("query", "")[:50],
                    "status": data.get("status"),
                    "tokens_used": data.get("tokens_used", 0),
                    "iterations": data.get("iterations", 0),
                    "started_at": data.get("started_at"),
                }
            )
        except (json.JSONDecodeError, KeyError):
            pass

    return sorted(sessions, key=lambda x: x.get("started_at", ""), reverse=True)


def cleanup_old_sessions(days: int = 7) -> int:
    """Remove sessions older than N days."""
    BUDGET_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    for path in BUDGET_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            started = datetime.fromisoformat(data.get("started_at", ""))
            if started < cutoff:
                path.unlink()
                removed += 1
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    return removed


# =============================================================================
# CLI
# =============================================================================


def cmd_start(args):
    """Start new budget session."""
    query = " ".join(args.query) if args.query else ""
    budget = BudgetGuard(
        query=query,
        max_tokens=args.tokens,
        max_iterations=args.iterations,
        max_time_minutes=args.time,
    )

    if args.json:
        print(json.dumps({"session_id": budget.session_id}, indent=2))
    else:
        print(f"Budget session started: {budget.session_id}")
        print(f"  Max tokens: {args.tokens:,}")
        print(f"  Max iterations: {args.iterations}")
        print(f"  Max time: {args.time} minutes")


def cmd_check(args):
    """Check if budget allows continuation."""
    budget = load_session(args.session_id)
    if not budget:
        print(f"Session not found: {args.session_id}")
        sys.exit(1)

    can_continue = budget.can_continue()

    if args.json:
        print(
            json.dumps(
                {
                    "can_continue": can_continue,
                    "remaining": budget.get_remaining(),
                },
                indent=2,
            )
        )
    else:
        if can_continue:
            remaining = budget.get_remaining()
            print(
                f"CONTINUE - {remaining['percent_tokens']:.0f}% tokens, {remaining['percent_iterations']:.0f}% iterations remaining"
            )
        else:
            print("STOP - Budget exceeded or timeout")

    sys.exit(0 if can_continue else 1)


def cmd_record(args):
    """Record resource usage."""
    budget = load_session(args.session_id)
    if not budget:
        print(f"Session not found: {args.session_id}")
        sys.exit(1)

    budget.record(tokens=args.tokens, iteration=args.iteration, step_name=args.step)

    if args.json:
        print(json.dumps(budget.get_status(), indent=2))
    else:
        status = budget.get_status()
        print(f"Recorded: +{args.tokens} tokens, iteration={args.iteration}")
        print(f"  Total: {status['tokens_used']:,}/{status['max_tokens']:,} tokens")
        print(f"  Iterations: {status['iterations']}/{status['max_iterations']}")


def cmd_status(args):
    """Show session status."""
    budget = load_session(args.session_id)
    if not budget:
        print(f"Session not found: {args.session_id}")
        sys.exit(1)

    status = budget.get_status()

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"\n{'=' * 50}")
        print(f"Research Budget: {status['session_id']}")
        print(f"{'=' * 50}")
        print(f"Status:      {status['status'].upper()}")
        print(
            f"Query:       {status['query'][:50]}..."
            if len(status["query"]) > 50
            else f"Query:       {status['query']}"
        )
        print(
            f"\nTokens:      {status['tokens_used']:,} / {status['max_tokens']:,} ({status['remaining']['percent_tokens']:.0f}% remaining)"
        )
        print(
            f"Iterations:  {status['iterations']} / {status['max_iterations']} ({status['remaining']['percent_iterations']:.0f}% remaining)"
        )
        print(
            f"Time:        {status['elapsed_minutes']:.1f} / {status['max_time_minutes']} min ({status['remaining']['time_minutes']:.1f} min remaining)"
        )
        print(f"\nStarted:     {status['started_at']}")
        print(f"Last active: {status['last_activity']}")
        print(f"{'=' * 50}\n")


def cmd_complete(args):
    """Mark session as completed."""
    budget = load_session(args.session_id)
    if not budget:
        print(f"Session not found: {args.session_id}")
        sys.exit(1)

    budget.complete()
    print(f"Session {args.session_id} marked as completed")


def cmd_list(args):
    """List all sessions."""
    sessions = list_sessions()

    if args.json:
        print(json.dumps(sessions, indent=2))
    else:
        if not sessions:
            print("No budget sessions found")
            return

        print(f"\n{'=' * 70}")
        print("Research Budget Sessions")
        print(f"{'=' * 70}")
        print(f"{'ID':<10} {'Status':<12} {'Tokens':<15} {'Iter':<6} {'Query':<25}")
        print("-" * 70)
        for s in sessions[:20]:  # Show last 20
            print(
                f"{s['session_id']:<10} {s['status']:<12} {s['tokens_used']:>10,}/200K {s['iterations']:<6} {s['query'][:25]}"
            )
        print(f"{'=' * 70}\n")


def cmd_cleanup(args):
    """Cleanup old sessions."""
    removed = cleanup_old_sessions(args.days)
    print(f"Removed {removed} sessions older than {args.days} days")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Research budget guard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # start command
    start_parser = subparsers.add_parser("start", help="Start new budget session")
    start_parser.add_argument("query", nargs="*", help="Research query")
    start_parser.add_argument(
        "--tokens", "-t", type=int, default=DEFAULT_MAX_TOKENS, help="Max tokens"
    )
    start_parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Max iterations",
    )
    start_parser.add_argument(
        "--time", type=int, default=DEFAULT_MAX_TIME_MINUTES, help="Max time in minutes"
    )
    start_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    start_parser.set_defaults(func=cmd_start)

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check if budget allows continuation"
    )
    check_parser.add_argument("session_id", help="Session ID")
    check_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    check_parser.set_defaults(func=cmd_check)

    # record command
    record_parser = subparsers.add_parser("record", help="Record resource usage")
    record_parser.add_argument("session_id", help="Session ID")
    record_parser.add_argument(
        "--tokens", "-t", type=int, default=0, help="Tokens used"
    )
    record_parser.add_argument(
        "--iteration", "-i", action="store_true", help="Count as iteration"
    )
    record_parser.add_argument("--step", "-s", help="Step name")
    record_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    record_parser.set_defaults(func=cmd_record)

    # status command
    status_parser = subparsers.add_parser("status", help="Show session status")
    status_parser.add_argument("session_id", help="Session ID")
    status_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    status_parser.set_defaults(func=cmd_status)

    # complete command
    complete_parser = subparsers.add_parser(
        "complete", help="Mark session as completed"
    )
    complete_parser.add_argument("session_id", help="Session ID")
    complete_parser.set_defaults(func=cmd_complete)

    # list command
    list_parser = subparsers.add_parser("list", help="List all sessions")
    list_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    list_parser.set_defaults(func=cmd_list)

    # cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old sessions")
    cleanup_parser.add_argument(
        "--days", "-d", type=int, default=7, help="Remove sessions older than N days"
    )
    cleanup_parser.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
