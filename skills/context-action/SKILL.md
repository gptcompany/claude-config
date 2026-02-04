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
      {label: "Checkpoint + /compact", description: "Salva stato in claude-flow, poi compatta"},
      {label: "Checkpoint + /clear", description: "Salva stato, poi nuova sessione"},
      {label: "Solo /compact", description: "Compatta senza salvare"},
      {label: "Ignora", description: "Continua senza azione"}
    ],
    multiSelect: false
  }]
})
```

2. **Eseguire azione scelta**:

- **Checkpoint + /compact**:
  ```bash
  npx @claude-flow/cli@latest session save --name "pre-compact-$(date +%Y%m%d-%H%M%S)"
  ```
  Poi suggerire `/compact`

- **Checkpoint + /clear**:
  ```bash
  npx @claude-flow/cli@latest session save --name "pre-clear-$(date +%Y%m%d-%H%M%S)"
  ```
  Poi suggerire `/clear`

- **Solo /compact**:
  Suggerire `/compact`

- **Ignora**:
  Continuare normalmente
