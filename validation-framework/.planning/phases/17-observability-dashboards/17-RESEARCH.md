# Phase 17: Observability & Dashboards - Research

**Researched:** 2026-01-26
**Domain:** Grafana dashboards, QuestDB time-series queries, Discord alerting, CLI reporting
**Confidence:** HIGH

<research_summary>
## Summary

Researched the observability stack for alert-first validation monitoring. The infrastructure already exists: Grafana is running (`grafana-server.service`), QuestDB has 50 tables including `validation`, `claude_quality_scores`, `claude_hook_invocations`, and the datasource is provisioned (`/etc/grafana/provisioning/datasources/questdb.yaml`).

Key finding: This is **configuration work, not implementation work**. The data flows already exist - we just need to create dashboards, set up alert rules, and build a CLI wrapper for queries. No new infrastructure needed.

**Primary recommendation:** File-provision Grafana dashboards and alerts (no UI clicking), use QuestDB materialized views for pre-computed aggregations, wrap QuestDB REST queries in a Node.js CLI for terminal-based reporting.

</research_summary>

<standard_stack>
## Standard Stack

### Core (Already Installed)
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Grafana | 10.x+ | Dashboard visualization, alerting | Industry standard, already running |
| QuestDB | 8.0+ | Time-series storage, SQL queries | Already has 50 tables with validation data |
| Node.js | 18+ | CLI reporting tool | Already used for hooks system |

### Supporting (Already Available)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| metrics.js | local | QuestDB ILP export + REST query | All QuestDB interactions |
| Discord webhook | - | Alert notifications | Critical failures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Grafana | Grafterm | Terminal-only, no persistent dashboards |
| CLI reports | Sampler | Requires YAML config, less flexible |
| Discord | Slack | Discord already integrated in system |

**No Installation Needed:**
Everything is already running. Just create configuration files.

</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Directory Structure
```
~/.claude/
├── grafana/
│   ├── dashboards/
│   │   ├── validation-overview.json     # Main dashboard
│   │   ├── validator-drilldown.json     # Per-validator details
│   │   ├── project-comparison.json      # Cross-project view
│   │   └── alert-history.json           # Alert timeline
│   └── alerting/
│       ├── contact-points.yaml          # Discord webhook config
│       └── alert-rules.yaml             # Alert rule definitions
├── scripts/
│   └── bin/
│       └── validation-report            # CLI entry point
└── validation-framework/
    └── src/
        └── cli/
            └── validation-report.js     # Report generation
```

### Pattern 1: File Provisioning (Grafana as Code)
**What:** Define dashboards and alerts in JSON/YAML, not UI
**When to use:** Always for reproducibility
**Example:**
```yaml
# /etc/grafana/provisioning/dashboards/validation.yaml
apiVersion: 1
providers:
  - name: 'Validation Framework'
    type: file
    folder: 'Validation'
    options:
      path: /home/sam/.claude/grafana/dashboards
```

### Pattern 2: Materialized Views for Aggregation
**What:** Pre-compute hourly/daily aggregations in QuestDB
**When to use:** Dashboard queries that aggregate over time
**Example:**
```sql
-- QuestDB materialized view
CREATE MATERIALIZED VIEW validation_hourly AS
SELECT
  timestamp_floor('h', timestamp) as hour,
  dimension,
  count() as total_runs,
  sum(passed) as passed_count,
  avg(duration) as avg_duration_ms
FROM validation
SAMPLE BY 1h;
```

### Pattern 3: REST Query Wrapper for CLI
**What:** Node.js CLI that calls QuestDB REST API
**When to use:** Terminal-based reporting
**Example:**
```javascript
// Source: metrics.js queryQuestDB()
const result = await queryQuestDB(`
  SELECT dimension,
         count() as runs,
         sum(case when passed = 1 then 1 else 0 end) * 100.0 / count() as pass_rate
  FROM validation
  WHERE timestamp > dateadd('d', -7, now())
  GROUP BY dimension
  ORDER BY pass_rate
`);
```

