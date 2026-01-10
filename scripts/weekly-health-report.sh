#!/bin/bash
# Weekly Health Report - Run drift-detector and send to Discord
#
# Usage: Add to crontab for weekly execution
# 0 8 * * 1 /home/sam/.claude/scripts/weekly-health-report.sh
#
# Sends a health report to Discord with:
# - Health score
# - Number of issues by severity
# - Top 5 issues with fix commands

set -euo pipefail

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
DRIFT_DETECTOR="${SCRIPT_DIR}/drift-detector.py"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check if drift-detector exists
if [[ ! -f "$DRIFT_DETECTOR" ]]; then
    echo "Error: drift-detector.py not found at $DRIFT_DETECTOR" >&2
    exit 1
fi

# Run drift-detector and capture only the JSON output
FULL_OUTPUT=$(python3 "$DRIFT_DETECTOR" --json 2>/dev/null)
REPORT=$(echo "$FULL_OUTPUT" | grep -E '^\{' -A 1000)

if [[ -z "$REPORT" ]]; then
    echo "Error: drift-detector returned no JSON output" >&2
    exit 1
fi

# Parse JSON output (drift-detector uses 'score' not 'health_score')
HEALTH_SCORE=$(echo "$REPORT" | jq -r '.score')
ISSUE_COUNT=$(echo "$REPORT" | jq -r '.issues | length')

# Count issues by severity
CRITICAL=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "critical")] | length')
HIGH=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "high")] | length')
MEDIUM=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "medium")] | length')
LOW=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "low")] | length')

# Get top 5 issues
TOP_ISSUES=$(echo "$REPORT" | jq -r '.issues[:5] | .[] | "- [\(.category)] \(.description)"')

# Determine status emoji
if [[ $HEALTH_SCORE -ge 90 ]]; then
    STATUS_EMOJI=":white_check_mark:"
elif [[ $HEALTH_SCORE -ge 70 ]]; then
    STATUS_EMOJI=":warning:"
else
    STATUS_EMOJI=":x:"
fi

# Build Discord message
MESSAGE="${STATUS_EMOJI} **Weekly Health Report** - ${TIMESTAMP}

**Health Score:** ${HEALTH_SCORE}/100

**Issues by Severity:**
- Critical: ${CRITICAL}
- High: ${HIGH}
- Medium: ${MEDIUM}
- Low: ${LOW}

**Top Issues:**
${TOP_ISSUES:-No issues found}

---
Run \`/health\` for detailed analysis."

# Send to Discord if webhook is configured
if [[ -n "$DISCORD_WEBHOOK" ]]; then
    PAYLOAD=$(jq -n --arg content "$MESSAGE" '{content: $content}')

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$DISCORD_WEBHOOK")

    if [[ "$HTTP_CODE" == "204" || "$HTTP_CODE" == "200" ]]; then
        echo "Weekly health report sent to Discord successfully"
    else
        echo "Failed to send to Discord (HTTP $HTTP_CODE)" >&2
    fi
else
    echo "DISCORD_WEBHOOK_URL not set, printing report to stdout:"
    echo ""
    echo "$MESSAGE"
fi

# Also save to log file
LOG_FILE="/tmp/weekly_health_report.log"
echo "[$TIMESTAMP] Health Score: $HEALTH_SCORE/100, Issues: $ISSUE_COUNT (C:$CRITICAL H:$HIGH M:$MEDIUM L:$LOW)" >> "$LOG_FILE"
