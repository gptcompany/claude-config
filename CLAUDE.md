# Global Claude Instructions

## Plan Mode Before Implementation

**Prima di implementare qualsiasi richiesta non banale:**

1. **Valuta la complessità** della richiesta dell'utente
2. **Se la richiesta richiede**:
   - Modifiche a più file
   - Decisioni architetturali
   - Nuove funzionalità
   - Refactoring significativo

   → **Entra in Plan Mode** (`EnterPlanMode`) per pianificare gli step necessari

3. **In Plan Mode**:
   - Esplora il codebase per capire il contesto
   - Identifica i file da modificare
   - Definisci gli step di implementazione
   - Presenta il piano all'utente per approvazione
   - Solo dopo approvazione, procedi con l'implementazione

4. **Eccezioni** (non serve Plan Mode):
   - Fix banali (typo, singola riga)
   - Query informative
   - Comandi espliciti e semplici

## Principi Generali

- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It
- **NO FRICTION**: Non aggiungere layer di indirezione inutili (wrapper, abstrazioni premature)
- Non over-engineerare
- Preferisci modifiche minimali e incrementali

## Comunicazione con l'Utente (MANDATORY)

**L'utente NON può eseguire comandi manuali durante la chat.**

L'utente spesso non legge i messaggi intermedi, specialmente quando:
- La chat viene compattata/riassunta
- Ci sono molti output di comandi
- La sessione è lunga

**Regole:**

1. **MAI chiedere all'utente di eseguire comandi manuali** a meno che non sia assolutamente impossibile automatizzare
2. **Se un safety hook blocca**, crea uno script ed eseguilo invece di chiedere comandi manuali
3. **Se servono permessi sudo**, crea uno script completo che l'utente può eseguire UNA SOLA VOLTA
4. **SEMPRE fornire un RAPPORTO FINALE** alla fine del task con:
   - ✅ Cosa è stato completato automaticamente
   - ⚠️ Cosa richiede azione manuale (se inevitabile)
   - 📋 Comandi esatti da copiare-incollare (se necessari)
   - 🔄 Stato attuale del sistema

**Anti-pattern:**
```
❌ "Esegui tu: sudo mkdir -p /path && ..."
❌ "Il safety hook blocca, copia questo comando"
❌ Messaggi con comandi sparsi nella conversazione
```

**Pattern corretto:**
```
✅ Creare script in /tmp o nel progetto
✅ Eseguire lo script automaticamente
✅ Se impossibile, fornire UN SOLO blocco di comandi alla fine
✅ Rapporto finale strutturato
```

## Anti-Superficialità (MANDATORY)

**Spingere per dettagli rivela la verità.**

Quando analizzi codice, valuti progressi, o riporti status:

1. **MAI accettare claim senza verifica**
   - "Funziona" → Mostrami i test che passano
   - "È implementato" → Quante LOC reali? Mostrami il codice
   - "È quasi fatto" → Qual è la % esatta? Cosa manca?

2. **Chiedi sempre prove concrete**
   ```
   ❌ "Gli hooks sono implementati"
   ✅ "Gli hooks sono implementati: 3 file, 127 LOC, 5 test passano"

   ❌ "Il sistema funziona"
   ✅ "Il sistema funziona: output di `pytest -v` con 12/12 test verdi"
   ```

3. **Quality Score = metriche reali**
   - Coverage %
   - Test passati/totali
   - LOC implementate vs pianificate
   - Edge cases gestiti

4. **Red flags da investigare**
   - Risposte vaghe o generiche
   - "Dovrebbe funzionare" senza test
   - Percentuali tonde (80%, 90%) senza giustificazione
   - Mancanza di output concreti

5. **Prima di dichiarare "completato"**
   - [ ] Ho eseguito il codice?
   - [ ] Ho visto l'output reale?
   - [ ] I test esistono E passano?
   - [ ] Posso mostrare prove concrete?

**Lesson learned**: L'assessment onesto richiede verifica attiva, non fiducia passiva.

## Security: Secret Management (MANDATORY)

**MAI esporre secrets nell'output della chat:**

1. **Verifica silenziosa**: `dotenvx get KEY -f /media/sam/1TB/.env 2>/dev/null | grep -q . && echo "Exists"`