### Anti-Patterns to Avoid
- **Manual UI dashboard creation:** Not reproducible, lost on reinstall
- **Polling QuestDB for alerts:** Use Grafana alerting instead
- **Raw queries without views:** Slow on large time ranges, use materialized views

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Alert delivery | Custom webhook handler | Grafana contact points | Handles retries, grouping, silencing |
| Time aggregation | JS loops over raw data | QuestDB SAMPLE BY + materialized views | Orders of magnitude faster |
| Dashboard state | Custom React dashboard | Grafana JSON provisioning | Free features: zoom, annotations, sharing |
| Webhook templating | String concatenation | Grafana notification templates | Go templating built-in |
| Flap prevention | Custom cooldown logic | Grafana pending periods + `keep_firing_for` | Battle-tested debouncing |

**Key insight:** Grafana + QuestDB handle 95% of observability needs out of the box. The only custom code needed is a CLI wrapper for terminal users who don't want to open a browser.

</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Alert Fatigue from Raw Data
**What goes wrong:** Every validation failure triggers Discord spam
**Why it happens:** Alerting on individual events instead of aggregates
**How to avoid:** Use Grafana's grouping and pending periods:
- Group alerts by project/dimension (1 notification per group)
- Set `for: 5m` to require condition persisting
- Use `keep_firing_for` to prevent flapping
**Warning signs:** >10 alerts/day per project

### Pitfall 2: Slow Dashboard Queries
**What goes wrong:** Dashboards time out on large time ranges
**Why it happens:** Querying raw data instead of aggregations
**How to avoid:** Create QuestDB materialized views for common aggregations
**Warning signs:** Queries taking >5 seconds, "Query timeout" errors

### Pitfall 3: Hardcoded Datasource UIDs
**What goes wrong:** Dashboards break when reimported
**Why it happens:** JSON contains absolute datasource UID
**How to avoid:** Use variable datasource references: `"datasource": {"type": "questdb", "uid": "${DS_QUESTDB}"}`
**Warning signs:** "Datasource not found" errors after import

### Pitfall 4: Missing Ownership in Alerts
**What goes wrong:** Alerts go to wrong channel or nobody responds
**Why it happens:** No routing rules per project/team
**How to avoid:** Use notification policies with label-based routing
**Warning signs:** Alerts sent to generic channel, slow response time

</common_pitfalls>

<code_examples>
## Code Examples

### Grafana Panel: Time Series (Pass Rate)
```json
// Source: Grafana docs + QuestDB integration
{
  "type": "timeseries",
  "title": "Validation Pass Rate",
  "datasource": {"type": "questdb", "uid": "${DS_QUESTDB}"},
  "targets": [{
    "refId": "A",
    "rawSql": "SELECT $__time(timestamp), sum(passed)*100.0/count() as pass_rate FROM validation WHERE $__timeFilter(timestamp) SAMPLE BY $__interval"
  }],
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "thresholds": {
        "steps": [
          {"value": 0, "color": "red"},
          {"value": 80, "color": "yellow"},
          {"value": 95, "color": "green"}
        ]
      }
    }
  }
}
```

### Discord Contact Point (YAML Provisioning)
```yaml
# Source: Grafana alerting file provisioning docs
apiVersion: 1
contactPoints:
  - orgId: 1
    name: discord-validation
    receivers:
      - uid: discord-webhook
        type: discord
        settings:
          url: ${DISCORD_WEBHOOK_URL}
          message: |
            {{ template "validation.alert" . }}
```

### Alert Rule: Tier 1 Failure
```yaml
# Source: Grafana alerting API docs
apiVersion: 1
groups:
  - orgId: 1
    name: validation-alerts
    folder: Validation
    interval: 1m
    rules:
      - uid: tier1-failure
        title: Tier 1 Validation Failed
        condition: C
        for: 5m
        labels:
          severity: critical
          tier: "1"
        annotations:
          summary: "Tier 1 blocker in {{ $labels.project }}"
          description: "{{ $values.A.Value }}% pass rate in last 5 minutes"
        data:
          - refId: A
            datasourceUid: questdb
            model:
              rawSql: |
                SELECT sum(passed)*100.0/count() as pass_rate
                FROM validation
                WHERE timestamp > dateadd('m', -5, now())
                  AND dimension IN ('syntax', 'tests', 'imports')
          - refId: C
            datasourceUid: "-100"
            model:
              type: threshold
              conditions:
                - evaluator:
                    type: lt
                    params: [80]
```

