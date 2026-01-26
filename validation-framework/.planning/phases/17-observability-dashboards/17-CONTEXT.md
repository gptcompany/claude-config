# Phase 17: Observability & Dashboards - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<vision>
## How This Should Work

Alert-first observability: il sistema ti avvisa quando qualcosa va storto, non devi guardare dashboard costantemente.

Quando apri Grafana, vedi lo storico: quali validator falliscono di più, trend nel tempo, pattern per progetto. Non real-time polling - i dati sono già in QuestDB, basta visualizzarli.

CLI per report veloci: `validation-report --last-week` senza aprire browser.

</vision>

<essential>
## What Must Be Nailed

- **Alert immediati** - Discord notification quando Tier 1 fallisce, senza dover guardare niente
- **Storico queryable** - Poter rispondere a "quali validator falliscono di più questa settimana?"
- **Zero friction** - Non aggiungere overhead al workflow quotidiano

</essential>

<specifics>
## Specific Ideas

- Discord webhook per alert (già usato per altri alert nel sistema)
- QuestDB ha già i dati (`claude_validation_results` table)
- Grafana già configurato, serve solo creare i dashboard
- CLI report per chi preferisce terminale a browser
- NO real-time WebSocket - YAGNI, aggiungere solo se serve

</specifics>

<notes>
## Additional Context

Expert council analysis scelta: Opzione Ibrida C → B (Alert-first + Storico)

Rationale:
1. Alert-first = valore immediato senza friction
2. Storico = insight quando accumuli dati (dopo 1-2 settimane uso)
3. Real-time = skip per ora, aggiungere se emerge necessità

Execution order rivisto:
- 17-01: Alert rules (Discord) - immediate value
- 17-02: QuestDB queries + views - foundation
- 17-03: Grafana storico dashboards - visualization
- 17-04: Reporting CLI - terminal-first users

</notes>

---

*Phase: 17-observability-dashboards*
*Context gathered: 2026-01-26*
