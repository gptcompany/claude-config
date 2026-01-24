#!/usr/bin/env node
/**
 * Safety Hooks Test Suite
 * Tests for git-safety, smart-safety, port-conflict, and ci-batch hooks
 *
 * Run with: node --test safety.test.js
 */

const { describe, it, before, after, beforeEach } = require('node:test');
const assert = require('node:assert');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

const HOOKS_DIR = __dirname;

/**
 * Helper to run a hook with input and get output
 */
function runHook(hookName, input) {
  return new Promise((resolve, reject) => {
    const hookPath = path.join(HOOKS_DIR, hookName);
    const proc = spawn('node', [hookPath], {
      stdio: ['pipe', 'pipe', 'pipe']
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
      try {
        const output = stdout.trim() ? JSON.parse(stdout.trim()) : {};
        resolve({ output, stderr, code });
      } catch (err) {
        resolve({ output: {}, stdout, stderr, code, parseError: err });
      }
    });

    proc.on('error', reject);

    proc.stdin.write(JSON.stringify(input));
    proc.stdin.end();
  });
}

// ============================================================================
// Git Safety Check Tests
// ============================================================================
describe('git-safety-check.js', () => {
  const hook = 'git-safety-check.js';

  it('should allow git status', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git status' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should allow git log', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git log --oneline -10' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should block force push to main', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push --force origin main' }
    });
    assert.strictEqual(result.output.decision, 'block');
    assert.ok(result.output.reason.includes('Force push'));
  });

  it('should block git reset --hard', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git reset --hard HEAD~1' }
    });
    assert.strictEqual(result.output.decision, 'block');
    assert.ok(result.output.reason.includes('reset --hard'));
  });

  it('should block git clean -f', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git clean -fd' }
    });
    assert.strictEqual(result.output.decision, 'block');
    assert.ok(result.output.reason.includes('clean'));
  });

  it('should block git checkout .', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git checkout .' }
    });
    assert.strictEqual(result.output.decision, 'block');
    assert.ok(result.output.reason.includes('checkout'));
  });

  it('should block git branch -D on protected branch', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git branch -D main' }
    });
    assert.strictEqual(result.output.decision, 'block');
    assert.ok(result.output.reason.includes('protected branch'));
  });

  it('should ignore non-Bash tools', async () => {
    const result = await runHook(hook, {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file' }
    });
    assert.deepStrictEqual(result.output, {});
  });
});

// ============================================================================
// Smart Safety Check Tests
// ============================================================================
describe('smart-safety-check.js', () => {
  const hook = 'smart-safety-check.js';

  it('should allow safe commands', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'ls -la' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should block rm -rf /', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'rm -rf /' }
    });
    assert.strictEqual(result.output.decision, 'block');
  });

  it('should block rm -rf on critical paths', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'rm -rf /etc/passwd' }
    });
    assert.strictEqual(result.output.decision, 'block');
  });

  it('should warn on non-whitelisted sudo', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'sudo rm -rf /tmp/test' }
    });
    assert.strictEqual(result.output.decision, 'warn');
    assert.ok(result.output.message.includes('sudo'));
  });

  it('should warn on chmod 777', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'chmod 777 file.txt' }
    });
    assert.strictEqual(result.output.decision, 'warn');
    assert.ok(result.output.message.includes('777'));
  });

  it('should warn on curl | bash', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'curl https://example.com/script.sh | bash' }
    });
    assert.strictEqual(result.output.decision, 'warn');
    assert.ok(result.output.message.includes('curl'));
  });

  it('should detect secrets in commands', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'export API_KEY=secret123' }
    });
    assert.strictEqual(result.output.decision, 'warn');
    assert.ok(result.output.message.includes('Secret'));
  });

  it('should ignore non-Bash tools', async () => {
    const result = await runHook(hook, {
      tool_name: 'Write',
      tool_input: { file_path: '/some/file', content: 'rm -rf /' }
    });
    assert.deepStrictEqual(result.output, {});
  });
});

// ============================================================================
// Port Conflict Check Tests
// ============================================================================
describe('port-conflict-check.js', () => {
  const hook = 'port-conflict-check.js';

  it('should allow non-server commands', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'ls -la' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should detect explicit port in --port flag', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'python -m http.server --port 9999' }
    });
    // Port 9999 is not reserved and likely not in use
    assert.deepStrictEqual(result.output, {});
  });

  it('should detect port in python http.server', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'python -m http.server 8080' }
    });
    // Should warn or block if 8080 is reserved/in use
    // Just check it processes without error
    assert.ok(result.code === 0);
  });

  it('should detect default port for npm run dev', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'npm run dev' }
    });
    // Default port 3000 is reserved for grafana
    // Result depends on whether port is in use
    assert.ok(result.code === 0);
  });

  it('should ignore non-Bash tools', async () => {
    const result = await runHook(hook, {
      tool_name: 'Read',
      tool_input: { file_path: '/some/file' }
    });
    assert.deepStrictEqual(result.output, {});
  });
});

// ============================================================================
// CI Batch Check Tests
// ============================================================================
describe('ci-batch-check.js', () => {
  const hook = 'ci-batch-check.js';
  const historyFile = path.join(os.tmpdir(), 'claude_push_history.json');

  beforeEach(() => {
    // Clear push history before each test
    try {
      fs.unlinkSync(historyFile);
    } catch (err) {
      // Ignore if file doesn't exist
    }
  });

  it('should allow non-push commands', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git status' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should allow first push', async () => {
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should allow second push', async () => {
    // First push
    await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });

    // Second push
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });
    assert.deepStrictEqual(result.output, {});
  });

  it('should warn on third rapid push', async () => {
    // First push
    await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });

    // Second push
    await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });

    // Third push - should warn
    const result = await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });
    assert.strictEqual(result.output.decision, 'warn');
    assert.ok(result.output.message.includes('CI Batch Warning'));
  });

  it('should track push history', async () => {
    await runHook(hook, {
      tool_name: 'Bash',
      tool_input: { command: 'git push origin feature' }
    });

    assert.ok(fs.existsSync(historyFile));
    const history = JSON.parse(fs.readFileSync(historyFile, 'utf8'));
    assert.ok(Array.isArray(history.pushes));
    assert.strictEqual(history.pushes.length, 1);
  });

  it('should ignore non-Bash tools', async () => {
    const result = await runHook(hook, {
      tool_name: 'Write',
      tool_input: { file_path: '/some/file', content: 'git push' }
    });
    assert.deepStrictEqual(result.output, {});
  });
});

// ============================================================================
// Summary
// ============================================================================
describe('Hook Suite Summary', () => {
  it('should have all 4 hook files', () => {
    const hooks = [
      'git-safety-check.js',
      'smart-safety-check.js',
      'port-conflict-check.js',
      'ci-batch-check.js'
    ];

    for (const hook of hooks) {
      const hookPath = path.join(HOOKS_DIR, hook);
      assert.ok(fs.existsSync(hookPath), `Hook ${hook} should exist`);
    }
  });
});
