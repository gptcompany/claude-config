---
name: confidence-gate
description: Autonomous confidence gate with multi-model verification. Eliminates "is this OK?" questions when confidence is high. Pluggable into any workflow.
argument-hint: "<step_output> [--confidence N] [--step NAME] [--threshold N] [--no-iterate] [--json]"
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
  - mcp__claude-flow__memory_store
  - mcp__claude-flow__memory_retrieve
  - mcp__pal__review
  - mcp__pal__consensus
  - mcp__pal__clink
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
| `--input`, `-i` | Step output to verify (or stdin) | stdin |
| `--confidence`, `-c` | Internal confidence score (0-100) | Auto-calculate |
| `--step`, `-s` | Step name for logging/tracking | "unknown" |
| `--threshold`, `-t` | Auto-approve threshold | 85 |
| `--no-iterate` | Skip iteration suggestions | false |
| `--json` | Output JSON for workflow parsing | false |
| `--save` | Save result to claude-flow memory | true |
| `--evolve`, `-e` | Enable evolution loop (iterate until convergence) | false |
| `--max-iterations`, `-m` | Max iterations for evolve loop | 3 |
| `--detect-evolve` | Auto-detect [E] marker and enable evolve | false |

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
| `AUTO_APPROVE` | External verifier approves with high confidence | Proceed |
| `CROSS_VERIFY` | First verifier uncertain, needs second opinion | Verify with backup |
| `ITERATE` | Verifiers found fixable issues | Return feedback for retry |
| `HUMAN_REVIEW` | Low confidence or verifiers reject | Pause and ask user |

## Verification Chain

```
1. Gemini 3 Flash Preview (primary, via Gemini CLI + OAuth subscription)
2. Gemini 2.5 Pro (cross-verify)
3. Gemini 2.5 Flash (fallback)
```

All models use Gemini CLI with Google AI Pro subscription (OAuth, no API keys).

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
  "decision": "auto_approve|cross_verify|iterate|human_review",
  "confidence_score": 92,
  "final_approved": true,
  "should_iterate": false,
  "iteration_feedback": null,
  "verifications": [
    {
      "provider": "gemini",
      "model": "google/gemini-3-flash-preview",
      "approved": true,
      "confidence": 88,
      "issues": [],
      "latency_ms": 2500
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
      iterate: retry_with_feedback
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

When invoked, use **PAL MCP** as primary path (via `mcp__pal__review`), with Gemini CLI Python script as fallback.

### Path 1: PAL MCP (preferred, within Claude Code)

Use `mcp__pal__review` for code review verification:

```
mcp__pal__review(
  code="<STEP_OUTPUT>",
  cli_name="gemini",
  focus="completeness,correctness,security,risks"
)
```

Or `mcp__pal__consensus` for multi-model agreement:

```
mcp__pal__consensus(
  prompt="Valuta questo output. Rispondi con JSON: {approved, confidence, issues, recommendation}.\n\n<STEP_OUTPUT>",
  cli_name="gemini"
)
```

PAL MCP uses Gemini CLI with OAuth subscription (no API keys needed for `clink`/`review`).

Parse the response and map to gate decisions:
- confidence >= 85 + approved → `AUTO_APPROVE`
- confidence 60-84 → `CROSS_VERIFY` (call again with different model)
- confidence < 60 → `HUMAN_REVIEW`

### Path 2: Python Script (fallback, for CLI/CI usage)

```bash
echo "$STEP_OUTPUT" | python3 ~/.claude/scripts/confidence_gate.py \
  --step "$STEP_NAME" \
  --json
```

This runs Gemini CLI directly (subprocess), useful for standalone/hook/CI usage.

## Memory Persistence

When `--save` is enabled (default), results are stored:

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
  }
}
```

Requires: Gemini CLI (`npm i -g @google/gemini-cli`) + Google AI Pro subscription (OAuth).

**Note:** Thresholds are hardcoded in the script and NOT exposed to Claude to prevent gaming.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | AUTO_APPROVE or CROSS_VERIFY approved |
| 1 | ITERATE - issues found, retry suggested |
| 2 | HUMAN_REVIEW - human approval required |
| 3 | Error (verification failed, config missing) |
