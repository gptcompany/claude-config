#!/usr/bin/env python3
"""
ClaudeFlow Wrapper - Primary orchestrator with Native Task fallback

Provides ClaudeFlow as primary execution engine with automatic fallback
to sequential Native Task execution when ClaudeFlow fails.

Features:
- Circuit breaker (failure_threshold=3)
- Health monitoring with QuestDB metrics
- Discord notification on degradation
- Automatic fallback to Native Tasks

USAGE:
    python claudeflow_wrapper.py spawn "research query" --max-workers 5
    python claudeflow_wrapper.py status
    python claudeflow_wrapper.py health
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any


# =============================================================================
# Configuration
# =============================================================================

QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", 9009))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ClaudeFlow settings
CLAUDEFLOW_TIMEOUT = 300  # 5 minutes default
MAX_WORKERS = 5

# Circuit breaker settings
FAILURE_THRESHOLD = 3
RESET_TIMEOUT = 120  # 2 minutes

# State file for persistent circuit breaker state
STATE_FILE = Path.home() / ".claude" / "metrics" / "claudeflow_circuit.json"


# =============================================================================
# Execution Mode
# =============================================================================


class ExecutionMode(str, Enum):
    """Execution mode for research."""

    CLAUDEFLOW = "claudeflow"
    NATIVE_FALLBACK = "native_fallback"
    DEGRADED = "degraded"


# =============================================================================
# Circuit Breaker (Persistent)
# =============================================================================


@dataclass
class CircuitState:
    """Persistent circuit breaker state."""

    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: Optional[str] = None
    opened_at: Optional[str] = None
    total_calls: int = 0
    total_failures: int = 0
    total_fallbacks: int = 0


class ClaudeFlowCircuitBreaker:
    """
    Persistent circuit breaker for ClaudeFlow.

    States:
    - CLOSED: Normal operation, ClaudeFlow is primary
    - OPEN: ClaudeFlow is failing, use Native Tasks
    - HALF_OPEN: Testing if ClaudeFlow recovered
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 120):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = self._load_state()

    def _load_state(self) -> CircuitState:
        """Load state from file."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                return CircuitState(**data)
            except Exception:
                pass
        return CircuitState()

    def _save_state(self):
        """Persist state to file."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "state": self._state.state,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_at": self._state.last_failure_at,
            "opened_at": self._state.opened_at,
            "total_calls": self._state.total_calls,
            "total_failures": self._state.total_failures,
            "total_fallbacks": self._state.total_fallbacks,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def is_open(self) -> bool:
        """Check if circuit is open (blocking ClaudeFlow)."""
        if self._state.state == "open":
            if self._state.opened_at:
                opened_at = datetime.fromisoformat(self._state.opened_at)
                elapsed = (datetime.now() - opened_at).total_seconds()
                if elapsed >= self.reset_timeout:
                    self._state.state = "half_open"
                    self._save_state()
                    print("  Circuit transitioning to HALF_OPEN", file=sys.stderr)
                    return False
            return True
        return False

    def get_mode(self) -> ExecutionMode:
        """Get current execution mode based on circuit state."""
        if self._state.state == "open":
            return ExecutionMode.NATIVE_FALLBACK
        elif self._state.state == "half_open":
            return ExecutionMode.DEGRADED
        return ExecutionMode.CLAUDEFLOW

    def record_success(self):
        """Record successful ClaudeFlow execution."""
        self._state.total_calls += 1
        self._state.success_count += 1
        self._state.failure_count = 0

        if self._state.state == "half_open":
            # Recovery confirmed
            self._state.state = "closed"
            print("  Circuit CLOSED - ClaudeFlow recovered", file=sys.stderr)
            _send_discord_notification(
                "ClaudeFlow Recovered",
                "Circuit breaker closed, normal operation resumed",
                "success",
            )

        self._save_state()

    def record_failure(self, error: str = None):
        """Record failed ClaudeFlow execution."""
        self._state.total_calls += 1
        self._state.total_failures += 1
        self._state.failure_count += 1
        self._state.last_failure_at = datetime.now().isoformat()

        if self._state.failure_count >= self.failure_threshold:
            self._state.state = "open"
            self._state.opened_at = datetime.now().isoformat()
            self._state.total_fallbacks += 1
            print(
                f"  Circuit OPEN - Falling back to Native Tasks: {error}",
                file=sys.stderr,
            )
            _send_discord_notification(
                "ClaudeFlow Degraded",
                f"Circuit breaker open after {self.failure_threshold} failures. Using Native Task fallback.\nError: {error[:200] if error else 'Unknown'}",
                "warning",
            )

        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self._state.state,
            "failure_count": self._state.failure_count,
            "total_calls": self._state.total_calls,
            "total_failures": self._state.total_failures,
            "total_fallbacks": self._state.total_fallbacks,
            "success_rate": (self._state.total_calls - self._state.total_failures)
            / max(self._state.total_calls, 1)
            * 100,
            "last_failure_at": self._state.last_failure_at,
            "opened_at": self._state.opened_at,
        }

    def reset(self):
        """Manually reset circuit breaker."""
        self._state = CircuitState()
        self._save_state()
        print("  Circuit breaker reset to CLOSED", file=sys.stderr)


