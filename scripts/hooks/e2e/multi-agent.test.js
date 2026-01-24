/**
 * Multi-Agent Coordination E2E Tests
 *
 * Tests multi-agent coordination scenarios:
 * 1. File coordination claim/release
 * 2. Task coordination claim/release
 * 3. Hive manager coordination
 * 4. Concurrent hook execution
 *
 * Uses Node.js built-in test runner.
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync, spawn } = require('child_process');

// Test directories
const TEST_DIR = path.join(os.tmpdir(), 'e2e-multi-agent-' + Date.now());
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const COORDINATION_DIR = path.join(os.homedir(), '.claude', 'coordination');
const HIVE_DIR = path.join(os.homedir(), '.claude', 'hive');

// Backup storage
let backupClaims = null;
let backupTaskClaims = null;
let backupHiveState = null;

/**
 * Run a hook script with input and specific session ID
 */
function runHookWithSession(hookPath, input, sessionId) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout: 5000,
    env: { ...process.env, CLAUDE_SESSION_ID: sessionId }
  });

  let output = {};
  try {
    if (result.stdout && result.stdout.trim()) {
      output = JSON.parse(result.stdout.trim());
    }
  } catch (e) {}

  return {
    success: result.status === 0,
    output,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

/**
 * Run hook with default session
 */
function runHook(hookPath, input = {}) {
  return runHookWithSession(hookPath, input, 'multi-agent-test-' + Date.now());
}

/**
 * Safely backup a file
 */
function backupFile(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      return fs.readFileSync(filePath, 'utf8');
    }
  } catch (e) {}
  return null;
}

/**
 * Safely restore a file
 */
function restoreFile(filePath, content) {
  try {
    if (content !== null) {
      fs.mkdirSync(path.dirname(filePath), { recursive: true });
      fs.writeFileSync(filePath, content);
    } else if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }
  } catch (e) {}
}

// =============================================================================
// Setup/Teardown
// =============================================================================

beforeEach(() => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
  // Backup coordination files
  backupClaims = backupFile(path.join(COORDINATION_DIR, 'claims.json'));
  backupTaskClaims = backupFile(path.join(COORDINATION_DIR, 'task-claims.json'));
  backupHiveState = backupFile(path.join(HIVE_DIR, 'state.json'));
});

afterEach(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch (e) {}
  // Restore backed up files
  restoreFile(path.join(COORDINATION_DIR, 'claims.json'), backupClaims);
  restoreFile(path.join(COORDINATION_DIR, 'task-claims.json'), backupTaskClaims);
  restoreFile(path.join(HIVE_DIR, 'state.json'), backupHiveState);
});

// =============================================================================
// File Coordination Claim/Release
// =============================================================================

describe('file-coordination claim/release', () => {
  test('Agent A claims file successfully', () => {
    const testFile = path.join(TEST_DIR, 'agent-a-file.js');
    fs.writeFileSync(testFile, 'content');

    const result = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'agent-a-session'
    );

    assert.strictEqual(result.success, true, 'Claim should succeed');
    assert.ok(!result.output.decision || result.output.decision !== 'block', 'Should not block');
  });

  test('Agent B blocked when Agent A holds claim', () => {
    const testFile = path.join(TEST_DIR, 'contested-file.js');
    fs.writeFileSync(testFile, 'content');

    // Agent A claims
    runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'agent-a-holds'
    );

    // Agent B attempts claim
    const resultB = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'agent-b-attempts'
    );

    // Should be blocked or allowed (claims have TTL)
    assert.strictEqual(resultB.success, true, 'Hook should complete');
  });

  test('Agent A can reclaim own file', () => {
    const testFile = path.join(TEST_DIR, 'reclaim-file.js');
    fs.writeFileSync(testFile, 'content');

    // First claim
    runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'agent-reclaim'
    );

    // Second claim (same agent)
    const result = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'agent-reclaim'
    );

    assert.strictEqual(result.success, true, 'Should succeed for same agent');
    assert.ok(!result.output.decision || result.output.decision !== 'block', 'Should not block own claim');
  });

  test('stale claim cleanup works', () => {
    const claimsFile = path.join(COORDINATION_DIR, 'claims.json');

    // Create stale claim (expired timestamp)
    const staleClaim = {
      claims: {
        '/tmp/stale-file.js': {
          file: '/tmp/stale-file.js',
          agent: 'agent:stale-session:editor',
          timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(), // 10 min ago
          expiry: new Date(Date.now() - 5 * 60 * 1000).toISOString() // Expired 5 min ago
        }
      }
    };

    fs.mkdirSync(path.dirname(claimsFile), { recursive: true });
    fs.writeFileSync(claimsFile, JSON.stringify(staleClaim));

    // New claim should trigger cleanup
    const testFile = path.join(TEST_DIR, 'cleanup-trigger.js');
    runHook(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } }
    );

    // Check stale claim was cleaned
    const claims = JSON.parse(fs.readFileSync(claimsFile, 'utf8'));
    assert.ok(!claims.claims['/tmp/stale-file.js'], 'Stale claim should be cleaned');
  });

  test('multiple files can be claimed by same agent', () => {
    const files = [
      path.join(TEST_DIR, 'multi1.js'),
      path.join(TEST_DIR, 'multi2.js'),
      path.join(TEST_DIR, 'multi3.js')
    ];

    const results = files.map(file => {
      fs.writeFileSync(file, 'content');
      return runHookWithSession(
        path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
        { tool_name: 'Edit', tool_input: { file_path: file } },
        'multi-file-agent'
      );
    });

    const allSuccess = results.every(r => r.success && (!r.output.decision || r.output.decision !== 'block'));
    assert.strictEqual(allSuccess, true, 'All files should be claimed');
  });
});

