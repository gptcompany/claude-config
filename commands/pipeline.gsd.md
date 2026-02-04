---
name: pipeline:gsd
description: Full autonomous GSD pipeline with research detection, discuss, plan, confidence gate, execute, validate. Usage: /pipeline:gsd <phase_number>
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

# /pipeline:gsd - Autonomous GSD Pipeline

Execute complete GSD phase with automatic research, discussion, confidence gates, and validation.

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
      {label: "Valida", description: "Ferma e valida il lavoro"},
      {label: "Human Review", description: "Richiedi revisione"}
    ],
    multiSelect: false
  }]
})

// ❌ WRONG - No interactive menu
"Opzioni:\nA) Continua\nB) Valida"
```

### 2. CONFIDENCE GATE → CALL SCRIPT DIRECTLY
**At plan and execute steps, MUST call the confidence gate script via Bash:**
```bash
# ✅ CORRECT - Calls real script with external verification
GATE_RESULT=$(echo "$STEP_OUTPUT" | python3 ~/.claude/scripts/confidence_gate.py --step "plan" --json 2>&1)
```

### 3. POST-PHASE → USE AskUserQuestion (NEVER just print ghost text)
**After completing a phase, Claude MUST call AskUserQuestion to ask what to do next:**
```javascript
// ✅ CORRECT - Interactive menu at end of phase
AskUserQuestion({
  questions: [{
    question: `Phase ${PHASE} completata. Cosa vuoi fare?`,
    header: "Phase Done",
    options: [
      {label: `Continua Phase ${NEXT_PHASE}`, description: "Procedi automaticamente"},
      {label: "Pausa", description: "Salva checkpoint e fermati"},
      {label: "Commit & Push", description: "Commit e push delle modifiche"}
    ],
    multiSelect: false
  }]
})

// ❌ WRONG - Just printing ghost text and stopping
echo "→ /pipeline:gsd $NEXT_PHASE"
```
**Claude MUST NOT stop with ghost text. MUST show interactive menu.**


## Usage

```bash
/pipeline:gsd                    # 🔄 Auto-detect: resume or start fresh
/pipeline:gsd 05                 # Execute phase 05
/pipeline:gsd 05 --no-research   # Skip research detection
/pipeline:gsd 05 --no-discuss    # Skip discussion phase
/pipeline:gsd 05 --threshold 90  # Custom confidence threshold
/pipeline:gsd 05 --gate-all      # 🔒 Paranoid: gate dopo OGNI step
/pipeline:gsd 05 --gate-dynamic  # 🧠 Dynamic: gate solo quando serve
/pipeline:gsd 05 --autodiscuss   # 🔄 Auto-iterate discuss until complete
/pipeline:gsd 05 --autofix       # 🔧 Auto-fix issues after execute
```

## Intelligent Entry Point

Il comando auto-detecta lo stato del progetto (come `/gsd:progress`):

```python
def detect_project_state():
    """Determine where to start/resume pipeline."""

    planning_dir = Path(".planning")

    if not planning_dir.exists():
        # No .planning folder - need initialization
        return {
            "state": "no_project",
            "action": "Run /gsd:new-project to initialize"
        }

    # Check for PROJECT.md
    if not (planning_dir / "PROJECT.md").exists():
        return {
            "state": "needs_project",
            "action": "Run /gsd:new-project"
        }

    # Check for ROADMAP.md
    if not (planning_dir / "ROADMAP.md").exists():
        return {
            "state": "needs_roadmap",
            "action": "Run /gsd:create-roadmap"
        }

    # Find current phase from STATE.md
    state = parse_state_md(planning_dir / "STATE.md")
    current_phase = state.get("current_phase")

    if current_phase:
        phase_dir = find_phase_directory(current_phase)
        next_step = detect_next_step(phase_dir)

        return {
            "state": "in_progress",
            "phase": current_phase,
            "next_step": next_step,
            "action": f"Resume phase {current_phase} at {next_step}"
        }

    # Find next unstarted phase
    next_phase = find_next_unstarted_phase()

    if next_phase:
        return {
            "state": "ready",
            "phase": next_phase,
            "action": f"Start phase {next_phase}"
        }

    # All phases complete
    return {
        "state": "milestone_complete",
        "action": "Run /gsd:complete-milestone or /gsd:new-milestone"
    }

