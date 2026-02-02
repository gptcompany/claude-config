# Phase 23: Hooks & Webhooks - Research

**Researched:** 2026-02-02
**Domain:** OpenClaw hooks system, webhook receivers, GitHub→agent triggers, Matrix escalation
**Confidence:** HIGH

<research_summary>
## Summary

Ricerca approfondita sul sistema hooks/webhooks di OpenClaw per Phase 23. Il sistema è maturo e ben documentato con due superfici distinte: **hooks interni** (event-driven TypeScript handlers nel gateway) e **webhook HTTP** (endpoint REST per trigger esterni).

L'architettura attuale ha già 3 hooks interni attivi (session-memory, command-logger, boot-md). La fase deve aggiungere: hook custom pre/post validation, webhook endpoint per GitHub events, e escalation su Matrix.

**Primary recommendation:** Usare il sistema hooks nativo di OpenClaw (HOOK.md + handler.ts) per hooks interni, il built-in `/hooks/agent` endpoint per webhook GitHub (con webhookd come receiver/verifier), e il canale Matrix esistente per escalation via `deliver` + `channel: matrix`.
</research_summary>

<standard_stack>
## Standard Stack

### Core (Built-in OpenClaw)
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| OpenClaw hooks system | v2026.1.x | Event-driven hooks interni | Nativo, discovery automatica, lifecycle gestito |
| OpenClaw webhook surface | v2026.1.x | HTTP endpoints `/hooks/*` | Built-in nel gateway, auth inclusa |
| webhookd | Deno 2.x | GitHub webhook receiver/verifier | Progetto ufficiale community, HMAC-SHA256 verification |

### Supporting
| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| Cloudflare Tunnel | Esistente | Espone webhook endpoint publicamente | GitHub deve raggiungere webhookd dietro NAT |
| Matrix channel | Esistente | Escalation/notifiche | `deliver: true, channel: matrix` nel webhook payload |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| webhookd (Deno) | Custom Node.js receiver | webhookd è già pronto, testato, minimal |
| CF Tunnel per webhook | Tailscale Funnel | CF Tunnel già configurato nella nostra infra |
| Matrix escalation | Discord webhook | Matrix è il canale nativo di Bambam |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Custom Hook (HOOK.md + handler.ts)

**What:** Hook custom che si triggera su eventi agent/command
**When to use:** Pre/post validation execution, audit logging
**Structure:**
```
~/.openclaw/hooks/validation-gate/
├── HOOK.md          # Metadata + events
└── handler.ts       # TypeScript handler
```

**HOOK.md format:**
```markdown
---
name: validation-gate
description: "Pre/post validation hooks for quality gates"
metadata:
  openclaw:
    emoji: "✅"
    events: ["command:new", "agent:bootstrap"]
    export: "default"
    requires:
      bins: ["python3"]
      config: ["workspace.dir"]
      os: ["linux"]
    always: false
---
```

**handler.ts:**
```typescript
import type { HookHandler } from "../../src/hooks/hooks.js";

const handler: HookHandler = async (event) => {
  if (event.type !== "command") return;
  // validation logic
  event.messages.push("✅ Validation gate passed");
};
export default handler;
```

### Pattern 2: GitHub → Agent via Webhook

**What:** GitHub event → webhookd (verifica HMAC) → OpenClaw `/hooks/agent` → agent esegue azione
**When to use:** Issue opened, PR review requested, CI failure
**Flow:**
```
GitHub webhook → CF Tunnel → webhookd:8787/webhook
  → verify HMAC-SHA256
  → normalize payload
  → POST gateway:8090/hooks/agent
    { message: "GitHub: new issue #123...", name: "GitHub", deliver: true, channel: "matrix" }
  → agent processes + replies to Matrix
```

### Pattern 3: Escalation su Matrix

**What:** Webhook `/hooks/agent` con `deliver: true, channel: "matrix"` per routing risposte
**When to use:** Qualsiasi trigger esterno che richiede notifica/azione umana
**Example:**
```bash
curl -X POST http://127.0.0.1:8090/hooks/agent \
  -H 'x-openclaw-token: <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "CI pipeline failed on main branch. Analyze and suggest fix.",
    "name": "CI-Alert",
    "deliver": true,
    "channel": "matrix",
    "to": "!GQeiGgJenxtCKbaxDL:matrix.lan",
    "model": "anthropic/claude-sonnet-4-20250514",
    "thinking": "medium",
    "timeoutSeconds": 300
  }'
```

