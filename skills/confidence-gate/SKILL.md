---
name: confidence-gate
description: Evidence-based review gate for plans and implementations.
argument-hint: "<plan-or-change>"
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /confidence-gate - Evidence-based review

Do not invent a numerical confidence score and do not use Claude Flow/Ruflo or
Gemini. The gate is based on reproducible evidence and independent review.

## Procedure

1. Identify the exact commit range or immutable artifact under review.
2. Check scope, requirements, tests, security and operational failure modes.
3. For substantial work, delegate a read-only review to Codex or Antigravity
   through the active Gobabygo coordinator contract.
4. Record findings with severity, file/line, impact and reproduction.
5. Return one decision:
   - `PASS`: no blocking finding and required checks pass.
   - `FIX`: concrete findings must be corrected and retested.
   - `HUMAN`: the decision affects secrets, production, money, destructive
     operations or unresolved product policy.
6. Persist the decision in the repository's review ledger or Spec Kit tasks.

Never weaken a guardrail to obtain `PASS`. A provider timeout is `HUMAN` or a
retry with a different reviewer, not implicit approval.
