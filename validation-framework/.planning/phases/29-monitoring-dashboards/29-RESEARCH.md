# Phase 29: Monitoring & Dashboards - Research

**Researched:** 2026-02-02
**Domain:** Grafana dashboards for OpenClaw monitoring, alerting Discord/Matrix
**Confidence:** HIGH

<research_summary>
## Summary

Fase 29 costruisce su infrastruttura già esistente: Grafana (Workstation), Prometheus con 3 metriche OpenClaw dalla fase 28 (`openclaw_daily_cost_usd`, `openclaw_budget_max_usd`, `openclaw_budget_exceeded`), pattern dashboard stabiliti dalla fase 17, e alerting Discord già configurato.

Il gap principale è: le metriche attuali coprono solo il budget. Servono metriche addizionali estratte dai log JSONL di OpenClaw (task success rate, durata sessioni, quality scores dall'autonomous loop). Il budget-enforcer script (fase 28) va esteso per esporre queste metriche aggiuntive nel file `.prom`.

Per Matrix alerting: il modo più semplice è usare il generic webhook di Grafana → Synapse client API direttamente (già usato dal budget-enforcer), oppure grafana-matrix-forwarder come bridge dedicato.

La verifica finale delle dashboard sarà visuale tramite OpenClaw con linux-desktop MCP e Playwright MCP per screenshot e validazione automatica.

**Primary recommendation:** Estendere budget-enforcer per esporre metriche aggiuntive (task success, duration, quality), creare dashboard JSON provisionata, configurare alert rules con contact point Matrix, verificare visualmente via OpenClaw + Playwright.
</research_summary>

<standard_stack>
## Standard Stack

### Core (già disponibile)
| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| Grafana | 11.x | Dashboard & alerting | Running su Workstation |
| Prometheus | 2.x | Metrics storage & query | Running su Workstation |
| node_exporter | textfile collector | Custom metrics ingestion | Configurato (fase 28) |
| budget-enforcer.sh | - | Log parsing → .prom file | Deployed (fase 28) |

### Metriche Esistenti (da fase 28)
| Metric | Type | Source |
|--------|------|--------|
| `openclaw_daily_cost_usd` | gauge | budget-enforcer → .prom |
| `openclaw_budget_max_usd` | gauge | budget-enforcer → .prom |
| `openclaw_budget_exceeded` | gauge | budget-enforcer → .prom |

### Metriche da Aggiungere (log parsing)
| Metric | Type | Source | Description |
|--------|------|--------|-------------|
| `openclaw_tasks_total` | counter | JSONL logs | Total agent runs today |
| `openclaw_tasks_success` | counter | JSONL logs | Successful completions |
| `openclaw_tasks_failed` | counter | JSONL logs | Failed/errored runs |
| `openclaw_task_duration_seconds` | gauge | JSONL logs | Average task duration |
| `openclaw_tokens_input_total` | counter | JSONL logs | Total input tokens today |
| `openclaw_tokens_output_total` | counter | JSONL logs | Total output tokens today |
| `openclaw_agent_runs{agent="X"}` | counter | JSONL logs | Per-agent run count |

### Alerting
| Component | Purpose | Config |
|-----------|---------|--------|
| Discord webhook | Critical alerts | Già configurato (fase 17) |
| Matrix (Synapse API) | Operational alerts | Budget-enforcer già usa questa via |
| Grafana contact point (webhook) | Alert routing | Da configurare per Matrix |

### Verifica Visuale
| Tool | Purpose | Access |
|------|---------|--------|
| Playwright MCP | Screenshot dashboard | Via MCPorter su OpenClaw |
| linux-desktop MCP | Desktop automation | Via SSH → bytebot container |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| textfile collector | Prometheus pushgateway | Pushgateway non raccomandato per batch jobs periodici |
| Direct Synapse API | grafana-matrix-forwarder | Forwarder è un container extra; Synapse API diretta è più semplice |
| Manual dashboard JSON | Grafana Foundation SDK | SDK è overkill per 1 dashboard |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Dashboard Structure
```
OpenClaw Dashboard
├── Row 1: Overview (stat panels)
│   ├── Daily Cost (gauge, $)
│   ├── Budget Remaining (gauge, %)
│   ├── Tasks Today (stat, count)
│   └── Success Rate (stat, %)
├── Row 2: Time Series
│   ├── Cost Over Time (time series, daily)
│   ├── Task Success/Fail (stacked bar)
│   └── Token Usage (time series)
├── Row 3: Per-Agent Breakdown
│   ├── Agent Runs (bar chart by agent)
│   └── Agent Cost (table)
└── Row 4: Quality & Alerts
    ├── Budget Alert Status (state timeline)
    └── Recent Alerts (log panel)
```

### Pattern 1: Log-Based Metrics via textfile Collector
**What:** Parse JSONL logs → write Prometheus textfile format → node_exporter scrapes
**When to use:** Quando la sorgente metriche è log-based (non OTEL/push)
**Why:** Già in uso dalla fase 28. Estendere lo script esistente è il path più semplice.

### Pattern 2: Dashboard JSON Provisioning
**What:** Dashboard JSON in `/var/lib/grafana/dashboards/openclaw/`, provisioning YAML punta alla directory
**When to use:** Dashboard gestite come code, riproducibili
**Why:** Stesso pattern usato per validation dashboards (fase 17)

### Pattern 3: Alert Rules via Provisioning
**What:** Alert rules YAML in `/etc/grafana/provisioning/alerting/`
**Why:** Reproducibile, versionabile, stesso pattern fase 17

### Anti-Patterns to Avoid
- **Dashboard creata solo via UI:** Non riproducibile, si perde al restart
- **Metriche push per batch jobs:** Prometheus pushgateway non è pensato per questo use case
- **Alert su ogni singola metrica:** Troppo rumore. Alert solo su: budget exceeded, success rate < 80%, zero tasks in 24h
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Metrics exposition | Custom HTTP server | node_exporter textfile | Già in uso, zero infra aggiuntiva |
| Dashboard | Build via API calls | JSON file provisioning | Più semplice, versionabile |
| Matrix alerting | Custom alerting daemon | Grafana webhook → curl Synapse | Budget-enforcer già fa questo |
| Visual verification | Manual screenshot review | Playwright MCP via OpenClaw | Automatizzabile, riproducibile |
| Cost calculation | Custom billing system | Extend budget-enforcer | Già parsing i log, aggiungere metriche |

**Key insight:** L'infrastruttura è già al 80%. Budget-enforcer fa parsing log e scrive .prom. Basta estenderlo con metriche aggiuntive e creare il dashboard JSON.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Stale textfile metrics
**What goes wrong:** Metriche nel .prom file non si aggiornano se lo script crasha
**Why it happens:** node_exporter serve l'ultimo file scritto, anche se vecchio di ore
**How to avoid:** Aggiungere timestamp metric (`openclaw_last_update_timestamp`) e alert se > 10 min stale
**Warning signs:** Dashboard mostra dati invariati per ore

### Pitfall 2: Dashboard JSON troppo complesso
**What goes wrong:** Dashboard con 20+ pannelli, lenta e confusa
**Why it happens:** Tentazione di mettere tutto in una dashboard
**How to avoid:** Max 8-10 pannelli. Overview + drilldown separati se serve
**Warning signs:** Load time > 3s, scroll infinito

### Pitfall 3: Alert flooding
**What goes wrong:** 50 alert in un'ora su Discord/Matrix
**Why it happens:** Alert troppo sensibili o senza grouping/repeat interval
**How to avoid:** group_wait: 1m, repeat_interval: 4h per warning, 1h per critical
**Warning signs:** Channel Discord/Matrix inutilizzabile per troppi messaggi

### Pitfall 4: Grafana non raggiunge Synapse per Matrix alerts
**What goes wrong:** Webhook timeout su Matrix homeserver
**Why it happens:** Grafana è su Workstation (192.168.1.111), Synapse su Muletto Docker (192.168.1.100)
**How to avoid:** Verificare connettività LAN, usare IP diretto non hostname
**Warning signs:** Alert rule "firing" ma nessun messaggio su Matrix
</common_pitfalls>

<code_examples>
## Code Examples

### Prometheus textfile format (metriche aggiuntive)
```bash
# Source: Prometheus documentation, node_exporter textfile collector
# File: /media/sam/1TB/moltbot-iac/workstation/node_exporter_textfile/openclaw.prom

# HELP openclaw_daily_cost_usd Estimated daily cost in USD
# TYPE openclaw_daily_cost_usd gauge
openclaw_daily_cost_usd 0.17

# HELP openclaw_tasks_total Total agent runs today
# TYPE openclaw_tasks_total gauge
openclaw_tasks_total 8

# HELP openclaw_tasks_success Successful agent runs today
# TYPE openclaw_tasks_success gauge
openclaw_tasks_success 7

# HELP openclaw_task_success_rate Task success rate (0-1)
# TYPE openclaw_task_success_rate gauge
openclaw_task_success_rate 0.875

# HELP openclaw_tokens_input_total Total input tokens today
# TYPE openclaw_tokens_input_total gauge
openclaw_tokens_input_total 45000

# HELP openclaw_tokens_output_total Total output tokens today
# TYPE openclaw_tokens_output_total gauge
openclaw_tokens_output_total 12000

# HELP openclaw_last_update_timestamp Unix timestamp of last metrics update
# TYPE openclaw_last_update_timestamp gauge
openclaw_last_update_timestamp 1738500000
```

### Grafana Alert Rule per Matrix (webhook contact point)
```yaml
# Source: Grafana alerting docs
apiVersion: 1
contactPoints:
  - orgId: 1
    name: matrix-openclaw
    receivers:
      - uid: matrix-openclaw-webhook
        type: webhook
        settings:
          url: "http://192.168.1.100:8008/_matrix/client/r0/rooms/!GQeiGgJenxtCKbaxDL:matrix.lan/send/m.room.message?access_token=${MATRIX_BOT_TOKEN}"
          httpMethod: POST
          # Custom body template needed - Synapse expects Matrix event format
```

### Verifica visuale con Playwright (via OpenClaw MCPorter)
```bash
# OpenClaw agent può verificare la dashboard così:
npx -y mcporter call playwright.browser_navigate \
  '{"url": "http://192.168.1.111:3000/d/openclaw-overview"}'

npx -y mcporter call playwright.browser_take_screenshot \
  '{"name": "openclaw-dashboard"}'

# O con linux-desktop per token-efficient check:
npx -y mcporter call linux-desktop.desktop_snapshot '{}'
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Grafana file provisioning only | Git Sync (bidirectional) | Grafana 11 | UI changes sync back to git repo |
| Alert rules in DB only | Alert provisioning YAML | Grafana 10+ | Reproducible alerting |
| grafana-matrix-forwarder | Direct Synapse API + Grafana webhook | 2025+ | Fewer moving parts |

**New tools/patterns to consider:**
- **Grafana Foundation SDK**: TypeScript/Go SDK per generare dashboard JSON programmaticamente. Overkill per 1 dashboard ma utile se ne servono molte.
- **Grafana Git Sync**: Bidirezionale UI ↔ Git. Utile se vuoi editare in UI e committare automaticamente.

**Deprecated/outdated:**
- **Grafana legacy alerting**: Completamente rimosso in favore di Unified Alerting
- **grafana-matrix-forwarder**: Funziona ma non mantenuto attivamente. Meglio webhook diretto.
</sota_updates>

<open_questions>
## Open Questions

1. **Metriche quality score dall'autonomous loop**
   - What we know: autonomous_loop.py scrive `.autonomous-state.json` con stato
   - What's unclear: Se include quality scores dal ValidationOrchestrator
   - Recommendation: Verificare il formato di `.autonomous-state.json` durante planning

2. **Storicizzazione metriche giornaliere**
   - What we know: Budget-enforcer calcola solo per today's log
   - What's unclear: Se serve storicizzare metriche per trend settimanali/mensili
   - Recommendation: Prometheus retention (15 days default) potrebbe bastare. Se serve di più, valutare recording rules.

3. **Verifica visuale: Playwright vs linux-desktop**
   - What we know: Entrambi disponibili via MCPorter
   - What's unclear: Quale è più affidabile per screenshot dashboard Grafana
   - Recommendation: Playwright è più preciso per web content. linux-desktop per verifica complessiva desktop.
</open_questions>

<verification_plan>
## Piano di Verifica Visuale (OpenClaw)

La verifica UAT delle dashboard sarà automatizzata tramite OpenClaw:

### Step 1: Playwright Screenshot
```
1. Navigate a Grafana dashboard URL
2. Wait per panel rendering (5s)
3. Screenshot full page
4. Verificare che pannelli mostrano dati (non "No data")
```

### Step 2: linux-desktop Validation
```
1. Aprire Firefox su Grafana URL
2. Screenshot con desktop_snapshot
3. Verificare layout visivamente (AT-SPI2 per struttura)
```

### Step 3: Alert Testing
```
1. Trigger alert simulato (impostare soglia bassa temporaneamente)
2. Verificare messaggio su Discord
3. Verificare messaggio su Matrix (room bambam)
4. Ripristinare soglia normale
```
</verification_plan>

<sources>
## Sources

### Primary (HIGH confidence)
- Phase 28 SUMMARY: metriche disponibili, budget-enforcer architecture
- Phase 17 dashboards: `/home/sam/.claude/grafana/` (pattern esistente)
- Phase 27 SUMMARY: autonomous loop architecture
- Grafana provisioning docs: https://grafana.com/docs/grafana/latest/administration/provisioning/

### Secondary (MEDIUM confidence)
- Grafana dashboard best practices: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/
- Grafana Discord alerting: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/configure-discord/
- Grafana webhook notifier: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/

### Tertiary (LOW confidence - needs validation)
- grafana-matrix-forwarder: https://github.com/hectorjsmith/grafana-matrix-forwarder (non mantenuto attivamente)
- ruby-grafana-matrix: https://github.com/ananace/ruby-grafana-matrix (alternativa)
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Grafana dashboards, Prometheus queries
- Ecosystem: node_exporter textfile, Grafana alerting, Matrix integration
- Patterns: Dashboard provisioning, log-based metrics, visual verification
- Pitfalls: Stale metrics, alert flooding, connectivity

**Confidence breakdown:**
- Standard stack: HIGH - infra già in uso, solo estensione
- Architecture: HIGH - pattern stabiliti dalle fasi precedenti
- Pitfalls: HIGH - esperienza diretta dalle fasi 17 e 28
- Code examples: MEDIUM - Matrix webhook format da verificare in implementazione

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - infra stabile)
</metadata>

---

*Phase: 29-monitoring-dashboards*
*Research completed: 2026-02-02*
*Ready for planning: yes*