def detect_next_step(phase_dir: Path) -> str:
    """Determine which step to resume from."""

    # Check for PLAN files
    plans = list(phase_dir.glob("*-PLAN.md"))

    if not plans:
        return "plan"  # Need to create plan

    # Check for SUMMARY files (execution complete)
    summaries = list(phase_dir.glob("*-SUMMARY.md"))

    if len(summaries) < len(plans):
        return "execute"  # Need to execute plans

    return "verify"  # All done, verify
```

## Dynamic Gating

Con `--gate-dynamic`, il sistema decide automaticamente quando serve un gate:

```python
def should_gate(step_name: str, output: str, context: dict) -> bool:
    """Dynamically decide if gate is needed."""

    # Always gate critical steps
    CRITICAL_STEPS = ["plan", "execute"]
    if step_name in CRITICAL_STEPS:
        return True

    # Gate if research found complex domain
    if step_name == "research" and context.get("niche_domain"):
        return True

    # Gate if discuss surfaced many unknowns
    if step_name == "discuss" and output.count("?") > 5:
        return True

    # Gate if previous step had issues
    if context.get("previous_confidence", 100) < 70:
        return True

    return False
```

## Pipeline Flow

```
┌─────────────────────────────────────────────┐
│  /pipeline:gsd {phase}                      │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 1. COMPLEXITY DETECTION                     │
│    Check for niche domain keywords          │
│    (3d, ml, blockchain, audio, shader...)   │
└─────────────────┬───────────────────────────┘
                  ↓ needs_research?
┌─────────────────────────────────────────────┐
│ 2. RESEARCH (if needed)                     │
│    /gsd:research-phase {phase}              │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 3. DISCUSS                                  │
│    /gsd:discuss-phase {phase}               │
│    Captures vision and boundaries           │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 3b. CONTEXT CONFIDENCE GATE (autonomous)    │  ← NEW
│     Evaluate CONTEXT.md via confidence gate │
│     Auto-enrich with Task agent if needed   │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 4. PLAN                                     │
│    /gsd:plan-phase {phase}                  │
│    Creates PLAN.md                          │
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
│ 6. EXECUTE                                  │
│    /gsd:execute-phase-sync {phase}          │
│    With claude-flow state sync              │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 6b. VERIFICATION (Pre-Validate)             │  ← NEW
│     6-phase verification runner             │
│     Build, Type, Lint, Test, Security, Diff │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 6c. PLAN-FIX (if verification failed)       │  ← NEW
│     Use /gsd:plan-fix for structured fix    │
│     Or delegate to coder agent              │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 7. VALIDATE                                 │
│    /validate                                │
│    14-dimension ValidationOrchestrator      │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 8. CONFIDENCE GATE (Implementation)         │
│    /confidence-gate --step implement        │
│    Detect [E] markers for evolution loop    │
└─────────────────┬───────────────────────────┘
                  ↓
                DONE
```

## Claude-Flow Integration (MANDATORY)

**Ogni step DEVE essere wrappato con checkpoint claude-flow.**

Prima di eseguire QUALSIASI step, Claude Code invoca:
```
mcp__claude-flow__session_save sessionId="gsd-{phase}-step{N}-pre"
mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step{N}" value={"status":"starting","timestamp":"{now}"} namespace="pipeline"
```

Dopo OGNI step completato:
```
mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step{N}" value={"status":"done","output":"{summary}","timestamp":"{now}"} namespace="pipeline"
mcp__claude-flow__session_save sessionId="gsd-{phase}-step{N}-done"
```

### Resume Protocol

All'avvio, Claude Code verifica stato precedente:
```
mcp__claude-flow__memory_search query="gsd:{project}:{phase}:*" namespace="pipeline"
```

Se trova step incompleto (status != "done"), offre:
- **Resume**: continua da ultimo step completato
- **Restart**: ricomincia da step 1

## Execution

When invoked with `/pipeline:gsd {phase}`:

### Step 0: Initialize & Check Resume

```python
# Claude Code MCP calls:
# mcp__claude-flow__memory_search query="gsd:*:{phase}:*" namespace="pipeline"

