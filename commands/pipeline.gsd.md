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

### 3. POST-PHASE → USE AskUserQuestion (NEVER just stop)
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

// ❌ WRONG - Just printing text and stopping
echo "→ /pipeline:gsd $NEXT_PHASE quando sei pronto..."
```
**Claude MUST NOT stop and wait. MUST show interactive menu.**


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

**Claude Code DEVE eseguire checkpoint per ogni step.**

### Pattern Checkpoint (IMPERATIVE)

**PRE-STEP** - Claude Code esegue via Bash:
```bash
npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:stepN" --value '{"status":"starting"}' --namespace pipeline
```

**POST-STEP** - Claude Code esegue via Bash:
```bash
npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:stepN" --value '{"status":"done"}' --namespace pipeline
```

**SESSION SAVE** - Solo in momenti critici (pre-implement, blocchi):
```bash
npx @claude-flow/cli@latest session save --name "gsd-PHASE-stepN"
```

### Resume Protocol (IMPERATIVE)

**ALL'AVVIO** Claude Code DEVE eseguire:
```bash
npx @claude-flow/cli@latest memory search --query "gsd:*:PHASE:*" --namespace pipeline
```

Se trova step incompleto (status != "done"), chiede all'utente:
- **Resume**: continua da ultimo step completato
- **Restart**: ricomincia da step 1

## Execution

When invoked with `/pipeline:gsd {phase}`:

### Step 0: Initialize & Check Resume

**Claude Code DEVE eseguire:**
```bash
npx @claude-flow/cli@latest memory search --query "gsd:*:PHASE:*" --namespace pipeline
```

Se trova step incompleto, usa AskUserQuestion per chiedere Resume/Restart.

### Step 1: Parse and Detect Complexity

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step1" --value '{"status":"starting"}' --namespace pipeline`

Claude Code legge PROJECT.md e ROADMAP.md, estrae la descrizione della fase richiesta, e determina se serve research cercando keywords:
- 3d, webgl, threejs, shader, glsl
- ml, machine learning, neural, tensorflow
- audio, dsp, synthesis, midi
- blockchain, web3, solidity
- realtime, websocket, streaming
- cryptography, distributed, consensus
- compiler, parser, graphics, ray tracing

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step1" --value '{"status":"done"}' --namespace pipeline`

### Step 2: Research (if needed)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step2" --value '{"status":"starting"}' --namespace pipeline`

Se NEEDS_RESEARCH=true e NO_RESEARCH!=true:
1. `/research "$PHASE_DESCRIPTION"` - CoAT iterativo con triangolazione
2. Se descrizione contiene keywords accademiche (model, algorithm, formula, paper, study, methodology, heston, volatility, pricing):
   - `/research-papers "$PHASE_DESCRIPTION"` - Query RAG per papers esistenti
3. `/gsd:research-phase $PHASE` - Struttura findings in RESEARCH.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step2" --value '{"status":"done"}' --namespace pipeline`

### Step 3: Discuss Phase

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step3" --value '{"status":"starting"}' --namespace pipeline`

Se NO_DISCUSS!=true:
- `/gsd:discuss-phase $PHASE` - Raccoglie contesto fase → CONTEXT.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step3" --value '{"status":"done"}' --namespace pipeline`

### Step 3b: Context Confidence Gate (Autonomous)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step3b" --value '{"status":"starting"}' --namespace pipeline`

Valuta CONTEXT.md con `/confidence-gate --step "context-PHASE" --input CONTEXT_FILE --json`:
- Exit 0: ✅ Approved
- Exit 1: ⚠️ Auto-enrich con Task agent researcher se AUTODISCUSS=true
- Exit 2: 🛑 Human review - AskUserQuestion

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step3b" --value '{"status":"done"}' --namespace pipeline`

### Step 4: Plan Phase

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step4" --value '{"status":"starting"}' --namespace pipeline`

- `/gsd:plan-phase $PHASE` → PLAN.md

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step4" --value '{"status":"done"}' --namespace pipeline`

### Step 5: Confidence Gate (Plan)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step5" --value '{"status":"starting"}' --namespace pipeline`

Valuta PLAN con `/confidence-gate --step "plan-PHASE" --detect-evolve --json`:
- Exit 0: ✅ Plan approved
- Exit 1: 🔄 Iterate (max 3x) con re-plan
- Exit 2: ⏸️ Human review

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step5" --value '{"status":"done"}' --namespace pipeline`

### Step 6: Execute

**CHECKPOINT PRE (CRITICAL):**
```bash
npx @claude-flow/cli@latest session save --name "gsd-PHASE-pre-execute"
npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6" --value '{"status":"starting"}' --namespace pipeline
```

- `/gsd:execute-phase-sync $PHASE`

**CHECKPOINT POST:**
```bash
npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6" --value '{"status":"done"}' --namespace pipeline
npx @claude-flow/cli@latest session save --name "gsd-PHASE-post-execute"
```

### Step 6b: Automated Verification (Pre-UAT)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6b" --value '{"status":"starting"}' --namespace pipeline`

Esegue verification-runner (Build, Type, Lint, Tests, Security):
- Tier 1 fail (Build/Type/Tests): blocca
- Tier 2 warn (Lint/Security): continua con warning

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6b" --value '{"status":"done"}' --namespace pipeline`

### Step 6c: Plan Fix (if verification failed)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6c" --value '{"status":"starting"}' --namespace pipeline`

Se TIER1_FAIL:
- Se UAT.md esiste: `/gsd:plan-fix $PHASE`
- Altrimenti: Task agent coder per fix immediato

Se TIER2_WARN e AUTOFIX=true: auto-fix lint

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step6c" --value '{"status":"done"}' --namespace pipeline`

### Step 7: Validate

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step7" --value '{"status":"starting"}' --namespace pipeline`

- `/validate` → 14-dimension ValidationOrchestrator

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step7" --value '{"status":"done"}' --namespace pipeline`

### Step 8: Confidence Gate (Implementation)

**CHECKPOINT PRE:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step8" --value '{"status":"starting"}' --namespace pipeline`

Valuta VALIDATE_OUTPUT con `/confidence-gate --step "impl-PHASE" --detect-evolve --json`:
- Exit 0: ✅ Phase complete
  ```bash
  npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:complete" --value '{"status":"success"}' --namespace pipeline
  npx @claude-flow/cli@latest session save --name "gsd-PHASE-complete"
  ```
- Exit 1: 🔄 Iterate
- Exit 2: ⏸️ Human review

**CHECKPOINT POST:** `npx @claude-flow/cli@latest memory store --key "gsd:PROJECT:PHASE:step8" --value '{"status":"done"}' --namespace pipeline`


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
