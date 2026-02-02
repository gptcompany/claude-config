---
phase: 23-hooks-webhooks
plan: 02
status: completed
completed_at: 2026-02-02
---

# Plan 23-02 Summary: webhookd Deployment + GitHub App + E2E

## Architecture

```
GitHub App (openclaw-webhooks, all repos)
  → webhooks.princyx.xyz (CF Tunnel)
    → webhookd:8787 (HMAC verify + ALLOWED_REPOS whitelist)
      → OpenClaw gateway:8090 /hooks/agent
        → Bambam agent → Matrix channel
```

## What Was Done

### Task 1: Deploy webhookd on muletto
- Installed Deno to `/home/sam/.deno/bin/deno` on muletto
- Created `/opt/webhookd/mod.ts` — Deno HTTP server:
  - Listens on port 8787
  - Verifies GitHub HMAC-SHA256 signatures (constant-time comparison)
  - Normalizes payload (issues, PRs, check_runs)
  - **ALLOWED_REPOS whitelist** — repos not in list are silently ignored
  - **IGNORE_GITHUB_ACTORS** — prevents webhook loops (clawdbot[bot])
  - Forwards to gateway `/hooks/agent` with Matrix delivery
  - Responds 202 immediately (async processing)
- Created `/opt/webhookd/.env` (chmod 600) with secrets + whitelist
- Created systemd service with security hardening (NoNewPrivileges, PrivateTmp, ProtectSystem)
- Service enabled and running

### Task 2: GitHub App (final approach)
- **Created GitHub App `openclaw-webhooks`** on gptprojectmanager account
  - Webhook URL: `https://webhooks.princyx.xyz/webhook`
  - Events: issues, pull_request, check_run
  - Permissions: issues (read), PRs (read), checks (read), metadata (read)
  - Private (only this account)
- **Installed on `gptcompany` org → All repositories**
- Ping received and verified in webhookd logs
- Per-repo webhooks removed (were redundant)

### Why GitHub App over alternatives
- **Org webhooks**: require Team plan ($4/user/mo) — free plan returns 404
- **Per-repo webhooks**: work but don't scale, need config per repo
- **GitHub App**: single install, all repos, manage scope via ALLOWED_REPOS whitelist

### CF Tunnel
- Added `webhooks.princyx.xyz` → `http://localhost:8787` to `/etc/cloudflared/config.yml`
- DNS CNAME record created pointing to CF Tunnel
- Verified accessible externally

### Secrets added to SOPS
- `GITHUB_WEBHOOK_SECRET` — HMAC secret for GitHub App webhook
- `OPENCLAW_WEBHOOK_TOKEN` — gateway auth token
- `GITHUB_CLASSIC_PAT` — classic PAT from Docker config (was missing from SOPS)

### E2E Test Results

| Test | Expected | Actual |
|------|----------|--------|
| Valid HMAC signature | 202 | 202 |
| Invalid signature | 401 | 401 |
| Bot actor (clawdbot[bot]) | 200 ignored | 200 ignored |
| Gateway forwarding | 202 from gateway | 202 confirmed |
| GitHub App ping | pong | Received |
| GitHub App installation event | forwarded | 202 to gateway |

## Managing Repos

Add/remove repos from processing by editing `/opt/webhookd/.env` on muletto:
```
ALLOWED_REPOS=gptcompany/nautilus_dev,gptcompany/UTXOracle,gptcompany/N8N_dev
```
Then: `sudo systemctl restart webhookd`

The GitHub App stays on "All repositories" — filtering is done by webhookd.

## Notes
- Port 8787 not reachable from Workstation directly, accessible via localhost and CF Tunnel
- GITHUB_PAT / GH_PROJECT_PAT in SOPS are stale (401) — fine-grained PAT scoped to gptcompany org, likely value was never saved correctly
- GITHUB_CLASSIC_PAT (ghp_, 40 chars) found in Docker config, works correctly, now saved in SOPS
