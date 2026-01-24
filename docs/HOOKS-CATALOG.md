# Claude Code Hooks Catalog

Complete reference for all 40+ hooks in the Claude Code hooks system.

**Last Updated:** 2026-01-24
**Version:** 14.6 (Phase 14.6-04)

---

## Table of Contents

1. [Hook Events Overview](#hook-events-overview)
2. [Core & Safety Hooks](#core--safety-hooks)
3. [Intelligence & Session Hooks](#intelligence--session-hooks)
4. [Quality & Productivity Hooks](#quality--productivity-hooks)
5. [Metrics & Monitoring Hooks](#metrics--monitoring-hooks)
6. [Coordination Hooks](#coordination-hooks)
7. [Control Hooks](#control-hooks)
8. [UX Hooks](#ux-hooks)
9. [Debug Hooks](#debug-hooks)
10. [Configuration Reference](#configuration-reference)

---

## Hook Events Overview

| Event | When Triggered | Can Block | Output Format |
|-------|----------------|-----------|---------------|
| `PreToolUse` | Before a tool executes | Yes | `{decision, reason}` |
| `PostToolUse` | After a tool completes | No | `{systemMessage}` |
| `UserPromptSubmit` | When user submits prompt | Yes | `{additionalContext}` |
| `Stop` | When Claude stops | Yes | `{decision, reason}` |
| `PreCompact` | Before context compaction | No | `{systemMessage}` |

---

## Core & Safety Hooks

### git-safety-check.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/safety/git-safety-check.js`
**Purpose:** Block destructive git operations (force push, hard reset) without confirmation

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git push --force origin main"
  }
}
```

**Output JSON:**
```json
{
  "decision": "block",
  "reason": "BLOCKED: Force push to protected branch 'main' requires explicit user confirmation"
}
```

**Configuration:**
- `PROTECTED_BRANCHES`: `["main", "master", "develop", "release"]`
- `DESTRUCTIVE_PATTERNS`: Force push, hard reset, branch -D, clean -f

---

### smart-safety-check.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/safety/smart-safety-check.js`
**Purpose:** Risk-aware command blocking with context-based assessment

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /important/directory"
  }
}
```

**Output JSON:**
```json
{
  "decision": "block",
  "reason": "HIGH RISK: Recursive delete of non-temp directory",
  "riskScore": 0.85,
  "riskFactors": ["recursive_delete", "outside_temp"]
}
```

**Configuration:**
- Risk threshold: 0.7 (block if higher)
- Safe directories: `/tmp`, `node_modules`, `__pycache__`

---

### port-conflict-check.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/safety/port-conflict-check.js`
**Purpose:** Detect and prevent port conflicts before starting servers

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm run dev"
  }
}
```

**Output JSON:**
```json
{
  "systemMessage": "Port 3000 is in use by process 'node' (PID: 12345). Consider: kill 12345 or use --port 3001"
}
```

**Configuration:**
- Default ports: `[3000, 3001, 5000, 5173, 8000, 8080]`
- Timeout: 5 seconds

---

### ci-batch-check.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/safety/ci-batch-check.js`
**Purpose:** Batch similar CI commands to prevent API rate limiting

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "gh run list --limit 10"
  }
}
```

**Output JSON:**
```json
{
  "systemMessage": "Batched 3 gh commands into 1 request to avoid rate limits"
}
```

**Configuration:**
- Batch window: 5 seconds
- Max batch size: 10 commands

---

## Intelligence & Session Hooks

### session-start.js

**Event:** SessionStart (via UserPromptSubmit)
**Path:** `~/.claude/scripts/hooks/session-start.js`
**Purpose:** Initialize session tracking, detect package manager, restore context

**Input JSON:**
```json
{
  "session_id": "session_abc123",
  "cwd": "/home/user/project"
}
```

**Output JSON:**
```json
{
  "additionalContext": "[New session] Project: my-app, PM: npm, Branch: main@abc1234"
}
```

**Configuration:**
- Session timeout: 30 minutes
- Package managers detected: npm, pnpm, yarn, bun, pip, poetry, cargo

---

### session-end.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/session-end.js`
**Purpose:** Analyze session, extract lessons, save metrics

**Input JSON:**
```json
{
  "stop_reason": "end_turn",
  "session_id": "session_abc123"
}
```

**Output JSON:**
```json
{
  "analyzed": true,
  "metrics": {
    "duration_min": 45,
    "tool_calls": 127,
    "errors": 3
  }
}
```

**Configuration:**
- Min session duration for analysis: 5 minutes
- Metrics export: QuestDB (if available)

---

### session-analyzer.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/intelligence/session-analyzer.js`
**Purpose:** Deep analysis of session patterns for meta-learning

**Input JSON:**
```json
{
  "session_id": "session_abc123",
  "transcript_summary": "Implemented user auth..."
}
```

**Output JSON:**
```json
{
  "patterns": [
    {"type": "refactor_cycle", "count": 3},
    {"type": "test_first", "count": 5}
  ],
  "suggestions": ["Consider TDD approach"]
}
```

---

### meta-learning.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/intelligence/meta-learning.js`
**Purpose:** Extract and store lessons learned across sessions

**Input JSON:**
```json
{
  "session_patterns": {...},
  "error_patterns": {...}
}
```

**Output JSON:**
```json
{
  "lessons_extracted": 3,
  "updated_rules": ["prefer_pytest_over_unittest"]
}
```

**Configuration:**
- Lessons file: `~/.claude/intelligence/lessons.json`
- Max lessons: 100

---

### lesson-injector.js

**Event:** UserPromptSubmit
**Path:** `~/.claude/scripts/hooks/intelligence/lesson-injector.js`
**Purpose:** Inject relevant lessons into context based on current task

**Input JSON:**
```json
{
  "message": "Write tests for the auth module"
}
```

**Output JSON:**
```json
{
  "additionalContext": "[Lesson] This project prefers pytest with fixtures. Last session: 5 tests passed."
}
```

---

### session-start-tracker.js

**Event:** UserPromptSubmit
**Path:** `~/.claude/scripts/hooks/intelligence/session-start-tracker.js`
**Purpose:** Track session continuity, inject previous insights

**Input JSON:**
```json
{
  "message": "Continue from where we left off"
}
```

**Output JSON:**
```json
{
  "additionalContext": "[prev: 45% ctx, 127 calls, uncommitted +50/-20, 3 tips (git:2/test:1), try: /commit]"
}
```

---

## Quality & Productivity Hooks

### tdd-guard.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/productivity/tdd-guard.js`
**Purpose:** Enforce test-driven development workflow

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/feature.py",
    "content": "def new_feature():..."
  }
}
```

**Output JSON:**
```json
{
  "decision": "block",
  "reason": "TDD Mode: Write test first! No test file found for src/feature.py"
}
```

**Configuration:**
- Enable via: `export TDD_MODE=1` or `.claude/tdd-mode`
- Test patterns: `test_*.py`, `*.test.ts`, `*_test.go`

---

### auto-format.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/productivity/auto-format.js`
**Purpose:** Automatically format code after writes

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/module.py"
  },
  "tool_response": "File written successfully"
}
```

**Output JSON:**
```json
{
  "formatted": true,
  "formatter": "ruff",
  "changes": 3
}
```

**Configuration:**
- Formatters: ruff (Python), prettier (JS/TS), rustfmt (Rust)
- Timeout: 10 seconds

---

### auto-simplify.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/productivity/auto-simplify.js`
**Purpose:** Detect over-engineered code and suggest simplifications

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/service.py",
    "content": "class AbstractFactoryBuilder..."
  }
}
```

**Output JSON:**
```json
{
  "systemMessage": "Complexity warning: 3 levels of abstraction. Consider: direct implementation"
}
```

---

### task-checkpoint.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/productivity/task-checkpoint.js`
**Purpose:** Auto-save progress checkpoints during long tasks

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {...}
}
```

**Output JSON:**
```json
{
  "checkpoint_saved": true,
  "checkpoint_id": "cp_20260124_120000",
  "files_tracked": 5
}
```

**Configuration:**
- Checkpoint interval: 5 tool calls or 10 minutes
- Storage: `~/.claude/checkpoints/`

---

### ci-autofix.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/quality/ci-autofix.js`
**Purpose:** Auto-fix common CI failures (lint, format)

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm run lint"
  },
  "tool_response": "error: 5 lint errors found"
}
```

**Output JSON:**
```json
{
  "autofix_applied": true,
  "fixes": ["eslint --fix", "prettier --write"],
  "errors_fixed": 5
}
```

---

### plan-validator.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/quality/plan-validator.js`
**Purpose:** Validate plan files before execution

