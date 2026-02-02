# Phase 27: Autonomous Loop (Piano C) - Research

**Researched:** 2026-02-02
**Domain:** OpenClaw autonomous coding loop with spec-first workflow
**Confidence:** HIGH

<research_summary>
## Summary

Researched the existing codebase to determine what's already built and what Phase 27 needs to add. The foundation is substantial: a 14-dimension validation orchestrator, an iterative Ralph loop state machine, agent spawn mechanisms, swarm coordination, and multiple state persistence patterns.

Phase 27 needs to wire these together into a single autonomous controller that: receives a spec, generates a plan, executes it, validates results, iterates if needed, and escalates on failure. The progressive-deploy system provides the final gate.

**Primary recommendation:** Build a thin orchestration layer on top of existing components (orchestrator.py + ralph_loop.py + agent spawn). Don't rebuild validation or iteration — compose them.
</research_summary>

<standard_stack>
## Standard Stack

### Already Built (reuse, don't rebuild)

| Component | Location | Purpose |
|-----------|----------|---------|
| orchestrator.py | ~/.claude/templates/validation/ | 14-dimension tiered validation (1,918 LOC) |
| ralph_loop.py | ~/.claude/templates/validation/ | Iterative validation state machine (728 LOC) |
| spec_pipeline.py | ~/.claude/scripts/ | Spec→plan→tasks→execute pipeline with resume |
| hive-manager.js | ~/.claude/scripts/hooks/control/ | Swarm parallel coordination |
| pre-push-review.py | ~/.claude/hooks/ | Risk-scored pre-push with AI escalation |

### State Persistence (choose one per concern)

| Pattern | Used By | Durability |
|---------|---------|------------|
| claude-flow memory | GSD sync, cross-session | In-memory + file |
| File-based JSON | Ralph state, checkpoints | Disk |
| PostgreSQL | spec_pipeline | Database |
| QuestDB ILP | Metrics only | Time-series |

### Supporting

| Component | Purpose |
|-----------|---------|
| Circuit breaker (resilience/) | Fault tolerance for external calls |
| Cache (resilience/cache.py) | Avoid re-validating unchanged files |
| Config loader (config_loader.py) | RFC 7396 merge patch config inheritance |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Compose Existing Tools via CLI

The autonomous loop should invoke existing tools via CLI (subprocess), not import them as libraries. This keeps each component independently testable and matches the OpenClaw exec model.

```bash
# Spec-first: generate plan
python3 spec_pipeline.py --feature "$SPEC" --stage plan

# Execute plan
/gsd:execute-phase $PHASE

# Validate results
python3 orchestrator.py 2 --files $CHANGED_FILES

# Iterate if needed
python3 ralph_loop.py --files $CHANGED_FILES --project $PROJECT
```

### Pattern 2: State Machine for Loop Control

Ralph loop already implements:
```
IDLE → VALIDATING → (BLOCKED | COMPLETE)
```

The autonomous controller needs a higher-level state machine:
```
SPEC_RECEIVED → PLANNING → EXECUTING → VALIDATING →
  (ITERATION if score < threshold) →
  (ESCALATION if max_iterations reached) →
  (PUSH_GATE if passed) →
  COMPLETE
```

### Pattern 3: Escalation Policy

From existing pre-push-review.py pattern:
1. Local fast check (free, <5s)
2. If issues → attempt auto-fix (ralph loop)
3. If still failing → escalate to Matrix (ask human)

### Anti-Patterns to Avoid
- **Don't rebuild validation**: orchestrator.py already handles 14 dimensions
- **Don't rebuild iteration**: ralph_loop.py already handles score tracking
- **Don't build custom state persistence**: claude-flow memory + file JSON are sufficient
- **Don't make it monolithic**: Keep it as a coordinator script that calls existing tools
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Validation | Custom checks | orchestrator.py CLI | 14 dimensions, 1918 LOC, tested |
| Iteration | Custom retry loop | ralph_loop.py | Score tracking, circuit breakers |
| Parallelism | Thread pool | hive-manager.js swarm | Already integrated with orchestrator |
| State persistence | Custom DB | claude-flow memory_store | Already used by GSD sync |
| Metrics | Custom logging | QuestDB ILP | Already integrated everywhere |
| Budget tracking | Custom counter | Ralph budget limits | max_budget_usd, cost_per_iteration |

**Key insight:** Phase 27 is a ~200 LOC coordinator, not a new system. It wires existing 3000+ LOC components.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Infinite Loop
**What goes wrong:** Agent keeps iterating without progress
**Why it happens:** Score oscillates, no stall detection
**How to avoid:** Ralph already has max_no_progress and max_consecutive_errors
**Warning signs:** Same score for 3+ iterations

