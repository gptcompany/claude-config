---
name: fresh-start
description: "Clear context and show next pipeline command. Usage: /fresh-start [gsd|speckit] [phase/spec]"
---

# /fresh-start - Clear e Riparti

Prepara il comando per riprendere dopo il clear.

## Usage

```bash
/fresh-start              # Auto-detect framework e stato
/fresh-start gsd 05       # Prepara /pipeline:gsd 05
/fresh-start speckit 03   # Prepara /pipeline:speckit 03
```

## Execution

Quando invocato:

1. **Detect current state** usando `project_state.py`
2. **Mostra istruzioni chiare**
3. **Termina con il comando da eseguire dopo clear**

```python
import subprocess
import sys

# Detect project state
result = subprocess.run(
    ["python3", "~/.claude/scripts/project_state.py", "--framework", "auto", "--json"],
    capture_output=True, text=True
)

# Parse arguments
args = "$ARGUMENTS".split()
framework = args[0] if args else None
target = args[1] if len(args) > 1 else None

if not framework:
    # Auto-detect from project_state.py
    import json
    state = json.loads(result.stdout)
    framework = state.get("details", {}).get("framework", "gsd")
    target = state.get("phase") or state.get("spec") or ""

# Build next command
if framework == "gsd":
    next_cmd = f"/pipeline:gsd {target}".strip()
elif framework == "speckit":
    next_cmd = f"/pipeline:speckit {target}".strip()
else:
    next_cmd = "/pipeline:gsd"
```

## Output

```
════════════════════════════════════════
  FRESH START
════════════════════════════════════════

📋 Stato attuale salvato
🔄 Esegui ora: /clear

Dopo il clear, esegui:
→ /pipeline:gsd 05

════════════════════════════════════════
```

**IMPORTANTE**: Copia il comando sopra. Dopo `/clear` il contesto sarà vuoto ma il comando suggerito apparirà come ghost text.

## Come funziona

1. Salva lo stato corrente (già in STATE.md / git)
2. Ti dice cosa fare: `/clear`
3. Ti prepara il comando successivo
4. Dopo clear → Tab autocompleta il comando suggerito
