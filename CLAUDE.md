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

1. **Verifica silenziosa**: Usa `grep -q` per verificare esistenza senza mostrare il valore
   ```bash
   # CORRETTO
   sops -d file.enc 2>/dev/null | grep -q "SECRET_NAME" && echo "Exists"

   # SBAGLIATO - espone il valore
   sops -d file.enc | grep "SECRET_NAME"
   ```

2. **SOPS/age per tutti i secrets**:
   - Credenziali Discord, API keys, tokens -> `.env.enc`
   - MAI credenziali inline in crontab
   - Script devono caricare da SOPS: `eval "$(sops --input-type dotenv --output-type dotenv -d .env.enc)"`

3. **Locations**:
   - Secrets cifrati: `/media/sam/1TB/<repo>/.env.enc`
   - Age keys: `~/.config/sops/age/keys.txt`
   - SOPS config: `/media/sam/1TB/.sops.yaml`

### Secrets SSOT (Single Source of Truth)

**SSOT Location:** `/media/sam/1TB/.env.enc` (SOPS+age encrypted)

| Key | Usage |
|-----|-------|
| `GITHUB_PAT` | GitHub API, CI/CD |
| `GITHUB_TOKEN` | GitHub MCP |
| `GH_PROJECT_PAT` | GitHub org secret for project boards (= GITHUB_TOKEN) |
| `LINEAR_API_KEY` | Linear MCP |
| `SENTRY_AUTH_TOKEN` | Sentry MCP |
| `OPENAI_API_KEY` | OpenAI API |
| `GEMINI_API_KEY` | Vertex AI |
| `N8N_API_KEY` | N8N MCP |
| `DISCORD_TOKEN` | Discord bot |
| `DISCORD_WEBHOOK_URL` | Pipeline alerts |
| `GRAFANA_URL/USERNAME/PASSWORD` | Grafana MCP |
| `FIRECRAWL_API_KEY` | Firecrawl MCP |
| `LANGSMITH_*` | LangSmith tracing |
| `WOLFRAM_LLM_APP_ID` | WolframAlpha (in .mcp.json env) |

**Total:** 35 keys in SSOT

**Comandi SOPS:**
```bash
# Decrypt to view (keys only, no values!)
sops -d /media/sam/1TB/.env.enc | cut -d= -f1

# Add new secret
sops /media/sam/1TB/.env.enc  # opens editor

# Verify key exists
sops -d /media/sam/1TB/.env.enc 2>/dev/null | grep -q "KEY_NAME" && echo "Exists"
```

**⚠️ DEPRECATO:**
- GSM (Google Secret Manager) - non usare
- `/media/sam/1TB/secrets.enc` - migrato a .env.enc
- `~/.claude/.env.enc` - migrato a /media/sam/1TB/.env.enc
- `/media/sam/1TB/.env` (plaintext) - eliminato

## MCP Server Configuration

**Config location:** `~/.mcp.json` (NON settings.json)

**Template:** `~/.claude/templates/mcp-config.json`

### MCP Servers Disponibili

| Server | Tipo | Descrizione |
|--------|------|-------------|
| `linear` | stdio | Issue tracking |
| `context7` | stdio+sops | Documentation lookup |
| `serena` | stdio | IDE assistant |
| `wolframalpha` | stdio | Math/computation |
| `download-mcp` | stdio | File downloads |
| `claude-flow` | stdio | Workflow orchestration |
| `grafana` | stdio+sops | Metrics/dashboards |
| `n8n-mcp` | stdio+sops | Workflow automation |
| `firecrawl-mcp` | stdio+sops | Web scraping |
| `sentry` | stdio+sops | Error tracking |
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
