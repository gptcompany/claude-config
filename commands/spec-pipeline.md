---
description: Automated SpecKit pipeline orchestrator - from feature description to validated tasks with dual tracking (tasks.md + GitHub Issues).
handoffs:
  - label: Implement Tasks
    agent: speckit.implement
    prompt: Start implementation from tasks.md
    send: true
---

# /spec-pipeline - Full SpecKit Pipeline with Dual Tracking

Orchestrates the complete SpecKit workflow from feature description to implementation-ready tasks, maintaining sync between tasks.md AND GitHub Issues.

**Production-Ready Features:**
- State persistence (PostgreSQL checkpoints)
- Step tracking (QuestDB metrics)
- Circuit breaker for external services
- Retry with exponential backoff
- Resume from failure capability

## Usage

```
/spec-pipeline "Feature description"     # Full pipeline
/spec-pipeline --sync                    # Sync existing tasks.md to Issues
/spec-pipeline --verify                  # Verify and update task status
/spec-pipeline --resume <run_id>         # Resume from checkpoint
/spec-pipeline --dry-run "Feature"       # Preview steps without executing
/spec-pipeline --status <run_id>         # Check run status
```

## Python Orchestrator

The pipeline is powered by a Python orchestrator for production-grade reliability:

```bash
# Direct invocation (for debugging)
python ~/.claude/scripts/spec_pipeline.py "Feature description"
python ~/.claude/scripts/spec_pipeline.py --resume <run_id>
python ~/.claude/scripts/spec_pipeline.py --status <run_id>
```

## Philosophy: Dual Tracking

**tasks.md** = Planning artifact (local, detailed, checkboxes)
**GitHub Issues** = Execution tracking (visibility, assignments, CI integration)

Both are kept in sync:
- New tasks → Create Issues
- Completed tasks [X] → Close Issues
- Closed Issues → Mark [X] in tasks.md

## Pipeline Workflow

### Step 0: Project Constitution (one-time setup)
```
/speckit:constitution
```
**Run once per project** to establish core principles and constraints.
Skip if `.specify/memory/constitution.md` already exists.

### Step 1: Feature Specification
```
/speckit:specify "$ARGUMENTS"
```
Creates/updates spec.md with user stories, priorities, acceptance criteria.

### Step 1.5: Requirements Quality Check (optional)
```
/speckit:checklist
```
Validates spec.md quality - like "unit tests for requirements".
Run if spec is complex or high-stakes.

### Step 2: Clarification (if needed)
```
/speckit:clarify
```
Identifies underspecified areas, asks targeted questions.

### Step 3: Academic Research (smart suggestion)

**Evaluate if research would benefit the spec** based on:
- Complexity of the feature
- Domain importance (finance, medical, legal)
- Need for mathematical rigor or proofs
- Recent academic advances in the field

**If beneficial**, derive research query from spec.md:
```python
# Extract from spec.md:
query = f"{feature_name} {domain_keywords} {technical_concepts}"
```

Then trigger research:
```
/research --academic "{derived_query}"
```

**Papers are saved to:**
- PDFs: `/media/sam/1TB/N8N_dev/papers/`
- Metadata: PostgreSQL `finance_papers.papers`
- Accessible via RAG for subsequent steps

**If not beneficial**: Skip and proceed to Step 4.

### Step 4: Implementation Plan
```
/speckit:plan
```
Creates plan.md with architecture, tech stack, file structure.
**Now informed by academic papers** (if research was triggered).

**Context7 Documentation Fetch:**
Before creating the plan, fetch technical documentation for identified technologies:

```
# Use Context7 MCP to get library documentation
# For each technology in the spec (e.g., React, PostgreSQL, FastAPI):
mcp__context7__get-library-docs(library_name="<technology>")
```

The orchestrator will:
1. Extract technologies from spec.md
2. Fetch docs via Context7 for each
3. Include relevant docs in plan context