previous_state = search_memory(f"gsd:*:{PHASE}:*")
if previous_state and not all_done(previous_state):
    last_completed = find_last_completed_step(previous_state)
    print(f"⏸️ Found incomplete run. Last completed: Step {last_completed}")
    print(f"→ Resume from Step {last_completed + 1}? (or --restart)")
    # Se resume, salta a step appropriato
```

### Step 1: Parse and Detect Complexity

```python
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step1" value={"status":"starting"} namespace="pipeline"

PHASE = "$ARGUMENTS"  # e.g., "05"

# Research keywords for niche domains
RESEARCH_KEYWORDS = [
    "3d", "webgl", "threejs", "shader", "glsl",
    "ml", "machine learning", "neural", "tensorflow",
    "audio", "dsp", "synthesis", "midi",
    "blockchain", "web3", "solidity",
    "realtime", "websocket", "streaming",
    "cryptography", "distributed", "consensus",
    "compiler", "parser", "graphics", "ray tracing"
]

# Read PROJECT.md and ROADMAP.md for context
project_context = read_file(".planning/PROJECT.md")
roadmap_context = read_file(".planning/ROADMAP.md")
phase_description = extract_phase_description(roadmap_context, PHASE)

needs_research = any(kw in phase_description.lower() for kw in RESEARCH_KEYWORDS)

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step1" value={"status":"done","needs_research":needs_research} namespace="pipeline"
```

### Step 2: Research (if needed)

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step2" value={"status":"starting"} namespace="pipeline"

if [ "$NEEDS_RESEARCH" = "true" ] && [ "$NO_RESEARCH" != "true" ]; then
    echo "🔬 Research phase detected - gathering domain knowledge..."
    /gsd:research-phase $PHASE
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step2" value={"status":"done","research_ran":$NEEDS_RESEARCH} namespace="pipeline"
```

### Step 3: Discuss Phase

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3" value={"status":"starting"} namespace="pipeline"

