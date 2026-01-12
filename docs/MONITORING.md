# Claude Code Monitoring Guide

This document provides comprehensive documentation for the monitoring infrastructure.

## Overview

The Claude Code monitoring system consists of:
- **Grafana Dashboards**: Visual monitoring at localhost:3000
- **QuestDB**: Time-series metrics storage
- **Discord Notifications**: Real-time alerts
- **Email Fallback**: Backup notification channel
- **Health Reports**: Weekly automated health checks

## Dashboard Reference

| Dashboard | Path | Purpose |
|-----------|------|---------|
| Claude Metrics | `/d/claude-metrics` | Agent/tool usage, session stats |
| Infrastructure Health | `/d/infrastructure-health` | System health, service status |
| Security | `/d/security-dashboard` | Security events, audit trails |
| Trading | `/d/trading` | Strategy performance |
| Health | `/d/health` | Overall system health |
| Circuit Breaker | `/d/circuit-breaker` | Rate limiting, circuit states |

**Access**: http://localhost:3000 (Grafana v12.3.1)

## Alerting Configuration

### Notification Channels

| Channel | Primary Use | Configuration |
|---------|-------------|---------------|
| Discord | All alerts | `DISCORD_WEBHOOK_URL` env var |
| Email | Critical + Fallback | `SMTP_*` env vars |

### Email Setup

Required environment variables for email notifications:
```bash
export SMTP_HOST="smtp.gmail.com"      # SMTP server
export SMTP_PORT="587"                  # TLS port
export SMTP_USER="your-email@gmail.com" # SMTP username
export SMTP_PASSWORD="app-password"     # Gmail app password
export SMTP_FROM="alerts@yourdomain.com" # From address
export ALERT_EMAIL="you@example.com"    # Recipient
```

For Gmail, create an App Password at https://myaccount.google.com/apppasswords

### Alert Thresholds

| Metric | Warning | Critical | Source |
|--------|---------|----------|--------|
| Health Score | <80 | <60 | drift-detector.py |
| Daily Cost | $30 | $50 | canonical.yaml |
| Hook Latency | 300ms | 500ms | metrics |
| Agent Success Rate | <85% | <80% | metrics |
| Context Utilization | >80% | >90% | sessions |

### Trigger Behavior

Email is sent when:
1. **Discord fails** - Automatic fallback
2. **Critical issues detected** - Always (even if Discord succeeds)
3. **Health score below 70** - Proactive alert

## Health Reports

### Weekly Report (Automated)

- **Schedule**: Every Monday at 8:00 AM
- **Script**: `~/.claude/scripts/weekly-health-report.sh`
- **Output**: Discord + Email (if critical)
- **Log**: `/tmp/weekly_health_report.log`

### Daily Report (Conditional)

- **Schedule**: Every day at 8:00 AM
- **Script**: `~/.claude/scripts/daily-health-report.sh`
- **Condition**: Only sends if issues detected
- **Output**: Discord only (unless critical)

### Manual Health Check

```bash
# Quick health check
/health

# Full system audit
/audit

# Metrics-only audit
/audit metrics
```

## QuestDB Metrics

### Tables

| Table | Purpose | Retention |
|-------|---------|-----------|
| claude_tool_usage | Tool call metrics | 90 days |
| claude_events | System events | 90 days |
| claude_sessions | Session data | 365 days |
| claude_agents | Agent spawns | 90 days |
| claude_hooks | Hook execution | 30 days |
| claude_tasks | Task tracking | 90 days |
| claude_context | Context usage | 90 days |

### Query Examples

```sql
-- Recent tool usage
SELECT * FROM claude_tool_usage
WHERE timestamp > dateadd('h', -24, now())
ORDER BY timestamp DESC LIMIT 100;

-- Session costs
SELECT session_id, sum(cost_usd) as total_cost
FROM claude_events
WHERE timestamp > dateadd('d', -7, now())
GROUP BY session_id;

-- Hook performance
SELECT hook_name, avg(duration_ms), count(*)
FROM claude_hooks
WHERE timestamp > dateadd('d', -7, now())
GROUP BY hook_name;
```

### Access

- **HTTP API**: http://localhost:9000
- **ILP Port**: localhost:9009
- **PostgreSQL Wire**: localhost:8812

## Troubleshooting

### Discord Not Working

1. Verify webhook URL:
   ```bash
   echo $DISCORD_WEBHOOK_URL
   ```
2. Test manually:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"content":"Test message"}' \
     "$DISCORD_WEBHOOK_URL"
   ```
3. Check webhook isn't rate-limited or deleted in Discord server settings

### Email Not Working

1. Verify SMTP configuration:
   ```bash
   echo "SMTP_HOST=$SMTP_HOST"
   echo "SMTP_USER=$SMTP_USER"
   echo "ALERT_EMAIL=$ALERT_EMAIL"
   ```
2. For Gmail, ensure:
   - 2FA is enabled
   - App password is used (not regular password)
   - Less secure app access is not needed with app passwords
3. Test with:
   ```bash
   echo "Test" | mail -s "Test" -S smtp="$SMTP_HOST:$SMTP_PORT" your@email.com
   ```

### Grafana Not Accessible

1. Check service:
   ```bash
   systemctl status grafana-server
   ```
2. Restart if needed:
   ```bash
   sudo systemctl restart grafana-server
   ```
3. Check port:
   ```bash
   curl -I http://localhost:3000
   ```

### QuestDB Not Responding

1. Check container:
   ```bash
   docker ps | grep questdb
   ```
2. Restart container:
   ```bash
   docker restart nautilus-questdb
   ```
3. Check logs:
   ```bash
   docker logs nautilus-questdb --tail 50
   ```

### Health Report Not Running

1. Check cron:
   ```bash
   crontab -l | grep health
   ```
2. Check log:
   ```bash
   tail -20 /tmp/weekly_health_report.log
   ```
3. Run manually:
   ```bash
   ~/.claude/scripts/weekly-health-report.sh
   ```

## Useful Commands

| Command | Purpose |
|---------|---------|
| `/health` | Quick health check |
| `/audit` | Full system audit |
| `/audit metrics` | Metrics-only audit |
| `/tips` | Session optimization tips |
| `/research "query"` | CoAT iterative research |
| `/research -a "query"` | CoAT + N8N academic pipeline |
| `/research-papers` | View academic research results |
| `/auto-resolve` | Auto-fix drift issues |

## File Locations

| File | Purpose |
|------|---------|
| `~/.claude/scripts/drift-detector.py` | Core health detection |
| `~/.claude/scripts/weekly-health-report.sh` | Weekly report script |
| `~/.claude/scripts/daily-health-report.sh` | Daily report script |
| `~/.claude/scripts/issue-resolver.py` | Auto-resolution pipeline |
| `~/.claude/scripts/trigger-n8n-research.sh` | N8N academic trigger |
| `~/.claude/canonical.yaml` | SSOT configuration |
| `~/.claude/docs/MONITORING.md` | This documentation |
| `/tmp/weekly_health_report.log` | Weekly report log |
| `/tmp/daily_health_report.log` | Daily report log |
| `/tmp/research_triggers.log` | Research trigger log |

## Related Documentation

- [canonical.yaml](../canonical.yaml) - System of record
- [drift-detector.py](../scripts/drift-detector.py) - Detection logic
