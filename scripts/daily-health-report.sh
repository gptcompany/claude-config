#!/bin/bash
# Daily Health Report - Conditional reporting
#
# Usage: Add to crontab for daily execution
# 0 8 * * * /home/sam/.claude/scripts/daily-health-report.sh
#
# Only sends report if:
# - Health score < 90
# - Any issues detected
# - Always sends on critical issues

set -euo pipefail

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
DRIFT_DETECTOR="${SCRIPT_DIR}/drift-detector.py"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="/tmp/daily_health_report.log"

# Check if drift-detector exists
if [[ ! -f "$DRIFT_DETECTOR" ]]; then
    echo "[$TIMESTAMP] Error: drift-detector.py not found" >> "$LOG_FILE"
    exit 1
fi

# Run drift-detector and capture JSON output
FULL_OUTPUT=$(python3 "$DRIFT_DETECTOR" --json 2>/dev/null)
REPORT=$(echo "$FULL_OUTPUT" | grep -E '^\{' -A 1000)

if [[ -z "$REPORT" ]]; then
    echo "[$TIMESTAMP] Error: drift-detector returned no JSON output" >> "$LOG_FILE"
    exit 1
fi

# Parse JSON output
HEALTH_SCORE=$(echo "$REPORT" | jq -r '.score')
ISSUE_COUNT=$(echo "$REPORT" | jq -r '.issues | length')

# Count issues by severity
CRITICAL=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "critical")] | length')
HIGH=$(echo "$REPORT" | jq -r '[.issues[] | select(.severity == "high")] | length')

# Determine if we should send a report
SHOULD_REPORT=false
REASON=""

if [[ "$CRITICAL" -gt 0 ]]; then
    SHOULD_REPORT=true
    REASON="critical issues detected"
elif [[ "$HIGH" -gt 0 ]]; then
    SHOULD_REPORT=true
    REASON="high severity issues detected"
elif [[ "$HEALTH_SCORE" -lt 90 ]]; then
    SHOULD_REPORT=true
    REASON="health score below 90"
fi

# Log the check
echo "[$TIMESTAMP] Health Score: $HEALTH_SCORE/100, Issues: $ISSUE_COUNT (C:$CRITICAL H:$HIGH), Report: $SHOULD_REPORT ($REASON)" >> "$LOG_FILE"

# Exit early if no report needed
if [[ "$SHOULD_REPORT" == "false" ]]; then
    exit 0
fi

# Get top 3 issues for daily (shorter than weekly)
TOP_ISSUES=$(echo "$REPORT" | jq -r '.issues[:3] | .[] | "- [\(.category)] \(.description)"')

# Determine status emoji
if [[ $HEALTH_SCORE -ge 90 ]]; then
    STATUS_EMOJI=":white_check_mark:"
elif [[ $HEALTH_SCORE -ge 70 ]]; then
    STATUS_EMOJI=":warning:"
else
    STATUS_EMOJI=":x:"
fi

# Build compact Discord message
MESSAGE="${STATUS_EMOJI} **Daily Health Check** - ${TIMESTAMP}

**Score:** ${HEALTH_SCORE}/100 | **Issues:** ${ISSUE_COUNT}

**Top Issues:**
${TOP_ISSUES:-No issues}

---
Run \`/health\` for details."

# Send to Discord if configured
if [[ -n "$DISCORD_WEBHOOK" ]]; then
    PAYLOAD=$(jq -n --arg content "$MESSAGE" '{content: $content}')

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$DISCORD_WEBHOOK")

    if [[ "$HTTP_CODE" == "204" || "$HTTP_CODE" == "200" ]]; then
        echo "[$TIMESTAMP] Daily report sent to Discord" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] Discord failed (HTTP $HTTP_CODE)" >> "$LOG_FILE"
    fi
else
    echo "[$TIMESTAMP] DISCORD_WEBHOOK_URL not set, report not sent" >> "$LOG_FILE"
fi
