# Phase 18: Validator Depth - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning
**Decision:** E2E Integration (via SWOT + PMW analysis)

<vision>
## How This Should Work

I validator visual, behavioral e performance esistono già (v3.0) ma sono "dormant" - non vengono chiamati automaticamente dai workflow GSD.

Phase 18 collega questi pezzi esistenti:
- **v3.0**: VisualTargetValidator, BehavioralValidator, PerformanceValidator
- **v5.0**: GSD workflows (execute-plan, verify-work, complete-milestone)
- **Phase 17**: Infrastruttura osservabilità (Grafana, QuestDB, CLI)

Quando un utente esegue `/gsd:verify-work`, i validator dovrebbero:
1. Eseguire automaticamente (se configurati per il progetto)
2. Catturare screenshot e confrontarli con baseline
3. Verificare DOM structure se behavioral test abilitato
4. Eseguire Lighthouse se performance test abilitato
5. Inviare risultati a QuestDB per visualizzazione in Grafana

Deve essere **opt-in** per progetto via `.claude/validation/config.json`.

</vision>

<essential>
## What Must Be Nailed

- **Hook nei workflow GSD** - verify-work chiama i validator automaticamente
- **Configurabilità** - ogni progetto decide quali validator abilitare
- **Fallback graceful** - se un validator fallisce (es. no browser), non blocca tutto
- **Metriche in Grafana** - risultati visual/behavioral visibili nei dashboard Phase 17

</essential>

<specifics>
## Specific Ideas

- Visual validator usa ODiff (pixel) + SSIM (perceptual) già implementati
- Behavioral validator usa Zhang-Shasha DOM diff già implementato
- Performance validator integra Lighthouse CI (già in v2.0)
- **Skip Mathematical validator** - troppo specializzato, pochi progetti lo usano
- Config esempio:
  ```json
  {
    "validators": {
      "visual": { "enabled": true, "baseline_dir": ".claude/baselines" },
      "behavioral": { "enabled": false },
      "performance": { "enabled": true, "thresholds": { "lcp": 2500 } }
    }
  }
  ```

</specifics>

<notes>
## Additional Context

**Decisione presa via SWOT + PMW analysis:**

| Opzione | Verdetto |
|---------|----------|
| A. Potenziamento | Scartata - ROI basso, validator già funzionano |
| B. E2E Integration | **SCELTA** - collega pezzi esistenti, valore immediato |
| C. Skip → Phase 19 | Scartata - validator rimarrebbero dormant |

**Rischi identificati:**
- Rallentamento pipeline se validator lenti → mitigation: timeout + parallel execution
- Browser non disponibile in CI → mitigation: skip graceful con warning

**Dipendenze:**
- Phase 17 complete (Grafana dashboards per visualizzare risultati)
- v5.0 GSD workflows (dove hookare i validator)

</notes>

---

*Phase: 18-validator-depth*
*Context gathered: 2026-01-26*
*Decision method: Council of Experts (SWOT + PMW)*
