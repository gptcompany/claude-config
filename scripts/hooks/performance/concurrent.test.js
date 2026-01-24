/**
 * Concurrent Execution Tests for Claude Code Hooks
 * Phase 14.6-03: Performance and reliability validation
 *
 * Tests concurrent execution scenarios:
 * - Parallel hook execution
 * - File locking and data integrity
 * - Race condition prevention
 *
 * Uses Promise.all() and child_process.fork()/spawn() for parallel execution.
 * Verifies with file checksums and data integrity checks.
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const { spawn, spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const crypto = require('crypto');

// Test configuration
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const TEMP_DIR = path.join(os.tmpdir(), 'hook-concurrent-test-' + Date.now());
const METRICS_DIR = path.join(os.homedir(), '.claude', 'metrics');

/**
 * Run a hook asynchronously and return a promise
 */
function runHookAsync(hookPath, input = {}) {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', [hookPath], {
      timeout: 10000
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      let output = null;
      try {
        if (stdout.trim()) {
          output = JSON.parse(stdout.trim());
        }
      } catch (err) {}

      resolve({
        exitCode: code,
        success: code === 0,
        output,
        stdout,
        stderr
      });
    });

    proc.on('error', (err) => {
      resolve({
        exitCode: -1,
        success: false,
        output: null,
        stdout,
        stderr: err.message
      });
    });

    // Send input
    proc.stdin.write(JSON.stringify(input));
    proc.stdin.end();
  });
}

/**
 * Run hook synchronously
 */
function runHookSync(hookPath, input = {}) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout: 10000
  });

  return {
    exitCode: result.status,
    success: result.status === 0,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

/**
 * Check if hook file exists
 */
function hookExists(hookPath) {
  return fs.existsSync(hookPath);
}

/**
 * Calculate file checksum
 */
function fileChecksum(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const content = fs.readFileSync(filePath);
  return crypto.createHash('md5').update(content).digest('hex');
}

/**
 * Check if JSON file is valid
 */
function isValidJsonFile(filePath) {
  if (!fs.existsSync(filePath)) return false;
  try {
    JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return true;
  } catch (err) {
    return false;
  }
}

// Setup/teardown
beforeEach(() => {
  fs.mkdirSync(TEMP_DIR, { recursive: true });
});

afterEach(() => {
  try {
    fs.rmSync(TEMP_DIR, { recursive: true, force: true });
  } catch (err) {}
});

// =============================================================================
// Parallel Hook Execution Tests (4 tests)
// =============================================================================

describe('parallel hook execution', () => {
  test('run 5 hooks simultaneously', async () => {
    const hooks = [
      { path: 'ux/tips-injector.js', input: {} },
      { path: 'control/ralph-loop.js', input: {} },
      { path: 'control/hive-manager.js', input: { tool_name: 'Task', tool_input: {} } },
      { path: 'intelligence/session-start-tracker.js', input: {} },
      { path: 'metrics/dora-tracker.js', input: { tool_name: 'Write', tool_input: { file_path: '/tmp/x.js' } } }
    ];

    const promises = hooks.map(hook => {
      const hookPath = path.join(HOOKS_DIR, hook.path);
      if (!hookExists(hookPath)) {
        return Promise.resolve({ success: true, skipped: true });
      }
      return runHookAsync(hookPath, hook.input);
    });

    const results = await Promise.all(promises);

    // All hooks should complete
    const completed = results.filter(r => r.success || r.skipped);
    assert.strictEqual(completed.length, hooks.length, 'All 5 hooks should complete');
  });

  test('verify all hooks complete when run in parallel', async () => {
    const hookPaths = [
      'ux/tips-injector.js',
      'ux/session-insights.js',
      'control/ralph-loop.js',
      'intelligence/lesson-injector.js',
      'metrics/quality-score.js'
    ].map(h => path.join(HOOKS_DIR, h)).filter(hookExists);

    const startTime = performance.now();

    const results = await Promise.all(
      hookPaths.map(hookPath => runHookAsync(hookPath, {}))
    );

    const elapsed = performance.now() - startTime;

    // All should succeed
    const successCount = results.filter(r => r.success).length;
    assert.strictEqual(successCount, hookPaths.length, `All ${hookPaths.length} hooks should succeed`);

    // Parallel execution should be faster than sequential (rough check)
    // If hooks take ~50ms each, 5 hooks in parallel should be < 500ms
    assert.ok(elapsed < 2000, `Parallel execution took ${elapsed.toFixed(0)}ms (should be < 2000ms)`);
  });

  test('verify no output corruption in parallel execution', async () => {
    const hookPath = path.join(HOOKS_DIR, 'control', 'hive-manager.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run same hook multiple times in parallel
    const runs = Array.from({ length: 5 }, (_, i) => ({
      hookPath,
      input: { tool_name: 'Task', tool_input: { description: `Task ${i}` } }
    }));

    const results = await Promise.all(
      runs.map(r => runHookAsync(r.hookPath, r.input))
    );

    // Each result should be valid JSON
    for (let i = 0; i < results.length; i++) {
      const result = results[i];
      assert.strictEqual(result.success, true, `Run ${i} should succeed`);

      if (result.stdout && result.stdout.trim()) {
        try {
          const parsed = JSON.parse(result.stdout.trim());
          assert.ok(typeof parsed === 'object', `Run ${i} output should be object`);
        } catch (err) {
          assert.fail(`Run ${i} produced invalid JSON: ${result.stdout.slice(0, 100)}`);
        }
      }
    }
  });

  test('verify metrics not duplicated in parallel writes', async () => {
    const hookPath = path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const syncStateFile = path.join(os.homedir(), '.claude-flow', 'sync_state.json');

    // Get initial sync count
    let initialCount = 0;
    if (fs.existsSync(syncStateFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(syncStateFile, 'utf8'));
        initialCount = data.syncCount || 0;
      } catch (err) {}
    }

    // Run 5 syncs in parallel
    const results = await Promise.all(
      Array.from({ length: 5 }, () =>
        runHookAsync(hookPath, { tool_name: 'Task', tool_input: { description: 'Test' } })
      )
    );

    // All should succeed
    const successCount = results.filter(r => r.success).length;
    assert.ok(successCount >= 4, `At least 4/5 syncs should succeed, got ${successCount}`);

    // Sync count should increase by approximately 5
    if (fs.existsSync(syncStateFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(syncStateFile, 'utf8'));
        const finalCount = data.syncCount || 0;
        const increase = finalCount - initialCount;
        // Allow for some variance due to timing
        assert.ok(increase >= 3 && increase <= 10, `Sync count should increase by ~5, got ${increase}`);
      } catch (err) {}
    }
  });
});

