---
status: complete
phase: 23-hooks-webhooks
source: 23-01-SUMMARY.md, 23-02-SUMMARY.md
started: 2026-02-02T13:05:00Z
updated: 2026-02-02T13:08:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Validation-gate hook attivo
expected: `openclaw hooks list` mostra validation-gate come hook registrato
result: pass

### 2. Webhook endpoint risponde
expected: curl a webhooks.princyx.xyz restituisce codice HTTP (non timeout)
result: pass

### 3. HMAC validation funziona
expected: Signature invalida → 401. Log confermano signature valide → 202.
result: pass

### 4. Bot actor filtering
expected: Webhook con sender clawdbot[bot] viene ignorato
result: pass

### 5. ALLOWED_REPOS whitelist
expected: Webhook da repo non in whitelist silenziosamente ignorato
result: pass

### 6. GitHub App installata e funzionante
expected: App riceve eventi, ping arrivano a webhookd
result: pass

### 7. CF Tunnel webhooks.princyx.xyz attivo
expected: DNS risolve a Cloudflare, tunnel instrada a webhookd:8787
result: pass

### 8. webhookd systemd service attivo
expected: `systemctl is-active webhookd` restituisce "active"
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Issues for /gsd:plan-fix

[none]
