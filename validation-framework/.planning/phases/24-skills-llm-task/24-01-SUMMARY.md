---
phase: 24-skills-llm-task
plan: 01
status: completed
completed_at: 2026-02-02
---

# Phase 24-01 Summary: Skills & LLM Task

## What Was Done

### Task 1: llm-task plugin config + TDD-cycle skill
- **llm-task plugin**: `{"enabled": true}` — plugin only accepts `enabled` flag. Model routing is configured in `agents.defaults.model` (Phase 21).
- **Verified model chain** (from `config get agents.defaults.model`):
  - Primary: `anthropic/claude-opus-4-5` (alias: opus)
  - Fallback 1: `openrouter/moonshotai/kimi-k2.5` (alias: kimi)
  - Fallback 2: `google/gemini-2.5-pro` (alias: gemini)
  - Fallback 3: `openai/gpt-5.2` (alias: gpt)
- **TDD-cycle skill** created at workspace `skills/tdd-cycle/SKILL.md` — no gating (exec runs on Workstation node, not container).

### Task 2: Lobster CLI + validate-review skill
- **Lobster CLI**: Cloned from `github.com/openclaw/lobster`, built with tsc, mounted as volume in gateway container.
  - Repo: `/home/sam/moltbot-infra/lobster-cli/`
  - Binary: `/home/sam/moltbot-infra/gateway-bin/lobster` (wrapper → `node /opt/lobster/bin/lobster.js`)
  - Volume mounts in docker-compose.yml:
    - `./lobster-cli:/opt/lobster:ro`
    - `./gateway-bin/lobster:/usr/local/bin/lobster:ro`
  - Added `lobster` to `tools.alsoAllow` in openclaw.json
- **Lobster plugin**: Bundled at `/app/extensions/lobster/index.ts`, enabled via `plugins.entries.lobster.enabled: true` + `plugins.allow`. Plugin spawns `lobster` CLI and parses JSON envelope.
- **validate-review skill** created with cross-model review chain (Kimi K2.5 → Gemini → GPT-5.2, excluding Claude for anti-self-review).

### Task 3: Claude Code delegation
- **claude stub**: `/home/sam/moltbot-infra/gateway-bin/claude` mounted at `/usr/local/bin/claude:ro` — satisfies `coding-agent` bundled skill gating (`anyBins: ["claude"]`).
- **claude-code workspace skill** created — delegates to Claude Code on Workstation via `exec host=node`.
- Note: Both skills appear in `skills list` as ready but are excluded from agent system prompt due to `bootstrapMaxChars: 20000` budget. Agent can still use `exec` directly for Claude Code delegation.

### Task 4: Verification
- `openclaw doctor`: Config valid, **3 plugins loaded** (matrix, llm-task, lobster), 0 errors
- `skills list`: **11/52 ready** (was 7/49)
- Agent tools: **22 tools** including `lobster` and `llm-task`
- Agent skills: **9 skills** in system prompt (budget-limited from 11 ready)
- Lobster tool tested: agent invoked it successfully
- validate-review tested: Kimi K2.5 cross-model review returned score 65/100
- Gateway logs: Clean, no errors

## Infrastructure Changes

### docker-compose.yml (muletto)
Added 3 volume mounts to openclaw-gateway service:
```yaml
- ./lobster-cli:/opt/lobster:ro          # Lobster CLI source + built JS
- ./gateway-bin/lobster:/usr/local/bin/lobster:ro  # Wrapper script
- ./gateway-bin/claude:/usr/local/bin/claude:ro    # Stub for skill gating
```

### New directories on muletto
- `/home/sam/moltbot-infra/lobster-cli/` — Lobster CLI repo (git clone)
- `/home/sam/moltbot-infra/gateway-bin/` — Wrapper scripts for container PATH

### openclaw.json changes
- `plugins.entries.lobster.enabled: true`
- `plugins.allow: ["matrix", "llm-task", "lobster"]`
- `tools.alsoAllow: ["llm-task", "lobster"]`
- `skills.entries.tdd-cycle.enabled: true`
- `skills.entries.validate-review.enabled: true`
- `skills.entries.coding-agent.enabled: true`
- `skills.entries.claude-code.enabled: true`

## Deviations from Plan

| Planned | Actual | Reason |
|---------|--------|--------|
| llm-task with defaultProvider/allowedModels | Only `enabled: true` | Runtime schema rejects extra keys |
| Install lobster via `npm install -g` | Clone repo + build + volume mount | Lobster CLI is a separate repo, not published on npm |
| Research said GPT-5.2 as primary fallback | Kimi K2.5 (OpenRouter) as 1st fallback | Verified from live config |
| Lobster binary in container PATH | Volume mount wrapper script | Container filesystem is ephemeral |

## Metrics

- Files modified: 2 (openclaw.json, docker-compose.yml)
- Files created: 4 (tdd-cycle/SKILL.md, validate-review/SKILL.md, claude-code/SKILL.md, gateway-bin/*)
- Repos cloned: 1 (lobster-cli)
- Skills ready: 7 → 11/52
- Plugins loaded: 2 → 3 (added lobster)
- Agent tools: 21 → 22 (added lobster)
- Config errors: 0
