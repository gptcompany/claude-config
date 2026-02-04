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

### 2. CONFIDENCE GATE → CALL /confidence-gate SKILL
**At steps 4, 7, 10 - MUST invoke the confidence-gate skill:**
```javascript
Skill({ skill: "confidence-gate", args: "--step plan --json" })
```

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
│ 2. CLARIFY                                  │
│    /speckit.clarify                         │
│    Identifies underspecified areas          │
│    Resolves [NEEDS CLARIFICATION] markers   │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 3. PLAN                                     │
│    /speckit.plan                            │
│    Creates plan.md with [P]/[E] markers     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 4. CONFIDENCE GATE (Plan)                   │
│    /confidence-gate --step plan             │
│    exit 0 → continue                        │
│    exit 1 → iterate (max 3x)                │
│    exit 2 → human review                    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 5. TASKS                                    │
│    /speckit.tasks                           │
│    Generates tasks.md from plan             │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 6. ANALYZE (pre-implement)                  │
│    /speckit.analyze                         │
│    Cross-artifact consistency check         │
│    Coverage gaps, constitution alignment    │
│    CRITICAL issues block implementation     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 7. CONFIDENCE GATE (Pre-Implement)          │
│    /confidence-gate --step analyze          │
│    Verify artifacts ready for implement     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 8. IMPLEMENT                                │
│    /speckit.implement-sync                  │
│    With Ralph debug loop for errors         │
│    Respects [P] parallel, [E] evolve        │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 9. VALIDATE                                 │
│    /validate                                │
│    14-dimension ValidationOrchestrator      │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 10. CONFIDENCE GATE (Post-Implement)        │
│     /confidence-gate --step implement       │
│     Detect [E] markers for evolution loop   │
└─────────────────┬───────────────────────────┘
                  ↓
                DONE
```

## Claude-Flow Integration (MANDATORY)

**Ogni step DEVE essere wrappato con checkpoint claude-flow.**

Prima di eseguire QUALSIASI step, Claude Code invoca:
```
mcp__claude-flow__session_save sessionId="speckit-{spec}-step{N}-pre"
mcp__claude-flow__memory_store key="speckit:{spec}:step{N}" value={"status":"starting","timestamp":"{now}"} namespace="pipeline"
```

Dopo OGNI step completato:
```
mcp__claude-flow__memory_store key="speckit:{spec}:step{N}" value={"status":"done","output":"{summary}","timestamp":"{now}"} namespace="pipeline"
mcp__claude-flow__session_save sessionId="speckit-{spec}-step{N}-done"
```

### Resume Protocol

All'avvio, Claude Code verifica stato precedente:
```
mcp__claude-flow__memory_search query="speckit:{spec}:*" namespace="pipeline"
```

Se trova step incompleto (status != "done"), offre:
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

```bash
# PRE-STEP CHECKPOINT (Claude Code invoca):
# mcp__claude-flow__session_save sessionId="speckit-{spec}-step1-pre"
# mcp__claude-flow__memory_store key="speckit:{spec}:step1" value={"status":"starting"} namespace="pipeline"

FEATURE="$ARGUMENTS"

if [ -n "$FEATURE" ]; then
    echo "📝 Creating specification..."
    /speckit.specify "$FEATURE"
fi

# POST-STEP CHECKPOINT (Claude Code invoca):
# mcp__claude-flow__memory_store key="speckit:{spec}:step1" value={"status":"done","artifact":"spec.md"} namespace="pipeline"
# mcp__claude-flow__session_save sessionId="speckit-{spec}-step1-done"
```

### Step 2: Clarify

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step2" value={"status":"starting"} namespace="pipeline"

if [ "$NO_CLARIFY" != "true" ]; then
    echo "🔍 Identifying underspecified areas..."
    /speckit.clarify

    # Check for remaining [NEEDS CLARIFICATION] markers
    if grep -q "\[NEEDS CLARIFICATION\]" specs/*/spec.md 2>/dev/null; then
        echo "⚠️ Unresolved clarifications found - resolving..."
        # Auto-resolve with reasonable defaults or pause for human input
    fi
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step2" value={"status":"done","clarifications_resolved":true} namespace="pipeline"
```

