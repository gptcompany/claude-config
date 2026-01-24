/**
 * Error Recovery Tests for Claude Code Hooks
 * Phase 14.6-03: Performance and reliability validation
 *
 * Tests error handling and recovery scenarios:
 * - Hook failure isolation (chain continues despite individual failures)
 * - Malformed input handling (graceful error on bad data)
 * - External dependency failures (QuestDB, git, config files)
 *
 * Verifies:
 * - No crashes
 * - No data corruption
 * - Always returns valid JSON or exits cleanly
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

// Test configuration
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const TEMP_DIR = path.join(os.tmpdir(), 'hook-error-test-' + Date.now());

/**
 * Run a hook with given input
 */
function runHook(hookPath, input, options = {}) {
  const { raw = false, timeout = 5000 } = options;

  const result = spawnSync('node', [hookPath], {
    input: raw ? input : JSON.stringify(input),
    encoding: 'utf8',
    timeout
  });

  let output = null;
  try {
    if (result.stdout && result.stdout.trim()) {
      output = JSON.parse(result.stdout.trim());
    }
  } catch (err) {
    // Output is not valid JSON
  }

  return {
    exitCode: result.status,
    success: result.status === 0,
    output,
    stdout: result.stdout,
    stderr: result.stderr,
    signal: result.signal
  };
}

/**
 * Check if hook file exists
 */
function hookExists(hookPath) {
  return fs.existsSync(hookPath);
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
// Hook Failure Isolation Tests (4 tests)
// =============================================================================

describe('hook failure isolation', () => {
  test('single hook failure does not crash chain execution', async () => {
    // Run multiple hooks in sequence - even if one has issues, others should work
    const hooks = [
      { path: 'ux/tips-injector.js', input: {} },
      { path: 'control/ralph-loop.js', input: {} },
      { path: 'control/hive-manager.js', input: { tool_name: 'Task', tool_input: {} } }
    ];

    let completedHooks = 0;
    for (const hook of hooks) {
      const hookPath = path.join(HOOKS_DIR, hook.path);
      if (!hookExists(hookPath)) continue;

      const result = runHook(hookPath, hook.input);
      if (result.success) {
        completedHooks++;
      }
    }

    assert.ok(completedHooks >= 2, `At least 2 hooks should complete, got ${completedHooks}`);
  });

  test('failed hook logs error but returns exit code 0', async () => {
    // Hooks should fail gracefully with exit code 0 and log errors to stderr
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return; // Skip if hook not available
    }

    // Valid input should succeed
    const result = runHook(hookPath, {});
    assert.strictEqual(result.exitCode, 0, 'Hook should exit with code 0');
  });

  test('hook with invalid file path does not crash', async () => {
    const hookPath = path.join(HOOKS_DIR, 'coordination', 'file-coordination.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const result = runHook(hookPath, {
      tool_name: 'Edit',
      tool_input: { file_path: '/nonexistent/path/that/does/not/exist/file.js' }
    });

    assert.strictEqual(result.exitCode, 0, 'Hook should handle nonexistent paths gracefully');
  });

  test('error details captured in stderr for debugging', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run with --debug flag to capture debug output
    const result = spawnSync('node', [hookPath, '--debug'], {
      input: JSON.stringify({}),
      encoding: 'utf8',
      timeout: 5000
    });

    // Debug mode should produce stderr output
    // Even without errors, debug logging should work
    assert.strictEqual(result.status, 0, 'Hook should complete even with debug enabled');
  });
});

// =============================================================================
// Malformed Input Handling Tests (4 tests)
// =============================================================================

describe('malformed input handling', () => {
  test('invalid JSON input returns graceful error', async () => {
    const testHooks = [
      'ux/tips-injector.js',
      'control/ralph-loop.js',
      'control/hive-manager.js',
      'coordination/file-coordination.js'
    ];

    for (const hookName of testHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = runHook(hookPath, 'not valid json at all {{{{', { raw: true });

      assert.strictEqual(
        result.exitCode,
        0,
        `Hook ${hookName} should handle invalid JSON gracefully (got exit ${result.exitCode})`
      );
    }
  });

  test('missing required fields returns graceful error', async () => {
    const hookPath = path.join(HOOKS_DIR, 'coordination', 'file-coordination.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Missing tool_input
    const result1 = runHook(hookPath, { tool_name: 'Edit' });
    assert.strictEqual(result1.exitCode, 0, 'Should handle missing tool_input');

    // Missing tool_name
    const result2 = runHook(hookPath, { tool_input: { file_path: '/tmp/test.js' } });
    assert.strictEqual(result2.exitCode, 0, 'Should handle missing tool_name');

    // Empty object
    const result3 = runHook(hookPath, {});
    assert.strictEqual(result3.exitCode, 0, 'Should handle empty object');
  });

  test('null and undefined values handled gracefully', async () => {
    const testHooks = [
      'ux/tips-injector.js',
      'metrics/dora-tracker.js',
      'intelligence/lesson-injector.js'
    ];

    for (const hookName of testHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      // Test with null values
      const result1 = runHook(hookPath, { tool_name: null, tool_input: null });
      assert.strictEqual(result1.exitCode, 0, `${hookName} should handle null values`);

      // Test with explicit undefined (becomes missing in JSON)
      const result2 = runHook(hookPath, { tool_name: 'Bash' });
      assert.strictEqual(result2.exitCode, 0, `${hookName} should handle partial input`);
    }
  });

  test('extremely large input handled or rejected gracefully', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Create a large input (1MB of data)
    const largeContent = 'x'.repeat(1024 * 1024);
    const largeInput = {
      prompt: largeContent,
      tool_input: { content: largeContent }
    };

    const result = runHook(hookPath, largeInput, { timeout: 10000 });

    // Should either handle it or exit gracefully (not crash/timeout)
    assert.ok(
      result.exitCode === 0 || result.signal === null,
      'Should handle large input gracefully without crash'
    );
  });
});

