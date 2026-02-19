---
name: confidence-gate
description: Autonomous confidence gate with multi-model verification. Eliminates "is this OK?" questions when confidence is high. Pluggable into any workflow.
argument-hint: "<step_output> [--confidence N] [--step NAME] [--threshold N] [--no-iterate] [--json] [--files FILE...] [--include-dirs DIR...]"
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
  - mcp__claude-flow__memory_store
  - mcp__claude-flow__memory_retrieve
  - mcp__pal__clink
  - mcp__pal__codereview
  - mcp__pal__consensus
  - mcp__pal__chat
---

# /confidence-gate - Autonomous Verification Gate

Multi-model verification gate that decides whether to proceed automatically, iterate, or require human review.

## Purpose

**Eliminates time-wasting questions like "Il piano va bene?"** by:
1. Calculating internal confidence score
2. Cross-verifying with external models (Gemini 3 Flash, Gemini 2.5 Pro)
3. Auto-approving when confidence is high
4. Suggesting iterations when issues found
5. Requesting human review only when necessary

## Usage

```bash
# Basic: pipe step output
echo "$STEP_OUTPUT" | /confidence-gate --step "plan"

# With explicit confidence
/confidence-gate --input "$OUTPUT" --confidence 75 --step "implement"

# Custom threshold
/confidence-gate --input "$OUTPUT" --threshold 90 --step "security-review"

# JSON output for workflow integration
/confidence-gate --input "$OUTPUT" --step "plan" --json

# Skip iteration suggestions
/confidence-gate --input "$OUTPUT" --step "plan" --no-iterate
```

## Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--output`, `--input`, `-o`, `-i` | Output to verify (or stdin) | stdin |
| `--files`, `-f` | File paths to ingest as input (concatenated) | - |
| `--include-dirs` | Directories for Gemini to browse natively | - |
| `--confidence`, `-c` | Internal confidence score (ignored, anti-bias) | 70 |
| `--step`, `-s` | Step name (plan\|implement\|verify\|test\|security-review) | "unknown" |
| `--threshold`, `-t` | Override auto_approve threshold | from config (85) |
| `--no-iterate` | Disable iteration suggestions (should_iterate=False) | false |
| `--json` | Output JSON for workflow parsing | false |
| `--evolve`, `-e` | Enable evolution loop (iterate until convergence) | false |
| `--max-iterations`, `-m` | Max iterations for evolve loop | 3 |
| `--detect-evolve` | Auto-detect [E] marker and enable evolve | false |
| `--gemini-model`, `-g` | Override Gemini model | from config |
| `--max-input-chars` | Override max input chars | 500000 |

## Evolution Loop [E] Marker

Tasks marked with `[E]` or `[evolve]` trigger automatic iteration:

```bash
# Explicit evolve mode
/confidence-gate --evolve --max-iterations 5

# Auto-detect [E] marker in input
/confidence-gate --detect-evolve
```

**In tasks.md:**
```markdown
- [E] Implement auth flow (iterative refinement)
- [P] Run tests in parallel
- [E][P] Complex task: evolve AND parallel
```

**Evolve behavior:**
1. Evaluate output with confidence gate
2. If not approved but `should_iterate=true`: apply feedback
3. Re-evaluate with updated output
4. Repeat until approved or max iterations reached

## Decisions (Anti-Bias)

**IMPORTANT: Confidence is calculated by EXTERNAL models (Gemini CLI), NOT by Claude.**
This prevents Claude from biasing the score to auto-approve.

| Decision | Trigger | Action |
|----------|---------|--------|
| `AUTO_APPROVE` | avg confidence >= threshold AND all models approved | Proceed |
| `CROSS_VERIFY` | avg confidence 60-84, or not all models approved | Verify with backup; may set should_iterate=True if issues found |
| `HUMAN_REVIEW` | avg confidence < 60, or all models failed | Pause and ask user |

Note: There is no separate ITERATE decision. Instead, `CROSS_VERIFY` with `should_iterate=True` serves that purpose -- the gate returns fixable issues as `iteration_feedback` for the caller to retry.

## Verification Chain

```
Path 1 (PAL MCP clink -> Gemini CLI, preferred inside Claude Code):
  mcp__pal__clink(cli_name="gemini", role="codereviewer", prompt=...)

Path 2 (PAL MCP clink -> Codex CLI, code review inside Claude Code):
  mcp__pal__clink(prompt="...", cli_name="codex", role="codereviewer")

Path 3 (PAL MCP consensus, multi-model for critical decisions):
  mcp__pal__consensus(step="...", models=[...])

Path 4 (Python script standalone, fallback for CLI/CI):
  python3 ~/.claude/scripts/confidence_gate.py --step NAME --json
  Uses both Gemini CLI + Codex CLI (if codex_cli.enabled in config)
```

Paths 1-2 use CLI OAuth subscriptions (no API keys). Path 3 uses API keys via PAL.
Path 4 runs Gemini CLI and optionally Codex CLI as subprocesses.

## Output Format

### Text Output (default)
```
[GATE] plan: AUTO_APPROVE (confidence: 92)
Decision: auto_approve
Confidence: 92
Final Approved: true
```

### JSON Output (--json)
```json
{
  "decision": "auto_approve|cross_verify|human_review",
  "confidence_score": 88,
  "final_approved": true,
  "should_iterate": false,
  "iteration_feedback": null,
  "verifications": [
    {
      "provider": "gemini_cli",
      "model": "gemini-3-flash-preview",
      "approved": true,
      "confidence": 90,
      "issues": [],
      "latency_ms": 2500
    },
    {
      "provider": "gemini_cli",
      "model": "gemini-2.5-pro",
      "approved": true,
      "confidence": 85,
      "issues": ["Minor: could add input validation"],
      "latency_ms": 4200
    },
    {
      "provider": "codex_cli",
      "model": "gpt-5.1-codex",
      "approved": true,
      "confidence": 88,
      "issues": [],
      "latency_ms": 3100
    }
  ]
}
```

