# Phase 15: Skills Port - Research

**Researched:** 2026-01-25
**Domain:** Enforcement-first skill system with hook integration
**Confidence:** HIGH

<research_summary>
## Summary

Researched the ECC skill system and our existing infrastructure to understand how to port enforcement-first skills that integrate with our hook system. Key finding: We already have significant infrastructure in place that ECC skills assume — the gap is enforcement orchestration, not primitive capabilities.

**What we have:**
- tdd-guard.js hook (PreToolUse on Write/Edit) with strict/warn/off modes
- /tdd:red, /tdd:green, /tdd:refactor, /tdd:cycle commands (but no enforcement)
- 36 hooks with PreToolUse blocking capability
- /validate skill for 14-dimension orchestrator

**What ECC has that we don't:**
- TDD workflow with session state tracking (which phase are we in?)
- Verification loop as sequential 6-phase execution
- Eval harness with pass@k metrics
- Coding standards skill with automated enforcement

**Primary recommendation:** Port ECC's TDD-workflow state machine, not just the prompts. The enforcement power comes from tracking session state (RED→GREEN→REFACTOR) and using PreToolUse hooks to block operations that violate the current phase.

</research_summary>

<standard_stack>
## Standard Stack

### Core (Already Exists)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| tdd-guard.js | Phase 14.5 | PreToolUse hook for TDD enforcement | ✅ Exists but needs state |
| hooks.json | Phase 14 | Hook configuration | ✅ Production |
| settings.json | - | Claude Code hooks binding | ✅ Production |
| /tdd:* commands | Current | TDD phase commands | ✅ Need enforcement |

### New Components Needed
| Component | Purpose | Priority |
|-----------|---------|----------|
| tdd-state.js | Track RED/GREEN/REFACTOR phase per session | P0 |
| tdd-enforcer.js | PreToolUse hook that checks state before blocking | P0 |
| verification-runner.js | Sequential 6-phase verification | P1 |
| eval-harness.js | pass@k metrics tracking | P2 |
| coding-standards.js | AST-based pattern enforcement | P2 |

### File Structure
```
~/.claude/scripts/hooks/skills/
├── tdd/
│   ├── tdd-state.js       # Session state management
│   ├── tdd-enforcer.js    # PreToolUse enforcement hook
│   └── tdd-state.test.js  # State management tests
├── verification/
│   ├── verification-runner.js  # 6-phase sequential runner
│   └── verification.test.js
└── eval/
    ├── eval-harness.js    # pass@k tracking
    └── eval.test.js
```

</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Session State Machine for TDD

**What:** Track TDD phase (IDLE, RED, GREEN, REFACTOR) in session state file
**When to use:** When enforcing multi-phase workflows where actions in phase N enable/disable actions in phase N+1
**Why it's critical:** Without state, hooks can only do stateless checks (file exists? test exists?). With state, hooks know "we're in RED phase, so block implementation writes"

**Implementation:**
```javascript
// ~/.claude/scripts/hooks/skills/tdd/tdd-state.js
const STATE_FILE = path.join(os.homedir(), '.claude', 'state', 'tdd-session.json');

const PHASES = {
  IDLE: 'IDLE',      // No active TDD workflow
  RED: 'RED',        // Writing failing tests
  GREEN: 'GREEN',    // Implementing to pass tests
  REFACTOR: 'REFACTOR', // Improving code with green tests
};

// Allowed tools per phase
const PHASE_RULES = {
  RED: {
    allowWrite: (file) => file.includes('test') || file.includes('spec'),
    blockReason: 'RED phase: Write tests first, not implementation code',
  },
  GREEN: {
    allowWrite: (file) => !file.includes('test') || !file.includes('spec'),
    blockReason: 'GREEN phase: Implement to pass tests, don\'t add more tests',
  },
  REFACTOR: {
    allowWrite: () => true, // All allowed in refactor
    requireTestsPass: true, // But must run tests after each edit
  },
};

function getState() {
  if (!fs.existsSync(STATE_FILE)) return { phase: PHASES.IDLE };
  return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
}

function setState(phase, testFile = null) {
  fs.writeFileSync(STATE_FILE, JSON.stringify({
    phase,
    startedAt: new Date().toISOString(),
    testFile,
    sessionId: process.env.CLAUDE_SESSION_ID,
  }));
}

function checkPhaseCompliance(filePath, toolName) {
  const state = getState();
  if (state.phase === PHASES.IDLE) return { allowed: true };

  const rules = PHASE_RULES[state.phase];
  if (!rules) return { allowed: true };

  if (toolName === 'Write' || toolName === 'Edit') {
    const allowed = rules.allowWrite(filePath);
    return {
      allowed,
      reason: allowed ? null : rules.blockReason,
    };
  }
  return { allowed: true };
}

module.exports = { getState, setState, checkPhaseCompliance, PHASES };
```