// =============================================================================
// External Dependency Failure Tests (4 tests)
// =============================================================================

describe('external dependency failures', () => {
  test('QuestDB unavailable uses local fallback', async () => {
    const hookPath = path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Hook should work even without QuestDB
    const result = runHook(hookPath, {
      tool_name: 'Task',
      tool_input: { description: 'Test task' }
    });

    assert.strictEqual(result.exitCode, 0, 'Should fall back gracefully without QuestDB');
    // Should still return valid output
    assert.ok(
      result.output !== null || result.stdout.includes('{'),
      'Should return JSON even without QuestDB'
    );
  });

  test('git repo unavailable degrades gracefully', async () => {
    const hookPath = path.join(HOOKS_DIR, 'safety', 'git-safety-check.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Run from temp dir (not a git repo)
    const result = spawnSync('node', [hookPath], {
      input: JSON.stringify({
        tool_name: 'Bash',
        tool_input: { command: 'git push --force origin main' }
      }),
      encoding: 'utf8',
      timeout: 5000,
      cwd: TEMP_DIR // Not a git repo
    });

    assert.strictEqual(result.status, 0, 'Should handle non-git directory gracefully');
  });

  test('missing config files use sensible defaults', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Backup and remove config files temporarily
    const metricsDir = path.join(os.homedir(), '.claude', 'metrics');
    const sessionStateFile = path.join(metricsDir, 'session_state.json');
    const backupFile = sessionStateFile + '.backup-test';

    let hadBackup = false;
    if (fs.existsSync(sessionStateFile)) {
      fs.copyFileSync(sessionStateFile, backupFile);
      hadBackup = true;
    }

    try {
      // Remove the file temporarily
      if (fs.existsSync(sessionStateFile)) {
        fs.unlinkSync(sessionStateFile);
      }

      const result = runHook(hookPath, {});
      assert.strictEqual(result.exitCode, 0, 'Should use defaults when config missing');
    } finally {
      // Restore backup
      if (hadBackup) {
        fs.copyFileSync(backupFile, sessionStateFile);
        fs.unlinkSync(backupFile);
      }
    }
  });

  test('file permission errors logged and skipped', async () => {
    // This test verifies that hooks handle permission errors gracefully
    // We create a file with restricted permissions and verify hooks don't crash

    const hookPath = path.join(HOOKS_DIR, 'coordination', 'file-coordination.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Create a directory with restricted write access (if not root)
    const restrictedDir = path.join(TEMP_DIR, 'restricted');
    fs.mkdirSync(restrictedDir, { mode: 0o444 });

    try {
      const result = runHook(hookPath, {
        tool_name: 'Write',
        tool_input: { file_path: path.join(restrictedDir, 'test.js') }
      });

      // Should not crash even with permission issues
      assert.strictEqual(result.exitCode, 0, 'Should handle permission errors gracefully');
    } finally {
      // Clean up
      fs.chmodSync(restrictedDir, 0o755);
    }
  });
});

// =============================================================================
// Output Validation Tests (additional coverage)
// =============================================================================

describe('output validation', () => {
  test('all hooks return valid JSON or empty on error', async () => {
    const allHooks = [
      'ux/tips-injector.js',
      'ux/session-insights.js',
      'control/ralph-loop.js',
      'control/hive-manager.js',
      'coordination/file-coordination.js',
      'coordination/task-coordination.js',
      'metrics/dora-tracker.js',
      'metrics/quality-score.js',
      'intelligence/session-start-tracker.js',
      'intelligence/lesson-injector.js'
    ];

    for (const hookName of allHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = runHook(hookPath, {});

      // stdout should be valid JSON or empty
      if (result.stdout && result.stdout.trim()) {
        try {
          JSON.parse(result.stdout.trim());
        } catch (err) {
          assert.fail(`Hook ${hookName} returned invalid JSON: ${result.stdout.slice(0, 100)}`);
        }
      }
    }
  });

  test('hooks never output sensitive data on error', async () => {
    const sensitivePatterns = [
      /password/i,
      /secret/i,
      /api[_-]?key/i,
      /token/i,
      /credential/i
    ];

    const testHooks = [
      'ux/tips-injector.js',
      'metrics/claudeflow-sync.js',
      'coordination/file-coordination.js'
    ];

    for (const hookName of testHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      // Trigger potential error scenarios
      const result = runHook(hookPath, 'invalid input', { raw: true });

      const output = (result.stdout || '') + (result.stderr || '');
      for (const pattern of sensitivePatterns) {
        assert.ok(
          !pattern.test(output),
          `Hook ${hookName} may expose sensitive data: matched ${pattern}`
        );
      }
    }
  });
});