## Workflow Integration Examples

### In GSD Pipeline
```yaml
stages:
  - name: plan
    command: "/gsd:plan-phase {phase}"
    post_hook: "/confidence-gate --step plan --json"
    on_result:
      auto_approve: continue
      cross_verify_with_iterate: retry_with_feedback
      human_review: pause
```

### In Speckit Pipeline
```yaml
- name: implement
  command: "/speckit:implement"
  post_hook: |
    RESULT=$(/confidence-gate --step implement --json)
    if echo "$RESULT" | jq -e '.final_approved' > /dev/null; then
      continue
    else
      iterate_with_feedback "$RESULT"
    fi
```

### Standalone in Bash
```bash
# After any step
OUTPUT=$(some_command)
GATE_RESULT=$(echo "$OUTPUT" | /confidence-gate --step "my-step" --json)

if [ "$(echo $GATE_RESULT | jq -r '.decision')" = "auto_approve" ]; then
  echo "Proceeding automatically"
else
  echo "Issues found: $(echo $GATE_RESULT | jq -r '.iteration_feedback')"
fi
```

## Execution

When invoked, use **PAL MCP** as primary path (Paths 1-3 within Claude Code), with the Python script as fallback (Path 4 for CLI/CI).

### Path 1: PAL MCP clink -> Gemini (preferred, within Claude Code)

Use `mcp__pal__clink` with `cli_name="gemini"` to route through Gemini CLI (OAuth, no API keys):

```
mcp__pal__clink(
  prompt="<REVIEW_PROMPT>\n\n---\n<STEP_OUTPUT>",
  cli_name="gemini",
  role="codereviewer"
)
```

The review prompt must ask for JSON response with `{approved, confidence, issues, recommendation}`.
Use the step-specific prompts from the Python script (plan, implement, verify, test, security-review).

### Path 2: PAL MCP clink -> Codex (code review, within Claude Code)

Use `mcp__pal__clink` with `cli_name="codex"` to route through Codex CLI (OpenAI subscription):

```
mcp__pal__clink(
  prompt="<REVIEW_PROMPT>\n\n---\n<STEP_OUTPUT>",
  cli_name="codex",
  role="codereviewer"
)
```

Best for code-focused reviews. Default model: gpt-5.1-codex (specialized for code review).

### Path 3: PAL MCP consensus (multi-model, for critical decisions)

Use `mcp__pal__consensus` for cross-provider verification (uses API keys, not CLI OAuth):

```
mcp__pal__consensus(
  step="Valuta questo output...\n\n<STEP_OUTPUT>",
  models=[
    {"model": "gemini-2.5-pro", "stance": "neutral"},
    {"model": "gpt-5.2", "stance": "neutral"}
  ]
)
```

Reserve for high-stakes decisions (security reviews, architecture choices).

### Confidence scoring (Paths 1-3)

Parse the response and map to gate decisions:
- confidence >= threshold (config, default 85) + approved -> `AUTO_APPROVE`
- confidence 60-84 -> `CROSS_VERIFY` (may suggest iteration if issues found)
- confidence < 60 -> `HUMAN_REVIEW`

### Path 4: Python Script (fallback, for CLI/CI usage)

```bash
echo "$STEP_OUTPUT" | python3 ~/.claude/scripts/confidence_gate.py \
  --step "$STEP_NAME" \
  --json

# With file inputs and directory browsing
python3 ~/.claude/scripts/confidence_gate.py \
  --files src/main.py src/utils.py \
  --include-dirs src/ tests/ \
  --step "implement" \
  --json
```

This runs Gemini CLI directly (subprocess), and optionally Codex CLI if `codex_cli.enabled` is true in config. Useful for standalone/hook/CI usage.

## Memory Persistence

When using Paths 1-3 (within Claude Code), store results via claude-flow memory:

```python
mcp__claude-flow__memory_store(
  key=f"gate:{project}:{step}:{timestamp}",
  value={
    "decision": result.decision,
    "confidence": result.confidence_score,
    "verifications": result.verifications,
    "approved": result.final_approved
  },
  namespace="confidence-gate"
)
```

This enables:
- Historical analysis of gate decisions
- Learning from past verifications
- Adjusting thresholds based on outcomes

## Configuration

Models configured in `~/.claude/config/confidence_gate.json`:

```json
{
  "gemini_cli_models": {
    "primary": "gemini-3-flash-preview",
    "cross_verify": "gemini-2.5-pro",
    "fallback": "gemini-2.5-flash"
  },
  "codex_cli": {
    "enabled": true,
    "model": "gpt-5.1-codex"
  },
  "pal_consensus": {
    "enabled": true,
    "models": [
      {"model": "gemini-2.5-pro", "stance": "neutral"},
      {"model": "gpt-5.2", "stance": "neutral"}
    ]
  }
}
```

Requires:
- Gemini CLI (`npm i -g @google/gemini-cli`) + Google AI Pro subscription (OAuth)
- Codex CLI (optional, `npm i -g @openai/codex`) + OpenAI subscription

**Note:** Thresholds default to 85 (auto_approve) and 60 (cross_verify). They can be overridden via `--threshold` CLI flag or `thresholds` config key, but are NOT exposed to Claude to prevent gaming.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | AUTO_APPROVE or CROSS_VERIFY approved |
| 1 | CROSS_VERIFY with should_iterate - issues found, retry suggested |
| 2 | HUMAN_REVIEW - human approval required |
| 3 | Error (verification failed, config missing) |
