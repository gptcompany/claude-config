#!/bin/bash
# Propaga fix config.yaml a tutte le repo con .claude-flow/

echo "=== PROPAGAZIONE CONFIG.YAML FIX ==="
FIXED=0
SKIPPED=0

for repo in /media/sam/1TB/*/; do
    config="$repo.claude-flow/config.yaml"
    if [ -f "$config" ]; then
        # Backup
        cp "$config" "$config.bak-$(date +%Y%m%d)"

        # Fix model names
        sed -i 's/gemini-2.5-flash-preview-05-20/google\/gemini-3-flash-preview/g' "$config"
        sed -i 's/gemini-2\.5-flash-preview-05-20/google\/gemini-3-flash-preview/g' "$config"
        sed -i 's/kimi-k2-5/kimi-k2.5/g' "$config"

        echo "✅ Fixed: $(basename $repo)"
        ((FIXED++))
    else
        ((SKIPPED++))
    fi
done

# Fix anche in validation-framework se non già fatto
VF_CONFIG="$HOME/.claude/validation-framework/.claude-flow/config.yaml"
if [ -f "$VF_CONFIG" ]; then
    sed -i 's/gemini-2.5-flash-preview-05-20/google\/gemini-3-flash-preview/g' "$VF_CONFIG"
    sed -i 's/kimi-k2-5/kimi-k2.5/g' "$VF_CONFIG"
    echo "✅ Fixed: validation-framework"
fi

echo ""
echo "=== RISULTATO ==="
echo "Fixed: $FIXED repo"
echo "Skipped: $SKIPPED (no config.yaml)"
echo ""
echo "Verifica con:"
echo "grep -r 'gemini-2.5-flash-preview-05-20\|kimi-k2-5' /media/sam/1TB/*/.claude-flow/config.yaml 2>/dev/null && echo '❌ Ancora da fixare' || echo '✅ Tutti fixati'"