2. **⚠️ CRITICAL: MAI usare `dotenvx get KEY` direttamente in chat**
   - I session logs (`.jsonl`) catturano TUTTO l'output dei comandi Bash
   - Anche `2>/dev/null` non basta: il valore appare nella risposta
   - **Questo ha causato leak di 7+ API keys nel Gennaio 2026**

3. **Pattern SICURI per leggere secrets:**
   ```bash
   # ✅ Solo verifica esistenza (output booleano)
   dotenvx get KEY -f /media/sam/1TB/.env 2>/dev/null | grep -q . && echo "Exists"

   # ✅ Iniettare in comando (secret mai visibile)
   dotenvx run -f /media/sam/1TB/.env -- ./my-script.sh

   # ✅ Script separato con output soppresso
   ~/.claude/scripts/rotate-key.sh KEY_NAME 2>&1 | grep -v 'sk-\|ghp_\|xoxb-'
   ```

4. **Pattern PERICOLOSI (MAI usare):**
   ```bash
   # ❌ Output diretto del secret
   dotenvx get OPENAI_API_KEY -f /media/sam/1TB/.env

   # ❌ Estrazione con cut/awk
   grep KEY .env | cut -d= -f2

   # ❌ Base64 encode visibile
   echo "$SECRET" | base64
   ```

5. **MAI** `cut -d= -f2`, `awk '{print $2}'` o simili per estrarre valori di secret.
   **MAI** fare base64 encode/decode di credenziali in comandi bash visibili in chat.
   Se serve processare secret, fallo in script separato con output soppresso.

3. **dotenvx per tutti i secrets** (ECIES encryption):
   - Credenziali Discord, API keys, tokens -> `.env` (cifrato con dotenvx)
   - MAI credenziali inline in crontab
   - Script devono caricare con: `dotenvx run -f .env -- cmd`

4. **Locations**:
   - Secrets cifrati: `/media/sam/1TB/.env` (SSOT master) + per-progetto `.env`
   - Private keys: `/media/sam/1TB/.env.keys` (chmod 600, MAI in git)

### Secrets SSOT (Single Source of Truth)

**SSOT Location:** `/media/sam/1TB/.env` (dotenvx ECIES encrypted)
**Keys Location:** `/media/sam/1TB/.env.keys` (chmod 600)

| Operazione | Comando |
|-----------|---------|
| Aggiungere secret | `secret-add KEY_NAME` (prompt sicuro, no echo) |
| Editare tutti | `secret-add` (apre editor) |
| ~~Leggere singolo~~ | ⚠️ **DEPRECATO** - causa leak in session logs |
| Verificare esistenza | `dotenvx get KEY -f /media/sam/1TB/.env 2>/dev/null \| grep -q . && echo "Exists"` |
| Iniettare in comando | `dotenvx run -f /media/sam/1TB/.env -- cmd` |
| Ruotare chiavi | `~/.claude/scripts/rotate-keys.sh [KEY_NAME]` |
| Contare keys | `dotenvx decrypt -f /media/sam/1TB/.env --stdout 2>/dev/null \| grep -c '='` |

| Key | Usage |
|-----|-------|
| `GITHUB_PAT` | GitHub API, CI/CD |
| `GITHUB_TOKEN` | GitHub MCP |
| `GH_PROJECT_PAT` | GitHub org secret for project boards (= GITHUB_TOKEN) |
| `LINEAR_API_KEY` | Linear MCP |
| `SENTRY_AUTH_TOKEN` | Sentry MCP |
| `OPENAI_API_KEY` | OpenAI API |
| `GEMINI_API_KEY` | Vertex AI |
| `OPENROUTER_API_KEY` | OpenRouter (OpenClaw cronjob/devops) |
| `OPENROUTER_API_KEY2` | OpenRouter (confidence-gate pipeline) |
| `N8N_API_KEY` | N8N MCP |
| `DISCORD_TOKEN` | Discord bot |
| `DISCORD_WEBHOOK_URL` | Pipeline alerts |
| `GRAFANA_URL/USERNAME/PASSWORD` | Grafana MCP |
| `FIRECRAWL_API_KEY` | Firecrawl MCP |
| `LANGSMITH_*` | LangSmith tracing |
| `WOLFRAM_LLM_APP_ID` | WolframAlpha (in .claude.json env) |
| `BRAVE_AI_API_KEY` | Brave Search API (openclaw web_search) |
| `CLOUDFLARE_API_KEY` | Cloudflare Global API |
| `CF_API_TOKEN` | Cloudflare Tunnel token |
| `CF_ACCOUNT_ID` | Cloudflare Account ID |
| `GOOGLE_OAUTH_CLIENT_ID` | Cloudflare Access OAuth |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Cloudflare Access OAuth |
| `CF_ACCESS_CLIENT_ID` | Cloudflare Service Token |
| `CF_ACCESS_CLIENT_SECRET` | Cloudflare Service Token |

