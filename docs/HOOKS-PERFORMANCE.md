# Claude Code Hooks Performance Guide

Performance tuning and optimization for the Claude Code hooks system.

**Last Updated:** 2026-01-24
**Version:** 14.6 (Phase 14.6-04)

---

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Optimization Tips](#optimization-tips)
3. [Benchmarking](#benchmarking)
4. [Monitoring](#monitoring)
5. [Common Performance Issues](#common-performance-issues)

---

## Performance Targets

### Hook Execution Time Targets

| Hook Category | Target | Maximum | Notes |
|---------------|--------|---------|-------|
| Safety Checks (PreToolUse) | < 50ms | 200ms | Critical path, blocks tool |
| Intelligence (PostToolUse) | < 100ms | 500ms | Non-blocking preferred |
| Session Hooks | < 200ms | 1000ms | Once per session |
| Stop Hooks | < 500ms | 2000ms | End of conversation |

### System Impact Targets

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Hook overhead per tool call | < 100ms | 200ms | 500ms |
| Memory per hook | < 50MB | 100MB | 200MB |
| CPU per hook | < 10% | 25% | 50% |
| Error rate | < 1% | 5% | 20% |

---

## Optimization Tips

### 1. Minimize Startup Time

**Problem:** Node.js startup time adds ~50ms per hook invocation.

**Solution:** Use inline scripts for simple checks.

```json
{
  "command": "node -e \"process.stdin.on('data',d=>{const i=JSON.parse(d);console.log(JSON.stringify(i.tool_name==='Bash'&&/--force/.test(i.tool_input.command)?{decision:'block',reason:'Force flag detected'}:{}))})\""
}
```

**Best Practice:** Keep inline scripts for <20 lines; use files for complex logic.

### 2. Lazy Loading

**Problem:** Loading all dependencies at startup slows hooks.

```javascript
// SLOW: Load everything at startup
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const gitUtils = require('./lib/git-utils');
const metrics = require('./lib/metrics');

// FAST: Load only what's needed
let gitUtils, metrics;

function getGitUtils() {
  if (!gitUtils) gitUtils = require('./lib/git-utils');
  return gitUtils;
}
```

### 3. Cache Expensive Operations

**Problem:** Repeated expensive operations (git commands, file reads).

```javascript
// SLOW: Execute git command every time
function getCurrentBranch() {
  return execSync('git branch --show-current').toString().trim();
}

// FAST: Cache with TTL
const cache = new Map();
const CACHE_TTL = 5000; // 5 seconds

function getCurrentBranch() {
  const cached = cache.get('branch');
  if (cached && Date.now() - cached.time < CACHE_TTL) {
    return cached.value;
  }
  const value = execSync('git branch --show-current').toString().trim();
  cache.set('branch', { value, time: Date.now() });
  return value;
}
```

### 4. Avoid Synchronous I/O

**Problem:** Synchronous file operations block the event loop.

```javascript
// SLOW: Synchronous read
const content = fs.readFileSync(file, 'utf8');

// FAST: For hooks that must complete quickly, keep sync but limit size
const fd = fs.openSync(file, 'r');
const buffer = Buffer.alloc(1024);
fs.readSync(fd, buffer, 0, 1024, 0);
fs.closeSync(fd);
const content = buffer.toString('utf8');
```

### 5. Stream Large Files

**Problem:** Reading entire large files into memory.

```javascript
// SLOW: Read entire file
const log = fs.readFileSync('large.log', 'utf8');
const lastLines = log.split('\n').slice(-100);

// FAST: Stream from end
const readline = require('readline');
const stream = fs.createReadStream('large.log', { start: Math.max(0, fs.statSync('large.log').size - 10000) });
const rl = readline.createInterface({ input: stream });
const lines = [];
rl.on('line', line => { lines.push(line); if (lines.length > 100) lines.shift(); });
```

### 6. Batch External Commands

**Problem:** Multiple external command executions.

```javascript
// SLOW: Multiple git commands
const branch = execSync('git branch --show-current').toString().trim();
const commit = execSync('git rev-parse HEAD').toString().trim();
const status = execSync('git status --porcelain').toString().trim();

// FAST: Single command with multiple outputs
const output = execSync('git branch --show-current && git rev-parse HEAD && git status --porcelain').toString();
const [branch, commit, ...status] = output.split('\n');
```

### 7. Use Native Node.js APIs

**Problem:** Spawning external processes for simple operations.

```javascript
// SLOW: External command
const files = execSync('find . -name "*.js"').toString().split('\n');

// FAST: Native Node.js
const glob = require('fast-glob');
const files = glob.sync('**/*.js');

// Or manual recursion for simple cases
function findFiles(dir, pattern) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...findFiles(fullPath, pattern));
    } else if (pattern.test(entry.name)) {
      results.push(fullPath);
    }
  }
  return results;
}
```

### 8. Early Exit Patterns

**Problem:** Doing unnecessary work when result is already determined.

```javascript
// SLOW: Check everything even when not needed
function checkSafety(input) {
  const isGitCommand = checkGitCommand(input);
  const isBashCommand = checkBashCommand(input);
  const hasForceFlag = checkForceFlag(input);
  const isProtectedBranch = checkProtectedBranch(input);

  if (isGitCommand && hasForceFlag && isProtectedBranch) {
    return { decision: 'block' };
  }
  return {};
}

// FAST: Exit early
function checkSafety(input) {
  if (input.tool_name !== 'Bash') return {};

  const cmd = input.tool_input?.command || '';
  if (!cmd.includes('git')) return {};
  if (!cmd.includes('--force') && !cmd.includes('-f')) return {};

  const branch = getCurrentBranch();
  if (!PROTECTED_BRANCHES.includes(branch)) return {};

  return { decision: 'block', reason: `Protected branch: ${branch}` };
}
```

---

## Benchmarking

### Hook Benchmark Script

```javascript
#!/usr/bin/env node
// benchmark-hooks.js

const { execSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const HOOKS_DIR = path.join(process.env.HOME, '.claude', 'scripts', 'hooks');
const ITERATIONS = 10;

const testInput = JSON.stringify({
  tool_name: 'Bash',
  tool_input: { command: 'echo test' }
});

function benchmarkHook(hookPath) {
  const times = [];

  for (let i = 0; i < ITERATIONS; i++) {
    const start = process.hrtime.bigint();

    try {
      execSync(`echo '${testInput}' | node "${hookPath}"`, {
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe']
      });
    } catch (e) {
      // Ignore errors for benchmarking
    }

    const end = process.hrtime.bigint();
    times.push(Number(end - start) / 1e6); // Convert to ms
  }

  const avg = times.reduce((a, b) => a + b, 0) / times.length;
  const min = Math.min(...times);
  const max = Math.max(...times);
  const p95 = times.sort((a, b) => a - b)[Math.floor(times.length * 0.95)];

  return { avg: avg.toFixed(2), min: min.toFixed(2), max: max.toFixed(2), p95: p95.toFixed(2) };
}

// Find all hooks
function findHooks(dir) {
  const hooks = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      hooks.push(...findHooks(fullPath));
    } else if (entry.name.endsWith('.js') && !entry.name.includes('.test.')) {
      hooks.push(fullPath);
    }
  }
  return hooks;
}

console.log('Hook Performance Benchmark');
console.log('==========================\n');
console.log(`Iterations: ${ITERATIONS}\n`);
console.log('Hook                           Avg(ms)  Min(ms)  Max(ms)  P95(ms)');
console.log('----                           -------  -------  -------  -------');

for (const hook of findHooks(HOOKS_DIR)) {
  const name = path.relative(HOOKS_DIR, hook).padEnd(30);
  const result = benchmarkHook(hook);
  console.log(`${name} ${result.avg.padStart(7)}  ${result.min.padStart(7)}  ${result.max.padStart(7)}  ${result.p95.padStart(7)}`);
}
```

### Run Benchmark

```bash
node ~/.claude/scripts/hooks/benchmark-hooks.js
```

### Expected Output

```
Hook Performance Benchmark
==========================

Iterations: 10

Hook                           Avg(ms)  Min(ms)  Max(ms)  P95(ms)
----                           -------  -------  -------  -------
safety/git-safety-check.js       42.15    38.20    48.50    47.80
safety/smart-safety-check.js     55.30    50.10    62.40    61.20
safety/port-conflict-check.js   125.45   110.20   145.80   142.30
productivity/tdd-guard.js        35.80    32.50    42.10    41.50
```

---

## Monitoring

### Real-Time Monitoring with trace.jsonl

```bash
# Watch hook performance in real-time
tail -f ~/.claude/debug/hooks/trace.jsonl | jq -c '{hook, duration_ms, success}'

# Alert on slow hooks (>200ms)
tail -f ~/.claude/debug/hooks/trace.jsonl | jq -c 'select(.duration_ms > 200) | {hook, duration_ms}'
```

### Performance Dashboard Query (QuestDB)

```sql
-- Average hook duration by hook name (last hour)
SELECT
  hook,
  avg(duration_ms) as avg_ms,
  max(duration_ms) as max_ms,
  count() as calls
FROM claude_hook_metrics
WHERE timestamp > now() - 1h
GROUP BY hook
ORDER BY avg_ms DESC;

-- Error rate by hook (last day)
SELECT
  hook,
  count() as total,
  sum(CASE WHEN success = false THEN 1 ELSE 0 END) as errors,
  sum(CASE WHEN success = false THEN 1 ELSE 0 END) * 100.0 / count() as error_pct
FROM claude_hook_metrics
WHERE timestamp > now() - 1d
GROUP BY hook
ORDER BY error_pct DESC;
```

### Grafana Dashboard Panels

```json
{
  "panels": [
    {
      "title": "Hook Duration (P95)",
      "type": "timeseries",
      "targets": [
        {
          "rawSql": "SELECT timestamp, hook, percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95 FROM claude_hook_metrics WHERE $__timeFilter(timestamp) SAMPLE BY 5m"
        }
      ]
    },
    {
      "title": "Hook Error Rate",
      "type": "gauge",
      "targets": [
        {
          "rawSql": "SELECT hook, sum(CASE WHEN success = false THEN 1 ELSE 0 END) * 100.0 / count() as error_pct FROM claude_hook_metrics WHERE timestamp > now() - 1h GROUP BY hook"
        }
      ]
    }
  ]
}
```

### Health Check Integration

```bash
# Add to crontab for periodic checks
*/15 * * * * node ~/.claude/scripts/hooks/debug/hook-health.js --check --export >> ~/.claude/logs/health-cron.log 2>&1
```

---

## Common Performance Issues

### Issue 1: Slow Git Operations

**Symptoms:** Hooks involving git commands take >500ms

**Diagnosis:**
```bash
time git status
time git branch --show-current
```

**Solutions:**
1. Use `--porcelain` flag for parsing
2. Cache git state within session
3. Use `libgit2` bindings (nodegit) for frequent operations

### Issue 2: Large State Files

**Symptoms:** Hooks slow down after extended use

**Diagnosis:**
```bash
ls -lh ~/.claude/coordination/*.json
ls -lh ~/.claude/hive/*.json
wc -l ~/.claude/debug/hooks/trace.jsonl
```

**Solutions:**
1. Implement automatic cleanup of expired entries
2. Rotate trace files at 5MB
3. Archive old state files

### Issue 3: Many Hooks on Same Event

**Symptoms:** Cumulative delay on tool execution

**Diagnosis:**
```bash
jq '.hooks.PreToolUse | length' ~/.claude/hooks/hooks.json
```

**Solutions:**
1. Consolidate related hooks
2. Use single dispatcher hook
3. Parallelize independent checks

### Issue 4: Memory Leaks

**Symptoms:** Hook processes use increasing memory

**Diagnosis:**
```bash
# Monitor memory during hook execution
while true; do
  ps aux | grep 'node.*hook' | awk '{sum+=$6} END {print sum/1024 "MB"}'
  sleep 1
done
```

**Solutions:**
1. Ensure hooks exit after output
2. Clear caches periodically
3. Avoid global state accumulation

---

## Performance Checklist

Before deploying a new hook:

- [ ] Execution time < 100ms for PreToolUse hooks
- [ ] No synchronous file operations on large files
- [ ] External commands cached or batched
- [ ] Early exit for non-matching inputs
- [ ] Memory usage < 50MB
- [ ] Error handling doesn't throw (graceful degradation)
- [ ] Benchmark results documented

---

## See Also

- [HOOKS-CATALOG.md](./HOOKS-CATALOG.md) - Complete hook reference
- [HOOKS-TROUBLESHOOTING.md](./HOOKS-TROUBLESHOOTING.md) - Common issues and solutions
