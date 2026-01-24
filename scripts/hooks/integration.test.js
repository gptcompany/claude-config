/**
 * Integration Tests for Phase 14.5 Hooks
 *
 * Tests the complete hook chain:
 * - Session start -> tips injection -> intelligence hooks
 * - Tool use -> safety check -> productivity hooks -> quality hooks
 * - Session end -> analyzer -> insights -> SSOT
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawnSync } = require('child_process');

// Test directories
const TEST_DIR = path.join(os.tmpdir(), 'integration-test-' + Date.now());
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');

// Setup/teardown
beforeEach(() => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
});

afterEach(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch (e) {}
});

/**
 * Run a hook script with input
 */
function runHook(hookPath, input = {}) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout: 5000
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

// =============================================================================
// Session Lifecycle Tests
// =============================================================================

describe('session lifecycle', () => {
  test('session-start-tracker runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'intelligence', 'session-start-tracker.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });

  test('lesson-injector runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'intelligence', 'lesson-injector.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });

  test('tips-injector runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'ux', 'tips-injector.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });

  test('session-analyzer runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'intelligence', 'session-analyzer.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });

  test('session-insights runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'ux', 'session-insights.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });
});

// =============================================================================
// Tool Use Chain Tests
// =============================================================================

describe('tool use chain', () => {
  test('file-coordination handles Edit tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Edit', tool_input: { file_path: '/tmp/test.js' } }
    );
    assert.strictEqual(result.success, true);
  });

  test('task-coordination handles Task tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'task-coordination.js'),
      { tool_name: 'Task', tool_input: { description: 'Test task' } }
    );
    assert.strictEqual(result.success, true);
  });

  test('dora-tracker handles Write tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
      { tool_name: 'Write', tool_input: { file_path: '/tmp/test.js' } }
    );
    assert.strictEqual(result.success, true);
  });

  test('quality-score handles Bash with pytest', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'quality-score.js'),
      {
        tool_name: 'Bash',
        tool_input: { command: 'pytest tests/' },
        tool_output: '10 passed, 2 failed'
      }
    );
    assert.strictEqual(result.success, true);
  });

  test('claudeflow-sync handles Task tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js'),
      { tool_name: 'Task', tool_input: { description: 'Test' } }
    );
    assert.strictEqual(result.success, true);
  });

  test('hive-manager handles Task tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'Test' } }
    );
    assert.strictEqual(result.success, true);
    assert.ok(result.output.tracked);
  });
});

// =============================================================================
// Control Hooks Tests
// =============================================================================

describe('control hooks', () => {
  test('ralph-loop returns empty when not active', () => {
    const result = runHook(path.join(HOOKS_DIR, 'control', 'ralph-loop.js'));
    assert.strictEqual(result.success, true);
    assert.deepStrictEqual(result.output, {});
  });

  test('meta-learning runs without error', () => {
    const result = runHook(path.join(HOOKS_DIR, 'intelligence', 'meta-learning.js'));
    assert.strictEqual(result.success, true);
    assert.ok(typeof result.output === 'object');
  });
});

// =============================================================================
// State Persistence Tests
// =============================================================================

describe('state persistence', () => {
  test('session-insights creates SSOT file', () => {
    const metricsDir = path.join(os.homedir(), '.claude', 'metrics');
    const insightsFile = path.join(metricsDir, 'session_insights.json');

    // Run session-insights
    runHook(
      path.join(HOOKS_DIR, 'ux', 'session-insights.js'),
      { session_id: 'test-session-' + Date.now() }
    );

    // Check file exists
    assert.ok(fs.existsSync(insightsFile));

    // Check structure
    const data = JSON.parse(fs.readFileSync(insightsFile, 'utf8'));
    assert.strictEqual(data.$schema, 'session_insights_v1');
    assert.ok(data.session_id);
    assert.ok(data.ended_at);
  });

  test('hive-manager persists state', () => {
    const hiveDir = path.join(os.homedir(), '.claude', 'hive');
    const stateFile = path.join(hiveDir, 'state.json');

    // Run hive-manager with Task tool
    runHook(
      path.join(HOOKS_DIR, 'control', 'hive-manager.js'),
      { tool_name: 'Task', tool_input: { description: 'Persistence test' } }
    );

    // Check state file exists
    assert.ok(fs.existsSync(stateFile));

    // Check structure
    const data = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
    assert.ok('tasks' in data);
    assert.ok('agents' in data);
  });
});

// =============================================================================
// Hook Chain Integration
// =============================================================================

describe('hook chain integration', () => {
  test('hooks do not block each other on valid input', () => {
    // Simulate a session flow
    const hooks = [
      { path: 'intelligence/session-start-tracker.js', input: {} },
      { path: 'intelligence/lesson-injector.js', input: { prompt: 'test' } },
      { path: 'ux/tips-injector.js', input: {} },
      { path: 'coordination/file-coordination.js', input: { tool_name: 'Edit', tool_input: { file_path: '/tmp/x.js' } } },
      { path: 'metrics/dora-tracker.js', input: { tool_name: 'Edit', tool_input: { file_path: '/tmp/x.js' } } },
      { path: 'intelligence/session-analyzer.js', input: {} },
      { path: 'ux/session-insights.js', input: { session_id: 'chain-test' } }
    ];

    for (const hook of hooks) {
      const result = runHook(path.join(HOOKS_DIR, hook.path), hook.input);
      assert.strictEqual(result.success, true, `Hook ${hook.path} failed: ${result.stderr}`);
    }
  });

  test('hooks handle empty input gracefully', () => {
    const hookPaths = [
      'intelligence/session-start-tracker.js',
      'intelligence/lesson-injector.js',
      'intelligence/session-analyzer.js',
      'intelligence/meta-learning.js',
      'ux/tips-injector.js',
      'ux/session-insights.js',
      'control/ralph-loop.js',
      'control/hive-manager.js',
      'coordination/file-coordination.js',
      'coordination/task-coordination.js',
      'metrics/dora-tracker.js',
      'metrics/quality-score.js',
      'metrics/claudeflow-sync.js'
    ];

    for (const hookPath of hookPaths) {
      const result = runHook(path.join(HOOKS_DIR, hookPath), {});
      assert.strictEqual(result.success, true, `Hook ${hookPath} failed on empty input`);
    }
  });

  test('hooks handle malformed input gracefully', () => {
    const hookPaths = [
      'ux/tips-injector.js',
      'ux/session-insights.js',
      'control/ralph-loop.js',
      'control/hive-manager.js'
    ];

    for (const hookPath of hookPaths) {
      // Test with non-JSON input (simulated via modified runHook)
      const result = spawnSync('node', [path.join(HOOKS_DIR, hookPath)], {
        input: 'not json',
        encoding: 'utf8',
        timeout: 5000
      });

      assert.strictEqual(result.status, 0, `Hook ${hookPath} crashed on malformed input`);
    }
  });
});

// =============================================================================
// Performance Tests
// =============================================================================

describe('performance', () => {
  test('hooks complete within 500ms', () => {
    const hooks = [
      'ux/tips-injector.js',
      'ux/session-insights.js',
      'control/ralph-loop.js',
      'control/hive-manager.js'
    ];

    for (const hook of hooks) {
      const start = Date.now();
      runHook(path.join(HOOKS_DIR, hook), {});
      const elapsed = Date.now() - start;

      assert.ok(elapsed < 500, `Hook ${hook} took ${elapsed}ms (> 500ms)`);
    }
  });
});