### Pattern 2: Skill Commands That Set State

**What:** /tdd:red command not just prompts, but also sets session state
**When to use:** When a command initiates an enforcement workflow
**Example:**

```markdown
<!-- ~/.claude/commands/tdd/red.md (updated) -->
# TDD Red Phase Command

## Pre-Execution Hook
\`\`\`json
{"set_tdd_state": "RED"}
\`\`\`

## Process
1. Set TDD state to RED (enforcement activated)
2. Write failing tests
3. Verify tests fail
4. Transition to GREEN: /tdd:green

## Enforcement
While in RED phase, Write/Edit to implementation files is **blocked**.
Only test files can be written.
```

### Pattern 3: PreToolUse Enforcement Hook

**What:** Hook that reads session state and blocks non-compliant actions
**Implementation:**
```javascript
// ~/.claude/scripts/hooks/skills/tdd/tdd-enforcer.js
async function main() {
  const input = await readStdinJson();
  const { tool_name, tool_input } = input;

  if (!['Write', 'Edit', 'MultiEdit'].includes(tool_name)) {
    return { decision: 'allow' };
  }

  const { allowed, reason } = checkPhaseCompliance(tool_input.file_path, tool_name);

  if (!allowed) {
    return {
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        decision: 'block',
        reason: `TDD ENFORCEMENT: ${reason}\n\nCurrent phase: ${getState().phase}\nTo exit TDD mode: /tdd:exit`,
      },
    };
  }

  return { decision: 'allow' };
}
```

### Pattern 4: Verification Loop as Sequential Runner

**What:** 6-phase verification that runs in order, each gate must pass
**ECC's phases:**
1. Build — `npm run build`
2. TypeCheck — `tsc --noEmit`
3. Lint — `npm run lint`
4. Test — `npm test`
5. Security — secret scan, dependency audit
6. Diff — git diff review

**Implementation pattern:**
```javascript
// ~/.claude/scripts/hooks/skills/verification/verification-runner.js
const PHASES = [
  { name: 'build', cmd: 'npm run build', failFast: true },
  { name: 'typecheck', cmd: 'npx tsc --noEmit', failFast: true },
  { name: 'lint', cmd: 'npm run lint', failFast: false },
  { name: 'test', cmd: 'npm test', failFast: true },
  { name: 'security', cmd: 'npm audit', failFast: false },
  { name: 'diff', cmd: 'git diff --stat', failFast: false },
];

async function runVerificationLoop() {
  const results = [];
  for (const phase of PHASES) {
    const result = await runPhase(phase);
    results.push(result);
    if (!result.passed && phase.failFast) {
      return { status: 'BLOCKED', failedAt: phase.name, results };
    }
  }
  return { status: 'READY', results };
}
```

### Anti-Patterns to Avoid

- **Stateless enforcement:** Without session state, you can only check "does test exist?" not "are we in a phase where tests should be written?"
- **Commands without state transitions:** If /tdd:red just outputs prompts without setting state, no enforcement happens
- **Global state files:** Use session-scoped state (`CLAUDE_SESSION_ID`) to avoid cross-session contamination
- **Blocking without escape hatch:** Always provide `/tdd:exit` to break out of stuck states

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TDD phase tracking | Custom phase tracking logic | Existing tdd-guard.js + state file | Already has file detection, just needs state |
| Verification phases | Custom sequential runner | Existing ci-autofix.js patterns | Already handles npm/build/test orchestration |
| Pass@k metrics | Custom tracking | QuestDB + existing metrics.js | Already have metrics infrastructure |
| AST analysis | Custom parser | ESLint + existing patterns | ESLint already does this, use as subprocess |
| Secret scanning | Custom regex | git-safety-check.js patterns | Already detects secrets |

