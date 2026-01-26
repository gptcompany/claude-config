# Phase 18: Validator Depth - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning
**Decision:** Connect existing validators (via consistency check)

<vision>
## How This Should Work

I validator visual e behavioral **esistono già e funzionano** (148 tests passing).
Il problema è che NON sono collegati all'orchestrator.

Quando l'utente modifica codice (Write/Edit), il hook `validation-orchestrator.js` già chiama `orchestrator.py`. Ma l'orchestrator usa STUB invece delle implementazioni reali.

**Gap identificato:**
```python
# orchestrator.py OGGI:
VALIDATOR_REGISTRY = {
    "visual": BaseValidator,        # ← STUB!
    # "behavioral": ???             # ← MANCANTE!
}
```

**Dopo Phase 18:**
```python
VALIDATOR_REGISTRY = {
    "visual": VisualTargetValidator,    # ← REALE
    "behavioral": BehavioralValidator,  # ← AGGIUNTO
}
```

</vision>

<essential>
## What Must Be Nailed

- **Collegare** VisualTargetValidator e BehavioralValidator all'orchestrator
- **Aggiungere** visual e behavioral ai default dimensions (Tier 3)
- **Non rompere** il sistema esistente (148 tests devono continuare a passare)
- **Graceful fallback** se ODiff/SSIM/ZSS non disponibili

</essential>

<specifics>
## Specific Ideas

### Verifica di Consistenza (completata)

| Componente | Stato | Test |
|------------|-------|------|
| VisualTargetValidator | ✅ OK | 74 passing |
| BehavioralValidator | ✅ OK | 74 passing |
| ODiff (pixel diff) | ✅ Disponibile | - |
| SSIM (perceptual) | ✅ Disponibile | - |
| ZSS (tree edit) | ✅ Disponibile | - |
| Hook PostToolUse | ✅ Configurato | - |
| Orchestrator Registry | ❌ STUB | da fixare |

### Scope Ridotto

Non servono 4 plans separati. Serve:

1. **Un singolo plan** che:
   - Importa i validator nell'orchestrator
   - Aggiorna VALIDATOR_REGISTRY
   - Aggiunge ai default dimensions
   - Testa l'integrazione

**Effort:** ~2h invece di ~8h originali

### Config per Progetto

I validator saranno opt-in via `.claude/validation/config.json`:
```json
{
  "dimensions": {
    "visual": {
      "enabled": true,
      "tier": 3,
      "baseline_dir": ".claude/baselines",
      "threshold": 0.85
    },
    "behavioral": {
      "enabled": true,
      "tier": 3,
      "similarity_threshold": 0.90
    }
  }
}
```

</specifics>

<notes>
## Additional Context

### Vincolo Importante

**NON modificare GSD/Speckit** - sono tool esterni terze parti.

La soluzione usa il sistema hooks esistente:
- `validation-orchestrator.js` già esiste e funziona
- Chiama `orchestrator.py` su ogni Write/Edit
- Basta collegare i validator, il resto è automatico

### Integrazione con Phase Successive

| Phase | Integrazione |
|-------|-------------|
| **19 - Hardening** | Può aggiungere timeout/retry ai validator ora funzionanti |
| **20 - Multi-Project** | Config inheritance già supportata |
| **17 - Observability** | Risultati già vanno a QuestDB/Grafana |

### Test Esistenti

- 74 tests visual validator
- 74 tests behavioral validator
- Copertura completa, solo da integrare

</notes>

---

*Phase: 18-validator-depth*
*Context gathered: 2026-01-26*
*Decision method: Consistency check + gap analysis*