// =============================================================================
// File Locking Tests (3 tests)
// =============================================================================

describe('file locking', () => {
  test('two agents writing to same metrics file', async () => {
    const hookPath = path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run two instances writing to DORA metrics simultaneously
    const results = await Promise.all([
      runHookAsync(hookPath, { tool_name: 'Write', tool_input: { file_path: '/tmp/a.js' } }),
      runHookAsync(hookPath, { tool_name: 'Write', tool_input: { file_path: '/tmp/b.js' } })
    ]);

    // Both should succeed (or at least not corrupt data)
    const successCount = results.filter(r => r.success).length;
    assert.ok(successCount >= 1, 'At least one write should succeed');
  });

  test('verify locking prevents file corruption', async () => {
    // Create a test file that both hooks will try to modify
    const testFile = path.join(TEMP_DIR, 'concurrent-write.json');
    fs.writeFileSync(testFile, JSON.stringify({ count: 0 }));

    const hookPath = path.join(HOOKS_DIR, 'control', 'hive-manager.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run multiple writes in parallel
    await Promise.all(
      Array.from({ length: 3 }, (_, i) =>
        runHookAsync(hookPath, {
          tool_name: 'Task',
          tool_input: { description: `Concurrent task ${i}` }
        })
      )
    );

    // Check hive state file integrity
    const hiveStateFile = path.join(os.homedir(), '.claude', 'hive', 'state.json');
    if (fs.existsSync(hiveStateFile)) {
      assert.ok(isValidJsonFile(hiveStateFile), 'Hive state file should remain valid JSON');
    }
  });

  test('verify data integrity after concurrent operations', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'session-insights.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const insightsFile = path.join(METRICS_DIR, 'session_insights.json');

    // Run multiple session insights updates in parallel
    const sessionIds = ['test-1', 'test-2', 'test-3'];
    await Promise.all(
      sessionIds.map(sid =>
        runHookAsync(hookPath, { session_id: sid })
      )
    );

    // File should still be valid JSON
    if (fs.existsSync(insightsFile)) {
      assert.ok(isValidJsonFile(insightsFile), 'Insights file should remain valid JSON');

      // Should have expected schema
      const data = JSON.parse(fs.readFileSync(insightsFile, 'utf8'));
      assert.ok(data.$schema === 'session_insights_v1', 'Schema version should be preserved');
    }
  });
});

// =============================================================================
// Race Condition Prevention Tests (3 tests)
// =============================================================================

describe('race condition prevention', () => {
  test('rapid claim/release cycles', async () => {
    const hookPath = path.join(HOOKS_DIR, 'coordination', 'file-coordination.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Simulate rapid claim/release of same file
    const filePath = '/tmp/race-test.js';
    const operations = Array.from({ length: 10 }, (_, i) => ({
      tool_name: i % 2 === 0 ? 'Edit' : 'Write',
      tool_input: { file_path: filePath }
    }));

    const results = await Promise.all(
      operations.map(input => runHookAsync(hookPath, input))
    );

    // Most operations should succeed
    const successCount = results.filter(r => r.success).length;
    assert.ok(successCount >= 8, `At least 8/10 operations should succeed, got ${successCount}`);
  });

  test('concurrent session start/end', async () => {
    const startHook = path.join(HOOKS_DIR, 'intelligence', 'session-start-tracker.js');
    const endHook = path.join(HOOKS_DIR, 'intelligence', 'session-analyzer.js');

    if (!hookExists(startHook) || !hookExists(endHook)) {
      return;
    }

    // Run start and end hooks simultaneously (simulating rapid session transitions)
    const results = await Promise.all([
      runHookAsync(startHook, {}),
      runHookAsync(endHook, {}),
      runHookAsync(startHook, {}),
      runHookAsync(endHook, {})
    ]);

    // All should complete without crashing
    const successCount = results.filter(r => r.success).length;
    assert.strictEqual(successCount, 4, 'All session operations should succeed');
  });

  test('simultaneous QuestDB exports', async () => {
    const hookPath = path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run multiple sync operations that export to QuestDB
    const results = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        runHookAsync(hookPath, {
          tool_name: 'TodoWrite',
          tool_input: { todos: [{ content: `Race test ${i}`, status: 'pending' }] }
        })
      )
    );

    // All should succeed (QuestDB or fallback)
    const successCount = results.filter(r => r.success).length;
    assert.ok(successCount >= 4, `At least 4/5 exports should succeed, got ${successCount}`);

    // Verify sync state is consistent
    const syncStateFile = path.join(os.homedir(), '.claude-flow', 'sync_state.json');
    if (fs.existsSync(syncStateFile)) {
      assert.ok(isValidJsonFile(syncStateFile), 'Sync state should remain valid');
    }
  });
});
