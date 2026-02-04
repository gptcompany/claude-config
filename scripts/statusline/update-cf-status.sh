#!/bin/bash
# Update claude-flow statusline cache
# Run via cron every 30s or daemon

CACHE_FILE="$HOME/.claude-flow/statusline-cache.txt"
mkdir -p "$(dirname "$CACHE_FILE")"

# Generate statusline and save to cache
npx @claude-flow/cli@latest hooks statusline 2>/dev/null > "$CACHE_FILE.tmp" && \
  mv "$CACHE_FILE.tmp" "$CACHE_FILE"
