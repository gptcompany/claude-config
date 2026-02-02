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
DOTENVX="/home/sam/.local/bin/dotenvx"
ENV_FILE="/media/sam/1TB/.env"

# Load secrets from dotenvx (not from environment/crontab!)
if [[ -f "$ENV_FILE" ]]; then
    eval "$($DOTENVX decrypt -f "$ENV_FILE" --stdout 2>/dev/null | grep -E '^[A-Z_]+=' | sed 's/^/export /')"
fi

DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Email configuration (fallback)
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SMTP_FROM="${SMTP_FROM:-alerts@claudecode.local}"
ALERT_EMAIL="${ALERT_EMAIL:-}"

# Email fallback function
send_email_fallback() {
    local subject="$1"
    local body="$2"

    if [[ -z "$SMTP_HOST" ]] || [[ -z "$ALERT_EMAIL" ]]; then
        echo "Email not configured (SMTP_HOST or ALERT_EMAIL missing)" >&2
        return 1
    fi

    # Convert Discord markdown to plain text for email
    local plain_body
    plain_body=$(echo "$body" | sed 's/\*\*//g' | sed 's/:white_check_mark:/[OK]/g' | sed 's/:warning:/[WARN]/g' | sed 's/:x:/[FAIL]/g')

    if command -v mail &> /dev/null && [[ -n "$SMTP_USER" ]]; then
        echo "$plain_body" | mail -s "$subject" \
            -S smtp="$SMTP_HOST:$SMTP_PORT" \
            -S smtp-use-starttls \
            -S smtp-auth=login \
            -S smtp-auth-user="$SMTP_USER" \
            -S smtp-auth-password="$SMTP_PASSWORD" \
            -S from="$SMTP_FROM" \
            "$ALERT_EMAIL" 2>/dev/null && return 0
    fi

    # Fallback to sendmail if available
    if command -v sendmail &> /dev/null; then
        {
            echo "From: $SMTP_FROM"
            echo "To: $ALERT_EMAIL"
            echo "Subject: $subject"
            echo "Content-Type: text/plain; charset=utf-8"
            echo ""
            echo "$plain_body"
        } | sendmail -t 2>/dev/null && return 0
    fi

    # Last resort: msmtp
    if command -v msmtp &> /dev/null; then
        echo "$plain_body" | msmtp --from="$SMTP_FROM" "$ALERT_EMAIL" 2>/dev/null && return 0
    fi

    echo "No mail command available (mail, sendmail, or msmtp required)" >&2
    return 1
}

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

# Track notification status
DISCORD_SUCCESS=false
EMAIL_SUCCESS=false

# Send to Discord if webhook is configured
if [[ -n "$DISCORD_WEBHOOK" ]]; then
    PAYLOAD=$(jq -n --arg content "$MESSAGE" '{content: $content}')

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$DISCORD_WEBHOOK")

    if [[ "$HTTP_CODE" == "204" || "$HTTP_CODE" == "200" ]]; then
        echo "Weekly health report sent to Discord successfully"
        DISCORD_SUCCESS=true
    else
        echo "Failed to send to Discord (HTTP $HTTP_CODE)" >&2
    fi
else
    echo "DISCORD_WEBHOOK_URL not set"
fi

# Email fallback: Send if Discord failed OR if there are critical issues
EMAIL_SUBJECT="[Claude Code] Weekly Health Report - Score: ${HEALTH_SCORE}/100"
if [[ "$CRITICAL" -gt 0 ]]; then
    EMAIL_SUBJECT="[CRITICAL] Claude Code Health Alert - Score: ${HEALTH_SCORE}/100"
fi

SHOULD_EMAIL=false
if [[ "$DISCORD_SUCCESS" == "false" ]]; then
    echo "Discord failed, attempting email fallback..."
    SHOULD_EMAIL=true
fi
if [[ "$CRITICAL" -gt 0 ]]; then
    echo "Critical issues detected ($CRITICAL), sending email alert..."
    SHOULD_EMAIL=true
fi

if [[ "$SHOULD_EMAIL" == "true" ]]; then
    if send_email_fallback "$EMAIL_SUBJECT" "$MESSAGE"; then
        echo "Email fallback sent successfully"
        EMAIL_SUCCESS=true
    else
        echo "Email fallback failed" >&2
    fi
fi

# If both Discord and email not configured, print to stdout
if [[ "$DISCORD_SUCCESS" == "false" ]] && [[ "$EMAIL_SUCCESS" == "false" ]] && [[ -z "$DISCORD_WEBHOOK" ]]; then
    echo ""
    echo "No notification channels configured. Report:"
    echo ""
    echo "$MESSAGE"
fi

# Also save to log file
LOG_FILE="/tmp/weekly_health_report.log"
echo "[$TIMESTAMP] Health Score: $HEALTH_SCORE/100, Issues: $ISSUE_COUNT (C:$CRITICAL H:$HIGH M:$MEDIUM L:$LOW)" >> "$LOG_FILE"
