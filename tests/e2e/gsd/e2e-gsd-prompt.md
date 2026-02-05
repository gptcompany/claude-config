# GSD E2E Test - Prompt per Nuova Sessione

## Istruzioni Pre-Test

1. Apri **NUOVA** sessione Claude Code (non questa!)
2. `cd` nella repo creata da `e2e-gsd-setup.sh`
3. Copia e incolla il prompt sotto

---

## Prompt da Copiare

```
Esegui il pipeline GSD completo per questo progetto Calculator CLI.
Il progetto ha già PROJECT.md e ROADMAP.md pronti.

Procedi con le fasi in ordine:

1. /gsd:research-phase 01
2. /gsd:discuss-phase 01
3. /gsd:plan-phase 01
4. /gsd:execute-phase 01
5. /gsd:verify-work
6. /gsd:sync-github --create-project

Esegui ogni fase e attendi il mio OK prima di procedere alla successiva.
Inizia con /gsd:research-phase 01
```

---

## Fasi Dettagliate (per riferimento)

### FASE 1 - Research Phase 01
```
/gsd:research-phase 01
```
- Cerca documentazione Click, pattern CLI Python
- Salva findings in memory claude-flow

### FASE 2 - Discuss Phase 01
```
/gsd:discuss-phase 01
```
- Rispondi alle domande (se presenti)
- Output JSON round tracking

### FASE 3 - Plan Phase 01
```
/gsd:plan-phase 01
```
- Genera `.planning/plans/PLAN-01-01.md`
- Include task breakdown dettagliato

### FASE 4 - Execute Phase 01
```
/gsd:execute-phase 01
```
- Implementa codice in `src/calculator/`
- Crea test in `tests/`
- Salva checkpoint memory

### FASE 5 - Verify
```
/gsd:verify-work
```
- Esegue test
- Verifica acceptance criteria
- UAT interattivo

### FASE 6 - Sync GitHub
```
/gsd:sync-github --create-project
```
- Crea milestone su GitHub
- Crea issues per ogni task
- Crea project board (se disponibile)

---

## Post-Test

Dopo completamento di tutte le fasi:

```bash
# Verifica risultati
~/.claude/tests/e2e/gsd/e2e-gsd-verify.sh /tmp/e2e-gsd-calculator-*

# Cleanup (opzionale)
~/.claude/tests/e2e/gsd/e2e-gsd-cleanup.sh /tmp/e2e-gsd-calculator-*
```
