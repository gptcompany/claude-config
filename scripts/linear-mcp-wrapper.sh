#!/bin/bash
# Linear MCP wrapper - loads API key from dotenvx at runtime
# Location: ~/.claude/scripts/linear-mcp-wrapper.sh
# SSOT: /media/sam/1TB/.env

export LINEAR_API_KEY=$(/home/sam/.local/bin/dotenvx get LINEAR_API_KEY -f /media/sam/1TB/.env 2>/dev/null)

if [ -z "$LINEAR_API_KEY" ]; then
    echo "ERROR: Failed to load LINEAR_API_KEY from dotenvx" >&2
    exit 1
fi

exec npx -y @mseep/linear-mcp "$@"
