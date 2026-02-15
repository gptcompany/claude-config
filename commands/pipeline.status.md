---
name: pipeline:status
description: Show current pipeline state from claude-flow memory. Usage: /pipeline:status [gsd|speckit] [phase|spec]
---

# /pipeline:status - Pipeline State Viewer

Mostra lo stato corrente del pipeline leggendo dalla memoria claude-flow.

## Usage

```bash
/pipeline:status              # Auto-detect e mostra stato
/pipeline:status gsd          # Mostra tutte le fasi GSD
/pipeline:status gsd 05       # Mostra stato fase 05
/pipeline:status speckit      # Mostra tutte le spec
/pipeline:status speckit 03   # Mostra stato spec 03
```

## Execution

Quando invocato, Claude Code esegue:

### 1. Query Memory

```bash
# Per GSD
npx @claude-flow/cli@latest memory search --query "gsd:*" --namespace pipeline --limit 50

# Per SpecKit
npx @claude-flow/cli@latest memory search --query "speckit:*" --namespace pipeline --limit 50

# O specifico
npx @claude-flow/cli@latest memory search --query "gsd:*:05:*" --namespace pipeline
```

### 2. Parse e Display

```python
FRAMEWORK = "$ARGUMENTS".split()[0] if "$ARGUMENTS" else "auto"
TARGET = "$ARGUMENTS".split()[1] if len("$ARGUMENTS".split()) > 1 else None

# Query memory
if FRAMEWORK == "auto":
    gsd_entries = memory_search("gsd:*", namespace="pipeline")
    speckit_entries = memory_search("speckit:*", namespace="pipeline")

    if gsd_entries and not speckit_entries:
        FRAMEWORK = "gsd"
    elif speckit_entries and not gsd_entries:
        FRAMEWORK = "speckit"
    else:
        # Mostra entrambi
        pass

# Build status table
for entry in entries:
    key_parts = entry.key.split(":")
    # gsd:{project}:{phase}:step{N} or speckit:{spec}:step{N}

    step = key_parts[-1]
    status = entry.value.get("status")
    timestamp = entry.value.get("timestamp")

    print(f"  {step}: {status_emoji(status)} {status}")
```

## Output Format

```
════════════════════════════════════════
  PIPELINE STATUS
════════════════════════════════════════

📦 Framework: GSD
📁 Project: nautilus_dev
📍 Phase: 05

┌──────────┬──────────┬─────────────────┐
│ Step     │ Status   │ Timestamp       │
├──────────┼──────────┼─────────────────┤
│ step1    │ ✅ done  │ 2026-02-04 15:30│
│ step2    │ ✅ done  │ 2026-02-04 15:45│
│ step3    │ ✅ done  │ 2026-02-04 16:00│
│ step4    │ 🔄 iter  │ 2026-02-04 16:15│
│ step5    │ ⏳ pend  │ -               │
│ step6    │ ⏳ pend  │ -               │
│ step7    │ ⏳ pend  │ -               │
│ step8    │ ⏳ pend  │ -               │
└──────────┴──────────┴─────────────────┘

📊 Progress: 3/8 steps (37%)
⏭️ Next: step4 (iterating)

Suggested command:
→ /pipeline:gsd 05

════════════════════════════════════════
```

## Status Emojis

| Status | Emoji | Meaning |
|--------|-------|---------|
| done | ✅ | Completato |
| starting | 🟡 | In corso |
| iterating | 🔄 | Iterazione |
| blocked | 🛑 | Bloccato (human review) |
| error | ❌ | Errore |
| pending | ⏳ | Non iniziato |

## Resume Suggestion

Se trova uno step incompleto, suggerisce:

```
⚠️ Incomplete pipeline detected!

Last completed: step3
Current: step4 (iterating)

Options:
  → /pipeline:gsd 05           # Resume from step4
  → /pipeline:gsd 05 --restart # Start fresh
```

## Memory Cleanup

Per pulire vecchi stati:

```bash
npx @claude-flow/cli@latest memory list --namespace pipeline --limit 100
# Poi delete selettivo se necessario
```
