# Phase 25: Gemini Cross-Review - Research

**Researched:** 2026-02-02
**Domain:** Gemini API integration per cross-model code review in OpenClaw Docker gateway
**Confidence:** HIGH

<research_summary>
## Summary

Ricercato come integrare Gemini come reviewer cross-model nel gateway OpenClaw Docker. La scoperta critica è che **la GEMINI_API_KEY attuale nel container restituisce 403** — chiave bannata o invalida. Questo è il blocco principale da risolvere.

L'approccio tecnico è semplice: Gemini API via API key (`GEMINI_API_KEY` env var) è il metodo più adatto per Docker headless — niente OAuth, niente browser, niente token refresh. OpenClaw supporta nativamente il provider `google` con `GEMINI_API_KEY`. Il routing avviene tramite `llm-task` tool che accetta provider/model come parametri.

**Primary recommendation:** Generare nuova GEMINI_API_KEY da AI Studio, iniettarla nel container via SOPS→docker-compose env, verificare con llm-task, poi configurare la review pipeline nel validate-review skill.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Componente | Versione | Scopo | Perché standard |
|-----------|---------|-------|----------------|
| Gemini 2.5 Pro | latest | Cross-model reviewer | Nella nostra fallback chain, gratis free tier |
| Gemini API Key auth | - | Autenticazione headless | Più semplice per Docker, no OAuth/browser |
| OpenClaw llm-task | built-in | Routing cross-model | Già configurato e funzionante (Phase 24) |
| SOPS+age | - | Secret management | Pattern esistente per tutti i secrets |

### Supporting
| Componente | Versione | Scopo | Quando usare |
|-----------|---------|-------|-------------|
| Gemini 2.5 Flash | latest | Fallback economico | Se Pro raggiunge rate limit |
| OpenRouter | - | Proxy alternativo | Se Google provider in cooldown totale |

### Alternatives Considered
| Invece di | Si potrebbe | Tradeoff |
|-----------|------------|----------|
| API Key | OAuth 2.0 | OAuth richiede browser flow, token refresh, volume persistence — overkill per server |
| API Key | Service Account | Service Account richiede GCP project, IAM — più complesso senza vantaggi per free tier |
| Google diretto | OpenRouter/google | OpenRouter aggiunge latenza e costo, ma bypassa rate limit Google diretto |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: API Key in Docker via Environment
**What:** Iniettare GEMINI_API_KEY come env var nel container gateway
**When to use:** Sempre — è il metodo standard per Docker headless
**Config:**
```yaml
# docker-compose.yml
services:
  openclaw-gateway:
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
```
```bash
# Decrypt da SOPS al deploy
eval "$(sops --input-type dotenv --output-type dotenv -d /media/sam/1TB/.env.enc)"
```

### Pattern 2: Cross-Model Review via llm-task
**What:** validate-review skill usa llm-task con provider esplicito per review indipendente
**When to use:** Ogni volta che si vuole review non-Claude
**Flow:**
1. Agent esegue validation (exec → orchestrator.py)
2. Agent invoca llm-task con `provider: "google"`, `model: "gemini-2.5-pro"`
3. Gemini riceve il report e restituisce score strutturato
4. Agent presenta risultato

### Pattern 3: Fallback Chain per Review
**What:** Se Gemini 403/429, fallback a Kimi K2.5 (OpenRouter), poi GPT-5.2
**When to use:** Resilienza review pipeline
**Implementation:** Già nel validate-review skill (Phase 24)

### Anti-Patterns to Avoid
- **OAuth in Docker**: Non usare OAuth per server-side — richiede browser, token refresh, volume per keychain
- **Gemini CLI in container**: Non installare Gemini CLI — è per uso interattivo, non programmatico
- **Stesso modello per coding e review**: Anti-pattern fondamentale — Claude non deve revieware codice Claude
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problema | Non costruire | Usa invece | Perché |
|----------|--------------|-----------|--------|
| Auth Gemini in Docker | OAuth flow custom | API Key env var | Google raccomanda API key per server |
| Token refresh | Token persistence logic | API Key (no expiry) | API key non scade mai (salvo revoca manuale) |
| Rate limit handling | Custom retry logic | OpenClaw provider cooldown | OpenClaw gestisce cooldown per-provider nativamente |
| Review prompt | Template engine custom | llm-task tool prompt param | llm-task accetta prompt inline, niente templating |
| Receipt/audit | Custom logging | Gateway logs + session history | Ogni llm-task call è loggata nella session history |

**Key insight:** L'infrastruttura per cross-model review è già al 90% — manca solo una API key Gemini valida e una verifica end-to-end.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Gemini API Key 403 Forbidden
**What goes wrong:** API key restituisce 403 anche se settata correttamente
**Why it happens:** Key revocata, progetto disabilitato, restrizioni regionali, o ToS violation
**How to avoid:** Generare nuova key da AI Studio (aistudio.google.com/app/apikey), verificare con curl diretto prima di configurare nel container
**Warning signs:** `Google API error 403` nei log gateway