if [ "$NO_DISCUSS" != "true" ]; then
    echo "💬 Gathering phase context..."
    /gsd:discuss-phase $PHASE
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3" value={"status":"done","artifact":"CONTEXT.md"} namespace="pipeline"
```

### Step 3b: Context Confidence Gate (Autonomous)

**Valuta CONTEXT.md con confidence gate - NO interazione utente:**

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"starting","type":"confidence_gate"} namespace="pipeline"

CONTEXT_FILE=$(ls .planning/phases/$PHASE*/*-CONTEXT.md 2>/dev/null | head -1)

if [ -z "$CONTEXT_FILE" ]; then
    echo "⚠️ No CONTEXT.md found - skipping context validation"
    # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"skipped","reason":"no_context"} namespace="pipeline"
    # Procedi comunque - plan-phase può funzionare senza CONTEXT.md
else
    echo "🔒 Evaluating context completeness via confidence gate..."

    CONTEXT_OUTPUT=$(cat "$CONTEXT_FILE")

    # Confidence gate valuta automaticamente:
    # - Sezioni compilate vs vuote
    # - Specificity del linguaggio
    # - Presenza di TBD/TODO/unclear markers
    GATE_RESULT=$(/confidence-gate --step "context-$PHASE" --input "$CONTEXT_FILE" --json 2>/dev/null)
    EXIT_CODE=$?
    CONFIDENCE=$(echo "$GATE_RESULT" | jq -r '.confidence' 2>/dev/null || echo 75)

    echo "📊 Context confidence: $CONFIDENCE%"

    case $EXIT_CODE in
        0)
            echo "✅ Context approved (confidence >= $THRESHOLD%)"
            # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"done","confidence":$CONFIDENCE,"approved":true} namespace="pipeline"
            ;;
        1)
            echo "⚠️ Context needs enrichment (confidence $CONFIDENCE% < $THRESHOLD%)"
            echo "   Gaps identified by confidence gate:"
            echo "$GATE_RESULT" | jq -r '.issues[]' 2>/dev/null | head -5

            # AUTO-ENRICH: Usa Task agent per arricchire context (NO user interaction)
            if [ "$AUTODISCUSS" = "true" ]; then
                echo "🤖 Auto-enriching context via Task agent..."
                # Task({
                #   subagent_type: "researcher",
                #   prompt: "Enrich this CONTEXT.md by filling gaps. Issues: $GATE_RESULT. File: $CONTEXT_FILE",
                #   run_in_background: false
                # })

                # Re-evaluate dopo enrichment
                GATE_RESULT=$(/confidence-gate --step "context-$PHASE-v2" --input "$CONTEXT_FILE" --json 2>/dev/null)
                CONFIDENCE=$(echo "$GATE_RESULT" | jq -r '.confidence' 2>/dev/null || echo 75)
                echo "📊 Post-enrichment confidence: $CONFIDENCE%"
            fi

            # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"done","confidence":$CONFIDENCE,"enriched":true} namespace="pipeline"
            ;;
        2)
            echo "🛑 Context critically incomplete - human review required"
            echo "$GATE_RESULT" | jq -r '.critical_issues[]' 2>/dev/null

            # UNICA interazione: chiedi se procedere comunque
            # AskUserQuestion: "Context incompleto. Procedere comunque?" → Sì/No
            # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"blocked","reason":"critical_gaps"} namespace="pipeline"
            ;;
    esac
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step3b" value={"status":"done"} namespace="pipeline"
```

### Step 4: Plan Phase

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step4" value={"status":"starting"} namespace="pipeline"

echo "📋 Creating execution plan..."
PLAN_OUTPUT=$(/gsd:plan-phase $PHASE)

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step4" value={"status":"done","artifact":"PLAN.md"} namespace="pipeline"
```

### Step 5: Confidence Gate (Plan)

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step5" value={"status":"starting","type":"gate"} namespace="pipeline"

echo "🔒 Evaluating plan confidence..."
GATE_RESULT=$(echo "$PLAN_OUTPUT" | /confidence-gate --step "plan-$PHASE" --detect-evolve --json)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "✅ Plan approved"
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step5" value={"status":"done","gate":"approved"} namespace="pipeline"
        ;;
    1)
        echo "🔄 Iterating on plan..."
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step5" value={"status":"iterating"} namespace="pipeline"
        for i in 1 2 3; do
            PLAN_OUTPUT=$(/gsd:plan-phase $PHASE)  # Re-plan with feedback context
            GATE_RESULT=$(echo "$PLAN_OUTPUT" | /confidence-gate --step "plan-$PHASE-v$i" --json)
            [ $? -eq 0 ] && break
        done
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step5" value={"status":"done","iterations":$i} namespace="pipeline"
        ;;
    2)
        echo "⏸️ Human review required for plan"
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step5" value={"status":"blocked","reason":"human_review"} namespace="pipeline"
        # mcp__claude-flow__session_save sessionId="gsd-{phase}-blocked-step5"
        exit 2
        ;;
esac
```

### Step 6: Execute

```bash
# PRE-STEP CHECKPOINT (CRITICAL - saves full context before execution):
# mcp__claude-flow__session_save sessionId="gsd-{phase}-pre-execute"
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6" value={"status":"starting","critical":true} namespace="pipeline"

echo "🚀 Executing phase..."
/gsd:execute-phase-sync $PHASE

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6" value={"status":"done","executed":true} namespace="pipeline"
# mcp__claude-flow__session_save sessionId="gsd-{phase}-post-execute"
```

### Step 6b: Automated Verification (Pre-UAT)

**Usa il verification-runner di /gsd:verify-work:**

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6b" value={"status":"starting"} namespace="pipeline"

