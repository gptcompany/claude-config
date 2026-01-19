# Runbook: QuestDB Issues

## Instances
- **nautilus-questdb**: Primary (ports 9000, 9009, 8812)
- **questdb-staging**: Staging for nautilus_dev (ports 9001, 9010, 8813)

## Symptoms
- Cannot write metrics via ILP (port 9009)
- Web console inaccessible (port 9000)
- Container marked as "unhealthy"

## Diagnosis

```bash
# Check container status
docker ps -a | grep questdb

# Check logs
docker logs nautilus-questdb --tail 100

# Test ILP connection
echo "test,source=runbook value=1 $(date +%s)000000000" | nc -q1 localhost 9009

# Test HTTP API
curl -s -G --data-urlencode "query=SELECT count() FROM test" http://localhost:9000/exec
```

## Common Issues

### 1. Container Unhealthy
**Cause**: Healthcheck failing but service works

**Fix**:
```bash
# Check actual functionality
curl -s http://localhost:9000/exec?query=SELECT%201

# If working, ignore unhealthy status or fix healthcheck in docker-compose
```

### 2. Cannot Write Metrics (ILP)
**Symptoms**: `nc` command hangs or fails

**Fix**:
```bash
# Check if port 9009 is listening
ss -tlnp | grep 9009

# Restart container
docker restart nautilus-questdb
```

### 3. Disk Space Full
**Error**: "could not open file for write"

**Fix**:
```bash
# Check disk usage
docker exec nautilus-questdb du -sh /var/lib/questdb/db/

# Clean old partitions (be careful!)
# Use QuestDB SQL to drop old data
curl -G --data-urlencode "query=ALTER TABLE claude_sessions DROP PARTITION WHERE timestamp < dateadd('d', -30, now())" http://localhost:9000/exec
```

### 4. WAL Issues
**Error**: "WAL apply failed"

**Fix**:
```bash
# Force WAL recovery
docker restart nautilus-questdb

# If persists, check logs for specific table
docker logs nautilus-questdb 2>&1 | grep -i wal
```

## Verification

```bash
# List tables
curl -s -G --data-urlencode "query=SHOW TABLES" http://localhost:9000/exec | jq '.dataset[][0]'

# Check recent data
curl -s -G --data-urlencode "query=SELECT * FROM claude_sessions ORDER BY timestamp DESC LIMIT 1" http://localhost:9000/exec | jq
```

## Backup

```bash
# Backup via snapshot
docker exec nautilus-questdb /opt/questdb/bin/questdb.sh backup /var/lib/questdb/backup

# Copy backup out
docker cp nautilus-questdb:/var/lib/questdb/backup ./questdb-backup-$(date +%Y%m%d)
```

## Escalation
- QuestDB docs: https://questdb.io/docs/
- GitHub issues: https://github.com/questdb/questdb/issues