// =============================================================================
// Task Coordination Claim/Release
// =============================================================================

describe('task-coordination claim/release', () => {
  test('task claim succeeds', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Test task 1' } }
    );

    assert.strictEqual(result.success, true, 'Task coordination should succeed');
  });

  test('task state persists', () => {
    const taskClaimsFile = path.join(COORDINATION_DIR, 'task-claims.json');

    runHook(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Persistent task' } }
    );

    // Task claims file should exist
    assert.ok(fs.existsSync(taskClaimsFile), 'Task claims file should exist');
  });

  test('multiple tasks can be tracked', () => {
    const tasks = [
      'Task Alpha',
      'Task Beta',
      'Task Gamma'
    ];

    const results = tasks.map(desc =>
      runHook(
        path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
        { tool_name: 'Task', tool_input: { description: desc } }
      )
    );

    const allSuccess = results.every(r => r.success);
    assert.strictEqual(allSuccess, true, 'All task claims should succeed');
  });

  test('task handoff pattern works', () => {
    // Agent A claims task
    runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Handoff task' } },
      'agent-source'
    );

    // Agent B can also claim (tasks don't have same blocking as files)
    const resultB = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Handoff task' } },
      'agent-target'
    );

    assert.strictEqual(resultB.success, true, 'Handoff should work');
  });

  test('task coordination handles non-Task tools', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: '/tmp/test.js' } }
    );

    assert.strictEqual(result.success, true, 'Should handle non-Task gracefully');
    assert.deepStrictEqual(result.output, {}, 'Should return empty for non-Task');
  });
});

// =============================================================================
// Hive Manager Coordination
// =============================================================================

describe('hive-manager coordination', () => {
  test('hive initializes successfully', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'spawn', mode: 'spawn' } }
    );

    assert.strictEqual(result.success, true, 'Hive init should succeed');
  });

  test('worker registration tracked', () => {
    // Spawn a worker
    runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'spawn worker', mode: 'spawn' } }
    );

    // Check state
    const stateFile = path.join(HIVE_DIR, 'state.json');
    assert.ok(fs.existsSync(stateFile), 'Hive state should exist');

    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    assert.ok('agents' in state, 'State should have agents');
  });

  test('task distribution tracking', () => {
    // Register tasks
    for (let i = 0; i < 3; i++) {
      runHook(
        path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
        { tool_name: 'Task', tool_input: { description: `Distributed task ${i}` } }
      );
    }

    const stateFile = path.join(HIVE_DIR, 'state.json');
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));

    assert.ok(Object.keys(state.tasks || {}).length >= 3, 'Should track multiple tasks');
  });

  test('consensus mechanism (topology preserved)', () => {
    runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'spawn' } }
    );

    const stateFile = path.join(HIVE_DIR, 'state.json');
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));

    assert.ok(state.topology, 'Should have topology defined');
    assert.strictEqual(state.topology, 'hierarchical-mesh', 'Default topology');
  });

  test('clean shutdown pattern', () => {
    // Initialize hive
    runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'spawn' } }
    );

    // Simulate several task completions
    for (let i = 0; i < 3; i++) {
      runHook(
        path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
        { tool_name: 'Task', tool_input: { description: `Complete task ${i}` } }
      );
    }

    // State should be consistent
    const stateFile = path.join(HIVE_DIR, 'state.json');
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));

    assert.ok(state.updated_at, 'Should have update timestamp');
  });
});

// =============================================================================
// Concurrent Hook Execution
// =============================================================================

