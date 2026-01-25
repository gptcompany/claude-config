# Phase 15: Skills Port - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<vision>
## How This Should Work

Skills are **enforcement infrastructure**, not documentation. When someone uses `/tdd:cycle`, it doesn't suggest writing tests — it blocks code changes until tests exist.

The core insight: guardrails beat guidance. A TDD skill that suggests tests is worthless. A TDD skill that blocks commits without tests changes behavior permanently.

Skills should ride the existing hook infrastructure (36 hooks, 497 tests). Not duplicate it. Enforcement happens at the tool boundary via PreToolUse/PostToolUse hooks.

The feel: When TDD workflow is active, the system itself prevents cutting corners. Not through prompts or reminders — through hard blocks. You literally cannot Write code without a failing test in RED phase.

</vision>

<essential>
## What Must Be Nailed

- **TDD-workflow as the anchor skill** — everything else benefits when code is test-driven. Fix the input, outputs fix themselves.
- **Hook-integrated enforcement** — skills enforce via hooks, not standalone CLI commands. PreToolUse blocks, PostToolUse validates.
- **Enforcement at tool boundary** — not suggestions, not CI-only, not prompt injection. Hard blocks when rules are violated.

</essential>

<specifics>
## Specific Ideas

**TDD-workflow phases (RED → GREEN → REFACTOR):**
- RED: Block Write/Edit tools for implementation files until a failing test exists
- GREEN: Block additional test creation until implementation makes tests pass
- REFACTOR: Suggest refactoring opportunities after green, optional enforcement

**Integration points:**
- `/tdd:cycle` skill triggers the workflow
- Existing hooks (PreToolUse, PostToolUse) provide enforcement
- State tracked in session (which phase we're in, what tests exist)

**Other skills (lower priority):**
- verification-loop: Run 6-phase sequential validation (already have 14-dim, this is a simplified path)
- coding-standards: Enforce via PreToolUse on Write/Edit (AST analysis)
- eval-harness: pass@k metrics on test runs

**What to ignore:**
- Documentation-first approach (gets ignored)
- Flexible opt-in enforcement (humans optimize for least resistance)
- CI-only enforcement (too late, bad patterns already committed)

</specifics>

<notes>
## Additional Context

**Power dynamics:**
- Leverage > effort: One anchor skill (TDD) that compounds into all other quality improvements
- Distribution > product: Skills ride existing hook infrastructure, instant distribution to all projects
- Speed > perfection: TDD-workflow first, other skills can follow

**The loser move:** Build 5 equal-priority skills with optional enforcement. Why it fails: no behavioral change, just more documentation nobody reads.

**The winner move:** Ship TDD-workflow with hard enforcement, prove it works, then port the rest knowing the enforcement pattern is solid.

</notes>

---

*Phase: 15-skills-port*
*Context gathered: 2026-01-25*