### Step 3: Plan

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step3" value={"status":"starting"} namespace="pipeline"

echo "📋 Creating technical plan..."
PLAN_OUTPUT=$(/speckit.plan)

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step3" value={"status":"done","artifact":"plan.md"} namespace="pipeline"
```

### Step 4: Confidence Gate (Plan)

**🚨 Claude MUST call the confidence-gate skill here:**

```javascript
// MANDATORY: Call confidence-gate skill
Skill({ skill: "confidence-gate", args: "--step plan --json" })
```

After getting the gate result, use AskUserQuestion if human review needed:

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step4" value={"status":"starting","type":"gate"} namespace="pipeline"

echo "🔒 Evaluating plan confidence..."
GATE_RESULT=$(echo "$PLAN_OUTPUT" | /confidence-gate --step "plan" --detect-evolve --json)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "✅ Plan approved"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step4" value={"status":"done","gate":"approved"} namespace="pipeline"
        ;;
    1)
        echo "🔄 Iterating on plan..."
        # mcp__claude-flow__memory_store key="speckit:{spec}:step4" value={"status":"iterating"} namespace="pipeline"
        for i in 1 2 3; do
            /speckit.clarify  # Re-clarify
            PLAN_OUTPUT=$(/speckit.plan)
            GATE_RESULT=$(echo "$PLAN_OUTPUT" | /confidence-gate --step "plan-v$i" --json)
            [ $? -eq 0 ] && break
        done
        # mcp__claude-flow__memory_store key="speckit:{spec}:step4" value={"status":"done","iterations":$i} namespace="pipeline"
        ;;
    2)
        echo "⏸️ Human review required for plan"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step4" value={"status":"blocked","reason":"human_review"} namespace="pipeline"
        # mcp__claude-flow__session_save sessionId="speckit-{spec}-blocked-step4"
        exit 2
        ;;
esac
```

### Step 5: Tasks

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step5" value={"status":"starting"} namespace="pipeline"

echo "📋 Generating tasks..."
/speckit.tasks

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step5" value={"status":"done","artifact":"tasks.md"} namespace="pipeline"
```

### Step 6: Analyze (Pre-Implement)

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step6" value={"status":"starting"} namespace="pipeline"

echo "🔬 Analyzing artifacts consistency..."
ANALYZE_OUTPUT=$(/speckit.analyze)

# Check for CRITICAL issues - block implementation if found
if echo "$ANALYZE_OUTPUT" | grep -q "CRITICAL"; then
    echo "🚫 CRITICAL issues found - blocking implementation"
    echo "$ANALYZE_OUTPUT" | grep -A2 "CRITICAL"
    # mcp__claude-flow__memory_store key="speckit:{spec}:step6" value={"status":"blocked","reason":"critical_issues"} namespace="pipeline"
    # mcp__claude-flow__session_save sessionId="speckit-{spec}-blocked-critical"
    exit 2  # Human review required
fi

# Auto-fix HIGH/MEDIUM issues if found
if echo "$ANALYZE_OUTPUT" | grep -qE "HIGH|MEDIUM"; then
    echo "🔧 Auto-fixing issues..."
    /speckit.autofix --threshold $THRESHOLD
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step6" value={"status":"done","issues_fixed":true} namespace="pipeline"
```

### Step 7: Confidence Gate (Pre-Implement)

**🚨 Claude MUST call the confidence-gate skill here:**

```javascript
// MANDATORY: Call confidence-gate skill for pre-implement validation
Skill({ skill: "confidence-gate", args: "--step analyze --json" })
```

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step7" value={"status":"starting","type":"gate"} namespace="pipeline"

