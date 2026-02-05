#!/bin/bash
# E2E GSD Cleanup - Rimuove repo test
# Usage: ./e2e-gsd-cleanup.sh [repo_path]

set +e

REPO_PATH="${1:-$(cat /tmp/e2e-gsd-last-repo.txt 2>/dev/null)}"

if [ -z "$REPO_PATH" ]; then
    echo "Usage: $0 <repo_path>"
    exit 1
fi

REPO_NAME=$(basename "$REPO_PATH")

echo "==========================================="
echo "  GSD E2E Cleanup"
echo "==========================================="
echo ""
echo "  Repo: $REPO_PATH"
echo "  GitHub: gptcompany/$REPO_NAME"
echo ""

read -p "Sei sicuro di voler eliminare? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

# 1. Delete GitHub repo
echo "[1/3] Deleting GitHub repository..."
if gh repo delete "gptcompany/$REPO_NAME" --yes 2>/dev/null; then
    echo "  GitHub repo deleted"
else
    echo "  [WARN] GitHub repo not found or already deleted"
fi

# 2. Delete local repo
echo "[2/3] Deleting local repository..."
if [ -d "$REPO_PATH" ]; then
    rm -rf "$REPO_PATH"
    echo "  Local repo deleted"
else
    echo "  [WARN] Local repo not found"
fi

# 3. Cleanup temp files
echo "[3/3] Cleaning temp files..."
rm -f /tmp/e2e-gsd-last-repo.txt 2>/dev/null

echo ""
echo "Cleanup complete."
