---
name: pipeline:speckit
description: Full autonomous SpecKit pipeline with clarify, plan, confidence gate, implement, analyze, validate. Usage: /pipeline:speckit <spec_number|feature_description>
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Task
  - Skill
  - AskUserQuestion
  - Glob
  - Grep
---

# /pipeline:speckit - Autonomous SpecKit Pipeline

Execute complete SpecKit workflow with automatic clarification, confidence gates, analysis, and validation.

## 🚨 MANDATORY EXECUTION RULES

**Claude MUST follow these rules when executing this pipeline:**

### 1. USER CHOICES → USE AskUserQuestion TOOL
**NEVER write choices as text.** Use the AskUserQuestion tool:
```javascript
// ✅ CORRECT - Shows interactive menu
AskUserQuestion({
  questions: [{
    question: "Cosa vuoi fare?",
    header: "Pipeline",
    options: [
      {label: "Continua", description: "Procedi con lo step successivo"},
      {label: "Valida MVP", description: "Ferma e valida"},
      {label: "Human Review", description: "Richiedi revisione"}
    ],
    multiSelect: false
  }]
})

// ❌ WRONG - No interactive menu
"Opzioni:\nA) Continua\nB) Valida"
```

### 2. CONFIDENCE GATE → CALL BASH SCRIPT DIRECTLY
**At steps 4, 7, 10 - MUST call the confidence gate script via Bash:**
```bash
# ✅ CORRECT - Calls real script with external verification
GATE_RESULT=$(echo "$STEP_OUTPUT" | python3 ~/.claude/scripts/confidence_gate.py --step "plan" --json 2>&1)
echo "$GATE_RESULT"

# ❌ WRONG - Never generate inline Python heredocs for cross-verification
# cat << 'SCRIPT_EOF' | python3 ...  # This will fail with heredoc errors
```
**NEVER improvise inline Python code for confidence gate. ALWAYS use the script.**

### 3. PIPELINE FLAG → DISABILITA CONTEXT WARNING
**All'inizio della pipeline, crea flag per evitare interruzioni:**
```bash
touch ~/.claude/stats/pipeline-active.flag
```
**Alla fine (success o error), rimuovi il flag:**
```bash
rm -f ~/.claude/stats/pipeline-active.flag
```

### 4. DELEGA A TASK AGENTS → PRESERVA CONTEXT PRINCIPALE
**Gli step pesanti DEVONO essere delegati a Task agents per non esaurire il context:**

| Step | Delega a | Comando |
|------|----------|---------|
| Plan | planner agent | `Task({ subagent_type: "planner", prompt: "Crea plan.md per spec X", run_in_background: true })` |
| Implement | coder agents | `Task({ subagent_type: "coder", prompt: "Implementa task Y", run_in_background: true })` |
| Analyze | code-analyzer agent | `Task({ subagent_type: "code-analyzer", prompt: "Analizza artifacts", run_in_background: true })` |

**Regole delegazione:**
- Step 1-2 (specify, clarify): esegui diretto (interattivi, richiedono AskUserQuestion)
- Step 3 (plan): **DELEGA** a planner agent
- Step 4-5 (gate, tasks): esegui diretto (veloci)
- Step 6 (analyze): **DELEGA** a code-analyzer agent
- Step 7 (gate): esegui diretto
- Step 8 (implement): **DELEGA** a coder agents (paralleli se possibile)
- Step 9-10 (validate, gate): esegui diretto


## Usage

```bash
/pipeline:speckit                    # 🔄 Auto-detect: resume or start fresh
/pipeline:speckit 05                 # Execute spec #05
/pipeline:speckit 05-user-auth       # Execute by full spec name
/pipeline:speckit "user auth flow"   # New feature (creates new spec)
/pipeline:speckit --no-clarify       # Skip clarification
/pipeline:speckit --threshold 90     # Custom confidence threshold
/pipeline:speckit --gate-all         # 🔒 Paranoid: gate dopo OGNI step
/pipeline:speckit --gate-dynamic     # 🧠 Dynamic: gate solo quando serve
```

