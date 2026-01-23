# Phase 11: Ralph Integration - Research

**Completed:** 2026-01-23
**Status:** Ready for planning

## Research Summary

This research covers the technical patterns needed to integrate validation orchestrator into the Ralph loop with metrics to Grafana and context to Sentry.

---

## 1. Claude Code Hooks Architecture

### Hook Events Available

From Claude Code hooks documentation:

| Event | Trigger | Use Case |
|-------|---------|----------|
| `PreToolUse` | Before tool execution | Block/modify tool calls |
| `PostToolUse` | After tool execution | Validation, logging |
| `Stop` | Agent stop/completion | Final validation pass |
| `SessionStart` | New session | Context initialization |
| `PreCompact` | Before context compaction | Save important state |

### hooks.json Configuration

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {
          "tool_name": "Write|Edit"
        },
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/validation_hook.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": {},
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/final_validation.py"
          }
        ]
      }
    ]
  }
}
```

### TypeScript Hook SDK Interfaces

```typescript
interface PostToolUseHookInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output?: string;
  timestamp: string;
}

interface StopHookInput {
  session_id: string;
  stop_reason: "end_turn" | "max_tokens" | "stop_sequence";
  final_message?: string;
}

interface HookResult {
  decision: "approve" | "block" | "modify";
  reason?: string;
  modified_input?: Record<string, unknown>;
}
```

### Hook Integration Pattern

```python
#!/usr/bin/env python3
"""PostToolUse hook for validation orchestrator."""

import json
import sys
from pathlib import Path

def main():
    # Read hook input from stdin
    hook_input = json.loads(sys.stdin.read())

    tool_name = hook_input.get("tool_name")
    tool_input = hook_input.get("tool_input", {})

    # Only validate Write/Edit operations
    if tool_name not in ["Write", "Edit"]:
        print(json.dumps({"decision": "approve"}))
        return

    # Get file path from tool input
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        print(json.dumps({"decision": "approve"}))
        return

    # Run validation
    from orchestrator import ValidationOrchestrator

    orchestrator = ValidationOrchestrator()
    result = orchestrator.validate_file(file_path, tier=1)  # Quick Tier 1 only

    if result.has_blockers:
        print(json.dumps({
            "decision": "block",
            "reason": f"Tier 1 blockers: {result.summary}"
        }))
    else:
        print(json.dumps({"decision": "approve"}))

if __name__ == "__main__":
    main()
```

---

## 2. Sentry Python Integration

### Context Injection Patterns

```python
import sentry_sdk
from sentry_sdk import set_context, set_tag, add_breadcrumb

def inject_validation_context(result: ValidationResult):
    """Inject validation context into Sentry for debugging."""

    # Set structured context (appears in "Additional Data")
    set_context("validation", {
        "tier": result.tier,
        "passed": result.passed,
        "score": result.score,
        "blockers": len(result.blockers),
        "warnings": len(result.warnings),
        "validators_run": result.validators_run,
    })

    # Set searchable tags
    set_tag("validation.tier", str(result.tier))
    set_tag("validation.passed", str(result.passed).lower())
    set_tag("validation.score", f"{result.score:.1f}")

    # Add breadcrumb for timeline
    add_breadcrumb(
        category="validation",
        message=f"Tier {result.tier}: {result.summary}",
        level="info" if result.passed else "warning",
        data={
            "validators": result.validators_run,
            "duration_ms": result.duration_ms,
        }
    )
```

### Sentry Transaction for Validation

```python
from sentry_sdk import start_transaction, start_span

