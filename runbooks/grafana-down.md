# Runbook: Grafana Down

## Symptoms
- Grafana UI not accessible at http://localhost:3000
- `curl http://localhost:3000/api/health` fails

## Diagnosis

```bash
# Check service status
sudo systemctl status grafana-server

# Check recent logs
sudo journalctl -u grafana-server --no-pager -n 50
```

## Common Issues

### 1. Datasource Conflict (Multiple Defaults)
**Error**: "Only one datasource per organization can be marked as default"

**Fix**:
```bash
# List all datasource configs
ls /etc/grafana/provisioning/datasources/

# Check which have isDefault: true
grep -r "isDefault: true" /etc/grafana/provisioning/datasources/

# Fix: keep only one default
sudo sed -i 's/isDefault: true/isDefault: false/' /etc/grafana/provisioning/datasources/questdb.yaml
sudo systemctl restart grafana-server
```

### 2. Port Already in Use
**Error**: "bind: address already in use"

**Fix**:
```bash
# Find what's using port 3000
sudo ss -tlnp | grep 3000

# Kill the process or change Grafana port
sudo kill <PID>
# OR
# Edit /etc/grafana/grafana.ini and change http_port
```

### 3. Database Issues
**Error**: Database migration failed

**Fix**:
```bash
# Backup and recreate database
sudo cp /var/lib/grafana/grafana.db /var/lib/grafana/grafana.db.bak
sudo rm /var/lib/grafana/grafana.db
sudo systemctl restart grafana-server
```

## Verification

```bash
# Check health
curl -s http://localhost:3000/api/health

# Expected output:
# {"database": "ok", "version": "X.X.X", "commit": "..."}
```

## Escalation
If issue persists, check:
- Disk space: `df -h /var/lib/grafana`
- Memory: `free -h`
- Grafana docs: https://grafana.com/docs/grafana/latest/troubleshooting/
