#!/usr/bin/env python3
"""
Spec Pipeline Orchestrator - Production-Ready

Orchestrates the complete SpecKit workflow with:
- State persistence (PostgreSQL checkpoints)
- Step tracking (QuestDB metrics)
- Fallbacks for external services
- Retry logic (exponential backoff)
- Resume from failure capability

USAGE:
    python spec_pipeline.py "Feature description"
    python spec_pipeline.py --resume <run_id>
    python spec_pipeline.py --dry-run "Feature description"
    python spec_pipeline.py --status <run_id>
"""

import argparse
import json
import os
import random
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Callable, Optional
from contextlib import contextmanager

# OpenTelemetry tracing (optional, graceful fallback)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource

    # Setup tracer
    resource = Resource.create({"service.name": "spec-pipeline"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    TRACER = trace.get_tracer("spec-pipeline")
    OTEL_ENABLED = True
except ImportError:
    TRACER = None
    OTEL_ENABLED = False


@contextmanager
def trace_step(name: str, attributes: dict = None):
    """Context manager for tracing pipeline steps. Graceful fallback if no OpenTelemetry."""
    if OTEL_ENABLED and TRACER:
        with TRACER.start_as_current_span(name, attributes=attributes or {}) as span:
            try:
                yield span
            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise
    else:
        # Fallback: just yield None, no tracing
        yield None


# Load environment
ENV_FILE = Path.home() / ".claude" / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


# =============================================================================
# Configuration
# =============================================================================

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5433))  # N8N postgres on 5433
POSTGRES_DB = os.getenv("POSTGRES_DB", "n8n")
POSTGRES_USER = os.getenv("POSTGRES_USER", "n8n")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "n8n")

QUESTDB_HOST = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_ILP_PORT = int(os.getenv("QUESTDB_ILP_PORT", 9009))

SPECKIT_DIR = Path.home() / ".specify"
CLAUDE_SCRIPTS = Path.home() / ".claude" / "scripts"


# =============================================================================
# State Machine
# =============================================================================


class PipelineState(str, Enum):
    """Pipeline states with string values for database storage."""

    NOT_STARTED = "not_started"
    CONSTITUTION = "constitution"
    SPEC_CREATED = "spec_created"
    CHECKLIST_DONE = "checklist_done"
    CLARIFIED = "clarified"
    RESEARCHED = "researched"
    PLAN_CREATED = "plan_created"
    TASKS_CREATED = "tasks_created"
    ANALYZED = "analyzed"
    ISSUES_CREATED = "issues_created"
    VERIFIED = "verified"
    SYNCED = "synced"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# State transitions (ordered)
STATE_ORDER = [
    PipelineState.NOT_STARTED,
    PipelineState.CONSTITUTION,
    PipelineState.SPEC_CREATED,
    PipelineState.CHECKLIST_DONE,
    PipelineState.CLARIFIED,
    PipelineState.RESEARCHED,
    PipelineState.PLAN_CREATED,
    PipelineState.TASKS_CREATED,
    PipelineState.ANALYZED,
    PipelineState.ISSUES_CREATED,
    PipelineState.VERIFIED,
    PipelineState.SYNCED,
    PipelineState.COMPLETED,
]

# Optional steps (can be skipped)
OPTIONAL_STEPS = {
    PipelineState.CHECKLIST_DONE,
    PipelineState.CLARIFIED,
    PipelineState.RESEARCHED,
    PipelineState.ANALYZED,
    PipelineState.VERIFIED,
    PipelineState.SYNCED,
}


# =============================================================================
# Retry Decorator
# =============================================================================


class RetriableError(Exception):
    """Error that can be retried."""

    pass


class FatalError(Exception):
    """Error that should not be retried."""

    pass


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retriable: tuple = (ConnectionError, TimeoutError, RetriableError, socket.error),
):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        retriable: Tuple of exception types to retry
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retriable as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise

                    # Exponential backoff with jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, delay * 0.1)
                    time.sleep(delay + jitter)

                    print(f"  Retry {attempt}/{max_attempts} after {delay:.1f}s: {e}")

                except FatalError:
                    raise

            raise last_exception

        return wrapper

    return decorator


