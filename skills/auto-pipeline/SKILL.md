---
name: auto-pipeline
description: Fully autonomous pipeline orchestrator for GSD and SpecKit. Auto-detects complexity, runs research/discuss/clarify as needed, then plan→gate→execute→analyze→gate.
argument-hint: "<framework> <phase|feature> [--no-research] [--no-discuss] [--threshold N]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Task
  - Skill
  - AskUserQuestion
---

# /auto-pipeline - Autonomous Pipeline Orchestrator

Orchestrates complete development cycle with automatic research, discussion, and confidence gates.

## Usage

```bash
# GSD framework
/auto-pipeline gsd 05

# SpecKit framework
/auto-pipeline speckit "user authentication feature"

# Skip optional phases
/auto-pipeline gsd 05 --no-research --no-discuss

# Custom confidence threshold
/auto-pipeline speckit "api endpoint" --threshold 90
```

## Execution Flow

### 1. Parse Arguments

```python
framework = args[0]  # "gsd" or "speckit"
target = args[1]     # phase number or feature description
options = parse_options(args[2:])
```

### 2. Complexity Detection (Research Trigger)

Check if research is needed based on keywords:

```python
RESEARCH_KEYWORDS = [
    # Niche domains
    "3d", "webgl", "threejs", "shader", "glsl",
    "ml", "machine learning", "neural", "tensorflow", "pytorch",
    "audio", "dsp", "synthesis", "midi",
    "blockchain", "web3", "solidity", "smart contract",
    "realtime", "websocket", "streaming",
    "cryptography", "encryption", "security protocol",
    # Complex patterns
    "distributed", "consensus", "raft", "paxos",
    "compiler", "parser", "ast", "lexer",
    "graphics", "rendering", "ray tracing",
]

def needs_research(description: str) -> bool:
    description_lower = description.lower()
    matches = [kw for kw in RESEARCH_KEYWORDS if kw in description_lower]
    return len(matches) >= 1 and "--no-research" not in options
```

### 3. Execute Pipeline

```bash
# === PHASE 1: RESEARCH (if needed) ===
if needs_research:
    if framework == "gsd":
        /gsd:research-phase {target}
    else:
        # SpecKit: use /research for academic sources
        /research "{target} best practices architecture"

# === PHASE 2: DISCUSS/CLARIFY ===
if "--no-discuss" not in options:
    if framework == "gsd":
        /gsd:discuss-phase {target}
    else:
        /speckit.clarify

# === PHASE 3: PLAN ===
if framework == "gsd":
    PLAN_OUTPUT=$(/gsd:plan-phase {target})
else:
    PLAN_OUTPUT=$(/speckit.plan)

# === PHASE 4: CONFIDENCE GATE (Plan) ===
echo "$PLAN_OUTPUT" | /confidence-gate --step "plan" --detect-evolve --json --evolve --max-iterations 3
EXIT_CODE=$?

if [ $EXIT_CODE -eq 2 ]; then
    # Human review required
    echo "⏸️ Plan requires human review"
    exit 2
fi

# === PHASE 5: EXECUTE ===
if framework == "gsd":
    /gsd:execute-phase {target}
else:
    /speckit.implement-sync

# === PHASE 6: ANALYZE (SpecKit) / VALIDATE (both) ===
if framework == "speckit":
    ANALYZE_OUTPUT=$(/speckit.analyze)
fi

VALIDATE_OUTPUT=$(/validate)

# === PHASE 7: CONFIDENCE GATE (Implementation) ===
echo "$VALIDATE_OUTPUT" | /confidence-gate --step "implement" --detect-evolve --json
EXIT_CODE=$?

if [ $EXIT_CODE -eq 1 ]; then
    # Cross-verify: issues found, needs second opinion or retry
    echo "Cross-verify triggered. Review feedback and iterate."
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Pipeline completed successfully"
fi
```

## Output

```
═══════════════════════════════════════════════════════════
  AUTO-PIPELINE: {framework} → {target}
═══════════════════════════════════════════════════════════

[1/7] Complexity Detection
      Keywords found: {keywords}
      Research needed: {yes/no}

[2/7] Research Phase
      {research output or "Skipped"}

[3/7] Discuss/Clarify Phase
      {discuss output or "Skipped"}

[4/7] Plan Phase
      Plan created: {path}

[5/7] Confidence Gate (Plan)
      Decision: {AUTO_APPROVE/CROSS_VERIFY/HUMAN_REVIEW}
      Confidence: {score}

[6/7] Execute Phase
      {execution summary}

[7/7] Confidence Gate (Implementation)
      Decision: {decision}
      Validation Score: {score}

═══════════════════════════════════════════════════════════
  RESULT: {AUTO_APPROVE/CROSS_VERIFY/HUMAN_REVIEW}
═══════════════════════════════════════════════════════════
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pipeline completed successfully |
| 1 | Cross-verify triggered (issues found, needs second opinion or retry) |
| 2 | Human review required |
| 3 | Error (missing config, API failure) |

## Configuration

In `.claude-flow/config.yaml`:

```yaml
autoPipeline:
  researchKeywords:
    - "3d"
    - "ml"
    - "blockchain"
    # ... add custom keywords
  skipResearchByDefault: false
  skipDiscussByDefault: false
  defaultThreshold: 85
  maxIterations: 3
```