**Total:** 60+ keys in SSOT

**⚠️ MANDATORY: SEMPRE backup PRIMA di modificare:**
```bash
cp /media/sam/1TB/.env /media/sam/1TB/.env.bak-$(date +%Y%m%d-%H%M%S)
cp /media/sam/1TB/.env.keys /media/sam/1TB/.env.keys.bak-$(date +%Y%m%d-%H%M%S)
```

**Multi-macchina**: Copiare `.env.keys` via scp a Workstation, Mac, Muletto.

**⚠️ DEPRECATO:**
- SOPS + age → migrato a dotenvx (Feb 2026)
- `.env.enc` → ora `.env` (cifrato con dotenvx)
- `~/.config/sops/age/keys.txt` → ora `.env.keys`
- `/media/sam/1TB/.sops.yaml` → deprecato
- GSM (Google Secret Manager) - non usare

### Infrastructure Security

**Machines:**
| Machine | IP | OS | Role |
|---------|----|----|------|
| Muletto | 192.168.1.100 | Ubuntu 24.04 | Synapse, Gateway, Bytebot, CF Tunnel |
| Workstation | 192.168.1.111 | Ubuntu 22.04 | Hyperliquid, N8N, Grafana, Docker |
| Mac | 192.168.1.112 | macOS 12.7.6 | Development |

**Cloudflare Access** protects web endpoints with Google OAuth:
- `cluster.princyx.xyz` (Moltbot Gateway) — App ID: f88d8c6a
- `matrix.princyx.xyz` (Matrix Synapse) — App ID: 2c5f43db
- `n8nubuntu.princyx.xyz` (N8N) — App ID: 95137f97
- **Allowlist**: gptprojectmanager@gmail.com, gptcoderassistant@gmail.com
- **Service Token**: CF_ACCESS_CLIENT_ID/SECRET (Token ID: 2d248458)
- **CF API Auth**: X-Auth-Email + X-Auth-Key (NOT Bearer token)
- **Account ID**: 25b3070915eb579b7d195a80c2445593
- **Zone ID**: 3d000ea0712744aab65025e409c4dd4d

**Docker Network Hardening** (Workstation):
- DOCKER-USER iptables chain prevents Docker firewall bypass
- Rules: LAN allowed, Internet blocked (except Hyperliquid P2P ports 4001-4009)
- Persistent via systemd: `docker-user-rules.service`
- Location: `/media/sam/1TB/moltbot-iac/workstation/docker-user-rules.sh`

**SSH Hardening** (Workstation):
- Password auth: disabled
- fail2ban: active

**Per-Project Secrets** (all dotenvx encrypted, .env.keys chmod 600):
- `/home/sam/hyperliquid-docker/.env` — VALIDATOR_PRIVATE_KEY (critical)
- `/media/sam/1TB/n_backup/.env` — POSTGRES_PASSWORD, N8N_ENCRYPTION_KEY
- `/media/sam/1TB/backstage-portal/.env` — Backstage config
- `/media/sam/1TB/N8N_dev/.env` — N8N config
- `/media/sam/1TB/hummingbot_scraper/.env` — DISCORD_TOKEN
- Secure restart: `dotenvx run -f .env -- cmd` (in-memory, no plaintext on disk)

**Full docs**: `/media/sam/1TB/moltbot-iac/docs/security.md`

## MCP Server Configuration

**Config location:** `~/.claude.json` (User MCPs - SSOT)

**Template:** `~/.claude/templates/mcp-config.json`