### Step 5: Task Generation
```
/speckit:tasks
```
Creates tasks.md with dependency-ordered, actionable tasks.

### Step 6: Cross-Artifact Analysis
```
/speckit:analyze
```
Validates consistency between:
- spec.md
- plan.md
- tasks.md
- **Research findings** (if available)

Checks for:
- Missing tasks for spec requirements
- Plan/task alignment
- Academic backing for critical decisions

### Step 7: GitHub Issues Sync
```
/speckit:taskstoissues
```
Creates GitHub Issues for each pending task in tasks.md.

### Step 8: Verification
```
/verify-tasks --commit
```
Verifies implementations exist, updates [X] checkboxes.

### Step 9: Issue Sync
Run sync script to close completed issues:
```bash
python scripts/sync_tasks_issues.py
```

## Sync Script Location

The sync script should be at: `scripts/sync_tasks_issues.py`

If it doesn't exist, create it with the following logic:
1. Parse tasks.md for completed tasks [X]
2. Find matching GitHub Issues by task ID
3. Close issues for completed tasks
4. For closed issues not in tasks.md as [X], update tasks.md

## Execution

**IMPORTANT: Use the Python orchestrator for all executions.**

When user runs `/spec-pipeline "Feature"`:

```bash
# Execute via orchestrator
python ~/.claude/scripts/spec_pipeline.py "$ARGUMENTS"
```

The orchestrator handles:
- State machine transitions
- Checkpoint persistence (PostgreSQL/file fallback)
- Circuit breaker for external services (GitHub, N8N)
- Retry with exponential backoff
- QuestDB metrics logging

**Flags:**
- `--sync`: Execute only steps 7-9 (sync existing tasks)
- `--verify`: Execute only step 8 (verify implementations)
- `--research`: Force research even if not suggested
- `--resume <run_id>`: Resume from checkpoint
- `--dry-run`: Preview steps without executing
- `--status <run_id>`: Check run status

**Resume after failure:**
```bash
# Get the run_id from previous execution
python ~/.claude/scripts/spec_pipeline.py --resume <run_id>
```

## Task ID to Issue Mapping

Tasks use IDs like `T001`, `T002`. GitHub Issues should include the task ID in the title:
```
[T001] Create project structure per implementation plan
```

This enables bidirectional sync.

## Labels

Apply these labels to created issues:
- `spec-{number}` (e.g., `spec-040`)
- `phase-{number}` (e.g., `phase-1`)
- Priority: `P1`, `P2`, `P3`

## Output

After pipeline completion, report:
```markdown
## Spec Pipeline Complete

### Artifacts Created
- spec.md: {path}
- plan.md: {path}
- tasks.md: {path}

### Research (if triggered)
- Query: "{derived_query}"
- Papers found: {count}
- Status: Processing (~15-30 min) / Completed
- View results: `/research-papers`

### Analysis Results
- Consistency: PASS/WARN
- Coverage: {X}% of spec requirements have tasks
- Issues found: {list if any}

### Task Summary
- Total: {count}
- Pending: {pending}
- Completed: {completed}

### GitHub Issues
- Created: {new_issues}
- Updated: {updated_issues}
- Closed: {closed_issues}
- Issues URL: {repo}/issues?q=label:spec-{number}

### Next Steps
1. Review issues at {url}
2. Assign issues to team members
3. Wait for research papers (if triggered)
4. Run `/speckit:implement` to start coding

### Useful Built-in Commands During Implementation
- `/todos` - Track implementation progress
- `/review` - Review code changes
- `/context` - Check context usage
- `/compact` - Reduce context if needed
```

## Integration with CI

Add to `.github/workflows/sync-tasks.yml`:
```yaml
on:
  push:
    paths: ['specs/**/tasks.md']
  issues:
    types: [closed]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/sync_tasks_issues.py
      - run: |
          git config user.name "github-actions[bot]"
          git add specs/*/tasks.md
          git diff --cached --quiet || git commit -m "chore: sync tasks.md with closed issues"
          git push
```