**Input JSON:**
```json
{
  "tool_name": "Read",
  "tool_input": {
    "file_path": "/.planning/PLAN.md"
  }
}
```

**Output JSON:**
```json
{
  "valid": true,
  "warnings": ["Missing test strategy section"]
}
```

---

### pr-readiness.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/quality/pr-readiness.js`
**Purpose:** Check PR readiness before creating

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "gh pr create"
  }
}
```

**Output JSON:**
```json
{
  "ready": false,
  "blockers": ["Tests failing", "No description"],
  "suggestions": ["Run: pytest", "Add PR template"]
}
```

---

### readme-generator.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/quality/readme-generator.js`
**Purpose:** Suggest README updates when code changes

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/api/routes.py"
  }
}
```

**Output JSON:**
```json
{
  "systemMessage": "README Update Suggested: API section may need update for new routes"
}
```

---

### architecture-validator.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/quality/architecture-validator.js`
**Purpose:** Detect new components and suggest ARCHITECTURE.md updates

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/services/auth.py"
  }
}
```

**Output JSON:**
```json
{
  "systemMessage": "Architecture Update Suggested: New components detected: AuthService (class)"
}
```

---

## Metrics & Monitoring Hooks

### dora-tracker.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/metrics/dora-tracker.js`
**Purpose:** Track DORA metrics (deployment frequency, lead time, etc.)

