#!/bin/bash
# Propaga fix modelli verificationChain a tutte le repo in /media/sam/1TB/
# FIX: gemini-2.5-flash-preview-05-20 -> google/gemini-3-flash-preview
# FIX: moonshotai/kimi-k2-5 -> moonshotai/kimi-k2.5

set -e

REPOS_DIR="/media/sam/1TB"
FIXED=0
SKIPPED=0

echo "=== Propagating config.yaml fixes ==="

for dir in "$REPOS_DIR"/*/.claude-flow; do
    if [ -d "$dir" ]; then
        config_file="$dir/config.yaml"
        if [ -f "$config_file" ]; then
            repo_name=$(dirname "$dir" | xargs basename)

            # Check if fix needed
            if grep -q "gemini-2.5-flash-preview-05-20\|moonshotai/kimi-k2-5" "$config_file" 2>/dev/null; then
                echo "Fixing: $repo_name"

                # Apply fixes
                sed -i 's/gemini-2.5-flash-preview-05-20/google\/gemini-3-flash-preview/g' "$config_file"
                sed -i 's/moonshotai\/kimi-k2-5/moonshotai\/kimi-k2.5/g' "$config_file"

                FIXED=$((FIXED + 1))
            else
                echo "OK: $repo_name (already fixed or different config)"
                SKIPPED=$((SKIPPED + 1))
            fi
        fi
    fi
done

echo ""
echo "=== Summary ==="
echo "Fixed: $FIXED"
echo "Skipped: $SKIPPED"
