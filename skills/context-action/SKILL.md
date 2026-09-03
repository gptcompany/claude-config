# /context-action - Gestione Context Alto

Quando il context è alto (>70%), usa questo skill per scegliere l'azione.

## Execution

Quando invocato, Claude Code DEVE:

1. **Mostrare menu con AskUserQuestion**:

```javascript
AskUserQuestion({
  questions: [{
    question: "Context alto - quale azione vuoi eseguire?",
    header: "Context",
    options: [
      {label: "Aggiorna stato + /compact", description: "Aggiorna gli artefatti del workflow, poi compatta"},
      {label: "Aggiorna stato + nuova sessione", description: "Aggiorna gli artefatti e prepara un handoff"},
      {label: "Solo /compact", description: "Compatta usando la history nativa"},
      {label: "Ignora", description: "Continua senza azione"}
    ],
    multiSelect: false
  }]
})
```

2. **Eseguire azione scelta**:

- **Aggiorna stato + /compact**:
  Aggiornare soltanto gli artefatti gia adottati dal workflow corrente, per
  esempio `tasks.md`, il ledger di review e l'handoff del coordinator. Non
  creare un secondo database di sessione. Poi suggerire `/compact`.

- **Aggiorna stato + nuova sessione**:
  Aggiornare gli stessi artefatti e scrivere un handoff conciso che contenga
  obiettivo, stato verificato, blocchi e prossima azione. Poi suggerire una
  nuova sessione o un resume esplicito.

- **Solo /compact**:
  Suggerire `/compact`

- **Ignora**:
  Continuare normalmente