echo "🔬 Running automated verification (6-phase)..."

# Usa lo stesso verification runner di /gsd:verify-work
VERIFY_OUTPUT=$(node ~/.claude/scripts/hooks/skills/verification/verification-runner.js 2>&1)
VERIFY_EXIT=$?

echo "$VERIFY_OUTPUT"

# Parse risultati
BUILD_PASS=$(echo "$VERIFY_OUTPUT" | grep -c "Build.*✓" || echo 0)
TYPE_PASS=$(echo "$VERIFY_OUTPUT" | grep -c "Type.*✓" || echo 0)
LINT_PASS=$(echo "$VERIFY_OUTPUT" | grep -c "Lint.*✓" || echo 0)
TEST_PASS=$(echo "$VERIFY_OUTPUT" | grep -c "Test.*✓" || echo 0)
SECURITY_PASS=$(echo "$VERIFY_OUTPUT" | grep -c "Security.*✓" || echo 0)

# Tier 1 (fail-fast): Build, Type Check, Tests
TIER1_FAIL=0
if [ "$BUILD_PASS" -eq 0 ] || [ "$TYPE_PASS" -eq 0 ] || [ "$TEST_PASS" -eq 0 ]; then
    TIER1_FAIL=1
    echo "❌ Tier 1 verification failed (build/type/tests)"
fi

# Tier 2 (warnings): Lint, Security
TIER2_WARN=0
if [ "$LINT_PASS" -eq 0 ] || [ "$SECURITY_PASS" -eq 0 ]; then
    TIER2_WARN=1
    echo "⚠️ Tier 2 warnings (lint/security)"
fi

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6b" value={"status":"done","tier1_fail":$TIER1_FAIL,"tier2_warn":$TIER2_WARN} namespace="pipeline"
```

### Step 6c: Plan Fix (if verification failed)

**Usa /gsd:plan-fix per issues strutturati (non sed inline):**

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6c" value={"status":"starting"} namespace="pipeline"

if [ "$TIER1_FAIL" -eq 1 ]; then
    echo "🔧 Verification failed - creating fix plan..."

    # Opzione 1: Se UAT.md esiste (post verify-work), usa plan-fix
    UAT_FILE=".planning/phases/$PHASE*/*-UAT.md"
    if ls $UAT_FILE 1>/dev/null 2>&1; then
        echo "  → Using /gsd:plan-fix for structured fix"
        /gsd:plan-fix $PHASE
    else
        # Opzione 2: Se no UAT, delega a coder agent per fix immediato
        echo "  → Delegating to coder agent for immediate fix"
        # Task({ subagent_type: "coder", prompt: "Fix verification failures in phase $PHASE. Errors: $VERIFY_OUTPUT" })

        # Re-run verification
        VERIFY_OUTPUT=$(node ~/.claude/scripts/hooks/skills/verification/verification-runner.js 2>&1)
        VERIFY_EXIT=$?
    fi

    # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6c" value={"status":"done","fix_ran":true} namespace="pipeline"
elif [ "$TIER2_WARN" -eq 1 ] && [ "$AUTOFIX" = "true" ]; then
    echo "🔧 Tier 2 warnings detected - auto-fixing lint/security..."

    # Quick lint fix (se disponibile)
    if [ -f "package.json" ]; then
        npm run lint:fix 2>/dev/null || npx eslint --fix . 2>/dev/null || true
    elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
        ruff check --fix . 2>/dev/null || black . 2>/dev/null || true
    fi

    # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6c" value={"status":"done","lint_fixed":true} namespace="pipeline"
else
    echo "✅ Verification passed - no fix needed"
    # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step6c" value={"status":"done","fix_needed":false} namespace="pipeline"
fi
```

### Step 7: Validate

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step7" value={"status":"starting"} namespace="pipeline"

echo "✔️ Running validation..."
VALIDATE_OUTPUT=$(/validate)

