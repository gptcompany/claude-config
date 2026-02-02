---
phase: 23-hooks-webhooks
plan: 01
status: completed
completed_at: 2026-02-02
---

# Plan 23-01 Summary: Validation-Gate Hook + Webhook Surface

## What Was Done

### Task 1: validation-gate hook
- Created `HOOK.md` + `handler.ts` in `/home/sam/moltbot-infra/clawdbot-config/hooks/validation-gate/` (mounted as `~/.openclaw/hooks/` in container)
- Hook triggers on `agent:bootstrap` events
- Injects `VALIDATION.md` into bootstrap files reminding agents to run tests before completing tasks
- Source: `openclaw-managed`

### Task 2: openclaw.json webhook surface + GitHub mapping
- Added `validation-gate: { enabled: true }` to `hooks.internal.entries`
- Enabled webhook surface: `hooks.enabled: true`, `hooks.path: "/hooks"`
- Generated webhook token (32-char hex) stored as `hooks.token`
- Added GitHub mapping: `match.path: "github"`, `action: "agent"`, `deliver: true`, `channel: "last"`
- **Note:** `hooks.mappings` requires array format (not object). `channel` accepts `"last"` (not platform names like `"matrix"`).

### Secrets
- `OPENCLAW_WEBHOOK_TOKEN` added to SOPS `/media/sam/1TB/.env.enc`

## Verification Results
- `openclaw doctor`: 0 config errors
- `openclaw hooks list`: 4/5 ready, validation-gate shown as `openclaw-managed`
- Webhook surface: 401 with wrong token, 400 with correct token (expected, no body)
- JSON valid
- Gateway healthy after restart

## Issues Encountered
1. **handler.ts shell escaping**: SSH heredoc with `!==` got escaped to `\!==`. Fixed by piping from local heredoc.
2. **hooks.mappings format**: Research said object format, but schema requires array. Fixed.
3. **channel field**: `"matrix"` is not a valid channel value. Used `"last"` instead (Matrix delivery will be handled by webhookd POST to `/hooks/agent` with explicit `channel`/`to` params).