def run_validation_with_sentry(orchestrator, file_path: str):
    """Run validation with Sentry performance monitoring."""

    with start_transaction(op="validation", name="ralph_loop_validation") as transaction:
        transaction.set_tag("file", file_path)

        # Tier 1 span
        with start_span(op="tier1", description="Blocker validation"):
            tier1_result = orchestrator.validate(file_path, tier=1)

        if tier1_result.has_blockers:
            transaction.set_status("internal_error")
            return tier1_result

        # Tier 2 span (parallel)
        with start_span(op="tier2", description="Warning validation"):
            tier2_result = orchestrator.validate(file_path, tier=2)

        # Tier 3 span (parallel)
        with start_span(op="tier3", description="Monitor validation"):
            tier3_result = orchestrator.validate(file_path, tier=3)

        transaction.set_status("ok")
        return merge_results(tier1_result, tier2_result, tier3_result)
```

### Error Context Enrichment

```python
def capture_validation_error(error: Exception, context: dict):
    """Capture validation error with full context."""

    with sentry_sdk.push_scope() as scope:
        # Add validation-specific context
        scope.set_context("validation_config", context.get("config", {}))
        scope.set_context("validation_state", context.get("state", {}))

        # Add file being validated
        scope.set_extra("file_path", context.get("file_path"))
        scope.set_extra("validators_attempted", context.get("validators"))

        # Capture with fingerprint for grouping
        scope.fingerprint = ["validation-error", context.get("validator_name", "unknown")]

        sentry_sdk.capture_exception(error)
```

---

## 3. Grafana Metrics Integration

### Prometheus Push Gateway Pattern

```python
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    push_to_gateway,
    delete_from_gateway
)

# Create isolated registry for validation metrics
validation_registry = CollectorRegistry()

# Define metrics
validation_runs = Counter(
    'validation_runs_total',
    'Total validation runs',
    ['tier', 'result', 'project'],
    registry=validation_registry
)

