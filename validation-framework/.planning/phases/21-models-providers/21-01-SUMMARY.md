# Plan 21-01: Multi-Model Provider Config — SUMMARY

**Status:** ✅ COMPLETE
**Date:** 2026-02-01

## What was built

1. **openclaw.json** — Updated with:
   - Fallback chain: `claude-opus-4-5` → `kimi-k2.5` (OpenRouter) → `gemini-2.5-pro` → `gpt-5.2`
   - Model aliases: `/opus`, `/kimi`, `/gemini`, `/gpt`
   - Auth profiles: 3 new (openrouter:default, google:default, openai:default) + 3 existing anthropic
   - Auth cooldowns: billingBackoff 5h, max 24h, failureWindow 24h
   - LLM Task plugin enabled
   - `llm_task` tool added to allow list

2. **docker-compose.yml** — Added env vars:
   - `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` (OPENAI_API_KEY already present)

## Verification passed

- [x] openclaw.json valid JSON
- [x] Fallback chain present
- [x] LLM Task plugin in allow list
- [x] All auth profiles present
- [x] Docker-compose valid YAML
- [x] All env vars in docker-compose
- [x] OPENROUTER_API_KEY exists in SOPS

## Human verification needed

1. SSH into muletto: `ssh 192.168.1.100`
2. Restart gateway: `cd /home/sam/moltbot-infra && docker compose up -d openclaw-gateway`
3. Run doctor: `docker exec openclaw-gateway node /app/dist/entry.js doctor`
4. Check providers listed
5. Test model alias in Bambam: `/kimi hello`
6. Check logs: `docker logs openclaw-gateway --tail 20`

## Files modified

- `/home/sam/moltbot-infra/clawdbot-config/openclaw.json` (muletto)
- `/home/sam/moltbot-infra/docker-compose.yml` (muletto)

## Backups

- `openclaw.json.bak-20260201-*`
- `docker-compose.yml.bak-20260201-*`
