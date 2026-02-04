#!/bin/bash
# Wrapper per claude-flow init con patch selettiva
# Mantiene nuove feature da npm, fixa solo i model names buggy

echo "=== Claude-Flow Init (with patches) ==="

# 1. Esegui init standard (prendi struttura aggiornata)
npx @claude-flow/cli@latest init "$@"

# 2. Patch selettiva SOLO dei campi problematici
if [ -f ".claude-flow/config.yaml" ]; then
    # Fix model names (pattern noti buggy)
    sed -i 's/gemini-2\.5-flash-preview-05-20/google\/gemini-3-flash-preview/g' .claude-flow/config.yaml
    sed -i 's/gemini-2\.5-flash-preview/google\/gemini-3-flash-preview/g' .claude-flow/config.yaml
    sed -i 's/kimi-k2-5/kimi-k2.5/g' .claude-flow/config.yaml

    # Verifica
    if grep -qE 'gemini-2\.5-flash-preview-05-20|kimi-k2-5' .claude-flow/config.yaml; then
        echo "⚠️ WARNING: Pattern buggy ancora presenti"
    else
        echo "✅ Config patchato correttamente"
    fi
else
    echo "❌ config.yaml non creato"
    exit 1
fi

echo "=== Init completato ==="
