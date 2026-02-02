# Phase 28: Usage Tracking & Budget - Research

**Researched:** 2026-02-02
**Domain:** OpenClaw token/cost tracking, budget enforcement, OpenTelemetry metrics
**Confidence:** HIGH

<research_summary>
## Summary

OpenClaw ha un sistema built-in di token/cost tracking per sessione e risposta, con metriche esportabili via OpenTelemetry (plugin `diagnostics-otel`). Tuttavia **non esiste** un meccanismo nativo di budget cap o hard stop sulla spesa. Il tracking è solo osservativo (`/status`, `/usage`), non enforcement.

La strategia è: abilitare l'export OTEL verso il nostro stack (Grafana/Prometheus), creare metriche aggregate per agent/task, e implementare un budget enforcer esterno (hook o cron) che ferma l'agent quando supera il budget.

**Primary recommendation:** Abilitare diagnostics-otel → OTEL Collector → Prometheus, poi creare un budget-enforcer hook che legge le metriche cumulative e blocca nuove sessioni sopra soglia.
</research_summary>

<standard_stack>
## Standard Stack

### Core (già in OpenClaw)
| Component | Purpose | Status |
|-----------|---------|--------|
| `/status` command | Session token count + estimated cost | Built-in |
| `/usage full` command | Per-response usage footer | Built-in |
| `models.providers.*.models[].cost` | Cost per 1M tokens (input/output/cache) | Config |
| `diagnostics-otel` plugin | OTEL export (metrics, traces, logs) | Available, not enabled |
| Session logs (JSONL) | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` | Built-in |

### Infrastructure da configurare
| Component | Purpose | What to do |
|-----------|---------|------------|
| OTEL Collector | Receive OTEL data, forward to backends | Deploy on Workstation |
| Prometheus | Store time-series metrics | Already running (Grafana stack) |
| Grafana | Dashboard + alerting | Already running |

### Non esiste (da creare)
| Component | Purpose | Approach |
|-----------|---------|----------|
| Budget enforcer | Hard stop on spend | Custom hook/cron |
| Per-agent aggregation | Track cost per agent | PromQL queries su `openclaw.cost.usd{agent=...}` |
| Per-task accounting | Cost per task/spec | Correlate session labels |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### OTEL Pipeline
```
OpenClaw Gateway → diagnostics-otel plugin → OTEL Collector → Prometheus
                                                              ↓
                                                           Grafana → Alerts → Discord/Matrix
```

### Config per abilitare OTEL
```json
{
  "plugins": {
    "allow": ["diagnostics-otel"],
    "entries": {
      "diagnostics-otel": { "enabled": true }
    }
  },
  "diagnostics": {
    "enabled": true,
    "otel": {
      "enabled": true,
      "endpoint": "http://192.168.1.111:4318",
      "protocol": "http/protobuf",
      "serviceName": "openclaw-gateway",
      "traces": false,
      "metrics": true,
      "logs": false,
      "sampleRate": 1.0,
      "flushIntervalMs": 30000
    }
  }
}
```

### Metriche OTEL esportate
| Metric | Type | Attributes | Uso |
|--------|------|-----------|-----|
| `openclaw.tokens` | counter | type, channel, provider, model | Token totali |
| `openclaw.cost.usd` | counter | channel, provider, model | Costo USD |
| `openclaw.run.duration_ms` | histogram | channel, provider, model | Durata run |
| `openclaw.context.tokens` | histogram | context, channel, provider, model | Context window |
| `openclaw.session.state` | counter | reason | Transizioni sessione |

### Budget Enforcer Pattern
```python
# Cron ogni 5 min, legge Prometheus, ferma agent se over budget
daily_cost = query_prometheus("sum(increase(openclaw_cost_usd_total[24h]))")
if daily_cost > MAX_DAILY_USD:
    # Metti agent in pausa via OpenClaw CLI o config
    escalate_matrix("Budget exceeded: ${daily_cost:.2f} > ${MAX_DAILY_USD}")
