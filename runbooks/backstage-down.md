# Runbook: Backstage Down

## Symptoms
- Backstage UI not accessible at http://localhost:3001
- Alert: `BackstageDown` firing

## Diagnosis

```bash
# Check container status
docker ps -a | grep backstage

# Check logs
docker logs backstage-portal --tail 100
```

## Common Issues

### 1. Container Stopped
**Fix**:
```bash
docker start backstage-portal
```

### 2. Container Crash Loop
**Symptoms**: Container keeps restarting

**Fix**:
```bash
# Check exit code
docker inspect backstage-portal --format='{{.State.ExitCode}}'

# Check logs for errors
docker logs backstage-portal --tail 200 | grep -i error

# Common cause: PostgreSQL not ready
docker logs n8n-postgres-1 --tail 50
```

### 3. PostgreSQL Connection Failed
**Error**: "connect ECONNREFUSED" or "FATAL: database does not exist"

**Fix**:
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# If not running:
docker start n8n-postgres-1

# Wait for PostgreSQL, then restart Backstage
sleep 10 && docker restart backstage-portal
```

### 4. High Memory Usage
**Symptoms**: Container OOM killed

**Fix**:
```bash
# Check memory limits
docker stats backstage-portal --no-stream

# Restart with increased memory
docker update --memory=2g backstage-portal
docker restart backstage-portal
```

## Verification

```bash
# Check container health
docker inspect backstage-portal --format='{{.State.Health.Status}}'

# Test UI
curl -s http://localhost:3001/api/health
```

## Auto-Remediation
If alert is firing, the auto-remediation webhook at http://localhost:9095 should automatically restart the container.

## Escalation
If container won't start after PostgreSQL is healthy:
1. Check GitHub token validity: `gh auth status`
2. Verify environment variables in docker-compose
3. Check disk space: `df -h`