# Global circuit breaker
CIRCUIT = ClaudeFlowCircuitBreaker(FAILURE_THRESHOLD, RESET_TIMEOUT)


# =============================================================================
# QuestDB Metrics
# =============================================================================


_questdb_socket: Optional[socket.socket] = None


def _get_questdb_socket() -> Optional[socket.socket]:
    """Get or create reusable QuestDB socket."""
    global _questdb_socket
    if _questdb_socket is None:
        try:
            _questdb_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _questdb_socket.connect((QUESTDB_HOST, QUESTDB_ILP_PORT))
            _questdb_socket.settimeout(2.0)
        except (socket.error, OSError):
            _questdb_socket = None
    return _questdb_socket


def _reset_questdb_socket():
    """Reset socket on error."""
    global _questdb_socket
    if _questdb_socket:
        try:
            _questdb_socket.close()
        except Exception:
            pass
        _questdb_socket = None


def _escape_tag(value: str) -> str:
    """Escape tag value for ILP."""
    return str(value).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def log_claudeflow_metric(
    mode: str, duration_ms: int, status: str, error_type: str = None
) -> bool:
    """Log ClaudeFlow execution metric to QuestDB."""
    sock = _get_questdb_socket()
    if not sock:
        return False

    try:
        tags = f"mode={_escape_tag(mode)},status={_escape_tag(status)}"
        fields = f"duration_ms={duration_ms}i"
        if error_type:
            fields += f',error_type="{error_type}"'
        timestamp_ns = int(datetime.now().timestamp() * 1e9)
        line = f"claudeflow_health,{tags} {fields} {timestamp_ns}\n"
        sock.sendall(line.encode())
        return True
    except (socket.error, OSError):
        _reset_questdb_socket()
        return False


# =============================================================================
# Discord Notifications
# =============================================================================


