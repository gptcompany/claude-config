# Phase 14: Hooks Node.js Port - Context

**Gathered:** 2026-01-24
**Status:** Ready for research

<vision>
## How This Should Work

Fresh architecture opportunity — not just porting existing hooks but redesigning the hook system properly. Follow ECC (everything-claude-code) patterns as the reference implementation.

The new system should feel like ECC's hooks: well-structured, Node.js-based, with clear conventions. This is a chance to do it right, not just translate Bash scripts to JavaScript.

</vision>

<essential>
## What Must Be Nailed

All four pillars equally important:

- **Cross-platform reliability** — Works identically on Linux, macOS, Windows without path/shell issues
- **Easy configuration** — Non-developers can enable/disable hooks without touching code
- **Performance** — Hooks execute fast, don't slow down Claude Code workflow
- **Extensibility** — Easy to add new hooks, customize behavior per project

</essential>

<specifics>
## Specific Ideas

- Use ECC hooks as the reference implementation to port from
- Node.js for cross-platform reliability (no shell compatibility issues)
- Declarative configuration (hooks.json or similar)
- Modular design where hooks can be enabled/disabled per project

</specifics>

<notes>
## Additional Context

This is Phase 14 of v4.0 milestone, following ECC Full Integration (Phase 13). The goal is to modernize the hook infrastructure that currently uses a mix of Bash and Python scripts.

Reference: `/media/sam/1TB/everything-claude-code/` for ECC patterns.

</notes>

---

*Phase: 14-hooks-nodejs-port*
*Context gathered: 2026-01-24*