**Key insight:** We're not building enforcement from scratch. We have 36 hooks with full PreToolUse blocking capability. The port is about:
1. Adding session state tracking
2. Connecting commands to state transitions
3. Connecting state to existing hook blocking

</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: State Corruption on Crash
**What goes wrong:** Claude crashes mid-session, state file shows "RED" but there's no active TDD session
**Why it happens:** State persists across sessions without cleanup
**How to avoid:**
- Include session ID in state file
- Check session ID on state read — if mismatch, reset to IDLE
- Add TTL (e.g., state expires after 2 hours)
**Warning signs:** Users reporting stuck TDD mode

### Pitfall 2: Over-Enforcement Breaks Workflow
**What goes wrong:** Blocks legitimate operations (e.g., blocking conftest.py in RED phase)
**Why it happens:** Too strict file detection
**How to avoid:**
- Whitelist patterns: test files, fixtures, conftest, setup.py
- Allow config files always
- Provide `/tdd:override` for edge cases
**Warning signs:** Users constantly using override or disabling

### Pitfall 3: Skill Commands Without Hook Binding
**What goes wrong:** /tdd:red sets state but nothing reads it
**Why it happens:** Forgot to add tdd-enforcer.js to hooks.json
**How to avoid:**
- Atomic change: state file + hook binding together
- Integration test that verifies blocking works
**Warning signs:** Tests pass but enforcement doesn't happen

### Pitfall 4: No Visibility Into Current State
**What goes wrong:** User doesn't know why their write was blocked
**Why it happens:** Block message doesn't explain state
**How to avoid:**
- Rich block messages: current phase, what's allowed, how to exit
- Add `/tdd:status` command to show state
**Warning signs:** User confusion about blocks

</common_pitfalls>

<code_examples>
## Code Examples

### TDD State Management (from our existing patterns)
```javascript
// Source: Adapted from ~/.claude/scripts/hooks/productivity/tdd-guard.js
const STATE_PATH = path.join(os.homedir(), '.claude', 'state', 'tdd-session.json');

function ensureStateDir() {
  const dir = path.dirname(STATE_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function getState() {
  ensureStateDir();
  if (!fs.existsSync(STATE_PATH)) {
    return { phase: 'IDLE', sessionId: null };
  }
  try {
    const state = JSON.parse(fs.readFileSync(STATE_PATH, 'utf8'));
    // Session check — if different session, reset
    if (state.sessionId !== process.env.CLAUDE_SESSION_ID) {
      return { phase: 'IDLE', sessionId: null };
    }
    return state;
  } catch {
    return { phase: 'IDLE', sessionId: null };
  }
}

function setState(phase) {
  ensureStateDir();
  const state = {
    phase,
    sessionId: process.env.CLAUDE_SESSION_ID,
    startedAt: new Date().toISOString(),
  };
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  return state;
}
```

### Command That Sets State (pseudo-code for command)
```markdown
<!-- ~/.claude/commands/tdd/red.md -->
# TDD Red Phase

## On Invocation
Run: `node ~/.claude/scripts/hooks/skills/tdd/set-state.js RED`

## Instructions
You are now in TDD RED phase. Your task is to write **failing tests**.

Rules:
- ONLY write test files (*.test.js, *.spec.ts, test_*.py)
- Implementation files will be BLOCKED
- Tests MUST fail (verify with test runner)

When ready for implementation, use `/tdd:green`.
```

