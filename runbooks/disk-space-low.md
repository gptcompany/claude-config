# Runbook: Disk Space Low

## Symptoms
- Alert: `DiskSpaceLow` firing
- Commands failing with "No space left on device"

## Diagnosis

```bash
# Check disk usage
df -h

# Find large directories
du -sh /* 2>/dev/null | sort -h | tail -20

# Check Docker usage
docker system df
```

## Quick Cleanup Actions

### 1. Docker Cleanup (Usually Biggest Win)
```bash
# Remove unused containers, networks, images
docker system prune -f

# Remove unused volumes (careful - data loss!)
docker volume prune -f

# Remove old images
docker image prune -a -f --filter "until=168h"  # 7 days
```

### 2. Cache Directories
```bash
# Python caches
find /home/sam -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null
find /home/sam -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null
find /home/sam -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null
find /home/sam -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# NPM cache
npm cache clean --force

# APT cache
sudo apt-get clean
sudo apt-get autoremove -y
```

### 3. Log Files
```bash
# Rotate and compress logs
sudo journalctl --vacuum-time=7d

# Clear old container logs
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### 4. Large Files in Repos
```bash
# Find large files
find /media/sam/1TB -name "*.log" -size +100M -exec ls -lh {} \;
find /media/sam/1TB -name "*.duckdb" -size +1G -exec ls -lh {} \;

# Check for .venv size
du -sh /media/sam/1TB/*/.venv 2>/dev/null
```

### 5. QuestDB Old Data
```bash
# Drop old partitions (older than 30 days)
curl -G --data-urlencode "query=ALTER TABLE claude_sessions DROP PARTITION WHERE timestamp < dateadd('d', -30, now())" http://localhost:9000/exec
```

## Preventive Measures

### Add to Crontab
```bash
# Weekly cleanup
0 3 * * 0 docker system prune -f >> /var/log/docker-cleanup.log 2>&1
0 4 * * 0 find /home/sam -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

### Monitor Disk Usage
- Grafana dashboard: System Overview
- Alert threshold: 85% usage

## Verification

```bash
# Check available space
df -h /

# Check Docker recovered space
docker system df
```

## Escalation
If cleanup doesn't help:
1. Identify which partition is full: `df -h`
2. Use `ncdu` for interactive exploration: `ncdu /`
3. Consider expanding partition or adding storage
