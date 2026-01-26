<purpose>
Validate built features through conversational testing with persistent state. Creates UAT.md that tracks test progress, survives /clear, and feeds into /gsd:plan-fix.

User tests, Claude records. One test at a time. Plain text responses.
</purpose>

<philosophy>
**Show expected, ask if reality matches.**

Claude presents what SHOULD happen. User confirms or describes what's different.
- "yes" / "y" / "next" / empty → pass
- Anything else → logged as issue, severity inferred

No Pass/Fail buttons. No severity questions. Just: "Here's what should happen. Does it?"
</philosophy>

<template>
@~/.claude/get-shit-done/templates/UAT.md
</template>

<process>

<step name="automated_validation">
**Run automated validation before conversational UAT:**

Before proceeding to manual testing, run automated validation to catch issues early.

### Tier 1 (Blockers) - MUST PASS

```bash
python3 ~/.claude/templates/validation/orchestrator.py 1
```

**If Tier 1 fails (exit code 1):**

```
════════════════════════════════════════
VALIDATION BLOCKED: Cannot Proceed to UAT
════════════════════════════════════════

Tier 1 (blocker) validation failed:
[List failing validators with messages]

UAT skipped - no point testing broken code.

Options:
1. Fix issues and re-run `/gsd:verify-work`
2. Run `/gsd:plan-fix` to create fix plan
════════════════════════════════════════
```

Do NOT proceed to UAT. Route user to fix issues first.

**If Tier 1 passes (exit code 0):**

Continue to Tier 2 validation.

### Tier 2 (Warnings) - Show to User

```bash
python3 ~/.claude/templates/validation/orchestrator.py 2
```

**Present Tier 2 results to user:**

```
## Automated Validation Results

### Tier 1 (Blockers): PASSED
All critical checks passed.

### Tier 2 (Warnings): [N] items
[List any warnings with suggestions]

Note: These are suggestions, not blockers. You can proceed with UAT.
```

User can acknowledge warnings and proceed to manual testing.

### Environment Control

```bash
if [ "${VALIDATION_ENABLED:-true}" = "false" ]; then
  echo "⚠️ Validation disabled - proceeding directly to UAT"
fi
```

### Quick Mode

If user runs with `--quick` flag, skip Tier 2:
```bash
# Only run Tier 1 for quick verification
python3 ~/.claude/templates/validation/orchestrator.py 1
```

Proceed to UAT after Tier 1 passes.
</step>

<step name="check_active_session">
**First: Check for active UAT sessions**

```bash
find .planning/phases -name "*-UAT.md" -type f 2>/dev/null | head -5
```

**If active sessions exist AND no $ARGUMENTS provided:**

Read each file's frontmatter (status, phase) and Current Test section.

Display inline:

```
## Active UAT Sessions

| # | Phase | Status | Current Test | Progress |
|---|-------|--------|--------------|----------|
| 1 | 04-comments | testing | 3. Reply to Comment | 2/6 |
| 2 | 05-auth | testing | 1. Login Form | 0/4 |

Reply with a number to resume, or provide a phase number to start new.
```

Wait for user response.

- If user replies with number (1, 2) → Load that file, go to `resume_from_file`
- If user replies with phase number → Treat as new session, go to `create_uat_file`

**If active sessions exist AND $ARGUMENTS provided:**

Check if session exists for that phase. If yes, offer to resume or restart.
If no, continue to `create_uat_file`.

**If no active sessions AND no $ARGUMENTS:**

```
No active UAT sessions.

Provide a phase number to start testing (e.g., /gsd:verify-work 4)
```

**If no active sessions AND $ARGUMENTS provided:**

Continue to `create_uat_file`.
</step>

<step name="find_summaries">
**Find what to test:**

Parse $ARGUMENTS as phase number (e.g., "4") or plan number (e.g., "04-02").

```bash
# Find phase directory
PHASE_DIR=$(ls -d .planning/phases/${PHASE_ARG}* 2>/dev/null | head -1)

# Find SUMMARY files
ls "$PHASE_DIR"/*-SUMMARY.md 2>/dev/null
```

Read each SUMMARY.md to extract testable deliverables.
</step>

<step name="extract_tests">
**Extract testable deliverables from SUMMARY.md:**

Parse for:
1. **Accomplishments** - Features/functionality added
2. **User-facing changes** - UI, workflows, interactions

Focus on USER-OBSERVABLE outcomes, not implementation details.

For each deliverable, create a test:
- name: Brief test name
- expected: What the user should see/experience (specific, observable)

Examples:
- Accomplishment: "Added comment threading with infinite nesting"
  → Test: "Reply to a Comment"
  → Expected: "Clicking Reply opens inline composer below comment. Submitting shows reply nested under parent with visual indentation."

Skip internal/non-observable items (refactors, type changes, etc.).
</step>

<step name="create_uat_file">
**Create UAT file with all tests:**

```bash
mkdir -p "$PHASE_DIR"
```

Build test list from extracted deliverables.

Create file:

```markdown
---
status: testing
phase: XX-name
source: [list of SUMMARY.md files]
started: [ISO timestamp]
updated: [ISO timestamp]
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: [first test name]
expected: |
  [what user should observe]
awaiting: user response

## Tests

### 1. [Test Name]
expected: [observable behavior]
result: [pending]

### 2. [Test Name]
expected: [observable behavior]
result: [pending]

...

## Summary

total: [N]
passed: 0
issues: 0
pending: [N]
skipped: 0

## Issues for /gsd:plan-fix

[none yet]
```

