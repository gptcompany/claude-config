# SpecKit E2E Test - Prompt per Nuova Sessione

## Istruzioni Pre-Test

1. Apri **NUOVA** sessione Claude Code (non questa!)
2. `cd` nella repo creata da `e2e-speckit-setup.sh`
3. Copia e incolla il prompt sotto

---

## Prompt da Copiare

```
Esegui il pipeline SpecKit completo per la spec 01-calculator-cli.
La spec e' gia' presente in specs/01-calculator-cli.md.

Procedi con le fasi in ordine:

1. /speckit.specify 01  (verifica spec esistente)
2. /speckit.clarify 01
3. /speckit.plan 01
4. /speckit.tasks 01
5. /speckit.analyze 01
6. /speckit.implement 01
7. /validate quick
8. /speckit.taskstoissues 01

Esegui ogni fase e attendi il mio OK prima di procedere alla successiva.
Inizia con /speckit.specify 01
```

---

## Fasi Dettagliate (per riferimento)

### FASE 1 - Specify
```
/speckit.specify 01
```
- Verifica spec esistente
- Aggiunge dettagli mancanti se necessario

### FASE 2 - Clarify
```
/speckit.clarify 01
```
- Pone domande di chiarimento
- Rispondere con dettagli quando richiesto
- Aggiorna spec con risposte

### FASE 3 - Plan
```
/speckit.plan 01
```
- Genera `specs/01-calculator-cli/plan.md`
- Include architettura e design decisions

### FASE 4 - Tasks
```
/speckit.tasks 01
```
- Genera `specs/01-calculator-cli/tasks.md`
- Task ordinati per dipendenza

### FASE 5 - Analyze
```
/speckit.analyze 01
```
- Verifica consistenza tra spec, plan, tasks
- Report di quality issues

### FASE 6 - Implement
```
/speckit.implement 01
```
- Implementa codice in `src/calculator/`
- Crea test in `tests/`
- Segue tasks.md in ordine

### FASE 7 - Validate
```
/validate quick
```
- Esegue validazione Tier 1-2
- Verifica security, tests, coverage

### FASE 8 - Sync GitHub
```
/speckit.taskstoissues 01
```
- Crea GitHub issues da tasks.md
- Assegna labels e milestone

---

## Post-Test

Dopo completamento di tutte le fasi:

```bash
# Verifica risultati
~/.claude/tests/e2e/speckit/e2e-speckit-verify.sh /tmp/e2e-speckit-calculator-*

# Cleanup (opzionale)
~/.claude/tests/e2e/speckit/e2e-speckit-cleanup.sh /tmp/e2e-speckit-calculator-*
```

---

## Note per il Test

1. **Clarify**: Quando Claude pone domande, rispondi con:
   - "Usa precisione default 2 decimali"
   - "Output su stdout, errori su stderr"
   - "Nessuna validazione input avanzata richiesta"

2. **Implement**: Se chiede conferma per procedere, conferma sempre

3. **Validate**: Se ci sono warning, sono accettabili per il test E2E
