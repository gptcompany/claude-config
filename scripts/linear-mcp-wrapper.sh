#!/bin/bash
# Linear MCP wrapper - loads API key from SOPS at runtime
# Location: ~/.claude/scripts/linear-mcp-wrapper.sh
# SSOT: /media/sam/1TB/.env.enc

export LINEAR_API_KEY=$(sops -d --input-type dotenv --output-type dotenv /media/sam/1TB/.env.enc 2>/dev/null | grep "^LINEAR_API_KEY=" | cut -d= -f2)

if [ -z "$LINEAR_API_KEY" ]; then
    echo "ERROR: Failed to load LINEAR_API_KEY from SOPS" >&2
    exit 1
fi

exec npx -y @mseep/linear-mcp "$@"