### Anti-Patterns to Avoid
- **Hook handlers lenti/bloccanti:** Usare fire-and-forget per operazioni lunghe
- **Webhook senza HMAC verification:** MAI accettare GitHub payload senza verifica firma
- **Business logic dentro webhookd:** webhookd è solo verifier+forwarder, la logica va nell'agent
- **Token webhook in query params:** Usare header Authorization, query params deprecati
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub webhook verification | Custom HMAC logic | webhookd built-in HMAC-SHA256 | Edge cases: timing attacks, encoding, replay |
| Hook discovery/lifecycle | Custom hook loader | OpenClaw hook system (HOOK.md scan) | Handles precedence, eligibility, enable/disable |
| Webhook auth | Custom token middleware | Gateway built-in `hooks.token` auth | Three methods supported, already hardened |
| Agent trigger da webhook | Custom REST→agent bridge | `/hooks/agent` endpoint | Handles async exec, delivery, model override |
| Matrix message delivery | Direct Matrix API calls | `deliver: true, channel: "matrix"` | Gateway gestisce sessioni, formatting, retry |

**Key insight:** OpenClaw ha già TUTTE le primitive necessarie. Non serve costruire middleware custom. Il gateway ha webhook endpoint nativi con auth, agent triggering, e delivery a canali. webhookd è il receiver ufficiale per GitHub.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Webhook Loop
**What goes wrong:** Agent risponde su GitHub → trigger nuovo webhook → loop infinito
**Why it happens:** GitHub webhook triggera su tutti gli eventi, incluse le risposte del bot
**How to avoid:** `IGNORE_GITHUB_ACTORS` in webhookd .env con username del bot; signature text coerente per detect bot replies
**Warning signs:** Risposte duplicate, crescita esponenziale di messaggi

### Pitfall 2: Hook Non Eligible
**What goes wrong:** Hook custom non viene caricato/eseguito
**Why it happens:** Missing binary, env var, o config path nel `requires` di HOOK.md
**How to avoid:** `openclaw hooks check` per verificare eligibility; `openclaw hooks list --eligible`; testare requirements prima
**Warning signs:** Hook appare in `hooks list` ma non in `hooks list --eligible`

### Pitfall 3: Webhook Timeout
**What goes wrong:** Agent task troppo lungo, GitHub retry, duplicati
**Why it happens:** GitHub fa retry dopo 10s timeout; agent tasks possono durare minuti
**How to avoid:** Webhook endpoint risponde 202 subito (async); `timeoutSeconds` nel payload agent; idempotency via `sessionKey`
**Warning signs:** Log con "duplicate webhook", risposte multiple allo stesso evento

### Pitfall 4: Payload Safety Wrapping
**What goes wrong:** Contenuto webhook trattato come untrusted, wrappato con safety boundaries
**Why it happens:** Default security behavior di OpenClaw — corretto per input esterni
**How to avoid:** Per source interne fidate si può usare `allowUnsafeExternalContent: true` (solo per sorgenti verificate)
**Warning signs:** Agent non riesce a processare payload complessi; risposte generiche
</common_pitfalls>

<code_examples>
## Code Examples

### 1. Custom Validation Hook

```typescript
// Source: OpenClaw hooks docs pattern
// File: ~/.openclaw/hooks/validation-gate/handler.ts

import type { HookHandler } from "../../src/hooks/hooks.js";

const handler: HookHandler = async (event) => {
  if (event.type !== "agent" || event.action !== "bootstrap") return;

  const workspaceDir = event.context.workspaceDir;
  if (!workspaceDir) return;

  // Inject validation reminder into bootstrap
  event.context.bootstrapFiles?.push({
    path: "VALIDATION.md",
    content: `# Validation Gate Active\n\nBefore completing any task:\n1. Run tests\n2. Check validation score\n3. Report metrics`,
  });

  event.messages.push("✅ Validation gate injected into session");
};

export default handler;
```

### 2. OpenClaw Config per Hooks + Webhooks

```json5
{
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "session-memory": { "enabled": true },
        "command-logger": { "enabled": true },
        "boot-md": { "enabled": true },
        "validation-gate": { "enabled": true }
      },
      "load": {
        "extraDirs": ["/home/node/clawd/hooks"]
      }
    },
    // Webhook surface
    "enabled": true,
    "token": "shared-secret-for-webhooks",
    "path": "/hooks",
    "presets": ["gmail"],
    "mappings": {
      "github": {
        "match": { "source": "github" },
        "action": "agent",
        "deliver": true,
        "channel": "matrix",
        "to": "!GQeiGgJenxtCKbaxDL:matrix.lan"
      }
    }
  }
}
```

### 3. GitHub Webhook → Agent Trigger (curl)

```bash
# Source: OpenClaw webhook docs
# Direct trigger without webhookd (for testing)
curl -X POST http://192.168.1.100:8090/hooks/agent \
  -H 'x-openclaw-token: <gateway-token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "New GitHub issue: Fix login timeout #456\n\nLabels: bug, priority-high\nBody: Users report login timing out after 30s...",
    "name": "GitHub",
    "sessionKey": "github-issue-456",
    "deliver": true,
    "channel": "matrix",
    "to": "!GQeiGgJenxtCKbaxDL:matrix.lan",
    "thinking": "medium",
    "timeoutSeconds": 300
  }'
