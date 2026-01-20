#!/usr/bin/env python3
"""
Pipeline metrics sync to QuestDB.

Uses existing schema from ~/.claude/schemas/metrics.yaml.
Reuses same ILP pattern as pre-push-review.py hook.

Tables used:
- claude_agents (agent spawns from Task tool)
- claude_tasks (from TodoWrite)
- claude_sessions (session summary)

This script is called by /gsd:pipeline and /spec-pipeline to record metrics.
"""

import json
import socket
import sys
from datetime import datetime, timezone


QUESTDB_HOST = "localhost"
QUESTDB_PORT = 9009


def send_to_questdb(line: str) -> bool:
    """Send ILP line to QuestDB."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((QUESTDB_HOST, QUESTDB_PORT))
        sock.sendall(line.encode())
        sock.close()
        return True
    except Exception as e:
        print(f"Warning: QuestDB unavailable: {e}", file=sys.stderr)
        return False


def escape_string(s: str) -> str:
    """Escape string for ILP format."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def record_agent_spawn(
    project: str,
    session_id: str,
    agent_type: str,
    duration_ms: int | None = None,
    success: bool = True,
    error: str | None = None,
) -> bool:
    """Record agent spawn to claude_agents table."""
    ts_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1e9)

    fields = [f"success={str(success).lower()}"]
    if duration_ms is not None:
        fields.append(f"duration_ms={duration_ms}i")
    if error:
        fields.append(f'error="{escape_string(error)}"')

    line = f"claude_agents,project={project},session_id={session_id},agent_type={agent_type} {','.join(fields)} {ts_ns}\n"
    return send_to_questdb(line)


def record_task(
    project: str,
    session_id: str,
    task_status: str,
    task_content: str,
    duration_min: float | None = None,
) -> bool:
    """Record task to claude_tasks table."""
    ts_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1e9)

    fields = [f'task_content="{escape_string(task_content[:100])}"']
    if duration_min is not None:
        fields.append(f"duration_min={duration_min}")

    line = f"claude_tasks,project={project},session_id={session_id},task_status={task_status} {','.join(fields)} {ts_ns}\n"
    return send_to_questdb(line)


def record_pipeline_step(
    project: str,
    step_name: str,
    status: str,
    phase: int | None = None,
    plan: int | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
) -> bool:
    """
    Record pipeline step to claude_agents table.

    Maps pipeline steps to agent_type for unified metrics.
    """
    ts_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1e9)

    # Map step to agent_type
    agent_type = f"pipeline_{step_name}"

    tags = [f"project={project}", f"agent_type={agent_type}"]
    if phase is not None:
        tags.append(f"phase={phase}")
    if plan is not None:
        tags.append(f"plan={plan}")

    fields = [f"success={str(status == 'completed').lower()}"]
    if duration_ms is not None:
        fields.append(f"duration_ms={duration_ms}i")
    if error:
        fields.append(f'error="{escape_string(error)}"')

    tag_str = ",".join(tags)
    field_str = ",".join(fields)
    line = f"claude_agents,{tag_str} {field_str} {ts_ns}\n"
    return send_to_questdb(line)


# CLI interface
if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Pipeline metrics to QuestDB")
    parser.add_argument("command", choices=["agent", "task", "step"])
    parser.add_argument("--project", default=os.path.basename(os.getcwd()))
    parser.add_argument("--session", default="unknown")
    parser.add_argument("--type", dest="agent_type", help="Agent type")
    parser.add_argument("--step", help="Step name")
    parser.add_argument("--status", default="completed")
    parser.add_argument("--phase", type=int)
    parser.add_argument("--plan", type=int)
    parser.add_argument("--duration", type=int, help="Duration in ms")
    parser.add_argument("--content", help="Task content")
    parser.add_argument("--error", help="Error message")

    args = parser.parse_args()

    if args.command == "agent":
        success = record_agent_spawn(
            project=args.project,
            session_id=args.session,
            agent_type=args.agent_type or "unknown",
            duration_ms=args.duration,
            success=args.status == "completed",
            error=args.error,
        )
    elif args.command == "task":
        success = record_task(
            project=args.project,
            session_id=args.session,
            task_status=args.status,
            task_content=args.content or "",
            duration_min=args.duration / 60000.0 if args.duration else None,
        )
    elif args.command == "step":
        success = record_pipeline_step(
            project=args.project,
            step_name=args.step or "unknown",
            status=args.status,
            phase=args.phase,
            plan=args.plan,
            duration_ms=args.duration,
            error=args.error,
        )
    else:
        success = False

    print(json.dumps({"success": success}))
