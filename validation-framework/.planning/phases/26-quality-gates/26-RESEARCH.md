# Phase 26: Quality Gates Integration - Research

**Researched:** 2026-02-02
**Domain:** Git hooks + validation framework integration for OpenClaw autonomous loop
**Confidence:** HIGH

<research_summary>
## Summary

Phase 26 integra il validation framework esistente come quality gate nel workflow Git dell'OpenClaw agent. L'obiettivo e impedire che codice di bassa qualita raggiunga main tramite git hooks pre-commit/pre-push che invocano l'orchestrator.

Il dominio e interamente interno: orchestrator.py gia supporta CLI con tier selection e `--files` per file modificati. exec-approvals gia configurato su tutti gli agent. Nessuna libreria esterna necessaria.

**Primary recommendation:** Creare hook scripts shell che invocano `python3 orchestrator.py` con tier appropriato, installarli via `git config core.hooksPath`, e auditare exec-approvals per garantire che gli agent possano eseguire validation.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| orchestrator.py | ~/.claude/templates/validation/ | 14-dimension validation CLI | Esistente, 1917 LOC |
| exec-approvals.json | /home/openclaw/.openclaw/ | Allowlist comandi agent | Esistente, security: allowlist |
| openclaw.json | Gateway container | Agent config con hooks | Esistente, 4 agent configurati |

### Git Hook Mechanism
| Approach | How | Tradeoff |
|----------|-----|----------|
| `core.hooksPath` | `git config core.hooksPath .githooks/` | Versionabile, portabile |
| `.git/hooks/` | Symlink o copia diretta | Non versionabile |
| pre-commit framework | `pip install pre-commit` | Overkill per uso interno |

**Raccomandazione:** `core.hooksPath` con directory `.githooks/` versionata nel repo. Niente pre-commit framework (YAGNI).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Shell hooks | pre-commit (Python) | Troppo overhead per 2 hook |
| Orchestrator CLI | Inline validation | Duplicazione, non DRY |
| Branch protection | GitHub API rules | Richiede PAT, aggiunge friction |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Hook Structure
```
.githooks/
├── pre-commit       # Tier 1 (quick) su staged files
└── pre-push         # Tier 1+2 su tutti i file modificati nel push
```

### Pattern 1: Staged-Files-Only Pre-Commit
**What:** Hook che valida solo i file staged, non tutto il repo
**When to use:** Sempre per pre-commit (velocita)
**Example:**
```bash
#!/bin/bash
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|ts|js)$')
if [ -n "$STAGED" ]; then
    python3 ~/.claude/templates/validation/orchestrator.py quick --files $STAGED
fi
```

### Pattern 2: Bypass per Agent
**What:** OpenClaw agent puo bypassare hooks con flag specifico
**When to use:** Quando l'agent ha gia validato pre-commit (validation-gate hook Phase 23)
**Note:** `--no-verify` gia nella allowlist exec-approvals? Da verificare.

### Anti-Patterns to Avoid
- **Validazione completa in pre-commit:** Troppo lenta, blocca il workflow
- **Hook non-bypassabile:** L'agent deve poter usare `--no-verify` dopo aver validato
- **Branch protection via GitHub API:** Aggiunge complessita per un solo developer
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Validation logic | Custom checks in hook | orchestrator.py CLI | Gia 14 dimensioni, testato |
| File filtering | Regex in hook | `git diff --name-only` | Git gestisce meglio |
| Exit codes | Custom error handling | orchestrator.py exit codes (0=pass, 1=fail) | Gia implementato |

**Key insight:** L'orchestrator e gia il quality gate. Gli hook sono solo glue scripts di 10-15 righe.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Hook troppo lento
**What goes wrong:** Pre-commit che esegue tutti i tier blocca per minuti
**Why it happens:** Validazione completa non necessaria per ogni commit
**How to avoid:** Pre-commit = Tier 1 (quick, <5s). Pre-push = Tier 1+2.
**Warning signs:** Developer bypassa sempre con --no-verify

### Pitfall 2: Hook non installato su agent
**What goes wrong:** Agent committa senza validation
**Why it happens:** `core.hooksPath` non configurato nel workspace dell'agent
**How to avoid:** Bootstrap script che setta `git config core.hooksPath` nel workspace
**Warning signs:** Commit senza validation in git log

### Pitfall 3: exec-approvals blocca validation
**What goes wrong:** Agent non puo eseguire python3/orchestrator
**Why it happens:** python3 non nella allowlist
**How to avoid:** Audit exec-approvals, verificare python3 + orchestrator path
**Warning signs:** Hook fallisce silenziosamente
</common_pitfalls>

<open_questions>
## Open Questions

1. **Agent bypass policy**
   - What we know: validation-gate hook (Phase 23) gia valida al bootstrap
   - What's unclear: L'agent deve ri-validare al commit se ha gia validato al bootstrap?
   - Recommendation: Pre-commit = always run (e veloce). Niente bypass automatico.

2. **Branch strategy enforcement**
   - What we know: ROADMAP menziona "branch strategy feature→main"
   - What's unclear: OpenClaw committa direttamente su main o usa feature branches?
   - Recommendation: Verificare workflow attuale dell'agent, decidere in planning.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- orchestrator.py CLI interface (read directly, lines 1898-1917)
- exec-approvals.json config (from Phase 22 SUMMARY)
- OpenClaw hooks config (from Phase 23 SUMMARY)

### Secondary (MEDIUM confidence)
- Git hooks documentation (`man githooks`) — standard, stable API
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Git hooks + existing orchestrator.py
- Ecosystem: Nessuna libreria esterna necessaria
- Patterns: Staged-files validation, tiered execution
- Pitfalls: Performance, agent integration, exec-approvals

**Confidence breakdown:**
- Standard stack: HIGH — tutto interno, codice gia letto
- Architecture: HIGH — pattern git hooks ben noti
- Pitfalls: HIGH — basati su esperienza fasi precedenti
- Code examples: HIGH — orchestrator CLI gia verificato

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days — internal tooling, stabile)
</metadata>

---

*Phase: 26-quality-gates*
*Research completed: 2026-02-02*
*Ready for planning: yes*