def _send_discord_notification(
    title: str, message: str, severity: str = "info"
) -> bool:
    """Send notification to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    import urllib.request
    import urllib.error

    colors = {
        "success": 0x28A745,  # Green
        "warning": 0xFFC107,  # Yellow
        "error": 0xDC3545,  # Red
        "info": 0x17A2B8,  # Blue
    }

    payload = {
        "embeds": [
            {
                "title": f"{'🟢' if severity == 'success' else '🟡' if severity == 'warning' else '🔴' if severity == 'error' else 'ℹ️'} {title}",
                "description": message,
                "color": colors.get(severity, colors["info"]),
                "footer": {"text": "ClaudeFlow Health Monitor"},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ]
    }

    try:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 204
    except (urllib.error.URLError, OSError):
        return False


# =============================================================================
# ClaudeFlow Execution
# =============================================================================


@dataclass
class ExecutionResult:
    """Result of research execution."""

    success: bool
    mode: ExecutionMode
    output: str
    duration_ms: int
    error: Optional[str] = None


def execute_with_claudeflow(
    query: str, max_workers: int = 5, timeout: int = 300
) -> ExecutionResult:
    """
    Execute research using ClaudeFlow hive-mind.

    Args:
        query: Research query
        max_workers: Maximum parallel workers
        timeout: Execution timeout in seconds

    Returns:
        ExecutionResult with output
    """
    start_time = time.time()

    try:
        # Build ClaudeFlow command
        cmd = [
            "npx",
            "claude-flow",
            "hive-mind",
            "spawn",
            "--topology",
            "hierarchical",
            "--max-workers",
            str(max_workers),
            "--task",
            query,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.home()),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if result.returncode == 0:
            CIRCUIT.record_success()
            log_claudeflow_metric("claudeflow", duration_ms, "success")
            return ExecutionResult(
                success=True,
                mode=ExecutionMode.CLAUDEFLOW,
                output=result.stdout,
                duration_ms=duration_ms,
            )
        else:
            error = result.stderr[:500] if result.stderr else "Unknown error"
            CIRCUIT.record_failure(error)
            log_claudeflow_metric("claudeflow", duration_ms, "failed", error[:100])
            return ExecutionResult(
                success=False,
                mode=ExecutionMode.CLAUDEFLOW,
                output=result.stdout,
                duration_ms=duration_ms,
                error=error,
            )

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        CIRCUIT.record_failure("Timeout")
        log_claudeflow_metric("claudeflow", duration_ms, "timeout")
        return ExecutionResult(
            success=False,
            mode=ExecutionMode.CLAUDEFLOW,
            output="",
            duration_ms=duration_ms,
            error=f"ClaudeFlow timed out after {timeout}s",
        )

    except FileNotFoundError:
        duration_ms = int((time.time() - start_time) * 1000)
        CIRCUIT.record_failure("Not found")
        log_claudeflow_metric("claudeflow", duration_ms, "not_found")
        return ExecutionResult(
            success=False,
            mode=ExecutionMode.CLAUDEFLOW,
            output="",
            duration_ms=duration_ms,
            error="ClaudeFlow not found - install via npm",
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        CIRCUIT.record_failure(str(e))
        log_claudeflow_metric("claudeflow", duration_ms, "error", type(e).__name__)
        return ExecutionResult(
            success=False,
            mode=ExecutionMode.CLAUDEFLOW,
            output="",
            duration_ms=duration_ms,
            error=str(e),
        )


def execute_with_native_tasks(query: str) -> ExecutionResult:
    """
    Execute research using Native Task tool (fallback).

    This returns instructions for Claude to execute sequentially.
    """
    start_time = time.time()

    # Generate sequential task instructions
    tasks = [
        f"WebSearch: {query}",
        f"Grep codebase for: {query.split()[0] if query else 'topic'}",
        "Synthesize findings into summary",
    ]

    output = f"""# Native Task Fallback Mode

ClaudeFlow circuit is open. Executing sequential research:

## Tasks to Execute
{chr(10).join(f"{i + 1}. {task}" for i, task in enumerate(tasks))}