## Intelligent Entry Point

Il comando auto-detecta lo stato del progetto:

```python
def detect_project_state():
    """Determine where to start/resume pipeline."""

    # Check for existing specs
    specs_dir = find_specs_directory()

    if not specs_dir:
        # No .specify folder - need initialization
        return {
            "state": "no_project",
            "action": "Run /speckit.specify to create first spec"
        }

    # Find active/in-progress specs
    active_specs = find_specs_with_state("in_progress")

    if active_specs:
        # Resume the most recent in-progress spec
        latest = sorted(active_specs, key=lambda s: s.modified_at)[-1]
        return {
            "state": "in_progress",
            "spec": latest,
            "next_step": detect_next_step(latest),
            "action": f"Resume {latest.name} at {detect_next_step(latest)}"
        }

    # Check for specs needing work
    pending_specs = find_specs_with_state("pending")

    if pending_specs:
        return {
            "state": "pending",
            "specs": pending_specs,
            "action": "Select spec to work on"
        }

    # All specs complete
    return {
        "state": "all_complete",
        "action": "All specs implemented. Create new spec?"
    }

def detect_next_step(spec):
    """Determine which step to resume from."""

    if not exists(spec.path / "spec.md"):
        return "specify"
    if has_clarifications_needed(spec):
        return "clarify"
    if not exists(spec.path / "plan.md"):
        return "plan"
    if not exists(spec.path / "tasks.md"):
        return "tasks"
    if has_analyze_issues(spec):
        return "analyze"
    if not all_tasks_complete(spec):
        return "implement"
    return "validate"
```

## Dynamic Gating

Con `--gate-dynamic`, il sistema decide automaticamente quando serve un gate:

```python
def should_gate(step_name: str, output: str, context: dict) -> bool:
    """Dynamically decide if gate is needed."""

    # Always gate critical steps
    CRITICAL_STEPS = ["plan", "analyze", "implement"]
    if step_name in CRITICAL_STEPS:
        return True

    # Gate if output has warning markers
    WARNING_MARKERS = ["TODO", "FIXME", "WARNING", "[NEEDS CLARIFICATION]", "CRITICAL"]
    if any(marker in output for marker in WARNING_MARKERS):
        return True

    # Gate if previous step failed
    if context.get("previous_step_failed"):
        return True

    # Gate if output is unusually short (might be incomplete)
    if len(output) < 500:  # Suspiciously short
        return True

    # Gate if complexity score is high
    complexity = calculate_complexity(output)
    if complexity > 0.7:
        return True

    # Skip gate for simple, deterministic outputs
    return False

def calculate_complexity(output: str) -> float:
    """Estimate output complexity 0-1."""
    factors = {
        "length": min(len(output) / 10000, 1.0) * 0.3,
        "code_blocks": output.count("```") / 20 * 0.2,
        "decisions": len(re.findall(r"(should|could|might|or)", output, re.I)) / 50 * 0.2,
        "questions": output.count("?") / 20 * 0.3,
    }
    return sum(factors.values())
