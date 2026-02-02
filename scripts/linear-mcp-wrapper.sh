#!/bin/bash
# Linear MCP wrapper - loads API key from dotenvx at runtime
# Location: ~/.claude/scripts/linear-mcp-wrapper.sh
# SSOT: /media/sam/1TB/.env (dotenvx encrypted)

exec /home/sam/.local/bin/dotenvx run -f /media/sam/1TB/.env -- npx -y @mseep/linear-mcp "$@"