**Input JSON:**
```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git push origin main"
  }
}
```

**Output JSON:**
```json
{
  "tracked": true,
  "metric": "deployment",
  "lead_time_hours": 2.5
}
```

**Configuration:**
- Metrics: Deployment Frequency, Lead Time, MTTR, Change Failure Rate
- Export: QuestDB table `claude_dora_metrics`

---

### quality-score.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/metrics/quality-score.js`
**Purpose:** Calculate session quality score

**Input JSON:**
```json
{
  "session_stats": {
    "tool_calls": 100,
    "errors": 5,
    "tests_written": 10
  }
}
```

**Output JSON:**
```json
{
  "quality_score": 0.85,
  "breakdown": {
    "error_rate": 0.95,
    "test_coverage": 0.80,
    "code_review": 0.80
  }
}
```

---

### claudeflow-sync.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/metrics/claudeflow-sync.js`
**Purpose:** Sync state with claude-flow MCP for crash recovery

**Input JSON:**
```json
{
  "tool_name": "Task",
  "tool_input": {
    "description": "Implement feature X"
  }
}
```

**Output JSON:**
```json
{
  "synced": true,
  "syncCount": 42,
  "agentSpawns": 3,
  "taskProgress": 5
}
```

**Configuration:**
- Sync triggers: Task, TodoWrite, Skill
- Memory store: `~/.claude-flow/memory/store.json`
- Periodic full sync: Every 10 tool calls

---

## Coordination Hooks

### file-coordination.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/coordination/file-coordination.js`
**Purpose:** Prevent file conflicts in multi-agent scenarios

**Input JSON:**
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/project/src/shared.py"
  }
}
```

**Output JSON (if blocked):**
```json
{
  "decision": "block",
  "reason": "File is claimed by agent:session-xyz:editor"
}
```

**Configuration:**
- Claims file: `~/.claude/coordination/claims.json`
- Claim expiry: 5 minutes
- Auto-release on session end

---

### task-coordination.js

**Event:** PreToolUse
**Path:** `~/.claude/scripts/hooks/coordination/task-coordination.js`
**Purpose:** Track task assignments across agents

**Input JSON:**
```json
{
  "tool_name": "Task",
  "tool_input": {
    "description": "Implement user registration"
  }
}
```

**Output JSON:**
```json
{
  "tracked": true,
  "task_id": "task-abc12345-120000",
  "similar_warning": "Similar task in progress by agent:xyz"
}
```

**Configuration:**
- Claims file: `~/.claude/coordination/task-claims.json`
- Stale threshold: 1 hour
- Informational only (never blocks)

---

## Control Hooks

### ralph-loop.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/control/ralph-loop.js`
**Purpose:** Implement Ralph Wiggum pattern for autonomous development

**Input JSON:**
```json
{
  "stop_reason": "end_turn",
  "transcript": "Tests still failing..."
}
```

**Output JSON (continue loop):**
```json
{
  "decision": "block",
  "reason": "## Ralph Loop [3/15]\n\nCI FAILED...\n\n**Task:** Fix all tests\n\nContinue until CI passes.",
  "systemMessage": "Ralph [3/15] CI: FAIL"
}
```

**Configuration:**
- Max iterations: 15
- Max budget: $20.00
- Max consecutive errors: 3
- CI validation between iterations
- Plugin state: `.claude/ralph-loop.local.md`

---

### hive-manager.js

**Event:** PostToolUse
**Path:** `~/.claude/scripts/hooks/control/hive-manager.js`
**Purpose:** Multi-agent coordination for parallel execution

**Input JSON:**
```json
{
  "tool_name": "Task",
  "tool_input": {
    "description": "spawn worker for feature X"
  }
}
```

**Output JSON:**
```json
{
  "tracked": true,
  "action": "agent_spawned",
  "agent_id": "agent_lx5k2_abc123"
}
```