```

### Cost Config per Provider
```json
{
  "models": {
    "providers": {
      "anthropic": {
        "models": [{
          "name": "claude-sonnet-4-20250514",
          "cost": { "input": 3.0, "output": 15.0, "cacheRead": 0.30, "cacheWrite": 3.75 }
        }]
      },
      "openrouter": {
        "models": [{
          "name": "google/gemini-2.5-flash",
          "cost": { "input": 0.15, "output": 0.60, "cacheRead": 0.0375, "cacheWrite": 0.15 }
        }]
      }
    }
  }
}
```

### Anti-Patterns
- **Parsare log JSONL per metriche**: Fragile, usa OTEL instead
- **Budget cap nel gateway code**: Non modificare OpenClaw source, usa hook esterno
- **Token counting manuale**: Inaccurato, lascia fare a OpenClaw
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting | Custom counter | OpenClaw `openclaw.tokens` metric | Già conta accuratamente |
| Cost calculation | Manual $/token math | `openclaw.cost.usd` metric | Gestisce cache pricing |
| Metrics pipeline | Custom log parser | diagnostics-otel → OTEL Collector | Standard, battle-tested |
| Time-series storage | SQLite/JSON file | Prometheus | Query, retention, alerting |
| Alert routing | Custom notification script | Grafana alerting | Già configurato per Discord |

**Key insight:** OpenClaw già traccia tutto, manca solo l'export (OTEL) e l'enforcement (hook esterno). Non serve reinventare il tracking.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: OTEL Collector non raggiungibile dal container
**What goes wrong:** Metriche non arrivano a Prometheus
**Why it happens:** Container Docker su muletto, Prometheus su workstation — network routing
**How to avoid:** Usare IP esplicito (192.168.1.111:4318), verificare firewall
**Warning signs:** Nessuna metrica `openclaw_*` in Prometheus

### Pitfall 2: Cost $0 per OAuth providers
**What goes wrong:** Google/Gemini OAuth non mostra costi
**Why it happens:** "OAuth tokens never show dollar cost" — design decision di OpenClaw
**How to avoid:** Configurare cost manualmente per OAuth models, o tracciare solo token count
**Warning signs:** `openclaw.cost.usd` = 0 per sessioni Google

### Pitfall 3: Per-agent attribution mancante
**What goes wrong:** Metriche aggregate senza distinzione per agent
**Why it happens:** Le attributes OTEL includono `channel`, `provider`, `model` ma non necessariamente `agent`
**How to avoid:** Verificare se `sessionKey` o custom labels includono agent name, altrimenti usare log correlation
**Warning signs:** Tutte le metriche hanno lo stesso set di labels

### Pitfall 4: Rate limit provider-wide instead of per-model
**What goes wrong:** Un modello Google in cooldown blocca tutti i modelli Google
**Why it happens:** OpenClaw cooldown è per-provider, non per-model (issue #5744)
**How to avoid:** Usare provider diversi per modelli diversi, o accettare il comportamento
**Warning signs:** Fallback chain non funziona come atteso
</common_pitfalls>

<code_examples>
## Code Examples

### OTEL Collector config (otel-collector.yaml)
```yaml
# Source: OpenTelemetry Collector docs
receivers:
  otlp:
    protocols:
      http:
        endpoint: "0.0.0.0:4318"

processors:
  batch:
    timeout: 30s

exporters:
  prometheusremotewrite:
    endpoint: "http://localhost:9090/api/v1/write"

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheusremotewrite]
```

### PromQL query per daily cost per provider
```promql
# Total cost last 24h by provider
sum by (provider) (increase(openclaw_cost_usd_total[24h]))

# Token usage per model last hour
sum by (model) (increase(openclaw_tokens_total[1h]))
```

### Budget check script (cron)
```bash
#!/bin/bash
# Query Prometheus for daily spend
DAILY=$(curl -s "http://localhost:9090/api/v1/query?query=sum(increase(openclaw_cost_usd_total[24h]))" \
  | jq -r '.data.result[0].value[1] // "0"')

MAX=5.00  # USD/day

if (( $(echo "$DAILY > $MAX" | bc -l) )); then
    # Escalate
    python3 /home/node/clawd/.autonomous-loop.py --test-escalation
fi
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual log parsing | diagnostics-otel plugin | 2025 | Standard OTEL export |
| Per-provider cooldown only | Per-model cooldown (requested, issue #5744) | Pending | May improve in future |
| No budget caps | Still no budget caps | Current | Must build externally |

**New patterns:**
- OTEL Collector as sidecar nel Docker compose
- Grafana alerting con contact points multipli (Discord + Matrix)

**Current limitations:**
- No native budget enforcement
- OAuth providers don't report cost
- Agent-level attribution depends on session labeling
</sota_updates>

<open_questions>
## Open Questions

1. **Agent attribution nelle metriche OTEL**
   - What we know: Metriche hanno `channel`, `provider`, `model` attributes
   - What's unclear: Se `agent` name è incluso come attribute (potrebbe essere in `sessionKey`)
   - Recommendation: Testare con OTEL abilitato, ispezionare attributes reali

2. **OTEL Collector deployment**
   - What we know: Serve un collector tra OpenClaw e Prometheus
   - What's unclear: Se Prometheus su workstation accetta remote write direttamente (senza collector)
   - Recommendation: Verificare se Grafana Alloy (già installato?) può fare da collector
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- Context7 `/llmstxt/openclaw_ai_llms-full_txt` — token-use, logging, diagnostics-otel config
- https://docs.openclaw.ai/token-use — cost structure, /status, /usage commands
- https://docs.openclaw.ai/logging — OTEL export, metric names, log format

### Secondary (MEDIUM confidence)
- https://github.com/openclaw/openclaw/issues/5744 — per-model rate limit issue
- OpenClaw config inspection (`config get auth`, `config get diagnostics`)

### Tertiary (LOW confidence)
- WebSearch general results — no budget cap feature confirmed anywhere
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw diagnostics + OTEL pipeline
- Ecosystem: OTEL Collector, Prometheus, Grafana
- Patterns: Metrics export, budget enforcement, alerting
- Pitfalls: Network routing, OAuth cost, attribution

**Confidence breakdown:**
- Token tracking: HIGH — documented, verified in config
- OTEL export: HIGH — documented with metric names
- Budget enforcement: HIGH (that it doesn't exist natively) — confirmed by docs + search
- Agent attribution: MEDIUM — needs testing

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days — OpenClaw stable release cycle)
</metadata>

---

*Phase: 28-usage-tracking*
*Research completed: 2026-02-02*
*Ready for planning: yes*