```

## Pipeline Flow

```
┌─────────────────────────────────────────────┐
│  /pipeline:speckit [feature]                │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 1. SPECIFY (if new feature)                 │
│    /speckit.specify "{feature}"             │
│    Creates spec.md                          │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 2. RESEARCH (if complex domain)             │
│    /research "{spec_description}"           │
│    /research-papers "{spec_description}"    │
│    Gathers domain knowledge before plan     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 3. CLARIFY                                  │
│    /speckit.clarify                         │
│    Identifies underspecified areas          │
│    Resolves [NEEDS CLARIFICATION] markers   │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 4. PLAN                                     │
│    /speckit.plan                            │
│    Creates plan.md with [P]/[E] markers     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 5. CONFIDENCE GATE (Plan)                   │
│    /confidence-gate --step plan             │
│    exit 0 → continue                        │
│    exit 1 → iterate (max 3x)                │
│    exit 2 → human review                    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 6. TASKS                                    │
│    /speckit.tasks                           │
│    Generates tasks.md from plan             │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 7. ANALYZE (pre-implement)                  │
│    /speckit.analyze                         │
│    Cross-artifact consistency check         │
│    Coverage gaps, constitution alignment    │
│    CRITICAL issues block implementation     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 8. CONFIDENCE GATE (Pre-Implement)          │
│    /confidence-gate --step analyze          │
│    Verify artifacts ready for implement     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 9. IMPLEMENT                                │
│    /speckit.implement-sync                  │
│    With Ralph debug loop for errors         │
│    Respects [P] parallel, [E] evolve        │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 10. VALIDATE                                │
│     /validate                               │
│     14-dimension ValidationOrchestrator     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 11. CONFIDENCE GATE (Post-Implement)        │
│     /confidence-gate --step implement       │
│     Detect [E] markers for evolution loop   │
└─────────────────┬───────────────────────────┘
                  ↓
                DONE
```

## Claude-Flow Integration (MANDATORY)

**Claude Code DEVE eseguire checkpoint per ogni step.**

### Pattern Checkpoint (IMPERATIVE)

**PRE-STEP** - Claude Code esegue via Bash:
```bash
npx @claude-flow/cli@latest memory store --key "speckit:SPEC:stepN" --value '{"status":"starting"}' --namespace pipeline
```

**POST-STEP** - Claude Code esegue via Bash:
```bash
npx @claude-flow/cli@latest memory store --key "speckit:SPEC:stepN" --value '{"status":"done"}' --namespace pipeline
```

**SESSION SAVE** - Solo in momenti critici (pre-implement, blocchi):
```bash
npx @claude-flow/cli@latest session save --name "speckit-SPEC-stepN"
```

### Resume Protocol (IMPERATIVE)

**ALL'AVVIO** Claude Code DEVE eseguire:
```bash
npx @claude-flow/cli@latest memory search --query "speckit:*:*" --namespace pipeline
```

Se trova step incompleto (status != "done"), chiede all'utente:
- **Resume**: continua da ultimo step completato
- **Restart**: ricomincia da step 1

## Execution

When invoked with `/pipeline:speckit [feature]`:

### Step 0: Initialize & Check Resume

**Claude MUST use AskUserQuestion if incomplete run found:**

```javascript
// If previous incomplete run detected, use AskUserQuestion:
AskUserQuestion({
  questions: [{
    question: `Found incomplete run at Step ${lastCompleted}. What do you want to do?`,
    header: "Resume",
    options: [
      {label: "Resume", description: `Continue from Step ${lastCompleted + 1}`},
      {label: "Restart", description: "Start fresh from Step 1"},
      {label: "Cancel", description: "Do nothing"}
    ],
    multiSelect: false
  }]
})
```

### Step 1: Specify (if new feature)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step1" --value '{"status":"starting"}' --namespace pipeline`

Se FEATURE non vuota:
- `/speckit.specify "$FEATURE"` → spec.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step1" --value '{"status":"done"}' --namespace pipeline`

### Step 1b: Research (if complex domain)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step1b" --value '{"status":"starting"}' --namespace pipeline`

Se spec contiene keywords (model, algorithm, ml, neural, 3d, audio, blockchain, realtime, cryptography):
1. `/research "$FEATURE"` - CoAT con triangolazione
2. `/research-papers "$FEATURE"` - Query RAG papers esistenti

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step1b" --value '{"status":"done"}' --namespace pipeline`

### Step 2: Clarify

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step2" --value '{"status":"starting"}' --namespace pipeline`

Se NO_CLARIFY!=true:
- `/speckit.clarify` - Risolve [NEEDS CLARIFICATION] markers

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step2" --value '{"status":"done"}' --namespace pipeline`