**Configuration:**
- Max agents: 10
- Agent timeout: 10 minutes (marked stuck)
- Topology: hierarchical-mesh
- State file: `~/.claude/hive/state.json`

---

## UX Hooks

### tips-injector.js

**Event:** UserPromptSubmit
**Path:** `~/.claude/scripts/hooks/ux/tips-injector.js`
**Purpose:** Inject optimization tips from previous session

**Input JSON:**
```json
{
  "message": "Continue working on the project"
}
```

**Output JSON:**
```json
{
  "additionalContext": "[Previous Session Tips] Session: 45min, 127 calls, 3 errors | 1. [85%] Use /commit for git -> /commit | 2. [70%] Consider TDD -> /tdd:red"
}
```

**Configuration:**
- Max tips age: 24 hours
- Max tips injected: 3
- One-time injection per session
- SSOT: `~/.claude/metrics/session_insights.json`

---

### session-insights.js

**Event:** Stop
**Path:** `~/.claude/scripts/hooks/ux/session-insights.js`
**Purpose:** Aggregate session data into SSOT for next session

**Input JSON:**
```json
{
  "session_id": "session_abc123"
}
```

**Output JSON:**
```json
{}
```

**SSOT Output (session_insights.json):**
```json
{
  "$schema": "session_insights_v1",
  "session_id": "session_abc123",
  "ended_at": "2026-01-24T12:00:00Z",
  "context": {"percentage": 45, "status": "normal"},
  "tips": [...],
  "git": {"uncommitted": true, "lines_added": 50}
}
```

---

## Debug Hooks

### hook-tracer.js

**Event:** All (meta-hook)
**Path:** `~/.claude/scripts/hooks/debug/hook-tracer.js`
**Purpose:** Trace all hook invocations for debugging

**Enable:** `export CLAUDE_HOOK_TRACE=1`

**Output (to `~/.claude/debug/hooks/trace.jsonl`):**
```json
{
  "ts": "2026-01-24T12:00:00Z",
  "event": "PreToolUse",
  "hook": "git-safety-check",
  "input": {"tool_name": "Bash", ...},
  "output": {},
  "duration_ms": 12,
  "success": true,
  "pid": 12345,
  "cwd": "/home/user/project"
}
```

**Configuration:**
- Trace file: `~/.claude/debug/hooks/trace.jsonl`
- Max file size: 5MB (auto-rotate)
- Enable: `CLAUDE_HOOK_TRACE=1`

---

### hook-health.js

**Event:** CLI tool (not a hook)
**Path:** `~/.claude/scripts/hooks/debug/hook-health.js`
**Purpose:** Monitor health of all hooks

**Usage:**
```bash
node ~/.claude/scripts/hooks/debug/hook-health.js --check
node ~/.claude/scripts/hooks/debug/hook-health.js --status
node ~/.claude/scripts/hooks/debug/hook-health.js --export
```

**Output:**
```
Hook Health Report
==================

Last Check: 2026-01-24T12:00:00Z
Total Hooks: 42

Healthy:  40
Degraded: 2
Failing:  0
Unknown:  0

DEGRADED:
  - auto-format: error_rate=6.5%
```

**Health Status:**
- HEALTHY: error_rate < 5%
- DEGRADED: error_rate >= 5%
- FAILING: error_rate >= 20% or script missing

---

## Configuration Reference

### hooks.json Structure

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "description": "Git safety checks",
        "enabled": true,
        "hooks": [
          {
            "command": "node $HOME/.claude/scripts/hooks/safety/git-safety-check.js",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CLAUDE_HOOK_TRACE` | Enable hook tracing | `0` |
| `TDD_MODE` | Enable TDD guard | `0` |
| `CLAUDE_SESSION_ID` | Override session ID | auto-generated |
| `HOOK_HEALTH_CHECK` | Set during health checks | `0` |

### File Locations

| File | Purpose |
|------|---------|
| `~/.claude/hooks/hooks.json` | Hook configuration |
| `~/.claude/metrics/session_insights.json` | Session SSOT |
| `~/.claude/coordination/claims.json` | File claims |
| `~/.claude/hive/state.json` | Multi-agent state |
| `~/.claude/debug/hooks/trace.jsonl` | Trace log |
| `~/.claude/debug/hooks/health.json` | Health status |

---

## See Also

- [HOOKS-TROUBLESHOOTING.md](./HOOKS-TROUBLESHOOTING.md) - Common issues and solutions
- [HOOKS-PERFORMANCE.md](./HOOKS-PERFORMANCE.md) - Performance tuning guide
