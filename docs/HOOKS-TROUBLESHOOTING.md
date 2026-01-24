# Claude Code Hooks Troubleshooting Guide

Common issues and solutions for the Claude Code hooks system.

**Last Updated:** 2026-01-24
**Version:** 14.6 (Phase 14.6-04)

---

## Table of Contents

1. [Hook Not Firing](#hook-not-firing)
2. [Hook Blocking Unexpectedly](#hook-blocking-unexpectedly)
3. [Performance Issues](#performance-issues)
4. [State Corruption](#state-corruption)
5. [Multi-Agent Issues](#multi-agent-issues)
6. [Diagnostic Commands](#diagnostic-commands)
7. [Log Locations](#log-locations)

---

## Hook Not Firing

### Symptoms
- Expected hook behavior doesn't occur
- No trace entries in debug log
- No error messages

### Diagnostic Steps

```bash
# 1. Check if hooks.json exists and is valid
cat ~/.claude/hooks/hooks.json | jq .

# 2. Verify hook is enabled
jq '.hooks.PreToolUse[] | select(.hooks[].command | contains("git-safety"))' ~/.claude/hooks/hooks.json

# 3. Check if script exists and is executable
ls -la ~/.claude/scripts/hooks/safety/git-safety-check.js

# 4. Test hook manually
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force"}}' | node ~/.claude/scripts/hooks/safety/git-safety-check.js

# 5. Enable tracing and retry
export CLAUDE_HOOK_TRACE=1
# ... trigger the hook action ...
cat ~/.claude/debug/hooks/trace.jsonl | tail -20
```

### Common Causes

#### 1. Matcher Not Matching

**Problem:** Hook matcher doesn't match the tool name.

```json
// WRONG: Case mismatch
"matcher": "bash"

// CORRECT:
"matcher": "Bash"
```

**Solution:** Check exact tool name in Claude Code documentation.

#### 2. Hook Disabled

**Problem:** Hook has `"enabled": false` in config.

```bash
# Check enabled status
jq '.hooks.PreToolUse[] | {matcher, enabled}' ~/.claude/hooks/hooks.json
```

**Solution:** Set `"enabled": true` or remove the field.

#### 3. Missing Dependencies

**Problem:** Hook requires a library that's not installed.

```bash
# Test for missing dependencies
node -e "require('$HOME/.claude/scripts/hooks/lib/utils.js')"
```

**Solution:** Run `npm install` in hooks directory or fix require paths.

#### 4. Incorrect Event Type

**Problem:** Hook registered for wrong event (e.g., PostToolUse instead of PreToolUse).

```bash
# List all hooks by event type
jq 'keys' ~/.claude/hooks/hooks.json
jq '.hooks.PreToolUse[].description' ~/.claude/hooks/hooks.json
```

---

## Hook Blocking Unexpectedly

### Symptoms
- Operations blocked that should be allowed
- Error message from hook doesn't match situation
- User confused by block reason

### Diagnostic Steps

```bash
# 1. Enable tracing to see hook input/output
export CLAUDE_HOOK_TRACE=1

# 2. Check recent trace entries
tail -50 ~/.claude/debug/hooks/trace.jsonl | jq 'select(.event=="PreToolUse")'

# 3. Test specific input
echo '{"tool_name":"Bash","tool_input":{"command":"YOUR_COMMAND"}}' | node ~/.claude/scripts/hooks/safety/git-safety-check.js

# 4. Check for stale claims (file coordination)
cat ~/.claude/coordination/claims.json | jq '.claims | to_entries[] | select(.value.expiry < now)'
```

### Common Causes

#### 1. Stale File Claims

**Problem:** File claimed by previous session that crashed.

```bash
# View current claims
cat ~/.claude/coordination/claims.json | jq .

# Clear all claims (use with caution)
echo '{"claims":{}}' > ~/.claude/coordination/claims.json
```

**Solution:** Claims auto-expire after 5 minutes, or manually clear.

#### 2. False Positive in Safety Check

**Problem:** git-safety-check blocking non-destructive command.

```bash
# Check what patterns are being matched
grep -n "DESTRUCTIVE" ~/.claude/scripts/hooks/safety/git-safety-check.js
```

**Solution:** Add exception to hook logic or use `--allow-force` flag.

#### 3. TDD Mode Unintentionally Enabled

**Problem:** TDD guard blocking implementation code.

```bash
# Check TDD mode status
echo $TDD_MODE
ls -la .claude/tdd-mode 2>/dev/null

# Disable TDD mode
unset TDD_MODE
rm -f .claude/tdd-mode
```

#### 4. Port Conflict False Positive

**Problem:** Port check reports conflict but port is actually free.

```bash
# Verify port status directly
ss -tulpn | grep :3000
lsof -i :3000

# Check hook's port detection
node -e "const {execSync} = require('child_process'); console.log(execSync('ss -tulpn').toString())"
```

---

## Performance Issues

### Symptoms
- Noticeable delay before tool execution
- Hook timeout errors
- High CPU usage during hooks

### Diagnostic Steps

```bash
# 1. Measure hook execution time
time (echo '{}' | node ~/.claude/scripts/hooks/safety/git-safety-check.js)

# 2. Check for slow hooks in trace
cat ~/.claude/debug/hooks/trace.jsonl | jq -s 'sort_by(.duration_ms) | reverse | .[0:10] | .[] | {hook, duration_ms}'

# 3. Profile specific hook
node --prof ~/.claude/scripts/hooks/safety/git-safety-check.js < test-input.json
```

### Common Causes

#### 1. Synchronous I/O Operations

**Problem:** Hook reading/writing large files synchronously.

```javascript
// SLOW: Synchronous file operations
const data = fs.readFileSync(largeFile);

// BETTER: Only read what's needed
const data = fs.readFileSync(file, { encoding: 'utf8' }).slice(0, 1000);
```

**Solution:** Use streaming or limit data size.

#### 2. External Command Execution

**Problem:** Hook spawning slow external processes.

```bash
# Identify slow external calls
strace -f -e trace=execve node ~/.claude/scripts/hooks/safety/git-safety-check.js 2>&1 | grep execve
```

**Solution:** Cache results, use native JS implementations.

#### 3. Too Many Hooks on Same Event

**Problem:** Multiple hooks registered for same event run sequentially.

```bash
# Count hooks per event
jq '.hooks | to_entries[] | {key, count: (.value | length)}' ~/.claude/hooks/hooks.json
```

**Solution:** Consolidate hooks or parallelize where possible.

#### 4. Large State Files

**Problem:** State files (claims.json, state.json) grow unbounded.

```bash
# Check state file sizes
ls -lh ~/.claude/coordination/*.json
ls -lh ~/.claude/hive/*.json
ls -lh ~/.claude/metrics/*.json

# Cleanup old entries
node -e "
const fs = require('fs');
const claims = JSON.parse(fs.readFileSync('$HOME/.claude/coordination/claims.json'));
const now = Date.now();
const cleaned = Object.fromEntries(
  Object.entries(claims.claims || {})
    .filter(([k, v]) => new Date(v.expiry).getTime() > now)
);
fs.writeFileSync('$HOME/.claude/coordination/claims.json', JSON.stringify({claims: cleaned}, null, 2));
console.log('Cleaned', Object.keys(claims.claims || {}).length - Object.keys(cleaned).length, 'expired claims');
"
```

---

## State Corruption

### Symptoms
- JSON parse errors
- Unexpected hook behavior
- Inconsistent state across sessions

### Diagnostic Steps

```bash
# 1. Validate JSON files
for f in ~/.claude/coordination/*.json ~/.claude/hive/*.json ~/.claude/metrics/*.json; do
  echo -n "$f: "
  jq . "$f" > /dev/null 2>&1 && echo "OK" || echo "INVALID"
done

# 2. Check for truncated files
for f in ~/.claude/**/*.json; do
  if [ -f "$f" ] && [ $(wc -c < "$f") -lt 3 ]; then
    echo "Possibly truncated: $f"
  fi
done

# 3. Look for conflicting writes
grep -l "EBUSY\|EACCES" ~/.claude/logs/*.log 2>/dev/null
```

### Recovery Procedures

#### Reset Coordination State

```bash
# Backup current state
cp ~/.claude/coordination/claims.json ~/.claude/coordination/claims.json.bak
cp ~/.claude/coordination/task-claims.json ~/.claude/coordination/task-claims.json.bak

# Reset to clean state
echo '{"claims":{}}' > ~/.claude/coordination/claims.json
echo '{"claims":{}}' > ~/.claude/coordination/task-claims.json
```

#### Reset Hive State

```bash
# Backup
cp ~/.claude/hive/state.json ~/.claude/hive/state.json.bak

# Reset
echo '{"agents":{},"tasks":{},"hive_id":null}' > ~/.claude/hive/state.json
```

#### Reset Session State

```bash
# Remove session state (will start fresh next session)
rm -f ~/.claude/metrics/session_state.json
rm -f ~/.claude/metrics/session_insights.json
```

#### Full Reset (Nuclear Option)

```bash
# Backup everything first
tar -czvf ~/.claude/hooks-backup-$(date +%Y%m%d).tar.gz ~/.claude/{coordination,hive,metrics,debug}

# Reset all state
rm -rf ~/.claude/coordination/*.json
rm -rf ~/.claude/hive/*.json
rm -rf ~/.claude/metrics/*.json
rm -rf ~/.claude/debug/hooks/*.jsonl

# Recreate with defaults
echo '{"claims":{}}' > ~/.claude/coordination/claims.json
echo '{"claims":{}}' > ~/.claude/coordination/task-claims.json
echo '{"agents":{},"tasks":{},"hive_id":null}' > ~/.claude/hive/state.json
```

---

## Multi-Agent Issues

### Symptoms
- Agents stepping on each other's work
- Duplicate task execution
- File conflicts

### Diagnostic Steps

```bash
# 1. Check active claims
cat ~/.claude/coordination/claims.json | jq '.claims | to_entries | length'
cat ~/.claude/coordination/task-claims.json | jq '.claims | to_entries[] | select(.value.status=="running")'

# 2. Check hive status
node -e "
const state = require('$HOME/.claude/hive/state.json');
console.log('Agents:', Object.keys(state.agents || {}).length);
console.log('Tasks:', Object.keys(state.tasks || {}).length);
console.log('Active:', Object.values(state.agents || {}).filter(a => a.status === 'active').length);
"

# 3. Check for stuck agents
cat ~/.claude/coordination/coordination.log | grep -i stuck | tail -20
```

### Common Causes

#### 1. Orphaned Claims

**Problem:** Agent crashed without releasing claims.

```bash
# Find old claims (>1 hour)
node -e "
const fs = require('fs');
const claims = JSON.parse(fs.readFileSync('$HOME/.claude/coordination/claims.json'));
const now = Date.now();
const hour = 60 * 60 * 1000;
Object.entries(claims.claims || {}).forEach(([file, claim]) => {
  const age = now - new Date(claim.timestamp).getTime();
  if (age > hour) {
    console.log('Orphaned:', file, '(age:', Math.round(age/60000), 'min)');
  }
});
"
```

**Solution:** Claims auto-expire after 5 minutes. For immediate fix:
```bash
# Clear specific claim
node -e "
const fs = require('fs');
const file = '$HOME/.claude/coordination/claims.json';
const claims = JSON.parse(fs.readFileSync(file));
delete claims.claims['/path/to/stuck/file'];
fs.writeFileSync(file, JSON.stringify(claims, null, 2));
"
```

#### 2. Session ID Mismatch

**Problem:** Different sessions using same session ID.

```bash
# Check current session ID
cat ~/.claude/coordination/session_id

# Force new session ID
rm ~/.claude/coordination/session_id
```

#### 3. Hive Not Initialized

**Problem:** Multi-agent coordination attempted without hive init.

```bash
# Check hive status
cat ~/.claude/hive/state.json | jq '.hive_id'

# Initialize if null
node -e "
const fs = require('fs');
const state = JSON.parse(fs.readFileSync('$HOME/.claude/hive/state.json'));
if (!state.hive_id) {
  state.hive_id = 'hive_' + Date.now().toString(36);
  state.created_at = new Date().toISOString();
  fs.writeFileSync('$HOME/.claude/hive/state.json', JSON.stringify(state, null, 2));
  console.log('Initialized hive:', state.hive_id);
}
"
```

---

## Diagnostic Commands

### Quick Health Check

```bash
# Run full health check
node ~/.claude/scripts/hooks/debug/hook-health.js --check
```

### View Recent Traces

```bash
# Last 20 hook invocations
tail -20 ~/.claude/debug/hooks/trace.jsonl | jq .

# Filter by event type
cat ~/.claude/debug/hooks/trace.jsonl | jq 'select(.event=="PreToolUse")'

# Filter by hook name
cat ~/.claude/debug/hooks/trace.jsonl | jq 'select(.hook=="git-safety-check")'

# Slowest hooks
cat ~/.claude/debug/hooks/trace.jsonl | jq -s 'sort_by(.duration_ms) | reverse | .[0:5]'
```

### Test Individual Hook

```bash
# Create test input
cat > /tmp/hook-test.json << 'EOF'
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git status"
  }
}
EOF

# Run hook
node ~/.claude/scripts/hooks/safety/git-safety-check.js < /tmp/hook-test.json
```

### View Coordination State

```bash
# File claims
cat ~/.claude/coordination/claims.json | jq .

# Task claims
cat ~/.claude/coordination/task-claims.json | jq .

# Coordination log
tail -50 ~/.claude/coordination/coordination.log
```

### View Hive State

```bash
# Full state
cat ~/.claude/hive/state.json | jq .

# Agent summary
cat ~/.claude/hive/state.json | jq '.agents | to_entries[] | {id: .key, status: .value.status}'

# Task summary
cat ~/.claude/hive/state.json | jq '.tasks | to_entries[] | {id: .key, status: .value.status}'

# Hive log
tail -50 ~/.claude/hive/hive.log
```

---

## Log Locations

| Log | Location | Purpose |
|-----|----------|---------|
| Trace | `~/.claude/debug/hooks/trace.jsonl` | All hook invocations |
| Health | `~/.claude/debug/hooks/health.json` | Health check results |
| Coordination | `~/.claude/coordination/coordination.log` | File/task claims |
| Hive | `~/.claude/hive/hive.log` | Multi-agent activity |
| Ralph | `~/.claude/metrics/ralph_iterations.jsonl` | Ralph loop history |
| Session | `~/.claude/metrics/session_insights.json` | Session SSOT |

### Log Rotation

```bash
# Rotate trace log (>5MB)
if [ $(stat -f%z ~/.claude/debug/hooks/trace.jsonl 2>/dev/null || stat -c%s ~/.claude/debug/hooks/trace.jsonl) -gt 5000000 ]; then
  mv ~/.claude/debug/hooks/trace.jsonl ~/.claude/debug/hooks/trace.backup.jsonl
fi

# Cleanup old backups
find ~/.claude -name "*.backup.*" -mtime +7 -delete
```

---

## See Also

- [HOOKS-CATALOG.md](./HOOKS-CATALOG.md) - Complete hook reference
- [HOOKS-PERFORMANCE.md](./HOOKS-PERFORMANCE.md) - Performance tuning guide
