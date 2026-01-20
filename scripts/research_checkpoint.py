#!/usr/bin/env python3
"""
Research Checkpoint Manager - State persistence for research flows

Provides checkpointing for research to enable resume-from-failure.
Uses file-based storage (PostgreSQL optional).

States:
- NOT_STARTED: Initial state
- QUERYING: Generating search queries
- SEARCHING: Executing searches
- TRIANGULATING: Cross-referencing sources
- PMW_ANALYSIS: Running Prove Me Wrong
- SYNTHESIZING: Creating final output
- COMPLETED: Research finished
- FAILED: Unrecoverable error

USAGE:
    from research_checkpoint import ResearchCheckpoint

    ckpt = ResearchCheckpoint(query="machine learning")
    ckpt.transition(ResearchState.SEARCHING)
    ckpt.save_data("web_results", results)

    # Later resume
    ckpt = ResearchCheckpoint.load(run_id)
    if ckpt.state == ResearchState.SEARCHING:
        # Resume from where we left off
        ...

CLI:
    python research_checkpoint.py create "query"
    python research_checkpoint.py status <run_id>
    python research_checkpoint.py resume <run_id>
    python research_checkpoint.py list
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


# =============================================================================
# Configuration
# =============================================================================

CHECKPOINT_DIR = Path.home() / ".claude" / "metrics" / "research_checkpoints"


# =============================================================================
# Research State Machine
# =============================================================================


class ResearchState(str, Enum):
    """Research flow states."""

    NOT_STARTED = "not_started"
    QUERYING = "querying"
    SEARCHING = "searching"
    CACHING = "caching"
    TRIANGULATING = "triangulating"
    PMW_ANALYSIS = "pmw_analysis"
    SYNTHESIZING = "synthesizing"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid state transitions
STATE_TRANSITIONS = {
    ResearchState.NOT_STARTED: [ResearchState.QUERYING, ResearchState.FAILED],
    ResearchState.QUERYING: [ResearchState.SEARCHING, ResearchState.FAILED],
    ResearchState.SEARCHING: [
        ResearchState.CACHING,
        ResearchState.TRIANGULATING,
        ResearchState.FAILED,
    ],
    ResearchState.CACHING: [ResearchState.TRIANGULATING, ResearchState.FAILED],
    ResearchState.TRIANGULATING: [
        ResearchState.PMW_ANALYSIS,
        ResearchState.SYNTHESIZING,
        ResearchState.FAILED,
    ],
    ResearchState.PMW_ANALYSIS: [ResearchState.SYNTHESIZING, ResearchState.FAILED],
    ResearchState.SYNTHESIZING: [
        ResearchState.SAVING,
        ResearchState.COMPLETED,
        ResearchState.FAILED,
    ],
    ResearchState.SAVING: [ResearchState.COMPLETED, ResearchState.FAILED],
    ResearchState.COMPLETED: [],  # Terminal state
    ResearchState.FAILED: [ResearchState.NOT_STARTED],  # Can retry from beginning
}


# =============================================================================
# Checkpoint Data
# =============================================================================


@dataclass
class ResearchCheckpointData:
    """Research checkpoint data."""

    run_id: str
    query: str
    state: str
    created_at: str
    updated_at: str
    iteration: int = 0
    confidence: float = 0.0
    sources_searched: int = 0
    findings_count: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_data: Dict[str, Any] = field(default_factory=dict)
    history: list = field(default_factory=list)


# =============================================================================
# Checkpoint Manager
# =============================================================================


class ResearchCheckpoint:
    """
    Research checkpoint manager.

    Provides state persistence for research flows, enabling:
    - Resume from failure
    - State tracking
    - Data storage per phase
    """

    def __init__(
        self,
        run_id: str | None = None,
        query: str = "",
    ):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self._data = ResearchCheckpointData(
            run_id=self.run_id,
            query=query,
            state=ResearchState.NOT_STARTED.value,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._ensure_dir()

        # Load existing or create new
        if run_id:
            self._load()
        else:
            self._save()

    def _ensure_dir(self):
        """Ensure checkpoint directory exists."""
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    def _get_path(self) -> Path:
        """Get checkpoint file path."""
        return CHECKPOINT_DIR / f"{self.run_id}.json"

    def _load(self):
        """Load checkpoint from file."""
        path = self._get_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._data = ResearchCheckpointData(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  Failed to load checkpoint: {e}", file=sys.stderr)
        else:
            print(f"  Checkpoint not found: {self.run_id}", file=sys.stderr)

    def _save(self):
        """Save checkpoint to file."""
        path = self._get_path()
        data = {
            "run_id": self._data.run_id,
            "query": self._data.query,
            "state": self._data.state,
            "created_at": self._data.created_at,
            "updated_at": datetime.now().isoformat(),
            "iteration": self._data.iteration,
            "confidence": self._data.confidence,
            "sources_searched": self._data.sources_searched,
            "findings_count": self._data.findings_count,
            "error": self._data.error,
            "metadata": self._data.metadata,
            "state_data": self._data.state_data,
            "history": self._data.history,
        }
        path.write_text(json.dumps(data, indent=2, default=str))

    @property
    def state(self) -> ResearchState:
        """Get current state."""
        return ResearchState(self._data.state)

    @property
    def query(self) -> str:
        """Get research query."""
        return self._data.query

    def can_transition(self, new_state: ResearchState) -> bool:
        """Check if transition to new state is valid."""
        current = self.state
        allowed = STATE_TRANSITIONS.get(current, [])
        return new_state in allowed

    def transition(self, new_state: ResearchState, error: str | None = None) -> bool:
        """
        Transition to new state.

        Args:
            new_state: Target state
            error: Error message (for FAILED state)

        Returns:
            True if transition successful
        """
        if not self.can_transition(new_state):
            print(
                f"  Invalid transition: {self.state.value} -> {new_state.value}",
                file=sys.stderr,
            )
            return False

        old_state = self._data.state
        self._data.state = new_state.value
        self._data.updated_at = datetime.now().isoformat()

        if error:
            self._data.error = error

        # Record in history
        self._data.history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "from_state": old_state,
                "to_state": new_state.value,
                "iteration": self._data.iteration,
                "error": error,
            }
        )

        self._save()
        print(f"  State: {old_state} -> {new_state.value}", file=sys.stderr)
        return True

    def save_data(self, key: str, data: Any):
        """
        Save data for current state.

        Args:
            key: Data key
            data: Data to save
        """
        if self._data.state not in self._data.state_data:
            self._data.state_data[self._data.state] = {}
        self._data.state_data[self._data.state][key] = data
        self._save()

    def get_data(
        self, state: ResearchState | None = None, key: str | None = None
    ) -> Any:
        """
        Get saved data.

        Args:
            state: State to get data for (default: current)
            key: Specific key (default: all data for state)

        Returns:
            Saved data
        """
        state_key = (state or self.state).value
        state_data = self._data.state_data.get(state_key, {})

        if key:
            return state_data.get(key)
        return state_data

    def update_metrics(
        self,
        iteration: int | None = None,
        confidence: float | None = None,
        sources_searched: int | None = None,
        findings_count: int | None = None,
    ):
        """Update research metrics."""
        if iteration is not None:
            self._data.iteration = iteration
        if confidence is not None:
            self._data.confidence = confidence
        if sources_searched is not None:
            self._data.sources_searched = sources_searched
        if findings_count is not None:
            self._data.findings_count = findings_count
        self._save()

    def set_metadata(self, key: str, value: Any):
        """Set metadata value."""
        self._data.metadata[key] = value
        self._save()

    def get_metadata(self, key: str | None = None) -> Any:
        """Get metadata."""
        if key:
            return self._data.metadata.get(key)
        return self._data.metadata

    def complete(self, confidence: float | None = None):
        """Mark research as completed."""
        if confidence is not None:
            self._data.confidence = confidence
        self.transition(ResearchState.COMPLETED)

    def fail(self, error: str):
        """Mark research as failed."""
        self.transition(ResearchState.FAILED, error=error)

    def get_status(self) -> Dict[str, Any]:
        """Get full checkpoint status."""
        return {
            "run_id": self._data.run_id,
            "query": self._data.query,
            "state": self._data.state,
            "iteration": self._data.iteration,
            "confidence": self._data.confidence,
            "sources_searched": self._data.sources_searched,
            "findings_count": self._data.findings_count,
            "error": self._data.error,
            "created_at": self._data.created_at,
            "updated_at": self._data.updated_at,
            "history_count": len(self._data.history),
            "can_resume": self.state
            not in [ResearchState.COMPLETED, ResearchState.FAILED],
        }

    @classmethod
    def load(cls, run_id: str) -> Optional["ResearchCheckpoint"]:
        """Load checkpoint by run ID."""
        path = CHECKPOINT_DIR / f"{run_id}.json"
        if not path.exists():
            return None
        return cls(run_id=run_id)

    @classmethod
    def list_all(cls) -> list:
        """List all checkpoints."""
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        checkpoints = []

        for path in CHECKPOINT_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                checkpoints.append(
                    {
                        "run_id": data.get("run_id"),
                        "query": data.get("query", "")[:50],
                        "state": data.get("state"),
                        "confidence": data.get("confidence", 0),
                        "iteration": data.get("iteration", 0),
                        "updated_at": data.get("updated_at"),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                pass

        return sorted(checkpoints, key=lambda x: x.get("updated_at", ""), reverse=True)


# =============================================================================
# CLI
# =============================================================================


def cmd_create(args):
    """Create new checkpoint."""
    query = " ".join(args.query) if args.query else ""
    ckpt = ResearchCheckpoint(query=query)

    if args.json:
        print(json.dumps({"run_id": ckpt.run_id}, indent=2))
    else:
        print(f"Checkpoint created: {ckpt.run_id}")
        print(f"  Query: {query}")
        print(f"  State: {ckpt.state.value}")


def cmd_status(args):
    """Show checkpoint status."""
    ckpt = ResearchCheckpoint.load(args.run_id)
    if not ckpt:
        print(f"Checkpoint not found: {args.run_id}")
        sys.exit(1)

    status = ckpt.get_status()

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"\n{'=' * 50}")
        print(f"Research Checkpoint: {status['run_id']}")
        print(f"{'=' * 50}")
        print(
            f"Query:      {status['query'][:50]}..."
            if len(status["query"]) > 50
            else f"Query:      {status['query']}"
        )
        print(f"State:      {status['state'].upper()}")
        print(f"Iteration:  {status['iteration']}")
        print(f"Confidence: {status['confidence']:.1f}%")
        print(f"Sources:    {status['sources_searched']}")
        print(f"Findings:   {status['findings_count']}")
        if status["error"]:
            print(f"Error:      {status['error']}")
        print(f"\nCreated:    {status['created_at']}")
        print(f"Updated:    {status['updated_at']}")
        print(f"Can Resume: {'Yes' if status['can_resume'] else 'No'}")
        print(f"{'=' * 50}\n")


def cmd_transition(args):
    """Transition checkpoint state."""
    ckpt = ResearchCheckpoint.load(args.run_id)
    if not ckpt:
        print(f"Checkpoint not found: {args.run_id}")
        sys.exit(1)

    try:
        new_state = ResearchState(args.state)
    except ValueError:
        print(f"Invalid state: {args.state}")
        print(f"Valid states: {', '.join(s.value for s in ResearchState)}")
        sys.exit(1)

    success = ckpt.transition(new_state, error=args.error)
    if success:
        print(f"Transitioned to: {new_state.value}")
    else:
        print("Transition failed")
        sys.exit(1)


def cmd_list(args):
    """List all checkpoints."""
    checkpoints = ResearchCheckpoint.list_all()

    if args.json:
        print(json.dumps(checkpoints, indent=2))
    else:
        if not checkpoints:
            print("No checkpoints found")
            return

        print(f"\n{'=' * 80}")
        print("Research Checkpoints")
        print(f"{'=' * 80}")
        print(f"{'ID':<10} {'State':<15} {'Conf':<6} {'Iter':<5} {'Query':<40}")
        print("-" * 80)
        for c in checkpoints[:20]:
            print(
                f"{c['run_id']:<10} {c['state']:<15} {c['confidence']:<6.1f} {c['iteration']:<5} {c['query'][:40]}"
            )
        print(f"{'=' * 80}\n")


def cmd_delete(args):
    """Delete checkpoint."""
    path = CHECKPOINT_DIR / f"{args.run_id}.json"
    if path.exists():
        path.unlink()
        print(f"Deleted checkpoint: {args.run_id}")
    else:
        print(f"Checkpoint not found: {args.run_id}")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Research checkpoint manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # create command
    create_parser = subparsers.add_parser("create", help="Create new checkpoint")
    create_parser.add_argument("query", nargs="*", help="Research query")
    create_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    create_parser.set_defaults(func=cmd_create)

    # status command
    status_parser = subparsers.add_parser("status", help="Show checkpoint status")
    status_parser.add_argument("run_id", help="Run ID")
    status_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    status_parser.set_defaults(func=cmd_status)

    # transition command
    trans_parser = subparsers.add_parser("transition", help="Transition state")
    trans_parser.add_argument("run_id", help="Run ID")
    trans_parser.add_argument("state", help="New state")
    trans_parser.add_argument("--error", "-e", help="Error message (for failed state)")
    trans_parser.set_defaults(func=cmd_transition)

    # list command
    list_parser = subparsers.add_parser("list", help="List all checkpoints")
    list_parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    list_parser.set_defaults(func=cmd_list)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete checkpoint")
    delete_parser.add_argument("run_id", help="Run ID")
    delete_parser.set_defaults(func=cmd_delete)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