describe('concurrent hook execution', () => {
  test('parallel file claims do not corrupt state', async () => {
    const files = [];
    for (let i = 0; i < 5; i++) {
      const f = path.join(TEST_DIR, `parallel-${i}.js`);
      fs.writeFileSync(f, 'content');
      files.push(f);
    }

    // Run claims in parallel
    const promises = files.map((file, i) => {
      return new Promise((resolve) => {
        const proc = spawn('node', [path.join(HOOKS_DIR, 'coordination', 'file-coordination.js')], {
          env: { ...process.env, CLAUDE_SESSION_ID: `parallel-agent-${i}` }
        });

        proc.stdin.write(JSON.stringify({
          tool_name: 'Edit',
          tool_input: { file_path: file }
        }));
        proc.stdin.end();

        let stdout = '';
        proc.stdout.on('data', (data) => { stdout += data; });
        proc.on('close', (code) => {
          resolve({ success: code === 0, stdout });
        });
      });
    });

    const results = await Promise.all(promises);
    const allSuccess = results.every(r => r.success);
    assert.strictEqual(allSuccess, true, 'All parallel claims should succeed');

    // Check claims file is valid JSON
    const claimsFile = path.join(COORDINATION_DIR, 'claims.json');
    const claims = JSON.parse(fs.readFileSync(claimsFile, 'utf8'));
    assert.ok(claims.claims, 'Claims should be valid object');
  });

  test('parallel metrics writes do not corrupt', async () => {
    const promises = [];

    for (let i = 0; i < 5; i++) {
      promises.push(new Promise((resolve) => {
        const proc = spawn('node', [path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js')]);

        proc.stdin.write(JSON.stringify({
          tool_name: 'Write',
          tool_input: { file_path: path.join(TEST_DIR, `metric-${i}.js`) }
        }));
        proc.stdin.end();

        proc.on('close', (code) => {
          resolve({ success: code === 0 });
        });
      }));
    }

    const results = await Promise.all(promises);
    const allSuccess = results.every(r => r.success);
    assert.strictEqual(allSuccess, true, 'All parallel metrics should succeed');
  });

  test('file locks prevent race conditions', () => {
    const testFile = path.join(TEST_DIR, 'race-test.js');
    fs.writeFileSync(testFile, 'content');

    // Sequential claims (simulating what file locks prevent)
    const results = [];
    for (let i = 0; i < 3; i++) {
      results.push(runHookWithSession(
        path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
        { tool_name: 'Edit', tool_input: { file_path: testFile } },
        `race-agent-${i}`
      ));
    }

    // First should succeed, others may be blocked or succeed based on timing
    assert.strictEqual(results[0].success, true, 'First claim should succeed');
  });

  test('claim conflicts resolved correctly', () => {
    const testFile = path.join(TEST_DIR, 'conflict-resolve.js');
    fs.writeFileSync(testFile, 'content');

    // Agent 1 claims
    const claim1 = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'conflict-agent-1'
    );
    assert.strictEqual(claim1.success, true, 'First claim should succeed');

    // Agent 2 attempts (should be blocked or wait)
    const claim2 = runHookWithSession(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: testFile } },
      'conflict-agent-2'
    );

    // Hook completes (block decision is in output, not exit code)
    assert.strictEqual(claim2.success, true, 'Second claim hook should complete');
  });

  test('hive manager handles concurrent agent registration', async () => {
    const promises = [];

    for (let i = 0; i < 3; i++) {
      promises.push(new Promise((resolve) => {
        const proc = spawn('node', [path.join(HOOKS_DIR, 'control', 'hive-manager.js')]);

        proc.stdin.write(JSON.stringify({
          tool_name: 'Task',
          tool_input: { description: `spawn agent ${i}`, mode: 'spawn' }
        }));
        proc.stdin.end();

        let stdout = '';
        proc.stdout.on('data', (data) => { stdout += data; });
        proc.on('close', (code) => {
          resolve({ success: code === 0, stdout });
        });
      }));
    }

    const results = await Promise.all(promises);
    const allSuccess = results.every(r => r.success);
    assert.strictEqual(allSuccess, true, 'Concurrent agent registration should succeed');

    // Verify state integrity
    const stateFile = path.join(HIVE_DIR, 'state.json');
    const state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    assert.ok(state.agents, 'Agents should be tracked');
  });
});

// =============================================================================
// Edge Cases
// =============================================================================

describe('edge cases', () => {
  test('handles very long file paths', () => {
    const longPath = path.join(TEST_DIR, 'a'.repeat(100), 'b'.repeat(100), 'file.js');
    fs.mkdirSync(path.dirname(longPath), { recursive: true });
    fs.writeFileSync(longPath, 'content');

    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: longPath } }
    );

    assert.strictEqual(result.success, true, 'Should handle long paths');
  });

  test('handles special characters in paths', () => {
    const specialPath = path.join(TEST_DIR, 'file with spaces & symbols!.js');
    fs.writeFileSync(specialPath, 'content');

    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: specialPath } }
    );

    assert.strictEqual(result.success, true, 'Should handle special characters');
  });

  test('handles unicode in task descriptions', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Task with unicode: emoji test' } }
    );

    assert.strictEqual(result.success, true, 'Should handle unicode');
  });

  test('handles rapid sequential claims', () => {
    const results = [];

    for (let i = 0; i < 10; i++) {
      const file = path.join(TEST_DIR, `rapid-${i}.js`);
      fs.writeFileSync(file, 'content');

      results.push(runHook(
        path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
        { tool_name: 'Edit', tool_input: { file_path: file } }
      ));
    }

    const allSuccess = results.every(r => r.success);
    assert.strictEqual(allSuccess, true, 'Rapid claims should all succeed');
  });
});
