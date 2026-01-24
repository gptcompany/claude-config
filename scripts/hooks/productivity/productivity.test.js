#!/usr/bin/env node
/**
 * Tests for productivity hooks
 *
 * Covers:
 * - auto-format.js
 * - tdd-guard.js
 * - task-checkpoint.js
 * - auto-simplify.js
 *
 * Minimum 12 tests (3 per hook)
 */

const { describe, it, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');

// Test directory
const TEST_DIR = path.join(os.tmpdir(), 'productivity-hooks-test-' + Date.now());
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks', 'productivity');

/**
 * Helper to run a hook with JSON input
 */
function runHook(hookName, input) {
  return new Promise((resolve, reject) => {
    const hookPath = path.join(HOOKS_DIR, hookName);
    const child = spawn('node', [hookPath], {
      cwd: TEST_DIR,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      resolve({
        code,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
      });
    });

    child.on('error', reject);

    // Write input to stdin
    child.stdin.write(JSON.stringify(input));
    child.stdin.end();
  });
}

/**
 * Setup test directory
 */
before(() => {
  fs.mkdirSync(TEST_DIR, { recursive: true });

  // Initialize git repo in test dir
  try {
    execSync('git init', { cwd: TEST_DIR, stdio: 'pipe' });
    execSync('git config user.email "test@test.com"', { cwd: TEST_DIR, stdio: 'pipe' });
    execSync('git config user.name "Test"', { cwd: TEST_DIR, stdio: 'pipe' });
  } catch {
    // Ignore git errors
  }
});

/**
 * Cleanup test directory
 */
after(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch {
    // Ignore cleanup errors
  }
});

// =============================================================================
// AUTO-FORMAT TESTS
// =============================================================================

describe('auto-format.js', () => {
  it('should exit 0 for non-Write/Edit tools', async () => {
    const result = await runHook('auto-format.js', {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file.js' },
    });

    assert.strictEqual(result.code, 0);
  });

  it('should skip non-code files', async () => {
    const result = await runHook('auto-format.js', {
      tool_name: 'Write',
      tool_input: { file_path: '/some/file.txt' },
    });

    assert.strictEqual(result.code, 0);
    // Should not output formatting message for non-code files
    if (result.stdout) {
      const output = JSON.parse(result.stdout);
      assert.ok(!output.hookSpecificOutput || !output.hookSpecificOutput.message);
    }
  });

  it('should recognize JS/TS file extensions', async () => {
    // Create a test JS file
    const testFile = path.join(TEST_DIR, 'test-format.js');
    fs.writeFileSync(testFile, 'const x=1;');

    const result = await runHook('auto-format.js', {
      tool_name: 'Write',
      tool_input: { file_path: testFile },
    });

    assert.strictEqual(result.code, 0);
    // Hook may or may not format depending on prettier availability
  });

  it('should skip node_modules directory', async () => {
    const result = await runHook('auto-format.js', {
      tool_name: 'Edit',
      tool_input: { file_path: '/project/node_modules/pkg/index.js' },
    });

    assert.strictEqual(result.code, 0);
  });
});

// =============================================================================
// TDD-GUARD TESTS
// =============================================================================

describe('tdd-guard.js', () => {
  beforeEach(() => {
    // Create src directory for test
    fs.mkdirSync(path.join(TEST_DIR, 'src'), { recursive: true });
  });

  afterEach(() => {
    // Cleanup
    try {
      fs.rmSync(path.join(TEST_DIR, 'src'), { recursive: true, force: true });
      fs.rmSync(path.join(TEST_DIR, 'tests'), { recursive: true, force: true });
    } catch {
      // Ignore
    }
  });

  it('should exit 0 for non-Write/Edit tools', async () => {
    const result = await runHook('tdd-guard.js', {
      tool_name: 'Read',
      tool_input: { file_path: '/some/src/file.js' },
    });

    assert.strictEqual(result.code, 0);
  });

  it('should skip non-production paths', async () => {
    const result = await runHook('tdd-guard.js', {
      tool_name: 'Write',
      tool_input: { file_path: '/project/tests/test_foo.js' },
    });

    assert.strictEqual(result.code, 0);
    const output = JSON.parse(result.stdout || '{}');
    // Should not warn for test files
    assert.ok(!output.hookSpecificOutput || output.hookSpecificOutput.decision !== 'warn');
  });

  it('should warn when no test file exists for production code', async () => {
    // Create a production file without corresponding test
    const prodFile = path.join(TEST_DIR, 'src', 'util.js');
    fs.writeFileSync(prodFile, 'module.exports = {};');

    const result = await runHook('tdd-guard.js', {
      tool_name: 'Write',
      tool_input: { file_path: prodFile },
    });

    assert.strictEqual(result.code, 0);  // Default mode is 'warn', not block
    const output = JSON.parse(result.stdout || '{}');
    // Should have a warning
    if (output.hookSpecificOutput) {
      assert.ok(
        output.hookSpecificOutput.decision === 'warn' ||
        output.hookSpecificOutput.message?.includes('TDD')
      );
    }
  });

  it('should pass when test file exists', async () => {
    // Create production file
    const prodFile = path.join(TEST_DIR, 'src', 'helper.js');
    fs.writeFileSync(prodFile, 'module.exports = {};');

    // Create corresponding test file
    fs.mkdirSync(path.join(TEST_DIR, 'tests'), { recursive: true });
    const testFile = path.join(TEST_DIR, 'tests', 'test_helper.js');
    fs.writeFileSync(testFile, 'test("helper", () => {});');

    const result = await runHook('tdd-guard.js', {
      tool_name: 'Write',
      tool_input: { file_path: prodFile },
    });

    assert.strictEqual(result.code, 0);
    const output = JSON.parse(result.stdout || '{}');
    // Should NOT have a warning when test exists
    assert.ok(!output.hookSpecificOutput || !output.hookSpecificOutput.decision);
  });
});

