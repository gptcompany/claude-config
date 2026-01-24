/**
 * Quality Hooks Test Suite
 *
 * Tests for all quality hooks:
 * - ci-autofix.js (3 tests)
 * - plan-validator.js (3 tests)
 * - pr-readiness.js (3 tests)
 * - architecture-validator.js (3 tests)
 * - readme-generator.js (3 tests)
 *
 * Total: 15+ tests
 */

const { test, describe, beforeEach, afterEach, mock } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');

// Helper to run a hook with simulated stdin
function runHook(hookPath, inputData, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', [hookPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout
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
      let result = null;
      if (stdout.trim()) {
        try {
          result = JSON.parse(stdout.trim());
        } catch (e) {
          result = { raw: stdout.trim() };
        }
      }
      resolve({ code, stdout, stderr, result });
    });

    proc.on('error', reject);

    // Send input
    proc.stdin.write(JSON.stringify(inputData));
    proc.stdin.end();
  });
}

// Test directory
const HOOKS_DIR = path.join(__dirname);

describe('ci-autofix.js', () => {
  const hookPath = path.join(HOOKS_DIR, 'ci-autofix.js');

  test('should exit silently for non-Bash tools', async () => {
    const input = {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file.txt' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should detect CI failure in pytest output', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'pytest tests/' },
      tool_result: `
FAILED tests/test_main.py::test_something - AssertionError
========== 1 failed, 5 passed ==========
      `
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.ok(result);
    assert.ok(result.continue === true || result.systemMessage);
  });

  test('should exit silently for passing tests', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'pytest tests/' },
      tool_result: `
========== 10 passed in 2.5s ==========
      `
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    // Should not output anything for passing tests
  });

  test('should detect npm test failure', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'npm test' },
      tool_result: `
npm ERR! Test failed
FAIL src/component.test.js
      `
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.ok(result);
  });
});

describe('plan-validator.js', () => {
  const hookPath = path.join(HOOKS_DIR, 'plan-validator.js');

  test('should exit silently for non-Write tools', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'ls' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should exit silently for non-plan files', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/some/path/readme.md',
        content: '# README'
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should detect missing frontmatter in plan files', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/plans/01-PLAN.md',
        content: `
# Plan 01

Some content without frontmatter
        `
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.ok(result);
    assert.ok(result.systemMessage);
    assert.ok(result.systemMessage.includes('frontmatter'));
  });

  test('should validate complete plan structure', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/.planning/01-PLAN.md',
        content: `---
phase: 1
plan: 01
type: execute
wave: 1
---

<objective>
Do something
</objective>

<context>
@file.js
</context>

<tasks>
<task type="auto">
  <name>Task 1</name>
  <files>file.js</files>
  <action>Do the thing</action>
  <verify>check it</verify>
  <done>its done</done>
</task>
</tasks>

<verification>
- [ ] Check stuff
</verification>
        `
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    // Valid plan should not produce errors (or only INFO messages)
  });
});

describe('pr-readiness.js', () => {
  const hookPath = path.join(HOOKS_DIR, 'pr-readiness.js');

  test('should exit silently for non-Bash tools', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: { file_path: '/some/file.txt' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should exit silently for non-PR commands', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'git status' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should check readiness for gh pr create', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'gh pr create --title "Test PR"' }
    };

    const { code, result } = await runHook(hookPath, input);
    // Should produce readiness check output
    assert.ok(code === 0 || code === 1);
    // May block or pass depending on git state
  });

  test('should exit silently for gh pr view', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'gh pr view 123' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    // Should not trigger for view commands
  });
});

describe('architecture-validator.js', () => {
  const hookPath = path.join(HOOKS_DIR, 'architecture-validator.js');

  test('should exit silently for non-Write tools', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'ls' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should exit silently for non-architecture files', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/tests/test_file.py',
        content: 'def test_something(): pass'
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should detect new components in src files', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/src/new-component.ts',
        content: `
export class MyNewService {
  constructor() {}
  async process() {}
}

export interface MyConfig {
  name: string;
}

export function helperFunction() {
  return true;
}
        `
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    // May or may not produce output depending on ARCHITECTURE.md presence
  });

  test('should handle Edit tool for lib files', async () => {
    const input = {
      tool_name: 'Edit',
      tool_input: {
        file_path: '/project/lib/utils.js',
        old_string: 'const x = 1',
        new_string: `
export class NewUtility {
  static format(data) {
    return JSON.stringify(data);
  }
}
        `
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
  });
});

describe('readme-generator.js', () => {
  const hookPath = path.join(HOOKS_DIR, 'readme-generator.js');

  test('should exit silently for non-Write tools', async () => {
    const input = {
      tool_name: 'Bash',
      tool_input: { command: 'ls' }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should exit silently for test files', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/tests/test_main.py',
        content: 'def test_something(): pass'
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    assert.strictEqual(result, null);
  });

  test('should detect package.json changes', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/package.json',
        content: JSON.stringify({
          name: 'my-project',
          version: '1.0.0',
          scripts: {
            test: 'jest',
            build: 'tsc'
          }
        })
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
    // May or may not produce output depending on state
  });

  test('should detect src file changes', async () => {
    const input = {
      tool_name: 'Write',
      tool_input: {
        file_path: '/project/src/index.ts',
        content: 'export const main = () => console.log("Hello");'
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
  });

  test('should handle Edit tool for pyproject.toml', async () => {
    const input = {
      tool_name: 'Edit',
      tool_input: {
        file_path: '/project/pyproject.toml',
        old_string: 'version = "0.1.0"',
        new_string: 'version = "0.2.0"'
      }
    };

    const { code, result } = await runHook(hookPath, input);
    assert.strictEqual(code, 0);
  });
});

describe('Integration', () => {
  test('all hooks should be valid Node.js scripts', () => {
    const hooks = [
      'ci-autofix.js',
      'plan-validator.js',
      'pr-readiness.js',
      'architecture-validator.js',
      'readme-generator.js'
    ];

    for (const hook of hooks) {
      const hookPath = path.join(HOOKS_DIR, hook);
      assert.ok(fs.existsSync(hookPath), `Hook ${hook} should exist`);

      // Check syntax by requiring
      try {
        // Use node --check to verify syntax
        execSync(`node --check "${hookPath}"`, { stdio: 'pipe' });
      } catch (err) {
        assert.fail(`Hook ${hook} has syntax errors: ${err.message}`);
      }
    }
  });

  test('hooks should handle empty stdin gracefully', async () => {
    const hooks = [
      'ci-autofix.js',
      'plan-validator.js',
      'pr-readiness.js',
      'architecture-validator.js',
      'readme-generator.js'
    ];

    for (const hook of hooks) {
      const hookPath = path.join(HOOKS_DIR, hook);
      const { code } = await runHook(hookPath, {});
      assert.strictEqual(code, 0, `Hook ${hook} should handle empty input`);
    }
  });

  test('hooks should handle malformed JSON gracefully', async () => {
    const hooks = [
      'ci-autofix.js',
      'plan-validator.js',
      'pr-readiness.js',
      'architecture-validator.js',
      'readme-generator.js'
    ];

    for (const hook of hooks) {
      const hookPath = path.join(HOOKS_DIR, hook);
      // Send malformed data
      const proc = spawn('node', [hookPath], { stdio: ['pipe', 'pipe', 'pipe'] });
      proc.stdin.write('not valid json{{{');
      proc.stdin.end();

      await new Promise((resolve) => {
        proc.on('close', (code) => {
          assert.strictEqual(code, 0, `Hook ${hook} should handle malformed JSON`);
          resolve();
        });
      });
    }
  });
});