### Verification Loop Runner
```javascript
// Source: Adapted from ci-autofix.js patterns
const { execSync } = require('child_process');

const PHASES = [
  { name: 'build', cmd: 'npm run build 2>&1', failFast: true },
  { name: 'typecheck', cmd: 'npx tsc --noEmit 2>&1', failFast: true },
  { name: 'lint', cmd: 'npm run lint 2>&1 | head -30', failFast: false },
  { name: 'test', cmd: 'npm test -- --coverage 2>&1 | tail -50', failFast: true },
  { name: 'security', cmd: 'npm audit 2>&1 | head -20', failFast: false },
  { name: 'diff', cmd: 'git diff --stat', failFast: false },
];

function runPhase(phase) {
  try {
    const output = execSync(phase.cmd, {
      encoding: 'utf8',
      timeout: 60000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { name: phase.name, passed: true, output };
  } catch (err) {
    return { name: phase.name, passed: false, output: err.stdout || err.message };
  }
}

async function runVerificationLoop() {
  const results = [];
  for (const phase of PHASES) {
    const result = runPhase(phase);
    results.push(result);
    console.error(`[${result.passed ? 'PASS' : 'FAIL'}] ${phase.name}`);
    if (!result.passed && phase.failFast) {
      return { status: 'BLOCKED', failedAt: phase.name, results };
    }
  }
  return { status: 'READY', results };
}
```

</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt-only TDD guidance | Hook-enforced TDD with state | Phase 15 | Real enforcement vs suggestions |
| CLI-only verification | Hook-integrated verification | Phase 11-12 | Automatic, not manual invocation |
| Manual pass@k tracking | Automated QuestDB metrics | Phase 14.5 | Historical tracking, dashboards |

**New patterns to consider:**
- **Pre-commit hooks for TDD state:** Reset state on commit to prevent cross-commit confusion
- **PostToolUse phase advancement:** Automatically advance from RED→GREEN when test runner shows failures

**Deprecated/outdated:**
- **Python hooks:** All hooks are Node.js now (Phase 14)
- **Manual tdd-config.json editing:** Should use `/tdd:config` command

</sota_updates>

<open_questions>
## Open Questions

1. **Phase advancement automation**
   - What we know: /tdd:red, /tdd:green, /tdd:refactor commands exist
   - What's unclear: Should phases advance automatically based on test results?
   - Recommendation: Start with manual phase transitions, add automation in Phase 16 if needed

2. **Multi-file TDD tracking**
   - What we know: Single file TDD tracking is clear
   - What's unclear: When implementing a feature that spans multiple files, how to track "which test file covers which implementation file"?
   - Recommendation: For Phase 15, track at session level (not file level). Revisit for Phase 16.

3. **Eval harness scope**
   - What we know: ECC's eval harness tracks pass@k
   - What's unclear: Do we need eval definitions stored in .claude/evals/ or is our test suite sufficient?
   - Recommendation: Defer eval harness to Plan 15-04, focus on TDD and verification first

</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `/media/sam/1TB/everything-claude-code/skills/tdd-workflow/SKILL.md` — ECC TDD skill structure
- `/media/sam/1TB/everything-claude-code/skills/verification-loop/SKILL.md` — ECC verification phases
- `/media/sam/1TB/everything-claude-code/commands/tdd.md` — ECC TDD command implementation
- `~/.claude/scripts/hooks/productivity/tdd-guard.js` — Our existing TDD hook (383 LOC)
- `~/.claude/settings.json` — Current hooks configuration

### Secondary (MEDIUM confidence)
- `~/.claude/commands/tdd/*.md` — Our existing TDD commands (need enhancement)
- `/media/sam/1TB/everything-claude-code/skills/eval-harness/SKILL.md` — ECC eval harness patterns

### Tertiary (LOW confidence - needs validation)
- None — all findings verified against source code

</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Claude Code hooks, skill system, session state
- Ecosystem: Node.js hooks, JSON state files, command files
- Patterns: State machine, PreToolUse blocking, sequential verification
- Pitfalls: State corruption, over-enforcement, missing bindings

**Confidence breakdown:**
- Standard stack: HIGH — verified against existing codebase
- Architecture: HIGH — patterns proven in existing hooks
- Pitfalls: HIGH — derived from existing hook development experience
- Code examples: HIGH — adapted from production hooks

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days — stable internal infrastructure)

</metadata>

---

*Phase: 15-skills-port*
*Research completed: 2026-01-25*
*Ready for planning: yes*