validation_duration = Histogram(
    'validation_duration_seconds',
    'Validation duration',
    ['tier', 'validator'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=validation_registry
)

validation_score = Gauge(
    'validation_score',
    'Current validation score',
    ['tier', 'project'],
    registry=validation_registry
)

blockers_count = Gauge(
    'validation_blockers_count',
    'Number of blockers found',
    ['project', 'validator'],
    registry=validation_registry
)

def push_validation_metrics(result: ValidationResult, project: str):
    """Push validation metrics to Prometheus Pushgateway."""

    # Increment run counter
    validation_runs.labels(
        tier=str(result.tier),
        result="pass" if result.passed else "fail",
        project=project
    ).inc()

    # Record duration per validator
    for validator, duration in result.durations.items():
        validation_duration.labels(
            tier=str(result.tier),
            validator=validator
        ).observe(duration)

    # Set current score
    validation_score.labels(
        tier=str(result.tier),
        project=project
    ).set(result.score)

    # Set blocker count
    for validator, count in result.blocker_counts.items():
        blockers_count.labels(
            project=project,
            validator=validator
        ).set(count)

    # Push to gateway
    push_to_gateway(
        gateway='localhost:9091',
        job='validation_orchestrator',
        grouping_key={'project': project},
        registry=validation_registry
    )
```

### Grafana Annotations via MCP

```python
# Using Grafana MCP tools available in the environment

def create_validation_annotation(result: ValidationResult):
    """Create Grafana annotation for validation event."""

    # Via MCP tool call (from hook context)
    annotation = {
        "dashboardUID": "validation-dashboard",
        "time": int(time.time() * 1000),
        "timeEnd": int(time.time() * 1000),
        "tags": [
            f"tier:{result.tier}",
            f"result:{'pass' if result.passed else 'fail'}",
            f"project:{result.project}"
        ],
        "text": f"Validation Tier {result.tier}: {result.summary}"
    }

    # MCP call: mcp__grafana__create_annotation
    return annotation
```

### Grafana Dashboard JSON

```json
{
  "title": "Validation Orchestrator",
  "uid": "validation-dashboard",
  "panels": [
    {
      "title": "Validation Pass Rate",
      "type": "stat",
      "targets": [
        {
          "expr": "sum(rate(validation_runs_total{result='pass'}[1h])) / sum(rate(validation_runs_total[1h])) * 100",
          "legendFormat": "Pass Rate %"
        }
      ]
    },
    {
      "title": "Blockers by Validator",
      "type": "timeseries",
      "targets": [
        {
          "expr": "sum by (validator) (validation_blockers_count)",
          "legendFormat": "{{validator}}"
        }
      ]
    },
    {
      "title": "Validation Duration",
      "type": "heatmap",
      "targets": [
        {
          "expr": "sum by (le) (rate(validation_duration_seconds_bucket[5m]))",
          "format": "heatmap"
        }
      ]
    }
  ]
}
```

---

## 4. Ralph Loop Architecture

### Loop State Machine

```
┌─────────────┐
│   IDLE      │ ←──────────────────────┐
└──────┬──────┘                        │
       │ commit detected               │
       ▼                               │
┌─────────────┐                        │
│  VALIDATE   │                        │
│  (Tier 1)   │                        │
└──────┬──────┘                        │
       │                               │
       ├── blockers? ──► BLOCKED ──► FIX_REQUESTED
       │                               │
       ▼                               │
┌─────────────┐                        │
│  VALIDATE   │                        │
│  (Tier 2+3) │                        │ no blockers
└──────┬──────┘                        │
       │                               │
       ├── score < threshold? ────────►│
       │                               │
       ▼                               │
┌─────────────┐                        │
│  COMPLETE   │ ───────────────────────┘
└─────────────┘
```

### Loop Implementation

```python
import asyncio
from enum import Enum
from dataclasses import dataclass

class LoopState(Enum):
    IDLE = "idle"
    VALIDATING = "validating"
    BLOCKED = "blocked"
    FIX_REQUESTED = "fix_requested"
    COMPLETE = "complete"

@dataclass
class RalphLoopConfig:
    max_iterations: int = 5
    min_score_threshold: float = 70.0
    tier1_timeout_seconds: float = 30.0
    tier2_timeout_seconds: float = 120.0

class RalphLoop:
    def __init__(self, orchestrator, config: RalphLoopConfig):
        self.orchestrator = orchestrator
        self.config = config
        self.state = LoopState.IDLE
        self.iteration = 0
        self.history = []

    async def run(self, changed_files: list[str]) -> LoopResult:
        """Run validation loop until quality threshold met or blocked."""

        self.state = LoopState.VALIDATING
        self.iteration = 0

        while self.iteration < self.config.max_iterations:
            self.iteration += 1

            # Phase 1: Tier 1 blockers (fail-fast)
            tier1_result = await asyncio.wait_for(
                self.orchestrator.validate_async(changed_files, tier=1),
                timeout=self.config.tier1_timeout_seconds
            )

            # Push metrics immediately
            push_validation_metrics(tier1_result, project=get_project_name())
            inject_validation_context(tier1_result)

            if tier1_result.has_blockers:
                self.state = LoopState.BLOCKED
                return LoopResult(
                    state=self.state,
                    blockers=tier1_result.blockers,
                    message="Tier 1 blockers - fix required",
                    iteration=self.iteration
                )

            # Phase 2: Tier 2+3 in parallel (informational)
            tier2_result, tier3_result = await asyncio.gather(
                asyncio.wait_for(
                    self.orchestrator.validate_async(changed_files, tier=2),
                    timeout=self.config.tier2_timeout_seconds
                ),
                asyncio.wait_for(
                    self.orchestrator.validate_async(changed_files, tier=3),
                    timeout=self.config.tier2_timeout_seconds
                )
            )

            # Push all metrics
            push_validation_metrics(tier2_result, project=get_project_name())
            push_validation_metrics(tier3_result, project=get_project_name())

            # Calculate combined score
            combined_score = self._calculate_score(tier1_result, tier2_result, tier3_result)

            if combined_score >= self.config.min_score_threshold:
                self.state = LoopState.COMPLETE
                return LoopResult(
                    state=self.state,
                    score=combined_score,
                    message=f"Validation passed (score: {combined_score:.1f})",
                    iteration=self.iteration
                )

            # Loop continues - log iteration
            self.history.append({
                "iteration": self.iteration,
                "score": combined_score,
                "tier1_passed": not tier1_result.has_blockers,
                "tier2_warnings": len(tier2_result.warnings),
                "tier3_monitors": len(tier3_result.monitors)
            })

        # Max iterations reached
        self.state = LoopState.COMPLETE
        return LoopResult(
            state=self.state,
            score=combined_score,
            message=f"Max iterations ({self.config.max_iterations}) reached",
            iteration=self.iteration
        )
```

---

## 5. Integration Points

### Post-Commit Hook (Git)

```bash
#!/bin/bash
# .git/hooks/post-commit

# Get changed files
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD)

