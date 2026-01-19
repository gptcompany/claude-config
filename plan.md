# Enterprise Cross-Check & Consolidation Plan

## Executive Summary

Dopo l'esplorazione completa del sistema, ho identificato le aree che necessitano intervento per raggiungere uno stato enterprise-grade consolidato.

---

## Stato Attuale

### Cosa Funziona Bene ✅

| Area | Status |
|------|--------|
| **Claude Global Config** | 34 hooks, metrics collection, SSOT via canonical.yaml |
| **Backstage Portal** | Template SpecKit configurato, scorecards, SLO templates |
| **Monitoring Stack** | Prometheus + Grafana + Loki + Alertmanager operativi |
| **Auto-remediation** | Webhook receiver attivo per fix automatici |

### Cosa Necessita Intervento ⚠️

| Area | Problema |
|------|----------|
| **nautilus_dev** | 6 test files fuori posto, 305MB cache in git, .gitignore incompleto |
| **LiquidationHeatmap** | .gitignore incompleto, backup files, 595MB .venv in git |
| **Metrics → QuestDB** | Hooks configurati ma verificare connessione attiva |
| **Backstage ↔ Metrics** | Dashboard Grafana non mostra dati (datasource UID) |

---

## Piano di Implementazione

### FASE 1: Repository Cleanup (Priorità Alta)

#### 1.1 nautilus_dev
```bash
# Spostare test files
mv scripts/test_*.py tests/scripts/
mv scripts/hyperliquid/test_orders.py tests/scripts/hyperliquid/

# Aggiornare .gitignore
echo ".mypy_cache/" >> .gitignore
echo ".ruff_cache/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
echo ".coverage" >> .gitignore
echo "htmlcov/" >> .gitignore

# Rimuovere cache da git history
git rm -r --cached .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage
```

#### 1.2 LiquidationHeatmap
```bash
# Aggiornare .gitignore
cat >> .gitignore << 'EOF'
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.hypothesis/
*.backup*
test_output.log
logs/
EOF

# Rimuovere backup files
rm ingest_full_history_n8n.py.backup_*

# Rimuovere duplicati
rm .claude/settings.local\ copy.json
```

#### 1.3 Tutte le Repo - Standard .gitignore
Creare template standard da applicare a tutte le repo.

---

### FASE 2: Metrics Integration Verification

#### 2.1 Verificare QuestDB Connection
```bash
# Test connessione ILP
echo "claude_test,source=verification value=1 $(date +%s)000000000" | nc -q1 localhost 9009

# Verificare tabelle esistenti
curl -G --data-urlencode "query=SHOW TABLES" http://localhost:9000/exec
```

#### 2.2 Verificare Hooks Attivi
```bash
# Check hooks in settings.json
cat ~/.claude/settings.json | jq '.hooks'

# Verificare metrics recenti
tail -100 ~/.claude/metrics/daily.jsonl | jq -s 'length'
```

#### 2.3 Creare Dashboard Claude Metrics in Grafana
- Tool usage over time
- Session duration
- Error rates
- TDD compliance
- Rework rate

---

### FASE 3: Backstage Consolidation

#### 3.1 Fix Grafana Datasource UID
```bash
# Verificare UID datasource
curl -s "http://admin:admin@localhost:3000/api/datasources" | jq '.[].uid'

# Aggiornare dashboard con UID corretto
```

#### 3.2 Verificare GitHub Discovery
```bash
# Check entità scoperte
docker logs backstage-portal 2>&1 | grep "github-provider"
```

#### 3.3 Template Repository Validation
- Verificare che il template SpecKit crei repo corrette
- Test scaffolding di una repo di prova

---

### FASE 4: Cross-Project Validation Script

#### 4.1 Creare Script di Validazione Enterprise
```python
# ~/.claude/scripts/enterprise-validator.py
# Checks:
# 1. Ogni repo ha catalog-info.yaml
# 2. Ogni repo ha .claude/validation/config.json
# 3. .gitignore è completo
# 4. Nessun file cache in git
# 5. Test files nella posizione corretta
# 6. CLAUDE.md presente e aggiornato
# 7. Metrics collection attiva
```

#### 4.2 Aggiungere a Cron
```bash
# Daily enterprise validation
0 8 * * * /usr/bin/python3 ~/.claude/scripts/enterprise-validator.py >> ~/.claude/logs/enterprise-validation.log 2>&1
```

---

### FASE 5: Documentation & Runbooks

#### 5.1 Aggiornare INFRASTRUCTURE.md
- Aggiungere sezione Loki/Promtail
- Aggiungere sezione Alertmanager
- Documentare auto-remediation

#### 5.2 Creare Runbooks per Alert
```
~/.claude/runbooks/
├── backstage-down.md
├── n8n-down.md
├── database-issues.md
├── disk-space-low.md
└── high-memory.md
```

---

## Deliverables

| # | Deliverable | Tempo Stimato |
|---|-------------|---------------|
| 1 | nautilus_dev cleanup | 10 min |
| 2 | LiquidationHeatmap cleanup | 10 min |
| 3 | Standard .gitignore template | 5 min |
| 4 | QuestDB metrics verification | 10 min |
| 5 | Grafana dashboard Claude metrics | 15 min |
| 6 | Backstage datasource fix | 5 min |
| 7 | Enterprise validator script | 20 min |
| 8 | Runbooks creation | 15 min |

**Totale stimato: ~90 minuti**

---

## Rischi e Mitigazioni

| Rischio | Mitigazione |
|---------|-------------|
| Perdita dati durante cleanup | Backup prima di ogni operazione |
| Breaking CI/CD | Verificare pipeline dopo ogni modifica |
| Metrics gap | Mantenere vecchi file fino a verifica nuovi |

---

## Success Criteria

- [ ] Tutte le repo passano enterprise-validator senza errori
- [ ] Grafana mostra metriche Claude da QuestDB
- [ ] Backstage mostra tutte le entità senza errori
- [ ] Nessun file cache/artifact nei repository git
- [ ] Alert attivi inviano notifiche Discord
- [ ] Auto-remediation funziona per container critici
