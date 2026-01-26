# Manual Setup Required for Grafana Provisioning

The safety hook blocks direct operations on /etc. Run these commands manually to complete the setup.

## Step 1: Remove old broken symlinks

```bash
sudo rm -f /etc/grafana/provisioning/alerting/validation-contact-points.yaml
sudo rm -f /etc/grafana/provisioning/alerting/validation-alert-rules.yaml
sudo rm -f /etc/grafana/provisioning/alerting/validation-policies.yaml
```

## Step 2: Create new symlinks pointing to accessible location

```bash
sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/contact-points.yaml /etc/grafana/provisioning/alerting/validation-contact-points.yaml
sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/alert-rules.yaml /etc/grafana/provisioning/alerting/validation-alert-rules.yaml
sudo ln -sf /media/sam/1TB/validation-framework/grafana/alerting/notification-policies.yaml /etc/grafana/provisioning/alerting/validation-policies.yaml
```

## Step 3: Restart Grafana

```bash
sudo systemctl restart grafana-server
```

## Step 4: Verify provisioning

```bash
# Check for errors in logs
sudo journalctl -u grafana-server --since "1 minute ago" | grep -iE "(error|provision|validation)"

# Verify alert rules via API
curl -s -u admin:admin http://localhost:3000/api/v1/provisioning/alert-rules | jq 'length'
```

## Files Location

Source files are at:
- `/media/sam/1TB/validation-framework/grafana/alerting/contact-points.yaml`
- `/media/sam/1TB/validation-framework/grafana/alerting/alert-rules.yaml`
- `/media/sam/1TB/validation-framework/grafana/alerting/notification-policies.yaml`

Backup copies at:
- `/home/sam/.claude/grafana/alerting/` (same files, but grafana user can't access)