### MCP Servers Disponibili

| Server | Tipo | Descrizione |
|--------|------|-------------|
| `linear` | stdio | Issue tracking |
| `context7` | stdio+dotenvx | Documentation lookup |
| `serena` | stdio | IDE assistant |
| `wolframalpha` | stdio | Math/computation |
| `download-mcp` | stdio | File downloads |
| `claude-flow` | stdio | Workflow orchestration |
| `grafana` | stdio+dotenvx | Metrics/dashboards |
| `n8n-mcp` | stdio+dotenvx | Workflow automation |
| `firecrawl-mcp` | stdio+dotenvx | Web scraping |
| `sentry` | stdio+dotenvx | Error tracking |
| `playwright` | stdio | Browser automation |
| `bytebot` | **SSE remote** | Desktop automation (Linux container) |

### Bytebot (Desktop Automation)

**Endpoint:** `http://192.168.1.100:9990/mcp` (muletto)

Capabilities:
- `computer_screenshot` - Cattura schermo
- `computer_click_mouse` - Click
- `computer_type_text` - Digita testo
- `computer_application` - Apri app (firefox, vscode, terminal)

Skill: `~/.claude/skills/bytebot/SKILL.md`

### OpenClaw (Agent Gateway + Node)

**Architecture:** Gateway (Muletto Docker) → Node (Workstation systemd) → exec on repos

**Gateway (Muletto 192.168.1.100):**
- Container: `openclaw-gateway` (`ghcr.io/openclaw/openclaw:main`)
- Config: `/home/sam/moltbot-infra/clawdbot-config/openclaw.json`
- Workspace: `/home/sam/moltbot-infra/clawd-workspace/` (SOUL.md, BOOT.md, USER.md, AGENTS.md)
- Persistent deps volume: `openclaw-node-modules` at `/app/node_modules`
- Entrypoint: `node /app/dist/entry.js gateway --bind lan --port 8090`
- Network: bridge + `moltbot-infra_moltbot-net` (for Synapse)

**Node (Workstation 192.168.1.111):**
- Service: `/etc/systemd/system/openclaw-node.service`
- User: `openclaw` (dedicated, isolated)
- WorkingDirectory: `/media/sam/1TB`
- Security: `InaccessiblePaths` on sops/ssh/gnupg/claude/clawdbot, `ReadOnlyPaths=/ /home/sam`
- Exec approvals: `/home/openclaw/.openclaw/exec-approvals.json` (`security: "full"`)
- ACLs: `openclaw` has rwx on `/media/sam/1TB` via POSIX ACL
- Filesystem: `chmod o+x` on `/home/sam`, `/home/sam/.local`, `/home/sam/.local/share` (traverse only, for uv python)

**Matrix channel (Bambam):**
- Room: `!GQeiGgJenxtCKbaxDL:matrix.lan` (name: "bambam")
- Bot user: `@clawdbot:matrix.lan`
- Send programmatic messages via Synapse API (NOT `openclaw message send` — uses separate client that loses room state)
- Bot only responds to messages from other users, not its own

**Multi-agent routing:** 4 agents (main, nautilus, utxoracle, n8n), deterministic per-session

**CLI (inside gateway container):**
```bash
ssh 192.168.1.100 'docker exec openclaw-gateway node /app/dist/entry.js <command>'
# Useful: skills list, doctor, config get/set, message send/read, agent, memory status/search
```

**Programmatic agent interaction (preferred over Matrix API):**
```bash
# Run agent turn and get JSON response
ssh 192.168.1.100 'docker exec openclaw-gateway node /app/dist/entry.js agent \
  --agent main --session-id <id> --message "..." --json --timeout 600'

# Run + deliver response to Matrix room
ssh 192.168.1.100 'docker exec openclaw-gateway node /app/dist/entry.js agent \
  --agent main --message "..." --deliver \
  --reply-channel matrix --reply-to "!GQeiGgJenxtCKbaxDL:matrix.lan" --json --timeout 600'
```

**Memory:** File-based via MEMORY.md in workspace (read every session). Embeddings via OpenAI text-embedding-3-small.

