#!/bin/bash
# Trigger N8N Academic Research Pipeline
#
# Usage:
#   trigger-n8n-research.sh "search query"
#   trigger-n8n-research.sh --status
#
# Triggers the finance paper analysis pipeline and optionally
# sends a Discord notification when complete.

set -euo pipefail

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
N8N_WEBHOOK="${N8N_RESEARCH_WEBHOOK:-https://n8nubuntu.princyx.xyz/webhook/779dcea3-a780-4c67-a092-4785d5df68f0}"
N8N_AUTH_TOKEN="${N8N_AUTH_TOKEN:-Admin123!}"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
LOG_FILE="/tmp/research_triggers.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Load Discord webhook from nautilus_dev .env if not set
if [[ -z "$DISCORD_WEBHOOK" ]] && [[ -f "/media/sam/1TB/nautilus_dev/.env" ]]; then
    DISCORD_WEBHOOK=$(grep "^DISCORD_WEBHOOK_URL=" /media/sam/1TB/nautilus_dev/.env | cut -d'=' -f2-)
fi

usage() {
    echo "Usage: $0 <query> | --status"
    echo ""
    echo "Arguments:"
    echo "  <query>     Search query for academic papers"
    echo "  --status    Check status of recent research triggers"
    echo ""
    echo "Examples:"
    echo "  $0 \"Kelly Criterion optimal fraction\""
    echo "  $0 --status"
    exit 1
}

# Check status of recent triggers
check_status() {
    echo "Recent Research Triggers:"
    echo "========================="
    if [[ -f "$LOG_FILE" ]]; then
        tail -10 "$LOG_FILE"
    else
        echo "No triggers logged yet."
    fi
}

# Trigger N8N pipeline
trigger_research() {
    local query="$1"

    echo "Triggering academic research for: $query"

    # Extract keywords from query (split by spaces, take significant words)
    local keywords
    keywords=$(echo "$query" | tr ' ' '\n' | grep -E '^[A-Za-z]{3,}' | head -5 | jq -R -s -c 'split("\n") | map(select(length > 0))')

    # Build JSON payload matching W6.3 expected format
    local payload
    payload=$(jq -n \
        --arg trigger "llm_autonomous" \
        --arg source "claude_code" \
        --argjson keywords "$keywords" \
        '{
          trigger: $trigger,
          source: $source,
          config: {
            arxiv_categories: ["q-fin.TR", "q-fin.CP", "q-fin.MF", "q-fin.PM", "stat.ML"],
            keywords: $keywords,
            max_papers: 5
          }
        }')

    # Send to N8N webhook with auth header
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "$N8N_WEBHOOK" \
        -H "Content-Type: application/json" \
        -H "X-N8N-Auth-Token: $N8N_AUTH_TOKEN" \
        -d "$payload" \
        --connect-timeout 10 \
        --max-time 30 2>/dev/null) || http_code="000"

    # Log the trigger
    echo "[$TIMESTAMP] Query: $query | Status: $http_code" >> "$LOG_FILE"

    if [[ "$http_code" == "200" ]] || [[ "$http_code" == "201" ]]; then
        echo "Research pipeline triggered successfully."
        echo "Expected completion: ~15-30 minutes"
        echo ""
        echo "You will receive a Discord notification when papers are ready."
        echo "Use '/research-papers' to view results."

        # Send Discord notification that research started
        if [[ -n "$DISCORD_WEBHOOK" ]]; then
            local discord_msg
            discord_msg=$(jq -n \
                --arg content ":mag: **Academic Research Triggered**\n\nQuery: \`$query\`\nTime: $TIMESTAMP\n\nExpected completion: ~15-30 min" \
                '{content: $content}')

            curl -s -o /dev/null \
                -H "Content-Type: application/json" \
                -d "$discord_msg" \
                "$DISCORD_WEBHOOK" 2>/dev/null || true
        fi

        return 0
    else
        echo "Failed to trigger research pipeline (HTTP $http_code)"
        echo ""
        echo "Troubleshooting:"
        echo "1. Check if N8N is running: docker ps | grep n8n"
        echo "2. Verify webhook URL: $N8N_WEBHOOK"
        echo "3. Check N8N logs: docker logs n8n-n8n-1"
        return 1
    fi
}

# Main
if [[ $# -eq 0 ]]; then
    usage
fi

case "$1" in
    --status|-s)
        check_status
        ;;
    --help|-h)
        usage
        ;;
    *)
        trigger_research "$1"
        ;;
esac