echo "🔒 Verifying artifacts ready for implementation..."
ANALYZE_OUTPUT=$(/speckit.analyze)  # Re-analyze after autofix
GATE_RESULT=$(echo "$ANALYZE_OUTPUT" | /confidence-gate --step "analyze" --json)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "✅ Artifacts verified - proceeding to implement"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step7" value={"status":"done","gate":"approved"} namespace="pipeline"
        ;;
    1)
        echo "🔄 Artifacts still need refinement - running autofix again..."
        /speckit.autofix --threshold $THRESHOLD --max-iterations 2
        # mcp__claude-flow__memory_store key="speckit:{spec}:step7" value={"status":"done","autofix_ran":true} namespace="pipeline"
        ;;
    2)
        echo "⏸️ Human review required before implementation"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step7" value={"status":"blocked","reason":"human_review"} namespace="pipeline"
        exit 2
        ;;
esac
```

### Step 8: Implement

```bash
# PRE-STEP CHECKPOINT (CRITICAL - saves full context before implementation):
# mcp__claude-flow__session_save sessionId="speckit-{spec}-pre-implement"
# mcp__claude-flow__memory_store key="speckit:{spec}:step8" value={"status":"starting","critical":true} namespace="pipeline"

echo "🚀 Implementing..."
/speckit.implement-sync

# implement-sync includes Ralph debug loop automatically
# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step8" value={"status":"done","implemented":true} namespace="pipeline"
# mcp__claude-flow__session_save sessionId="speckit-{spec}-post-implement"
```

### Step 9: Validate

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step9" value={"status":"starting"} namespace="pipeline"

echo "✔️ Running validation..."
VALIDATE_OUTPUT=$(/validate)

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step9" value={"status":"done","validation_ran":true} namespace="pipeline"
```

### Step 10: Confidence Gate (Post-Implement)

**🚨 Claude MUST call the confidence-gate skill here:**

```javascript
// MANDATORY: Call confidence-gate skill for final validation
Skill({ skill: "confidence-gate", args: "--step implement --detect-evolve --json" })
```

**After the gate, use AskUserQuestion for next action:**

```javascript
// MANDATORY: Show interactive menu for next steps
AskUserQuestion({
  questions: [{
    question: "Pipeline completata. Cosa vuoi fare ora?",
    header: "Pipeline",
    options: [
      {label: "Continua", description: "Procedi con la prossima spec/feature"},
      {label: "Deploy", description: "Deploy/release della feature"},
      {label: "Review", description: "Revisione manuale prima di procedere"},
      {label: "Done", description: "Finito per ora"}
    ],
    multiSelect: false
  }]
})
```

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="speckit:{spec}:step10" value={"status":"starting","type":"gate"} namespace="pipeline"

echo "🔒 Evaluating implementation confidence..."
GATE_RESULT=$(echo "$VALIDATE_OUTPUT" | /confidence-gate --step "impl" --detect-evolve --json)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "✅ Feature implemented successfully"
        # FINAL CHECKPOINT - mark pipeline complete:
        # mcp__claude-flow__memory_store key="speckit:{spec}:step10" value={"status":"done","pipeline":"complete"} namespace="pipeline"
        # mcp__claude-flow__memory_store key="speckit:{spec}:complete" value={"timestamp":"{now}","success":true} namespace="pipeline"
        # mcp__claude-flow__session_save sessionId="speckit-{spec}-complete"
        # >>> USE AskUserQuestion FOR NEXT STEPS <<<
        ;;
    1)
        echo "🔄 Implementation needs iteration - see feedback"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step10" value={"status":"iterate","feedback":"see_gate_result"} namespace="pipeline"
        # >>> USE AskUserQuestion TO ASK USER <<<
        ;;
    2)
        echo "⏸️ Human review required"
        # mcp__claude-flow__memory_store key="speckit:{spec}:step10" value={"status":"blocked","reason":"human_review"} namespace="pipeline"
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