Write to `.planning/phases/XX-name/{phase}-UAT.md`

Proceed to `present_test`.
</step>

<step name="present_test">
**Present current test to user:**

Read Current Test section from UAT file.

Display:

```
## Test {number}: {name}

**Expected:** {expected}

Does this match what you see?
```

Wait for user response (plain text, no AskUserQuestion).
</step>

<step name="process_response">
**Process user response and update file:**

**If response indicates pass:**
- Empty response, "yes", "y", "ok", "pass", "next", "approved", "✓"

Update Tests section:
```
### {N}. {name}
expected: {expected}
result: pass
```

**If response indicates skip:**
- "skip", "can't test", "n/a"

Update Tests section:
```
### {N}. {name}
expected: {expected}
result: skipped
reason: [user's reason if provided]
```

**If response is anything else:**
- Treat as issue description

Infer severity from description:
- Contains: crash, error, exception, fails, broken, unusable → blocker
- Contains: doesn't work, wrong, missing, can't → major
- Contains: slow, weird, off, minor, small → minor
- Contains: color, font, spacing, alignment, visual → cosmetic
- Default if unclear: major

Update Tests section:
```
### {N}. {name}
expected: {expected}
result: issue
reported: "{verbatim user response}"
severity: {inferred}
```

Append to Issues section:
```
- UAT-{NNN}: {brief summary from response} ({severity}) - Test {N}
```

**After any response:**

Update Summary counts.
Update frontmatter.updated timestamp.

If more tests remain → Update Current Test, go to `present_test`
If no more tests → Go to `complete_session`
</step>

<step name="resume_from_file">
**Resume testing from UAT file:**

Read the full UAT file.

Find first test with `result: [pending]`.

Announce:
```
Resuming: Phase {phase} UAT
Progress: {passed + issues + skipped}/{total}
Issues found so far: {issues count}

Continuing from Test {N}...
```

Update Current Test section with the pending test.
Proceed to `present_test`.
</step>

<step name="complete_session">
**Complete testing and commit:**

Update frontmatter:
- status: complete
- updated: [now]

Clear Current Test section:
```
## Current Test

[testing complete]
```

Commit the UAT file:
```bash
git add ".planning/phases/XX-name/{phase}-UAT.md"
git commit -m "test({phase}): complete UAT - {passed} passed, {issues} issues"
```

Present summary:
```
## UAT Complete: Phase {phase}

| Result | Count |
|--------|-------|
| Passed | {N}   |
| Issues | {N}   |
| Skipped| {N}   |

[If issues > 0:]
### Issues Found

[List from Issues section]
```

**If issues > 0:** Proceed to `diagnose_issues`

**If issues == 0:**
```
All tests passed. Ready to continue.

- `/gsd:plan-phase {next}` — Plan next phase
- `/gsd:execute-phase {next}` — Execute next phase
```
</step>

<step name="diagnose_issues">
**Diagnose root causes before planning fixes:**

```
---

{N} issues found. Diagnosing root causes...

Spawning parallel debug agents to investigate each issue.
```

- Load diagnose-issues workflow
- Follow @~/.claude/get-shit-done/workflows/diagnose-issues.md
- Spawn parallel debug agents for each issue
- Collect root causes
- Update UAT.md with root causes
- Proceed to `offer_plan_fix`

Diagnosis runs automatically - no user prompt. Parallel agents investigate simultaneously, so overhead is minimal and fixes are more accurate.
</step>

<step name="offer_plan_fix">
**Offer next steps after diagnosis:**

```
---

## Diagnosis Complete

| Issue | Root Cause |
|-------|------------|
| UAT-001 | {root_cause} |
| UAT-002 | {root_cause} |
...

Next steps:
- `/gsd:plan-fix {phase}` — Create fix plan with root causes
- `/gsd:verify-work {phase}` — Re-test after fixes
```
</step>

</process>

<update_rules>
**Section update rules:**

| Section | Rule | When |
|---------|------|------|
| Frontmatter.status | OVERWRITE | Start, complete |
| Frontmatter.updated | OVERWRITE | Every update |
| Current Test | OVERWRITE | Each test transition |
| Tests.{N}.result | OVERWRITE | When user responds |
| Summary | OVERWRITE | After each response |
| Issues | APPEND | When issue found |

**Update file AFTER processing each response.** If context resets, file shows exactly where to resume.
</update_rules>

<severity_inference>
**Infer severity from user's natural language:**

| User says | Infer |
|-----------|-------|
| "crashes", "error", "exception", "fails completely" | blocker |
| "doesn't work", "nothing happens", "wrong behavior" | major |
| "works but...", "slow", "weird", "minor issue" | minor |
| "color", "spacing", "alignment", "looks off" | cosmetic |

Default to **major** if unclear. User can correct if needed.

**Never ask "how severe is this?"** - just infer and move on.
</severity_inference>

<success_criteria>
- [ ] UAT file created with all tests from SUMMARY.md
- [ ] Tests presented one at a time with expected behavior
- [ ] User responses processed as pass/issue/skip
- [ ] Severity inferred from description (never asked)
- [ ] File updated after each response
- [ ] Can resume perfectly from any /clear
- [ ] Committed on completion
- [ ] Clear next steps based on results
</success_criteria>