### CLI Query (Node.js)
```javascript
// Source: existing metrics.js library
const { queryQuestDB } = require('./lib/metrics');

async function getValidationReport(days = 7) {
  const result = await queryQuestDB(`
    SELECT
      dimension,
      count() as runs,
      sum(passed) as passed,
      sum(case when passed = 0 then 1 else 0 end) as failed,
      round(sum(passed)*100.0/count(), 1) as pass_rate,
      round(avg(duration)/1000.0, 2) as avg_duration_sec
    FROM validation
    WHERE timestamp > dateadd('d', -${days}, now())
    GROUP BY dimension
    ORDER BY pass_rate ASC
  `);

  return result?.dataset || [];
}
```

</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Legacy alerting | Grafana Unified Alerting | 2023 | Single alert system across all datasources |
| Manual views | Materialized Views | QuestDB 8.0+ | Auto-refresh aggregations |
| Custom webhook code | Grafana contact points | Grafana 9+ | Built-in retry, templating, routing |
| JSON files in repo | File provisioning | Grafana 8+ | Dashboards as code, GitOps compatible |

**New tools/patterns to consider:**
- **Grafana Alerting Templates:** Go templating for Discord/Slack messages
- **QuestDB SAMPLE BY + ALIGN TO CALENDAR:** Auto-aligned time buckets
- **Grafana Variables:** `${DS_QUESTDB}` for portable dashboards

**Deprecated/outdated:**
- **Legacy alerting:** Removed in Grafana 11, use Unified Alerting
- **Panel JSON `graph` type:** Use `timeseries` instead (modern)
- **QuestDB manual aggregation:** Use materialized views

</sota_updates>

<open_questions>
## Open Questions

1. **Grafana folder structure**
   - What we know: File provisioning supports folder assignment
   - What's unclear: Whether to use single "Validation" folder or per-project folders
   - Recommendation: Start with single folder, split later if dashboard count grows

2. **Alert escalation chain**
   - What we know: Discord webhook for immediate alerts
   - What's unclear: Whether to add secondary escalation (email, PagerDuty) later
   - Recommendation: Start with Discord-only, add escalation if critical alerts are missed

</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- /grafana/grafana (Context7) - Dashboard provisioning, panel config, alert rules
- /questdb/documentation (Context7) - SAMPLE BY, materialized views, Grafana integration
- metrics.js (local) - queryQuestDB(), exportToQuestDB() already implemented

### Secondary (MEDIUM confidence)
- [Grafana Alerting Best Practices](https://grafana.com/docs/grafana/latest/alerting/guides/best-practices/) - Symptom-based alerting, grouping
- [Configure Discord for Alerting](https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/configure-discord/) - Webhook setup
- [Grafterm](https://github.com/slok/grafterm) - Terminal dashboard alternative (not chosen)
- [Sampler](https://dev.to/sqshq/sampler-dashboards-monitoring-and-alerting-right-from-your-terminal-5h5e) - CLI dashboard alternative (not chosen)

### Tertiary (LOW confidence - needs validation)
- None - all findings verified against official sources

</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Grafana + QuestDB
- Ecosystem: Discord webhook, Node.js CLI
- Patterns: File provisioning, materialized views, alert routing
- Pitfalls: Alert fatigue, slow queries, datasource UIDs

**Confidence breakdown:**
- Standard stack: HIGH - already running, verified via systemctl and curl
- Architecture: HIGH - from official Grafana/QuestDB docs
- Pitfalls: HIGH - documented in Grafana best practices
- Code examples: HIGH - from Context7 + local metrics.js

**Research date:** 2026-01-26
**Valid until:** 2026-02-26 (30 days - stable ecosystem)

</metadata>

---

*Phase: 17-observability-dashboards*
*Research completed: 2026-01-26*
*Ready for planning: yes*
