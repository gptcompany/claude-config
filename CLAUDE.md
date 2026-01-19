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

**Total:** 34 keys in SSOT

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

## Testing Requirements (MANDATORY)

**Ogni implementazione deve includere test:**

1. **Unit Tests**: Test per funzioni/classi individuali
2. **Integration Tests**: Test per componenti che interagiscono
3. **E2E Tests (quando applicabile)**:
   - Testa il flusso completo end-to-end
   - Usa dati reali quando possibile (non solo mock)
   - Verifica comportamento in condizioni realistiche

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

## claude-flow Integration (GSD/Speckit)

**Potenzia GSD e Speckit con persistenza e coordinamento via claude-flow MCP.**

Gli agenti claude-flow sono pattern cognitivi/coordinatori — l'esecuzione effettiva (inclusi tutti gli MCP) resta su Claude Code.

### Quando usare claude-flow

Durante esecuzione di workflow GSD o Speckit:

1. **State persistence** (cross-session):
   ```
   # Prima di spawning Task agents
   mcp__claude-flow__memory_store key="gsd:state:{phase}" value={state_json}

   # Task agents recuperano stato
   mcp__claude-flow__memory_retrieve key="gsd:state:{phase}"
   ```

2. **Session resume** (crash recovery):
   ```
   # A ogni checkpoint o fine piano
   mcp__claude-flow__session_save sessionId="gsd-{project}-{phase}"

   # Per riprendere dopo interruzione
   mcp__claude-flow__session_restore sessionId="gsd-{project}-{phase}"
   ```

3. **Coordination tracking**:
   ```
   # Traccia task distribuiti
   mcp__claude-flow__task_create task="Execute plan 05-01"
   mcp__claude-flow__task_status taskId={id}
   ```

### Pattern consigliato per /gsd:execute-phase

```
1. session_save all'inizio (checkpoint iniziale)
2. memory_store per stato fase
3. Spawn Task agents (esecuzione parallela)
4. Ogni agent: memory_retrieve → esegui → memory_store risultato
5. Orchestrator: memory_retrieve tutti i risultati
6. session_save alla fine (checkpoint finale)
```

### Vantaggi

- **Zero modifiche** a GSD/Speckit frameworks
- **Crash recovery**: session_restore riprende da ultimo checkpoint
- **Cross-session state**: memoria persiste tra /clear
- **Audit trail**: tutto in ~/.claude-flow/

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
