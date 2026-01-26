# Plan 17-01 Summary: Discord Alert Notifications

**Phase:** 17-observability-dashboards
**Plan:** 01 - Discord Alert Notifications
**Status:** PARTIAL - Manual step required
**Completed:** 2026-01-26

## Objective

Set up Discord alert notifications for validation failures using Grafana Unified Alerting.

## What Was Done

### Task 1: Create Grafana alerting directory structure and contact point

**Status:** DONE

Created directory structure and contact-points.yaml:
- `/home/sam/.claude/grafana/alerting/contact-points.yaml`
- `/media/sam/1TB/validation-framework/grafana/alerting/contact-points.yaml` (grafana-accessible copy)

Contact points created:
- `discord-validation-critical` - For Tier 1 blockers (critical severity)
- `discord-validation-warning` - For Tier 2 warnings
- `discord-validation-quality` - For quality score alerts

All use `${DISCORD_WEBHOOK_URL}` environment variable (already configured in Grafana systemd service).

### Task 2: Create alert rules for Tier 1 validation failures

**Status:** DONE

Created alert-rules.yaml with 5 rules across 3 groups:

**Group: validation-tier1-critical** (interval: 1m)
1. `validation-tier1-failure` - Tier 1 pass rate < 80% over 5 minutes
2. `validation-tier1-zero` - Zero Tier 1 validations passing (complete failure)

**Group: validation-tier2-warnings** (interval: 2m)
3. `validation-tier2-failure` - Tier 2 pass rate < 70% over 10 minutes

**Group: validation-quality-score** (interval: 5m)
4. `validation-quality-drop` - Quality score drops >20% from 24h baseline
5. `validation-quality-critical` - Quality score below 50

Dimensions monitored:
- Tier 1 (blockers): syntax, tests, imports
- Tier 2 (warnings): linting, types, coverage

### Task 3: Create notification policy and provision to Grafana

**Status:** PARTIAL

Created notification-policies.yaml with routing rules:
- Tier 1 critical -> immediate notification (10s group_wait, 15m repeat)
- Tier 2 warnings -> standard notification (1m group_wait, 4h repeat)
- Quality alerts -> quality-specific channel

**Manual Step Required:**

The safety hook blocks operations on system paths. Run these commands manually:

```bash
# Remove old broken symlinks and create new ones
sudo rm -f /etc/grafana/provisioning/alerting/validation-contact-points.yaml
sudo rm -f /etc/grafana/provisioning/alerting/validation-alert-rules.yaml
sudo rm -f /etc/grafana/provisioning/alerting/validation-policies.yaml

sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/contact-points.yaml /etc/grafana/provisioning/alerting/validation-contact-points.yaml
sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/alert-rules.yaml /etc/grafana/provisioning/alerting/validation-alert-rules.yaml
sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/notification-policies.yaml /etc/grafana/provisioning/alerting/validation-policies.yaml

# Restart Grafana
sudo systemctl restart grafana-server
```

See `MANUAL-SETUP.md` for detailed instructions.

## Files Created

| File | Purpose |
|------|---------|
| `~/.claude/grafana/alerting/contact-points.yaml` | Discord webhook contact points |
| `~/.claude/grafana/alerting/alert-rules.yaml` | 5 alert rules for Tier 1/2/Quality |
| `~/.claude/grafana/alerting/notification-policies.yaml` | Alert routing policies |
| `/media/sam/1TB/validation-framework/grafana/alerting/*` | Grafana-accessible copies |

## Verification Checklist

After running manual setup:

- [ ] `~/.claude/grafana/alerting/` directory exists with 3 YAML files
- [ ] `/media/sam/1TB/validation-framework/grafana/alerting/` has same 3 files
- [ ] Symlinks exist in `/etc/grafana/provisioning/alerting/`
- [ ] No YAML syntax errors (validated with Python yaml.safe_load)
- [ ] Grafana restart successful (no provisioning errors in logs)
- [ ] Alert rules visible in Grafana UI (Alerting > Alert rules > Validation Framework folder)
- [ ] Contact points visible (Alerting > Contact points)

## Technical Notes

1. **DISCORD_WEBHOOK_URL**: Already configured in `/etc/systemd/system/grafana-server.service.d/env.conf`

2. **QuestDB Tables Used**:
   - `validation` - dimension, passed, duration, timestamp
   - `claude_quality_scores` - project, score_total, timestamp

3. **Flap Prevention**: All rules use `for:` clause (2-15 minutes depending on severity)

4. **No Hardcoded Secrets**: Webhook URL uses environment variable substitution

## Next Steps

1. Run manual setup commands (see above)
2. Verify provisioning in Grafana logs
3. Test alerts by triggering a validation failure
4. Proceed to Plan 17-02 (QuestDB queries + views)

---

*Plan: 17-01*
*Completed: 2026-01-26*
*Author: Claude Opus 4.5*