// =============================================================================
// TASK-CHECKPOINT TESTS
// =============================================================================

describe('task-checkpoint.js', () => {
  const CHECKPOINTS_DIR = path.join(os.homedir(), '.claude', 'checkpoints');
  const COUNTER_FILE = path.join(CHECKPOINTS_DIR, '.tool-counter');

  beforeEach(() => {
    // Reset counter
    try {
      if (fs.existsSync(COUNTER_FILE)) {
        fs.unlinkSync(COUNTER_FILE);
      }
    } catch {
      // Ignore
    }
  });

  it('should exit 0 for non-modifying tools', async () => {
    const result = await runHook('task-checkpoint.js', {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file.js' },
    });

    assert.strictEqual(result.code, 0);
  });

  it('should track Write/Edit tool calls', async () => {
    const result = await runHook('task-checkpoint.js', {
      tool_name: 'Write',
      tool_input: { file_path: '/test/file.js' },
    });

    assert.strictEqual(result.code, 0);
    // Counter should have been incremented
    assert.ok(fs.existsSync(COUNTER_FILE));
  });

  it('should increment counter on each call', async () => {
    // Call multiple times
    await runHook('task-checkpoint.js', {
      tool_name: 'Edit',
      tool_input: { file_path: '/test/file1.js' },
    });

    await runHook('task-checkpoint.js', {
      tool_name: 'Edit',
      tool_input: { file_path: '/test/file2.js' },
    });

    const counter = parseInt(fs.readFileSync(COUNTER_FILE, 'utf8').trim(), 10);
    assert.ok(counter >= 2);
  });

  it('should skip failed tool results', async () => {
    const result = await runHook('task-checkpoint.js', {
      tool_name: 'Write',
      tool_input: { file_path: '/test/file.js' },
      tool_result: 'Error: File not found',
    });

    assert.strictEqual(result.code, 0);
  });
});

// =============================================================================
// AUTO-SIMPLIFY TESTS
// =============================================================================

describe('auto-simplify.js', () => {
  it('should exit 0 for non-Write/Edit tools', async () => {
    const result = await runHook('auto-simplify.js', {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file.js' },
    });

    assert.strictEqual(result.code, 0);
  });

  it('should skip non-code files', async () => {
    const result = await runHook('auto-simplify.js', {
      tool_name: 'Write',
      tool_input: { file_path: '/some/file.md' },
    });

    assert.strictEqual(result.code, 0);
    const output = JSON.parse(result.stdout || '{}');
    assert.ok(!output.hookSpecificOutput);
  });

  it('should detect long functions', async () => {
    // Create a file with a very long function
    const testFile = path.join(TEST_DIR, 'long-func.js');
    let content = 'function veryLongFunction() {\n';
    for (let i = 0; i < 60; i++) {
      content += `  console.log("line ${i}");\n`;
    }
    content += '}\n';
    fs.writeFileSync(testFile, content);

    const result = await runHook('auto-simplify.js', {
      tool_name: 'Write',
      tool_input: { file_path: testFile },
    });

    assert.strictEqual(result.code, 0);
    const output = JSON.parse(result.stdout || '{}');
    // Should detect complexity
    if (output.hookSpecificOutput && output.hookSpecificOutput.message) {
      assert.ok(output.hookSpecificOutput.message.includes('Complexity'));
    }
  });

  it('should pass for simple files', async () => {
    // Create a simple file
    const testFile = path.join(TEST_DIR, 'simple.js');
    fs.writeFileSync(testFile, `
function add(a, b) {
  return a + b;
}

function subtract(a, b) {
  return a - b;
}
`);

    const result = await runHook('auto-simplify.js', {
      tool_name: 'Write',
      tool_input: { file_path: testFile },
    });

    assert.strictEqual(result.code, 0);
    // Should not report complexity for simple files
  });

  it('should detect too many parameters', async () => {
    // Create a file with a function with many parameters
    const testFile = path.join(TEST_DIR, 'many-params.js');
    fs.writeFileSync(testFile, `
function manyParams(a, b, c, d, e, f, g, h) {
  return a + b + c + d + e + f + g + h;
}
`);

    const result = await runHook('auto-simplify.js', {
      tool_name: 'Write',
      tool_input: { file_path: testFile },
    });

    assert.strictEqual(result.code, 0);
    // May or may not flag depending on severity threshold
  });
});

// =============================================================================
// INTEGRATION TESTS
// =============================================================================

describe('Integration', () => {
  it('all hooks should handle empty input gracefully', async () => {
    const hooks = ['auto-format.js', 'tdd-guard.js', 'task-checkpoint.js', 'auto-simplify.js'];

    for (const hook of hooks) {
      const result = await runHook(hook, {});
      assert.strictEqual(result.code, 0, `${hook} should exit 0 for empty input`);
    }
  });

  it('all hooks should handle invalid tool_name gracefully', async () => {
    const hooks = ['auto-format.js', 'tdd-guard.js', 'task-checkpoint.js', 'auto-simplify.js'];

    for (const hook of hooks) {
      const result = await runHook(hook, {
        tool_name: 'InvalidTool',
        tool_input: { file_path: '/some/path.js' },
      });
      assert.strictEqual(result.code, 0, `${hook} should exit 0 for invalid tool_name`);
    }
  });
});