### Pitfall 2: Token/Cost Explosion
**What goes wrong:** Autonomous loop burns through API budget
**Why it happens:** Each iteration = full validation + potential AI review
**How to avoid:** Ralph has max_budget_usd ($20), cost_per_iteration ($2). Set tight limits.
**Warning signs:** iteration_cost > expected_cost * 1.5

### Pitfall 3: Stale Context
**What goes wrong:** Agent workspace diverges from expected state
**Why it happens:** Failed iteration leaves dirty state
**How to avoid:** Checkpoint before each iteration, rollback on failure
**Warning signs:** git status shows unexpected changes

### Pitfall 4: Escalation Fatigue
**What goes wrong:** Too many Matrix messages, human ignores them
**Why it happens:** Escalation threshold too low
**How to avoid:** Only escalate on blocker-level failures after 3+ iterations
**Warning signs:** Multiple unacknowledged escalations
</common_pitfalls>

<code_examples>
## Code Examples

### Autonomous Controller Skeleton
```python
# autonomous_loop.py - thin coordinator (~200 LOC)
import subprocess, json, sys

class AutonomousLoop:
    def __init__(self, spec: str, project: str, max_rounds: int = 5):
        self.spec = spec
        self.project = project
        self.max_rounds = max_rounds
        self.state = "SPEC_RECEIVED"

    def run(self):
        for round in range(self.max_rounds):
            # 1. Execute current plan
            result = subprocess.run(
                ["python3", "orchestrator.py", "2", "--files"] + self.changed_files,
                capture_output=True
            )

            if result.returncode == 0:
                self.state = "PUSH_GATE"
                return self.push_gate()

            if round >= self.max_rounds - 1:
                self.state = "ESCALATION"
                return self.escalate()

            # 2. Auto-fix via ralph loop
            subprocess.run(
                ["python3", "ralph_loop.py", "--files", ",".join(self.changed_files)]
            )

    def push_gate(self):
        """Final gate: progressive-deploy check"""
        # ...

    def escalate(self):
        """Notify via Matrix when stuck"""
        # ...
```

### OpenClaw Agent Integration
```bash
# From cron or webhook trigger:
ssh 192.168.1.100 'docker exec openclaw-gateway node /app/dist/entry.js agent \
  --agent main --session-id auto-loop-$(date +%s) \
  --message "Execute autonomous loop for spec: $SPEC" \
  --json --timeout 600'
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Manual spec → plan → execute | Automated pipeline (spec_pipeline.py) | Already built |
| Single validation pass | Iterative ralph loop | Already built |
| Blocking pre-push | Risk-scored with AI escalation | Already built |

**New in our codebase:**
- Gemini cross-review (Phase 25): Second opinion on code quality
- Quality gates (Phase 26): Pre-commit/pre-push hooks in agent workspace
- Budget tracking in Ralph: max_budget_usd prevents runaway costs
</sota_updates>

<open_questions>
## Open Questions

1. **Progressive-deploy as final gate**
   - What we know: progressive-deploy exists, has its own planning/phases structure
   - What's unclear: How exactly to trigger it from autonomous loop (API? CLI?)
   - Recommendation: Check progressive-deploy for a CLI entry point during planning

2. **Matrix escalation format**
   - What we know: Can send via Synapse API to bambam room
   - What's unclear: Best message format for actionable escalations
   - Recommendation: Simple format: "BLOCKED: {issue}\nContext: {link}\nAction needed: {suggestion}"
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- orchestrator.py (1,918 LOC) - read and analyzed
- ralph_loop.py (728 LOC) - read and analyzed
- spec_pipeline.py - read and analyzed
- exec-approvals.json - read and analyzed
- pre-push-review.py (289 LOC) - read and analyzed

### Secondary (HIGH confidence)
- Phase 22-26 SUMMARY.md files - recent, verified
- OpenClaw config in CLAUDE.md - current

### Tertiary
- None needed - all internal code
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw autonomous agent loop
- Ecosystem: Existing validation framework components
- Patterns: State machine composition, CLI coordination
- Pitfalls: Infinite loops, cost explosion, stale state

**Confidence breakdown:**
- Standard stack: HIGH - all code read directly
- Architecture: HIGH - based on existing patterns
- Pitfalls: HIGH - from Ralph loop production experience
- Code examples: HIGH - based on existing implementations

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (internal code, stable)
</metadata>

---

*Phase: 27-autonomous-loop*
*Research completed: 2026-02-02*
*Ready for planning: yes*
