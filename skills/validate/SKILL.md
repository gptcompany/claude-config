---
name: validate
description: Run 14-dimension ValidationOrchestrator. Tier 1 blockers, Tier 2 warnings, Tier 3 monitors. Supports quick validation and full validation.
---

# /validate - Unified Validation Command

Run the 14-dimension ValidationOrchestrator on the current project.

## Commands

### `/validate`

Run all tiers (full validation).

**Action:**
```bash
python3 ~/.claude/templates/validation/orchestrator.py all
```

Output: Full validation report with all 14 dimensions

---

### `/validate quick` or `/validate 1`

Run Tier 1 blockers only (fast validation).

**Arguments:**
- `quick` or `1`: Run only blocking validators

**Action:**
```bash
python3 ~/.claude/templates/validation/orchestrator.py 1
```

Output: Tier 1 results (code_quality, type_safety, security, coverage)

---

### `/validate 2`

Run Tier 2 warnings only.

**Action:**
```bash
python3 ~/.claude/templates/validation/orchestrator.py 2
```

Output: Tier 2 results (design_principles, oss_reuse, accessibility, performance)

---

### `/validate 3`

Run Tier 3 monitors only.

**Action:**
```bash
python3 ~/.claude/templates/validation/orchestrator.py 3
```

Output: Tier 3 results (mathematical, api_contract, visual, behavioral)

---

## Prerequisites

The project must have a validation config at `.claude/validation/config.json`.

To scaffold validation for a new project:
```bash
~/.claude/templates/validation/scaffold.sh {project_path} [domain]
```

Domains: `trading`, `workflow`, `data`, `general` (default)

---

## Tier Summary

| Tier | Purpose | Behavior | Validators |
|------|---------|----------|------------|
| 1 | Blockers | MUST pass - blocks CI/merge | code_quality, type_safety, security, coverage |
| 2 | Warnings | SHOULD fix - auto-suggest | design_principles, oss_reuse, accessibility, performance |
| 3 | Monitors | Track metrics - Grafana | mathematical, api_contract, visual, behavioral |

---

## Exit Codes

- 0: All specified tiers passed
- 1: Tier 1 blockers failed
- 2: Validation error (config not found, orchestrator error)

---

## Execution Instructions

When the user invokes `/validate [tier]`:

1. Check if `.claude/validation/config.json` exists in current project
2. If missing, suggest: "Run `~/.claude/templates/validation/scaffold.sh .` to setup"
3. Execute the appropriate orchestrator command based on tier argument
4. Parse output and show summary:
   - Success: "Validation passed (Tier X)"
   - Failure: Show failed validators with brief reason

**KISS Principle**: Show minimal output. User wants pass/fail and next action.

## Example Flow

```
User: /validate quick
Agent: Running Tier 1 validation...

Tier 1 (BLOCKER): [PASS]
  [+] code_quality: Ruff passed
  [+] type_safety: Type check passed
  [+] security: Security check passed
  [+] coverage: 87% coverage

User: /validate
Agent: Running full validation...

VALIDATION REPORT
=================
Tier 1: PASS (4/4)
Tier 2: WARN (3/4) - oss_reuse: Consider using lodash for debounce
Tier 3: PASS (4/4)

Result: PASSED (12/12 validators)
```