# =============================================================================
# Circuit Breaker
# =============================================================================


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""

    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    last_failure_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit breaker for external services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 3,
        reset_timeout: int = 60,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = CircuitBreakerState()

    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._state.state == "open":
            # Check if we should transition to half-open
            if self._state.opened_at:
                elapsed = (datetime.now() - self._state.opened_at).total_seconds()
                if elapsed >= self.reset_timeout:
                    self._state.state = "half_open"
                    return False
            return True
        return False

    def record_success(self):
        """Record successful call."""
        self._state.failure_count = 0
        self._state.state = "closed"

    def record_failure(self, error: str = None):
        """Record failed call."""
        self._state.failure_count += 1
        self._state.last_failure_at = datetime.now()

        if self._state.failure_count >= self.failure_threshold:
            self._state.state = "open"
            self._state.opened_at = datetime.now()
            print(f"  Circuit OPEN for {self.service_name}: {error}")

    def __enter__(self):
        if self.is_open():
            raise RetriableError(f"Circuit open for {self.service_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(str(exc_val) if exc_val else None)
        return False


# Global circuit breakers
CIRCUITS = {
    "github": CircuitBreaker("github", failure_threshold=3, reset_timeout=60),
    "n8n": CircuitBreaker("n8n", failure_threshold=2, reset_timeout=120),
    "context7": CircuitBreaker("context7", failure_threshold=3, reset_timeout=30),
    "postgres": CircuitBreaker("postgres", failure_threshold=3, reset_timeout=30),
    "questdb": CircuitBreaker("questdb", failure_threshold=5, reset_timeout=60),
}


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


def _escape_field(value: str) -> str:
    """Escape field string value for ILP."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def log_pipeline_metric(
    run_id: str,
    project: str,
    step_name: str,
    duration_ms: int,
    status: str,
    retry_count: int = 0,
    error_type: str = None,
) -> bool:
    """Log pipeline step metric to QuestDB."""
    if CIRCUITS["questdb"].is_open():
        return False

    sock = _get_questdb_socket()
    if not sock:
        return False

    try:
        # Build ILP line
        tags = f"run_id={_escape_tag(run_id)},project={_escape_tag(project)},step_name={_escape_tag(step_name)}"
        fields = f'duration_ms={duration_ms}i,status="{_escape_field(status)}",retry_count={retry_count}i'
        if error_type:
            fields += f',error_type="{_escape_field(error_type)}"'

        timestamp_ns = int(datetime.now().timestamp() * 1e9)
        line = f"spec_pipeline_metrics,{tags} {fields} {timestamp_ns}\n"

        sock.sendall(line.encode())
        CIRCUITS["questdb"].record_success()
        return True

    except (socket.error, OSError) as e:
        _reset_questdb_socket()
        CIRCUITS["questdb"].record_failure(str(e))
        return False


# =============================================================================
# Discord Alerting
# =============================================================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def send_pipeline_alert(
    run_id: str,
    project: str,
    step_name: str,
    error_message: str,
    severity: str = "error",
) -> bool:
    """Send pipeline failure alert to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return False

    import urllib.request
    import urllib.error

    color = 0xDC3545 if severity == "error" else 0xFFC107  # Red or Yellow

    payload = {
        "embeds": [
            {
                "title": f"{'🔴' if severity == 'error' else '⚠️'} Spec Pipeline {severity.upper()}",
                "color": color,
                "fields": [
                    {"name": "Project", "value": project, "inline": True},
                    {"name": "Step", "value": step_name, "inline": True},
                    {"name": "Run ID", "value": f"`{run_id[:8]}...`", "inline": True},
                    {
                        "name": "Error",
                        "value": f"```{error_message[:500]}```",
                        "inline": False,
                    },
                ],
                "footer": {"text": "Spec Pipeline Orchestrator"},
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
# PostgreSQL Checkpoint
# =============================================================================


def _get_pg_connection():
    """Get PostgreSQL connection."""
    try:
        import psycopg2

        return psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            connect_timeout=5,
        )
    except ImportError:
        print("Warning: psycopg2 not installed, using file-based checkpoint")
        return None
    except Exception as e:
        CIRCUITS["postgres"].record_failure(str(e))
        return None


@dataclass
class PipelineRun:
    """Pipeline run data."""

    run_id: str
    project: str
    feature_description: str
    current_state: PipelineState
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    steps: dict = field(default_factory=dict)


class CheckpointManager:
    """Manages pipeline checkpoints in PostgreSQL with file fallback."""

    def __init__(self):
        self._conn = None
        self._use_file = False
        self._file_path = Path.home() / ".claude" / "metrics" / "pipeline_runs.json"

    def _get_conn(self):
        """Get or create connection."""
        if self._use_file:
            return None

        if self._conn is None or self._conn.closed:
            self._conn = _get_pg_connection()
            if self._conn is None:
                self._use_file = True

        return self._conn

    def _ensure_tables(self):
        """Ensure tables exist."""
        conn = self._get_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS spec_pipeline_runs (
                            run_id UUID PRIMARY KEY,
                            project VARCHAR(255),
                            feature_description TEXT,
                            current_state VARCHAR(50),
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW(),
                            metadata JSONB DEFAULT '{}'
                        )
                    """
                    )
                conn.commit()
            except Exception as e:
                print(f"Warning: Could not create tables: {e}")
                self._use_file = True

    def save(self, run: PipelineRun):
        """Save pipeline run to checkpoint."""
        conn = self._get_conn()

        if conn and not self._use_file:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO spec_pipeline_runs
                            (run_id, project, feature_description, current_state, metadata)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (run_id) DO UPDATE SET
                            current_state = EXCLUDED.current_state,
                            updated_at = NOW(),
                            metadata = EXCLUDED.metadata
                    """,
                        (
                            run.run_id,
                            run.project,
                            run.feature_description,
                            run.current_state.value,
                            json.dumps(run.metadata),
                        ),
                    )
                conn.commit()
                return
            except Exception as e:
                print(f"Warning: PostgreSQL save failed: {e}")
                self._use_file = True

        # File fallback
        self._save_to_file(run)

    def load(self, run_id: str) -> Optional[PipelineRun]:
        """Load pipeline run from checkpoint."""
        conn = self._get_conn()

        if conn and not self._use_file:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT run_id, project, feature_description, current_state,
                               created_at, updated_at, metadata
                        FROM spec_pipeline_runs
                        WHERE run_id = %s
                    """,
                        (run_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return PipelineRun(
                            run_id=str(row[0]),
                            project=row[1],
                            feature_description=row[2],
                            current_state=PipelineState(row[3]),
                            created_at=row[4],
                            updated_at=row[5],
                            metadata=row[6] or {},
                        )
            except Exception as e:
                print(f"Warning: PostgreSQL load failed: {e}")
                self._use_file = True

        # File fallback
        return self._load_from_file(run_id)

    def _save_to_file(self, run: PipelineRun):
        """Save to JSON file (fallback)."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        runs = {}
        if self._file_path.exists():
            try:
                runs = json.loads(self._file_path.read_text())
            except Exception:
                pass

        runs[run.run_id] = {
            "run_id": run.run_id,
            "project": run.project,
            "feature_description": run.feature_description,
            "current_state": run.current_state.value,
            "created_at": run.created_at.isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": run.metadata,
        }

        self._file_path.write_text(json.dumps(runs, indent=2))

    def _load_from_file(self, run_id: str) -> Optional[PipelineRun]:
        """Load from JSON file (fallback)."""
        if not self._file_path.exists():
            return None

        try:
            runs = json.loads(self._file_path.read_text())
            if run_id in runs:
                data = runs[run_id]
                return PipelineRun(
                    run_id=data["run_id"],
                    project=data["project"],
                    feature_description=data["feature_description"],
                    current_state=PipelineState(data["current_state"]),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(
                        data.get("updated_at", data["created_at"])
                    ),
                    metadata=data.get("metadata", {}),
                )
        except Exception:
            pass

        return None

    def close(self):
        """Close connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()


# =============================================================================
# Step Executors
# =============================================================================


@dataclass
class StepResult:
    """Result of a step execution."""

    success: bool
    skipped: bool = False
    skip_reason: str = None
    error: str = None
    output: str = None
    duration_ms: int = 0


def _run_skill(skill_name: str, args: str = None, timeout: int = 300) -> StepResult:
    """
    Run a SpecKit skill.

    Two modes:
    1. Interactive (default): Return skill command for Claude to execute
    2. Batch (--batch flag): Use claude CLI to execute non-interactively

    In interactive mode, the orchestrator is meant to be called by Claude,
    which will then execute the returned skill command.
    """
    start = time.time()

    # Build skill command
    skill_cmd = f"/speckit:{skill_name}"
    if args:
        skill_cmd += f" {args}"

    # Check if batch mode is enabled (via environment variable)
    batch_mode = os.getenv("SPEC_PIPELINE_BATCH", "false").lower() == "true"

    if batch_mode:
        # Use claude CLI to run skill non-interactively
        result = _run_skill_batch(skill_cmd, timeout)
    else:
        # Interactive mode: Return instruction for Claude to execute
        result = _run_skill_interactive(skill_cmd)

    result.duration_ms = int((time.time() - start) * 1000)
    return result


def _run_skill_batch(skill_cmd: str, timeout: int) -> StepResult:
    """
    Run skill using claude CLI in batch mode.

    This creates a new Claude session to execute the skill.
    """
    try:
        # Build the prompt that instructs Claude to run the skill
        prompt = f"""Execute the following skill command and report the result:

{skill_cmd}

After completion, summarize what was created/modified."""

        # Run claude in print mode
        result = subprocess.run(
            [
                "claude",
                "-p",  # Print mode (non-interactive)
                "--permission-mode",
                "bypassPermissions",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.cwd()),
        )

        if result.returncode == 0:
            return StepResult(
                success=True,
                output=result.stdout[:500] if result.stdout else "Completed",
            )
        else:
            return StepResult(
                success=False,
                error=result.stderr[:200] if result.stderr else "Unknown error",
            )

    except subprocess.TimeoutExpired:
        return StepResult(
            success=False,
            error=f"Skill timed out after {timeout}s",
        )
    except FileNotFoundError:
        return StepResult(
            success=False,
            error="claude CLI not found - install claude-code",
        )
    except Exception as e:
        return StepResult(
            success=False,
            error=str(e)[:200],
        )


def _run_skill_interactive(skill_cmd: str) -> StepResult:
    """
    Interactive mode: Return skill command for Claude to execute.

    In this mode, the orchestrator is called by Claude, and we return
    instructions for Claude to execute the skill in the current session.
    """
    # Write the skill command to a state file for Claude to pick up
    state_file = Path.home() / ".claude" / "metrics" / "pipeline_next_skill.txt"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        state_file.write_text(skill_cmd)
    except Exception:
        pass

    print(f"  >>> Execute: {skill_cmd}")

    return StepResult(
        success=True,
        output=f"EXECUTE: {skill_cmd}",
    )


def step_constitution(run: PipelineRun) -> StepResult:
    """Step 0: Project Constitution (one-time setup)."""
    constitution_path = SPECKIT_DIR / "memory" / "constitution.md"

    if constitution_path.exists():
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="Constitution already exists",
        )

    return _run_skill("constitution")


def step_specify(run: PipelineRun) -> StepResult:
    """Step 1: Feature Specification."""
    return _run_skill("specify", f'"{run.feature_description}"')


def step_checklist(run: PipelineRun) -> StepResult:
    """Step 1.5: Requirements Quality Check (optional)."""
    # Check complexity from metadata
    complexity = run.metadata.get("complexity", "medium")
    if complexity == "low":
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="Low complexity, checklist skipped",
        )

    return _run_skill("checklist")


def step_clarify(run: PipelineRun) -> StepResult:
    """Step 2: Clarification (if needed)."""
    return _run_skill("clarify")


def step_research(run: PipelineRun) -> StepResult:
    """Step 3: Academic Research (smart suggestion)."""
    # Check if research is beneficial
    importance = run.metadata.get("importance", "medium")
    complexity = run.metadata.get("complexity", "medium")

    if importance == "low" and complexity == "low":
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="Low importance/complexity, research skipped",
        )

    # Check N8N circuit breaker
    if CIRCUITS["n8n"].is_open():
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="N8N circuit open, falling back to web search",
        )

    # Trigger N8N research
    trigger_script = CLAUDE_SCRIPTS / "trigger-n8n-research.sh"
    if trigger_script.exists():
        try:
            result = subprocess.run(
                [str(trigger_script), run.feature_description],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return StepResult(
                    success=True,
                    output="Research pipeline triggered (async)",
                )
        except subprocess.TimeoutExpired:
            CIRCUITS["n8n"].record_failure("Timeout")
        except Exception as e:
            CIRCUITS["n8n"].record_failure(str(e))

    return StepResult(
        success=True,
        skipped=True,
        skip_reason="Research trigger failed, continuing without",
    )


def step_plan(run: PipelineRun) -> StepResult:
    """Step 4: Implementation Plan."""
    # Extract technologies from spec for Context7 doc fetching
    technologies = _extract_technologies_from_spec(run)

    if technologies:
        run.metadata["technologies"] = technologies
        print(f"  Technologies detected: {', '.join(technologies)}")
        print("  Context7 will fetch docs for these during planning")

    return _run_skill("plan")


def _extract_technologies_from_spec(run: PipelineRun) -> list[str]:
    """
    Extract technology names from spec.md for Context7 doc fetching.

    Looks for common patterns:
    - Tech stack mentions
    - Framework names
    - Library references
    """
    # Common technology keywords to detect
    TECH_PATTERNS = {
        # Python
        "python",
        "fastapi",
        "django",
        "flask",
        "pydantic",
        "sqlalchemy",
        "pytest",
        "asyncio",
        "celery",
        "redis",
        "pandas",
        "numpy",
        # JavaScript/TypeScript
        "react",
        "vue",
        "angular",
        "nextjs",
        "nodejs",
        "express",
        "typescript",
        "javascript",
        "tailwind",
        "prisma",
        # Databases
        "postgresql",
        "postgres",
        "mysql",
        "mongodb",
        "sqlite",
        "questdb",
        "timescaledb",
        "clickhouse",
        # Infrastructure
        "docker",
        "kubernetes",
        "terraform",
        "ansible",
        "nginx",
        "aws",
        "gcp",
        "azure",
        # Other
        "graphql",
        "rest",
        "grpc",
        "websocket",
        "kafka",
        "rabbitmq",
    }

    # Try to read spec.md
    spec_paths = [
        SPECKIT_DIR / "specs" / "spec.md",
        Path.cwd() / ".specify" / "specs" / "spec.md",
        Path.cwd() / "spec.md",
    ]

    spec_content = ""
    for spec_path in spec_paths:
        if spec_path.exists():
            try:
                spec_content = spec_path.read_text().lower()
                break
            except Exception:
                pass

    if not spec_content:
        # Use feature description as fallback
        spec_content = run.feature_description.lower()

    # Find matching technologies
    found = []
    for tech in TECH_PATTERNS:
        if tech in spec_content:
            found.append(tech)

    # Limit to top 5 most relevant
    return found[:5]


def step_tasks(run: PipelineRun) -> StepResult:
    """Step 5: Task Generation."""
    return _run_skill("tasks")


def step_analyze(run: PipelineRun) -> StepResult:
    """Step 6: Cross-Artifact Analysis."""
    return _run_skill("analyze")


def step_issues(run: PipelineRun) -> StepResult:
    """Step 7: GitHub Issues Sync."""
    if CIRCUITS["github"].is_open():
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="GitHub circuit open",
        )

    return _run_skill("taskstoissues")


def step_verify(run: PipelineRun) -> StepResult:
    """Step 8: Verification."""
    # Check if there are implementations to verify
    tasks_path = run.metadata.get("tasks_path")
    if not tasks_path:
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="No tasks to verify",
        )

    # Run verify-tasks
    try:
        result = subprocess.run(
            ["python", "-m", "verify_tasks", "--commit"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return StepResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )
    except Exception as e:
        return StepResult(
            success=True,
            skipped=True,
            skip_reason=f"Verification skipped: {e}",
        )


def step_sync(run: PipelineRun) -> StepResult:
    """Step 9: Issue Sync."""
    sync_script = Path("scripts/sync_tasks_issues.py")
    if not sync_script.exists():
        return StepResult(
            success=True,
            skipped=True,
            skip_reason="Sync script not found",
        )

    try:
        result = subprocess.run(
            ["python", str(sync_script)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return StepResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )
    except Exception as e:
        return StepResult(
            success=True,
            skipped=True,
            skip_reason=f"Sync skipped: {e}",
        )


# Step registry
STEP_EXECUTORS = {
    PipelineState.CONSTITUTION: step_constitution,
    PipelineState.SPEC_CREATED: step_specify,
    PipelineState.CHECKLIST_DONE: step_checklist,
    PipelineState.CLARIFIED: step_clarify,
    PipelineState.RESEARCHED: step_research,
    PipelineState.PLAN_CREATED: step_plan,
    PipelineState.TASKS_CREATED: step_tasks,
    PipelineState.ANALYZED: step_analyze,
    PipelineState.ISSUES_CREATED: step_issues,
    PipelineState.VERIFIED: step_verify,
    PipelineState.SYNCED: step_sync,
}


# =============================================================================
# Pipeline Orchestrator
# =============================================================================


class SpecPipelineOrchestrator:
    """Main orchestrator for spec pipeline."""

    def __init__(self, project: str = None, dry_run: bool = False):
        self.project = project or self._detect_project()
        self.dry_run = dry_run
        self.checkpoint = CheckpointManager()

    def _detect_project(self) -> str:
        """Detect project name from git or directory."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return Path(result.stdout.strip()).name
        except Exception:
            pass

        return Path.cwd().name

    def run(self, feature_description: str, run_id: str = None) -> PipelineRun:
        """
        Run the pipeline for a feature.

        Args:
            feature_description: Description of the feature to implement
            run_id: Optional run ID to resume from

        Returns:
            PipelineRun with final state
        """
        # Create or load run
        if run_id:
            run = self.checkpoint.load(run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            print(f"Resuming run {run_id} from state {run.current_state.value}")
        else:
            run = PipelineRun(
                run_id=str(uuid.uuid4()),
                project=self.project,
                feature_description=feature_description,
                current_state=PipelineState.NOT_STARTED,
            )
            print(f"Starting new run {run.run_id}")

        if self.dry_run:
            return self._dry_run(run)

        # Execute pipeline
        try:
            run = self._execute_pipeline(run)
        except Exception as e:
            run.current_state = PipelineState.FAILED
            run.metadata["error"] = str(e)
            self.checkpoint.save(run)
            raise

        return run

    def _dry_run(self, run: PipelineRun) -> PipelineRun:
        """Show what would be executed without running."""
        print("\n=== DRY RUN ===\n")
        print(f"Project: {run.project}")
        print(f"Feature: {run.feature_description}")
        print(f"Run ID: {run.run_id}")
        print(f"Current State: {run.current_state.value}")
        print("\nSteps to execute:")

        start_idx = STATE_ORDER.index(run.current_state) + 1
        for i, state in enumerate(STATE_ORDER[start_idx:-1], 1):
            optional = " (optional)" if state in OPTIONAL_STEPS else ""
            print(f"  {i}. {state.value}{optional}")

        return run

    def _execute_pipeline(self, run: PipelineRun) -> PipelineRun:
        """Execute pipeline steps."""
        # Find starting point
        start_idx = STATE_ORDER.index(run.current_state) + 1

        for state in STATE_ORDER[start_idx:-1]:  # Skip COMPLETED
            executor = STEP_EXECUTORS.get(state)
            if not executor:
                continue

            print(f"\n[{state.value}] Starting...")
            start_time = time.time()

            # Wrap step execution with tracing
            with trace_step(
                f"pipeline.{state.value}",
                {"run_id": run.run_id, "project": run.project},
            ):
                try:
                    result = self._execute_step_with_retry(executor, run, state)
                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    log_pipeline_metric(
                        run.run_id,
                        run.project,
                        state.value,
                        duration_ms,
                        "failed",
                        error_type=type(e).__name__,
                    )
                    # Send alert for unhandled exceptions
                    send_pipeline_alert(
                        run.run_id,
                        run.project,
                        state.value,
                        str(e),
                        severity="error",
                    )
                    raise

            duration_ms = int((time.time() - start_time) * 1000)

            if result.skipped:
                print(f"  Skipped: {result.skip_reason}")
                status = "skipped"
            elif result.success:
                print(f"  Completed in {duration_ms}ms")
                status = "success"
            else:
                print(f"  Failed: {result.error}")
                status = "failed"

            # Log metric
            log_pipeline_metric(
                run.run_id,
                run.project,
                state.value,
                duration_ms,
                status,
                error_type=result.error[:50] if result.error else None,
            )

            # Update state
            run.current_state = state
            run.steps[state.value] = {
                "status": status,
                "duration_ms": duration_ms,
                "output": result.output,
                "error": result.error,
            }
            self.checkpoint.save(run)

            # Handle failure
            if not result.success and not result.skipped:
                if state not in OPTIONAL_STEPS:
                    # Required step failed - send error alert
                    send_pipeline_alert(
                        run.run_id,
                        run.project,
                        state.value,
                        result.error or "Unknown error",
                        severity="error",
                    )
                    run.current_state = PipelineState.FAILED
                    self.checkpoint.save(run)
                    raise FatalError(
                        f"Required step {state.value} failed: {result.error}"
                    )
                else:
                    # Optional step failed - send warning alert
                    send_pipeline_alert(
                        run.run_id,
                        run.project,
                        state.value,
                        result.error or "Unknown error",
                        severity="warning",
                    )

        # Pipeline completed
        run.current_state = PipelineState.COMPLETED
        self.checkpoint.save(run)
        print(f"\n=== Pipeline completed: {run.run_id} ===")

        return run

    @retry(max_attempts=3, base_delay=2.0, max_delay=30.0)
    def _execute_step_with_retry(
        self, executor: Callable, run: PipelineRun, state: PipelineState
    ) -> StepResult:
        """Execute step with retry logic."""
        return executor(run)

    def get_status(self, run_id: str) -> Optional[dict]:
        """Get status of a run."""
        run = self.checkpoint.load(run_id)
        if not run:
            return None

        return {
            "run_id": run.run_id,
            "project": run.project,
            "feature": run.feature_description,
            "state": run.current_state.value,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "steps": run.steps,
        }


# =============================================================================
# CLI
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Spec Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python spec_pipeline.py "Add user authentication"
  python spec_pipeline.py --resume abc123
  python spec_pipeline.py --dry-run "Add caching"
  python spec_pipeline.py --status abc123
        """,
    )

    parser.add_argument("feature", nargs="?", help="Feature description")
    parser.add_argument("--resume", metavar="RUN_ID", help="Resume from run ID")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would execute"
    )
    parser.add_argument("--status", metavar="RUN_ID", help="Get run status")
    parser.add_argument("--project", help="Override project name")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run in batch mode using claude CLI (non-interactive)",
    )

    args = parser.parse_args()

    # Set batch mode environment variable
    if args.batch:
        os.environ["SPEC_PIPELINE_BATCH"] = "true"

    orchestrator = SpecPipelineOrchestrator(
        project=args.project,
        dry_run=args.dry_run,
    )

    if args.status:
        status = orchestrator.get_status(args.status)
        if status:
            print(json.dumps(status, indent=2))
        else:
            print(f"Run {args.status} not found")
            sys.exit(1)

    elif args.resume:
        run = orchestrator.run(None, run_id=args.resume)
        print(f"\nFinal state: {run.current_state.value}")

    elif args.feature:
        run = orchestrator.run(args.feature)
        print(f"\nFinal state: {run.current_state.value}")
        print(f"Run ID: {run.run_id}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