```

### 4. webhookd systemd Service

```ini
# Source: webhookd DEPLOY.md
# File: /etc/systemd/system/webhookd.service
[Unit]
Description=webhookd (GitHub webhook → OpenClaw)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/webhookd
ExecStart=/usr/bin/deno run -A --env-file=.env mod.ts
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict

[Install]
WantedBy=multi-user.target
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `openclaw hooks` (webhook mgmt) | `openclaw webhooks` (renamed) | v2026.1.x | CLI command rename, breaking |
| Query param token auth | Header auth (Bearer/x-openclaw-token) | v2026.1.x | Query params deprecated |
| Gateway auth optional ("none" mode) | Auth mandatory (token/password/Tailscale) | v2026.1.x | Security hardening |
| Raw webhook payload | Safety-wrapped content (default) | v2026.1.x | Per-hook opt-out con `allowUnsafeExternalContent` |
| Custom webhook receivers | webhookd official Deno receiver | 2025-2026 | Standardizzato, HMAC built-in |

**New tools/patterns:**
- **Hook Packs (npm):** Distribuire hooks come npm packages con `openclaw hooks install`
- **Plugin Hooks:** Hooks bundled dentro plugins, gestiti dal plugin lifecycle
- **`hooks.mappings`:** Custom routing declarativo per webhook payload diversi
- **`hooks.transformsDir`:** Custom JS/TS transforms per normalizzare payload

**Deprecated/outdated:**
- `hooks.internal.handlers[]` array format → usare `hooks.internal.entries{}` object format
- Token in query params → usare header auth
- `gateway.auth.mode: "none"` → rimosso, auth obbligatoria
</sota_updates>

<open_questions>
## Open Questions

1. **Hook execution order con validation gate**
   - What we know: Hooks registrati per evento eseguono tutti, ma ordine non garantito
   - What's unclear: Se serve ordering esplicito pre→post validation
   - Recommendation: Testare con hook semplice, verificare se ordine naturale (discovery order) è sufficiente

2. **webhookd deployment location**
   - What we know: Deve stare raggiungibile da GitHub; può girare su muletto (stessa macchina del gateway)
   - What's unclear: Se deployare dentro stesso container o come servizio separato
   - Recommendation: Servizio systemd separato su muletto, CF Tunnel per expose pubblico

3. **Webhook token vs Gateway token**
   - What we know: `hooks.token` per webhook auth è separato da `gateway.auth.token`
   - What's unclear: Se conviene usare stesso token o tokens diversi
   - Recommendation: Tokens diversi per separation of concerns (webhook token meno privilegiato)
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [OpenClaw Hooks Docs](https://docs.openclaw.ai/hooks.md) — Hook types, HOOK.md format, handler API, lifecycle, config
- [OpenClaw Webhook Docs](https://docs.openclaw.ai/automation/webhook) — Webhook endpoints, auth, /hooks/agent, /hooks/wake
- [OpenClaw CLI Hooks](https://docs.openclaw.ai/cli/hooks.md) — CLI commands per hook management
- [webhookd DEPLOY.md](https://github.com/Rabithua/openclaw/blob/master/services/webhookd/DEPLOY.md) — GitHub webhook receiver setup

### Secondary (MEDIUM confidence)
- [OpenClaw Gateway Config](https://docs.openclaw.ai/gateway/configuration) — Config structure verificata con nostra istanza reale
- Gateway config live (`/home/node/.openclaw/openclaw.json`) — Verificato via SSH+docker exec

### Tertiary (LOW confidence)
- Nessuna — tutti i findings verificati con docs ufficiali o config live
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw hooks system (internal + webhook)
- Ecosystem: webhookd, GitHub webhooks, Matrix channel delivery
- Patterns: HOOK.md + handler.ts, webhook→agent trigger, escalation
- Pitfalls: Loops, eligibility, timeouts, safety wrapping

**Confidence breakdown:**
- Standard stack: HIGH — documentazione ufficiale + config live verificata
- Architecture: HIGH — pattern documentati con esempi funzionanti
- Pitfalls: HIGH — documentati in docs ufficiali e community
- Code examples: HIGH — da docs ufficiali, verificati con API reale

**Research date:** 2026-02-02
**Valid until:** 2026-03-04 (30 days — OpenClaw hooks system stabile)
</metadata>

---

*Phase: 23-hooks-webhooks*
*Research completed: 2026-02-02*
*Ready for planning: yes*
