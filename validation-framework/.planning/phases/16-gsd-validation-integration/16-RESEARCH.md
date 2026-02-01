# Phase 16 Research: GSD-Validation Integration

## Context

Based on 360° cross-check analysis (2026-01-26), we found that:
- ValidationOrchestrator is complete (1,100 LOC, 358 tests)
- Routing/tier logic exists in orchestrator.py and config_loader.py
- Swarm infrastructure exists (hive-manager.js 491 LOC)
- Session save/restore hooks exist but are not wired

**The gap is INTEGRATION, not implementation.**

## Current State Analysis

### What EXISTS and works standalone

| Component | Location | LOC | Status |
|-----------|----------|-----|--------|
| ValidationOrchestrator | `~/.claude/templates/validation/orchestrator.py` | 1,100 | ✅ Complete |
| Tier selection | `orchestrator.py:817-950` | - | ✅ Works |
| File-type routing | `orchestrator.py:1040-1054` | - | ✅ Works |
| Domain presets | `config_loader.py:159-230` | - | ✅ Works |
| Hive Manager | `~/.claude/scripts/hooks/control/hive-manager.js` | 491 | ✅ Ported |
| ClaudeFlow Sync | `~/.claude/scripts/hooks/metrics/claudeflow-sync.js` | 479 | ✅ Written |
| Memory Store | `.claude-flow/memory/store.json` | - | ✅ Working |

### What's NOT connected

| Gap | Current | Target |
|-----|---------|--------|
| GSD → Validation | Uses VerificationRunner | Call orchestrator.py |
| Session checkpoint | Never called | session_save before/after |
| Agent spawn | Log only | Actual spawn |
| Tier 3 parallel | Sequential | Swarm workers |

## Files to Modify

### 1. GSD Workflows (3 files)

```
~/.claude/get-shit-done/workflows/execute-plan.md
~/.claude/get-shit-done/workflows/verify-work.md
~/.claude/get-shit-done/workflows/complete-milestone.md
```

**Changes needed:**
- Add `python3 ~/.claude/templates/validation/orchestrator.py {tier}` calls
- Add blocking logic on Tier 1 failures
- Show Tier 2 warnings to user

### 2. Orchestrator Agent Spawn (1 file)

```
~/.claude/templates/validation/orchestrator.py
```

**Changes needed:**
- Lines 489-604: Change from log-only to actual spawn
- Use `subprocess.Popen` or Task tool equivalent

### 3. Hook Wiring (settings.json)

```
~/.claude/settings.json
```

**Changes needed:**
- Add claudeflow-sync.js to PostToolUse chain
- Enable session_save/restore triggers

### 4. Swarm Integration (orchestrator.py)

**Changes needed:**
- For Tier 3, spawn hive workers via hive-manager.js
- Collect results from parallel validators

## Integration Points

### execute-plan.md Integration

```markdown
## Post-Implementation Validation

After completing implementation:

1. Run Tier 1 validation:
   ```bash
   python3 ~/.claude/templates/validation/orchestrator.py 1
   ```

2. **If Tier 1 fails:**
   - DO NOT mark plan complete
   - Show failures
   - Suggest: "Run /gsd:plan-fix to address issues"

3. **If Tier 1 passes:**
   - Mark plan complete
   - Log result in SUMMARY.md
```

### verify-work.md Integration

```markdown
## Automated Validation (Before UAT)

1. Run Tier 1 (blockers):
   ```bash
   python3 ~/.claude/templates/validation/orchestrator.py 1
   ```
   - MUST pass to proceed

2. Run Tier 2 (warnings):
   ```bash
   python3 ~/.claude/templates/validation/orchestrator.py 2
   ```
   - Show to user for awareness

3. **If Tier 1 fails:** Skip UAT, go to /gsd:plan-fix

4. **If Tier 1 passes:** Proceed to conversational UAT
```

### complete-milestone.md Integration

```markdown
## Milestone Quality Gate

Before archiving milestone:

1. Run ALL tiers:
   ```bash
   python3 ~/.claude/templates/validation/orchestrator.py all
   ```

2. **Requirements:**
   - Tier 1: MUST be 100% pass
   - Tier 2: Documented exceptions allowed
   - Tier 3: Metrics recorded (non-blocking)

3. **If Tier 1 < 100%:**
   - Block milestone completion
   - List failing validators
   - Require fix or explicit override with reason
```

## Test Strategy

### Plan 16-01: GSD Workflow Integration
- 10 tests: execute-plan calls orchestrator
- 10 tests: verify-work shows tier results
- 5 tests: complete-milestone blocks on failures

### Plan 16-02: Agent & Swarm Activation
- 8 tests: agent spawn on Tier 2 failures
- 8 tests: swarm workers for Tier 3
- 4 tests: result collection and aggregation

### Plan 16-03: Session Checkpoint Integration
- 6 tests: session_save before phase
- 6 tests: session_restore on resume
- 4 tests: crash recovery simulation

### Plan 16-04: E2E Integration Tests
- 10 tests: full pipeline execute-plan → verify-work
- 5 tests: milestone completion with validation gate
- 5 tests: failure scenarios and recovery

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing GSD flows | Feature flag: `VALIDATION_ENABLED` env var |
| Slow validation blocking workflow | Async Tier 2/3, only Tier 1 sync |
| Agent spawn failures | Graceful fallback to manual suggestion |
| Swarm overhead | Only use for Tier 3 (>2 validators) |

## Success Criteria

- [ ] /gsd:execute-plan runs Tier 1 and blocks on failure
- [ ] /gsd:verify-work shows Tier 1+2 before UAT
- [ ] /gsd:complete-milestone enforces quality gate
- [ ] Agent spawn actually executes (not just logs)
- [ ] Tier 3 runs in parallel via swarm
- [ ] Session checkpoints enable crash recovery
- [ ] 80+ tests with 95%+ pass rate