# Trigger Ralph loop
python3 ~/.claude/templates/validation/ralph_loop.py \
    --files "$CHANGED_FILES" \
    --project "$(basename $(git rev-parse --show-toplevel))"
```

### PostToolUse Hook (Claude Code)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": {
          "tool_name": "Write|Edit|Bash"
        },
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/templates/validation/post_tool_hook.py"
          }
        ]
      }
    ]
  }
}
```

### MCP Server Integration

The validation orchestrator can expose itself as an MCP server:

```python
from mcp.server import Server
from mcp.types import Tool

server = Server("validation-orchestrator")

@server.tool()
async def validate_files(files: list[str], tier: int = 1) -> dict:
    """Validate files using the orchestrator."""
    orchestrator = ValidationOrchestrator()
    result = await orchestrator.validate_async(files, tier=tier)
    return result.to_dict()

@server.tool()
async def get_validation_status() -> dict:
    """Get current validation status."""
    return {
        "state": ralph_loop.state.value,
        "iteration": ralph_loop.iteration,
        "last_score": ralph_loop.last_score
    }
```

---

## 6. ECC vs Our Approach Comparison

| Aspect | ECC (6-phase) | Ours (14-dim tiered) | Ralph Integration |
|--------|---------------|---------------------|-------------------|
| **Execution** | Sequential gates | Parallel within tiers | Sequential tiers, parallel validators |
| **Blocking** | Any phase fails = stop | Only Tier 1 blocks | Tier 1 blocks, T2/T3 advisory |
| **Trigger** | Manual `/verify` | Automatic on commit | PostToolUse + post-commit |
| **Loop** | One-shot | Iterative | Iterative with backpressure |
| **Metrics** | None | QuestDB | Prometheus + Grafana |
| **Error context** | None | None → Sentry | Full Sentry injection |

---

## 7. Implementation Recommendations

### Priority Order

1. **PostToolUse Hook** - Integrate validation into Claude Code workflow
2. **Tier 1 Blocking** - Essential for quality gate
3. **Prometheus Metrics** - Enable Grafana visibility
4. **Sentry Context** - Debug context for failures
5. **Ralph Loop** - Full iterative validation

### Technical Decisions

| Decision | Recommendation | Rationale |
|----------|----------------|-----------|
| Hook language | Python | Reuse existing orchestrator |
| Metrics push | Prometheus Pushgateway | Already have Prometheus/Grafana |
| Loop storage | In-memory + claude-flow | Crash recovery via session_save |
| MCP server | Optional | Nice-to-have, not essential |

### Risk Mitigation

- **Hook timeout**: Set 30s max for Tier 1 to avoid blocking workflow
- **Pushgateway failure**: Log locally if push fails, don't block
- **Sentry rate limits**: Batch context updates, use sampling
- **Loop runaway**: Hard cap at 5 iterations

---

## References

- Claude Code Hooks: hooks.json schema, PreToolUse/PostToolUse events
- TypeScript Hook SDK: mizunashi-mana/claude-code-hook-sdk interfaces
- Sentry Python: set_context, set_tag, add_breadcrumb, start_transaction
- Prometheus client_python: push_to_gateway, CollectorRegistry, Counter/Gauge/Histogram
- Grafana MCP: create_annotation, dashboard management

---

*Research completed: 2026-01-23*
*Ready for: /gsd:plan-phase 11*