# POST-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step7" value={"status":"done","validation_ran":true} namespace="pipeline"
```

### Step 8: Confidence Gate (Implementation)

```bash
# PRE-STEP CHECKPOINT:
# mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step8" value={"status":"starting","type":"gate"} namespace="pipeline"

echo "🔒 Evaluating implementation confidence..."
GATE_RESULT=$(echo "$VALIDATE_OUTPUT" | /confidence-gate --step "impl-$PHASE" --detect-evolve --json)
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "✅ Phase $PHASE completed successfully"
        # FINAL CHECKPOINT - mark phase complete:
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step8" value={"status":"done","pipeline":"complete"} namespace="pipeline"
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:complete" value={"timestamp":"{now}","success":true} namespace="pipeline"
        # mcp__claude-flow__session_save sessionId="gsd-{phase}-complete"
        NEXT_PHASE=$((PHASE + 1))

        # >>> MANDATORY: Use AskUserQuestion for next action <<<
        # Claude MUST call AskUserQuestion here, NOT just print ghost text
        ;;
    1)
        echo "🔄 Implementation needs iteration - see feedback"
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step8" value={"status":"iterate","feedback":"see_gate_result"} namespace="pipeline"

        # >>> MANDATORY: Use AskUserQuestion for iteration choice <<<
        ;;
    2)
        echo "⏸️ Human review required"
        # mcp__claude-flow__memory_store key="gsd:{project}:{phase}:step8" value={"status":"blocked","reason":"human_review"} namespace="pipeline"
        ;;
esac

# >>> POST-PHASE: Claude MUST use AskUserQuestion <<<
```

**🚨 MANDATORY: After phase completion, Claude MUST call AskUserQuestion:**

```javascript
// Exit code 0: Phase completed
AskUserQuestion({
  questions: [{
    question: `Phase ${PHASE} completata. Cosa vuoi fare?`,
    header: "Phase Done",
    options: [
      {label: `Continua Phase ${NEXT_PHASE}`, description: "Procedi automaticamente alla prossima fase"},
      {label: "Pausa", description: "Salva checkpoint e fermati qui"},
      {label: "Review", description: "Revisione manuale prima di continuare"},
      {label: "Commit & Push", description: "Commit le modifiche e push"}
    ],
    multiSelect: false
  }]
})

// Exit code 1: Iteration needed
AskUserQuestion({
  questions: [{
    question: "Iterazione necessaria. Come procedere?",
    header: "Iterate",
    options: [
      {label: "Riprova automatico", description: "Re-esegui la fase con le correzioni"},
      {label: "Fix manuale", description: "Voglio correggere manualmente"},
      {label: "Ignora e continua", description: "Procedi comunque alla prossima fase"}
    ],
    multiSelect: false
  }]
})
```

**Based on user choice:**
- `Continua Phase N`: Execute `/pipeline:gsd {NEXT_PHASE}` automatically
- `Pausa`: Save checkpoint and stop
- `Review`: Show summary and wait
- `Commit & Push`: Run git commit and push
- `Riprova automatico`: Re-run current phase
- `Fix manuale`: Stop and let user fix
- `Ignora e continua`: Execute next phase anyway
```

## Ghost Text Pattern

Per attivare il suggerimento automatico Tab, ogni step termina con:
```
→ /pipeline:gsd {next}
```
Claude Code riconosce questo pattern e lo propone come ghost text.

## Options

| Option | Description |
|--------|-------------|
| `--no-research` | Skip automatic research detection |
| `--no-discuss` | Skip discussion phase |
| `--threshold N` | Custom confidence threshold (default: 85) |
| `--evolve` | Force evolution loop even without [E] marker |
| `--autodiscuss` | Validate CONTEXT.md and re-run /gsd:discuss-phase if incomplete |
| `--autofix` | Auto-fix lint issues, use /gsd:plan-fix for verification failures |
| `--gate-all` | Gate after EVERY step (includes autodiscuss) |
| `--gate-dynamic` | Only gate when complexity detected |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pipeline completed successfully |
| 1 | Iteration needed (issues found) |
| 2 | Human review required |
| 3 | Error |