### Pitfall 2: Provider Cooldown Totale Google
**What goes wrong:** Rate limit su un modello Google (es. gemini-2.5-flash) mette in cooldown TUTTO il provider Google, bloccando anche gemini-2.5-pro
**Why it happens:** OpenClaw traccia cooldown per-provider, non per-modello (issue #5744)
**How to avoid:** Usare modelli Google diversi solo se necessario; per review usare un solo modello Google. In alternativa, usare OpenRouter per accedere a Gemini senza cooldown provider Google
**Warning signs:** `Provider google in cooldown` nei log anche con quota disponibile su altri modelli

### Pitfall 3: Free Tier Quota Esaurita
**What goes wrong:** 100 RPD (Gemini 2.5 Pro) o 250 RPD (Flash) esaurite
**Why it happens:** Free tier ha limiti giornalieri stretti, reset a mezzanotte Pacific
**How to avoid:** Usare review solo per task significativi, non per ogni micro-commit. Fallback a Kimi/GPT quando quota esaurita
**Warning signs:** 429 Too Many Requests dopo ~100 chiamate/giorno

### Pitfall 4: Latenza Cross-Model Review
**What goes wrong:** Review con Gemini aggiunge 10-30s per ogni validazione
**Why it happens:** Round-trip API + Gemini thinking time
**How to avoid:** Review solo su tier 2+ validation, non su tier 1 quick. Async review (non blocca il workflow)
**Warning signs:** Agent idle per >30s durante review
</common_pitfalls>

<code_examples>
## Code Examples

### Verifica API Key con curl
```bash
# Verifica chiave Gemini direttamente
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}" | head -5
# Se OK: lista modelli
# Se 403: chiave invalida
```

### llm-task invocation per review (validate-review skill)
```
# L'agent invoca il tool llm-task con:
tool: llm-task
params:
  provider: google
  model: gemini-2.5-pro
  prompt: "Analyze this validation report. Return JSON: {score: 0-100, issues: [{severity, description, suggestion}], summary: string}"
  input: "<validation output>"
```

### Docker-compose env injection
```yaml
# docker-compose.yml - openclaw-gateway service
environment:
  - GEMINI_API_KEY  # Populated from host env (SOPS decrypt)
```

### SOPS decrypt + docker-compose
```bash
# start-secure.sh pattern
eval "$(sops --input-type dotenv --output-type dotenv -d /media/sam/1TB/.env.enc)"
docker-compose up -d openclaw-gateway
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Vecchio approccio | Approccio attuale | Quando cambiato | Impatto |
|-------------------|-------------------|-----------------|---------|
| Gemini CLI OAuth in Docker | API Key env var | Sempre preferito per server | Elimina complessità OAuth, token refresh, volume persistence |
| Per-provider cooldown | Per-model cooldown (issue #5744) | Non ancora risolto | Workaround: usare un solo modello Google, o passare per OpenRouter |
| Gemini 2.0 Flash | Gemini 2.5 Flash/Pro | 2025 | 2.0 flash/lite retire 2026-03-03. Usare 2.5+ |

**Nuovi modelli:**
- **Gemini 3 Pro Preview**: $2.00/M input, $12.00/M output — preview, non in free tier
- **Gemini 2.5 Flash-Lite**: 1000 RPD free — opzione ultra-economica per review semplici

**Free tier changes (Dec 2025):**
- Quote ridotte: Flash da centinaia a ~20-250 RPD
- Pro: ~100 RPD free
- Enforcement più stretto
</sota_updates>

<open_questions>
## Open Questions

1. **GEMINI_API_KEY attuale invalida — perché?**
   - What we know: La key nel container restituisce 403
   - What's unclear: Se è stata revocata, se il progetto è disabilitato, o se ci sono restrizioni regionali
   - Recommendation: Generare nuova key da AI Studio, testarla con curl, poi iniettare nel container

2. **Per-model cooldown fix (issue #5744)**
   - What we know: OpenClaw tracka cooldown per-provider, non per-modello
   - What's unclear: Se/quando sarà fixato upstream
   - Recommendation: Per ora usare un solo modello Google per review (gemini-2.5-pro), non mescolare con flash

3. **Free tier sufficiente per uso production?**
   - What we know: ~100 RPD per Pro, ~250 per Flash
   - What's unclear: Se il nostro volume di review supererà i limiti giornalieri
   - Recommendation: Iniziare con free tier, monitorare usage, considerare Tier 1 paid ($0.30/M) se necessario
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) - Free tier, paid tiers
- [Gemini API Key docs](https://ai.google.dev/gemini-api/docs/api-key) - GEMINI_API_KEY env var, best practices
- [Gemini Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits) - Per-tier limits
- [OpenClaw Model Providers](https://docs.openclaw.ai/concepts/model-providers) - google provider, GEMINI_API_KEY auth

### Secondary (MEDIUM confidence)
- [Gemini CLI Auth docs](https://geminicli.com/docs/get-started/authentication/) - OAuth headless limitations
- [OpenClaw issue #5744](https://github.com/openclaw/openclaw/issues/5744) - Per-model cooldown bug
- [Google Gemini 403 troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting) - API key 403 causes

### Tertiary (LOW confidence - needs validation)
- WebSearch: Free tier quota exact numbers variano per fonte (100 vs 250 RPD per Pro)
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Google Gemini API, API Key auth
- Ecosystem: OpenClaw llm-task, provider routing, SOPS secret management
- Patterns: Docker env injection, cross-model review pipeline, fallback chain
- Pitfalls: 403 key errors, provider cooldown, rate limits

**Confidence breakdown:**
- Standard stack: HIGH - API key è il metodo documentato per server
- Architecture: HIGH - Pattern già in uso (Phase 24 validate-review)
- Pitfalls: HIGH - 403 error verificato empiricamente, cooldown issue documentato
- Code examples: HIGH - Da docs ufficiali e config esistente

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - Gemini API stabile, ma monitorare model retirement 2026-03-03)
</metadata>

---

*Phase: 25-gemini-cross-review*
*Research completed: 2026-02-02*
*Ready for planning: yes (blocco: nuova GEMINI_API_KEY necessaria)*
