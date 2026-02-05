# E2E Test Suite - GSD e SpecKit Pipelines

Test end-to-end completi per verificare che i pipeline GSD e SpecKit funzionino correttamente su un progetto reale.

## Prerequisiti

- Claude Code installato e funzionante
- `gh` CLI autenticato con accesso a `gptcompany` org
- `npx` disponibile per claude-flow
- Python 3.11+ con pytest

## Quick Start

### GSD Pipeline Test

```bash
# 1. Setup - crea repo test
~/.claude/tests/e2e/gsd/e2e-gsd-setup.sh

# 2. Apri NUOVA sessione Claude Code
# 3. cd /tmp/e2e-gsd-calculator-*
# 4. Copia prompt da e2e-gsd-prompt.md ed esegui

# 5. Dopo completamento, verifica
~/.claude/tests/e2e/gsd/e2e-gsd-verify.sh

# 6. Cleanup
~/.claude/tests/e2e/gsd/e2e-gsd-cleanup.sh
```

### SpecKit Pipeline Test

```bash
# 1. Setup - crea repo test
~/.claude/tests/e2e/speckit/e2e-speckit-setup.sh

# 2. Apri NUOVA sessione Claude Code
# 3. cd /tmp/e2e-speckit-calculator-*
# 4. Copia prompt da e2e-speckit-prompt.md ed esegui

# 5. Dopo completamento, verifica
~/.claude/tests/e2e/speckit/e2e-speckit-verify.sh

# 6. Cleanup
~/.claude/tests/e2e/speckit/e2e-speckit-cleanup.sh
```

## Struttura

```
~/.claude/tests/e2e/
├── README.md                    # Questo file
├── gsd/
│   ├── e2e-gsd-setup.sh        # Crea repo + struttura GSD
│   ├── e2e-gsd-prompt.md       # Prompt da copiare in nuova sessione
│   ├── e2e-gsd-verify.sh       # Verifica post-esecuzione
│   └── e2e-gsd-cleanup.sh      # Rimuove repo test
└── speckit/
    ├── e2e-speckit-setup.sh    # Crea repo + spec iniziale
    ├── e2e-speckit-prompt.md   # Prompt da copiare in nuova sessione
    ├── e2e-speckit-verify.sh   # Verifica post-esecuzione
    └── e2e-speckit-cleanup.sh  # Rimuove repo test
```

## Cosa Viene Testato

### GSD Pipeline

| Fase | Cosa testa |
|------|------------|
| `research-phase` | Ricerca Context7, Semantic Scholar, memory |
| `discuss-phase` | JSON round output, confidence tracking |
| `plan-phase` | Generazione PLAN-XX-YY.md |
| `execute-phase` | Implementazione codice, test |
| `verify-work` | UAT interattivo |
| `sync-github` | Milestones, issues, project board |

Verifica aggiuntiva:
- Claude-flow memory checkpoints
- Session save/restore
- Git history

### SpecKit Pipeline

| Fase | Cosa testa |
|------|------------|
| `specify` | Creazione/validazione spec.md |
| `clarify` | Domande di chiarimento |
| `plan` | Generazione plan.md |
| `tasks` | Generazione tasks.md ordinato |
| `analyze` | Consistenza cross-artifact |
| `implement` | Codice + test |
| `validate` | Validazione 14-dimension |
| `taskstoissues` | GitHub issues da tasks |

Verifica aggiuntiva:
- Acceptance criteria coverage
- Validation report
- Claude-flow memory

## Scoring

I verify script assegnano un punteggio 0-10:

| Score | Significato |
|-------|-------------|
| 10/10 | Tutti i check passano |
| 8-9/10 | Check critici passano, alcuni warning |
| 7/10 | Minimo accettabile |
| <7/10 | Test fallito |

### Check Critici (FAIL se mancano)

- File generati (PLAN.md, plan.md, tasks.md)
- Codice implementato
- Test esistenti e passanti
- Operations matematiche presenti

### Check Warning (non bloccanti)

- GitHub sync
- Memory checkpoints
- Commit messages significativi
- Coverage reports

## Mock Project: Calculator CLI

Entrambi i test usano lo stesso progetto mock:
- CLI calculator Python con Click
- Operazioni: +, -, *, /
- Gestione errori
- Test coverage 80%+

Questo progetto e' abbastanza semplice da completare in ~30 min ma abbastanza complesso da testare l'intero pipeline.

## Troubleshooting

### Setup fallisce

```bash
# Verifica gh auth
gh auth status

# Verifica npx
npx --version

# Verifica accesso org
gh repo list gptcompany --limit 1
```

### Verify mostra molti warning

I warning per GitHub sync e memory sono normali se:
- Repo GitHub non creata (local only mode)
- Claude-flow non inizializzato completamente

### Cleanup non elimina repo GitHub

```bash
# Elimina manualmente
gh repo delete gptcompany/e2e-gsd-calculator-* --yes
gh repo delete gptcompany/e2e-speckit-calculator-* --yes
```

## Integrazione CI

Per eseguire in CI (senza interazione):

```bash
# 1. Setup
./e2e-gsd-setup.sh

# 2. Esegui Claude in batch mode (richiede Claude API)
# TODO: aggiungere supporto batch

# 3. Verify
./e2e-gsd-verify.sh && echo "PASS" || echo "FAIL"
```

## Manutenzione

Questi test vanno aggiornati quando:
- Cambiano i comandi GSD/SpecKit
- Cambiano gli output attesi
- Cambiano le strutture file (.planning/, specs/)
- Cambiano i check di validazione