### Step 3: Plan

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step3" --value '{"status":"starting"}' --namespace pipeline`

- `/speckit.plan` → plan.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step3" --value '{"status":"done"}' --namespace pipeline`

### Step 4: Confidence Gate (Plan)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step4" --value '{"status":"starting"}' --namespace pipeline`

Valuta PLAN con `python3 ~/.claude/scripts/confidence_gate.py --step "plan" --detect-evolve --json`:
- Exit 0: ✅ Plan approved
- Exit 1: 🔄 Iterate (max 3x) - re-clarify + re-plan
- Exit 2: ⏸️ Human review

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step4" --value '{"status":"done"}' --namespace pipeline`

### Step 5: Tasks

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step5" --value '{"status":"starting"}' --namespace pipeline`

- `/speckit.tasks` → tasks.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step5" --value '{"status":"done"}' --namespace pipeline`

### Step 6: Analyze (Pre-Implement)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step6" --value '{"status":"starting"}' --namespace pipeline`

- `/speckit.analyze` - Cross-artifact consistency
- Se CRITICAL: blocca, human review
- Se HIGH/MEDIUM: `/speckit.autofix`

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step6" --value '{"status":"done"}' --namespace pipeline`

### Step 7: Confidence Gate (Pre-Implement)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step7" --value '{"status":"starting"}' --namespace pipeline`

- `/confidence-gate --step "analyze" --json`
- Exit 0: ✅ Proceed
- Exit 1: 🔄 Autofix again
- Exit 2: ⏸️ Human review

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step7" --value '{"status":"done"}' --namespace pipeline`

### Step 8: Implement

**CHECKPOINT PRE (CRITICAL):**
```bash
npx @claude-flow/cli@latest session save --name "speckit-SPEC-pre-implement"
npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step8" --value '{"status":"starting"}' --namespace pipeline
```

- `/speckit.implement-sync` (include Ralph debug loop)

**CHECKPOINT POST:**
```bash
npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step8" --value '{"status":"done"}' --namespace pipeline
npx @claude-flow/cli@latest session save --name "speckit-SPEC-post-implement"
```

### Step 9: Validate

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step9" --value '{"status":"starting"}' --namespace pipeline`

- `/validate` → 14-dimension ValidationOrchestrator

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step9" --value '{"status":"done"}' --namespace pipeline`

### Step 10: Confidence Gate (Post-Implement)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step10" --value '{"status":"starting"}' --namespace pipeline`

Valuta VALIDATE_OUTPUT con `/confidence-gate --step "impl" --detect-evolve --json`:
- Exit 0: ✅ Feature complete
  ```bash
  npx @claude-flow/cli@latest memory store --key "speckit:SPEC:complete" --value '{"status":"success"}' --namespace pipeline
  npx @claude-flow/cli@latest session save --name "speckit-SPEC-complete"
  ```
  AskUserQuestion per next steps (Continua/Deploy/Review/Done)
- Exit 1: 🔄 Iterate
- Exit 2: ⏸️ Human review

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "speckit:SPEC:step10" --value '{"status":"done"}' --namespace pipeline`
        ;;
esac
```

## Markers

| Marker | Meaning | Behavior |
|--------|---------|----------|
| `[P]` | Parallel | Tasks run concurrently |
| `[E]` | Evolve | Iterate until convergence |
| `[NEEDS CLARIFICATION]` | Underspecified | Must resolve before proceed |
| `[Gap]` | Missing coverage | Flagged in analyze |

## Options

| Option | Description |
|--------|-------------|
| `--no-clarify` | Skip clarification phase |
| `--threshold N` | Custom confidence threshold (default: 85) |
| `--evolve` | Force evolution loop |
| `--dry-run` | Show what would execute without running |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pipeline completed successfully |
| 1 | Iteration needed (issues found) |
| 2 | Human review required |
| 3 | Error |