**MCPorter (MCP bridge for Bambam):**
- Config: `/home/openclaw/.mcporter/mcporter.json` (chmod 600)
- Bambam usa `exec` → `npx -y mcporter call <server.tool> args...`
- Per aggiungere MCP: editare mcporter.json con nuovo server
- Chrome headless service: `chrome-headless.service` + `chrome-cdp-proxy.service` sulla Workstation

**MCPorter Servers configurati (7):**

| Server | Tools | Uso |
|--------|-------|-----|
| `playwright` | 22 | Browser automation, visual validation (headless Chrome) |
| `context7` | 2 | Documentation lookup per librerie |
| `grafana` | 55 | Metriche, dashboards, alerting |
| `sentry` | 22 | Error tracking, issue analysis |
| `linear` | 7 | Issue tracking |
| `firecrawl` | 8 | Web scraping |
| `linux-desktop` | AT-SPI2 | Desktop automation leggera (via SSH → muletto bytebot container) |

**linux-desktop-mcp** (token-efficient desktop automation):
- Pacchetto Python 0.1.0 dentro container `bytebot-desktop` su Muletto
- Usa AT-SPI2 accessibility tree (testo strutturato, NO screenshot raw → basso consumo token)
- Wrapper: `/home/openclaw/.mcporter/linux-desktop-mcp-wrapper.sh` (SSH → docker exec)
- Prerequisito: SSH key openclaw → sam@192.168.1.100 (authorized_keys)
- Alternativa pesante: Bytebot API (`http://192.168.1.100:9990/mcp`) per screenshot reali

**Agents per repo (Claude Code, in .claude/agents/):**
- nautilus_dev: 7 agents
- UTXOracle: 9 agents
- N8N_dev: 3 agents

### OpenClaw Config Audit (2026-02-01)

**Workspace isolati per agent:**
- `main` → `/home/node/clawd`
- `nautilus` → `/home/node/clawd-nautilus`
- `utxoracle` → `/home/node/clawd-utxoracle`
- `n8n` → `/home/node/clawd-n8n`