## Instructions
Execute each task sequentially using the Task tool with subagent_type=Explore.
"""

    duration_ms = int((time.time() - start_time) * 1000)
    log_claudeflow_metric("native_fallback", duration_ms, "degraded")

    return ExecutionResult(
        success=True,
        mode=ExecutionMode.NATIVE_FALLBACK,
        output=output,
        duration_ms=duration_ms,
    )


def execute_research(
    query: str, max_workers: int = 5, timeout: int = 300
) -> ExecutionResult:
    """
    Execute research with automatic fallback.

    Primary: ClaudeFlow hive-mind
    Fallback: Native Task sequential execution
    """
    # Check circuit breaker
    if CIRCUIT.is_open():
        print("  Circuit OPEN - using Native Task fallback", file=sys.stderr)
        return execute_with_native_tasks(query)

    # Try ClaudeFlow
    mode = CIRCUIT.get_mode()
    if mode == ExecutionMode.DEGRADED:
        print("  Circuit HALF_OPEN - testing ClaudeFlow recovery", file=sys.stderr)

    result = execute_with_claudeflow(query, max_workers, timeout)

    # If failed and we have attempts left, fallback
    if not result.success:
        print("  ClaudeFlow failed, falling back to Native Tasks", file=sys.stderr)
        return execute_with_native_tasks(query)

    return result


# =============================================================================
# CLI
# =============================================================================


def cmd_spawn(args):
    """Execute research query."""
    query = " ".join(args.query)
    result = execute_research(query, args.max_workers, args.timeout)

    if args.json:
        output = {
            "success": result.success,
            "mode": result.mode.value,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "output": result.output[:1000] if result.output else None,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"Mode: {result.mode.value}")
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration_ms}ms")
        if result.error:
            print(f"Error: {result.error}")
        print(f"{'=' * 60}\n")
        print(result.output)


def cmd_status(args):
    """Show circuit breaker status."""
    stats = CIRCUIT.get_stats()

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"\n{'=' * 40}")
        print("ClaudeFlow Circuit Breaker Status")
        print(f"{'=' * 40}")
        print(f"State:          {stats['state'].upper()}")
        print(f"Failure Count:  {stats['failure_count']}/{FAILURE_THRESHOLD}")
        print(f"Total Calls:    {stats['total_calls']}")
        print(f"Total Failures: {stats['total_failures']}")
        print(f"Total Fallbacks:{stats['total_fallbacks']}")
        print(f"Success Rate:   {stats['success_rate']:.1f}%")
        if stats["last_failure_at"]:
            print(f"Last Failure:   {stats['last_failure_at']}")
        if stats["opened_at"]:
            print(f"Opened At:      {stats['opened_at']}")
        print(f"{'=' * 40}\n")


def cmd_health(args):
    """Run health check and log metrics."""
    stats = CIRCUIT.get_stats()

    # Log current health to QuestDB
    log_claudeflow_metric(
        "health_check",
        0,
        stats["state"],
    )

    mode = CIRCUIT.get_mode()

    if args.json:
        print(
            json.dumps(
                {
                    "healthy": stats["state"] == "closed",
                    "mode": mode.value,
                    "stats": stats,
                },
                indent=2,
            )
        )
    else:
        status = "HEALTHY" if stats["state"] == "closed" else "DEGRADED"
        print(f"ClaudeFlow Health: {status} ({mode.value})")


def cmd_reset(args):
    """Reset circuit breaker."""
    CIRCUIT.reset()
    print("Circuit breaker reset to CLOSED state")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ClaudeFlow wrapper with circuit breaker and fallback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # spawn command
    spawn_parser = subparsers.add_parser("spawn", help="Execute research query")
    spawn_parser.add_argument("query", nargs="+", help="Research query")
    spawn_parser.add_argument(
        "--max-workers", "-w", type=int, default=5, help="Max parallel workers"
    )
    spawn_parser.add_argument(
        "--timeout", "-t", type=int, default=300, help="Timeout in seconds"
    )
    spawn_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    spawn_parser.set_defaults(func=cmd_spawn)

    # status command
    status_parser = subparsers.add_parser("status", help="Show circuit breaker status")
    status_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    status_parser.set_defaults(func=cmd_status)

    # health command
    health_parser = subparsers.add_parser("health", help="Run health check")
    health_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    health_parser.set_defaults(func=cmd_health)

    # reset command
    reset_parser = subparsers.add_parser("reset", help="Reset circuit breaker")
    reset_parser.set_defaults(func=cmd_reset)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