**Exec Approvals** (`~/.openclaw/exec-approvals.json`):
- Default: `security: "allowlist"`, `ask: "on-miss"`, `askFallback: "deny"`
- Per-agent allowlists: git, python3, node, npm, npx, pytest, .local/bin/*
- `autoAllowSkills: true` per tutti gli agent

**Memory Flush**: abilitato pre-compaction (`softThresholdTokens: 4000`)

**Browser**: `evaluateEnabled: false` (anti-injection), profilo `openclaw` → CDP `http://192.168.1.111:9223`

**Cron** (4 job, tutti agent "main"):
- node-health-check: ogni 6h UTC
- Auth check: ogni 6h
- Daily QA: 09:00 Europe/Rome
- Weekly review: lunedì 08:00 Europe/Rome

**Hooks** (3 attivi): boot-md, session-memory, command-logger

**SSH openclaw→muletto**: `command=` restriction — può solo eseguire `linux-desktop-mcp`

## Testing Requirements (MANDATORY)

**Ogni implementazione deve includere test:**

1. **Unit Tests**: Test per funzioni/classi individuali
2. **Integration Tests**: Test per componenti che interagiscono
3. **E2E Tests (quando applicabile)**:
   - Testa il flusso completo end-to-end
   - Usa dati reali quando possibile (non solo mock)
   - Verifica comportamento in condizioni realistiche

### Preferisci Test con Dati Reali (MANDATORY)

**NON creare test con mock inutili.** Usa dati reali quando disponibili:

1. **Se API key disponibile** → Usa l'API vera
   - Verifica sempre: `grep -q API_KEY .env && echo "disponibile"`
   - Se disponibile, testa con chiamate reali

2. **Mock SOLO quando necessario:**
   - API esterne non disponibili (no key)
   - Rate limiting
   - Edge cases impossibili con dati reali

3. **Test con dati reali > Test con mock**
   - I mock possono diventare obsoleti
   - I dati reali verificano il comportamento effettivo
   - Più fiducia nei risultati

**Anti-pattern da evitare:**
```python
# ❌ Mock inutile quando API disponibile
with patch('api.fetch', return_value=fake_data):
    result = collector.collect()

# ✅ Test con dati reali
result = await collector.collect()
assert not result.empty
```

**Prima di considerare un task completato:**
- [ ] Unit tests passano
- [ ] Integration tests passano
- [ ] E2E tests con dati reali (se applicabile)
- [ ] Coverage adeguata per codice critico

**Pattern consigliato:**
```python
# tests/e2e/test_feature_e2e.py
@pytest.mark.e2e
def test_complete_flow_with_real_data():
    """Test end-to-end con dati reali."""
    # Setup con dati reali (non mock)
    # Esegui il flusso completo
    # Verifica risultati
```

## Project Validation System

**Ogni progetto DEVE avere una validation config** per `/spec-pipeline`.

### Setup (una tantum per progetto)

```bash
# Crea struttura validation
mkdir -p .claude/validation

# Copia template e personalizza
cp ~/.claude/templates/validation-config.json .claude/validation/config.json
```

### File richiesti

```
{progetto}/
└── .claude/
    └── validation/
        └── config.json    # OBBLIGATORIO per /spec-pipeline
```

### Config minima

```json
{
  "domain": "your-domain",
  "anti_patterns": [],
  "research_keywords": {
    "trigger": [],
    "skip": []
  }
}
```

### Riferimenti

- **Template**: `~/.claude/templates/validation-config.json`
- **Esempi**: nautilus_dev, UTXOracle, N8N_dev
- **Comando**: `/new-project` per scaffold completo

## claude-flow Auto-Sync (OBBLIGATORIO per GSD/Speckit)

**Quando esegui `/gsd:*` o `/speckit.*` con Task agents, DEVI:**

### 1. PRIMA di spawning Task agents
```
mcp__claude-flow__session_save sessionId="{project}-{phase}-start"
mcp__claude-flow__memory_store key="gsd:{project}:{phase}" value={"status":"starting","plans":[...]}
```

### 2. DOPO completamento Task agents
```
mcp__claude-flow__memory_store key="gsd:{project}:{phase}" value={"status":"done","results":[...]}
mcp__claude-flow__session_save sessionId="{project}-{phase}-done"
```

### 3. A INIZIO sessione (se riprendi lavoro)
```
mcp__claude-flow__memory_retrieve key="gsd:{project}:*"
# Se trova stato precedente → mostra e chiedi se continuare
```

### Benefici
- **Crash recovery**: `session_restore` riprende da ultimo checkpoint
- **Cross-session**: stato persiste tra /clear e "Brewed"
- **Metriche**: sync automatico a QuestDB via hook

### Alternative con garanzia
Usa `/gsd:execute-phase-sync` o `/speckit.implement-sync` per sync automatico garantito.

### GitHub Sync Strategy

Combinazione ottimale per tracking completo:

1. **Durante esecuzione** (real-time, framework agnostic):
   ```
   mcp__claude-flow__github_issue_track action="create" title="Plan 05-01" labels=["gsd-plan"]
   mcp__claude-flow__github_issue_track action="update" issueNumber={n} body="Progress: 2/4 tasks"
   mcp__claude-flow__github_issue_track action="close" issueNumber={n}
   ```

2. **Fine milestone** (batch sync completo):
   ```
   /gsd:sync-github --create-project
   ```
   - Crea GitHub ProjectsV2 board
   - Sincronizza Phases → Milestones
   - Sincronizza Plans → Issues
   - Applica labels standard

## Academic Research Pipeline (N8N)

### /research - Flusso Asincrono

Le fonti in `research.md` sono **metadata** (titolo, abstract, DOI) da API search.

Il contenuto RAG dei papers viene processato in **15-30 min** (N8N pipeline).

### Accesso ai dati RAG

Dopo processing completato (notifica Discord):

```bash
/research-papers "query"    # Query RAG knowledge base
```

### CAS Validation (MANDATORY)

**⚠️ Prima di implementare formule da papers → SEMPRE validare con CAS**

```bash
curl -s -X POST http://localhost:8769/validate \
  -H "Content-Type: application/json" \
  -d '{"latex": "x^2 + 2*x + 1", "cas": "maxima"}' | jq .
```

- **Engines**: maxima (algebra), sagemath (hybrid), matlab (numeric)
- **Quando**: Implementa/modifica formula → ✅ | Solo spiegazione → ❌
- **Se fallisce**: NON implementare, segnala errore all'utente
