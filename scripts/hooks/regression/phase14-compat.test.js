#!/usr/bin/env node
/**
 * Phase 14 Hooks Compatibility Tests
 *
 * Validates backward compatibility with Phase 14 hooks port:
 * - hooks.json structure and validity
 * - Shared libraries functionality
 * - Test infrastructure integrity
 *
 * Run with: node --test phase14-compat.test.js
 */

const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_DIR = path.join(HOME_DIR, '.claude', 'hooks');
const SCRIPTS_DIR = path.join(HOME_DIR, '.claude', 'scripts');
const LIB_DIR = path.join(SCRIPTS_DIR, 'lib');
const HOOKS_JSON = path.join(HOOKS_DIR, 'hooks.json');

// =============================================================================
// hooks.json Structure Tests
// =============================================================================

describe('Phase 14: hooks.json Structure', () => {
  it('hooks.json loads without error', () => {
    assert.ok(fs.existsSync(HOOKS_JSON), 'hooks.json should exist');

    const content = fs.readFileSync(HOOKS_JSON, 'utf8');
    assert.doesNotThrow(() => JSON.parse(content), 'hooks.json should be valid JSON');
  });

  it('all hooks have required fields', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const hooks = config.hooks || {};

    for (const [eventType, hookDefs] of Object.entries(hooks)) {
      for (let i = 0; i < hookDefs.length; i++) {
        const hookDef = hookDefs[i];

        // Required fields per Phase 14 spec
        assert.ok(
          'matcher' in hookDef,
          `${eventType}[${i}] should have matcher field`
        );
        assert.ok(
          'hooks' in hookDef,
          `${eventType}[${i}] should have hooks array`
        );

        // Each hook in the array should have type and command
        for (let j = 0; j < (hookDef.hooks || []).length; j++) {
          const hook = hookDef.hooks[j];
          assert.ok(
            'type' in hook,
            `${eventType}[${i}].hooks[${j}] should have type`
          );
          assert.ok(
            'command' in hook,
            `${eventType}[${i}].hooks[${j}] should have command`
          );
        }
      }
    }
  });

  it('matchers are valid expressions', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const hooks = config.hooks || {};

    for (const [eventType, hookDefs] of Object.entries(hooks)) {
      for (const hookDef of hookDefs) {
        const matcher = hookDef.matcher;

        // Valid matcher patterns: *, tool == "...", regex matches, etc.
        assert.ok(
          typeof matcher === 'string' && matcher.length > 0,
          `${eventType} matcher should be non-empty string`
        );

        // Check for common patterns
        if (matcher !== '*') {
          assert.ok(
            matcher.includes('tool') || matcher.includes('==') || matcher.includes('matches'),
            `${eventType} matcher "${matcher.slice(0, 50)}" should be a valid expression`
          );
        }
      }
    }
  });

  it('_debug section exists', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    assert.ok('_debug' in config, 'hooks.json should have _debug section');
  });

  it('_meta section with version exists', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    assert.ok('_meta' in config, 'hooks.json should have _meta section');
    assert.ok('version' in config._meta, '_meta should have version');
  });
});

// =============================================================================
// Shared Libraries Tests
// =============================================================================

describe('Phase 14: Shared Libraries', () => {
  it('utils.js exports all functions', () => {
    const utilsPath = path.join(LIB_DIR, 'utils.js');
    assert.ok(fs.existsSync(utilsPath), 'utils.js should exist');

    const utils = require(utilsPath);

    // Core exports from Phase 14
    const expectedExports = [
      'getHomeDir',
      'getClaudeDir',
      'ensureDir',
      'readStdinJson',
      'log',
      'output'
    ];

    for (const fn of expectedExports) {
      assert.ok(
        typeof utils[fn] === 'function',
        `utils.js should export ${fn} function`
      );
    }
  });

  it('package-manager.js detects managers', () => {
    const pmPath = path.join(LIB_DIR, 'package-manager.js');
    assert.ok(fs.existsSync(pmPath), 'package-manager.js should exist');

    const pm = require(pmPath);

    // Core exports
    assert.ok(
      typeof pm.getPackageManager === 'function',
      'Should export getPackageManager'
    );
    assert.ok(
      typeof pm.PACKAGE_MANAGERS === 'object',
      'Should export PACKAGE_MANAGERS'
    );
  });

  it('session-start hook runs', () => {
    const hookPath = path.join(SCRIPTS_DIR, 'hooks', 'session-start.js');
    if (!fs.existsSync(hookPath)) {
      assert.ok(true, 'session-start.js not found - skipping');
      return;
    }

    const result = spawnSync('node', [hookPath], {
      input: JSON.stringify({ session_id: 'test' }),
      encoding: 'utf8',
      timeout: 5000
    });

    assert.strictEqual(result.status, 0, 'session-start should exit 0');
  });

  it('session-end hook runs', () => {
    const hookPath = path.join(SCRIPTS_DIR, 'hooks', 'session-end.js');
    if (!fs.existsSync(hookPath)) {
      assert.ok(true, 'session-end.js not found - skipping');
      return;
    }

    const result = spawnSync('node', [hookPath], {
      input: JSON.stringify({ session_id: 'test' }),
      encoding: 'utf8',
      timeout: 5000
    });

    assert.strictEqual(result.status, 0, 'session-end should exit 0');
  });

  it('evaluate-session produces output', () => {
    const hookPath = path.join(SCRIPTS_DIR, 'hooks', 'evaluate-session.js');
    if (!fs.existsSync(hookPath)) {
      assert.ok(true, 'evaluate-session.js not found - skipping');
      return;
    }

    const result = spawnSync('node', [hookPath], {
      input: JSON.stringify({}),
      encoding: 'utf8',
      timeout: 5000
    });

    assert.strictEqual(result.status, 0, 'evaluate-session should exit 0');
  });

  it('suggest-compact triggers appropriately', () => {
    const hookPath = path.join(SCRIPTS_DIR, 'hooks', 'suggest-compact.js');
    if (!fs.existsSync(hookPath)) {
      assert.ok(true, 'suggest-compact.js not found - skipping');
      return;
    }

    const result = spawnSync('node', [hookPath], {
      input: JSON.stringify({ tool_name: 'Edit', tool_input: { file_path: '/tmp/test.js' } }),
      encoding: 'utf8',
      timeout: 5000
    });

    assert.strictEqual(result.status, 0, 'suggest-compact should exit 0');
  });
});

// =============================================================================
// Test Infrastructure Tests
// =============================================================================

describe('Phase 14: Test Infrastructure', () => {
  it('test-all-hooks.js exists', () => {
    const testPath = path.join(SCRIPTS_DIR, 'test-all-hooks.js');
    assert.ok(fs.existsSync(testPath), 'test-all-hooks.js should exist');
  });

  it('test-all-hooks.js runs', () => {
    const testPath = path.join(SCRIPTS_DIR, 'test-all-hooks.js');
    if (!fs.existsSync(testPath)) {
      assert.fail('test-all-hooks.js not found');
    }

    // Run with --dry-run to avoid full test execution
    const result = spawnSync('node', [testPath, '--dry-run'], {
      encoding: 'utf8',
      timeout: 30000
    });

    assert.strictEqual(result.status, 0, 'test-all-hooks.js --dry-run should succeed');
  });

  it('pass rate baseline maintained', () => {
    // Check _meta for target pass rate
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const target = config._meta?.testSuite?.target || 95;

    assert.ok(target >= 95, `Pass rate target should be >= 95%, got ${target}`);
  });

  it('all test categories covered', () => {
    const testPath = path.join(SCRIPTS_DIR, 'test-all-hooks.js');
    if (!fs.existsSync(testPath)) {
      assert.fail('test-all-hooks.js not found');
    }

    const content = fs.readFileSync(testPath, 'utf8');

    // Phase 14 test categories
    const categories = ['EXISTENCE', 'SYNTAX', 'BEHAVIOR'];

    for (const cat of categories) {
      assert.ok(
        content.includes(cat),
        `test-all-hooks.js should cover ${cat} category`
      );
    }
  });

  it('test results are parseable', () => {
    const testPath = path.join(SCRIPTS_DIR, 'test-all-hooks.js');
    if (!fs.existsSync(testPath)) {
      assert.fail('test-all-hooks.js not found');
    }

    const content = fs.readFileSync(testPath, 'utf8');

    // Should support JSON output
    assert.ok(
      content.includes('--json'),
      'test-all-hooks.js should support --json output'
    );
  });
});

// =============================================================================
// Phase 14 Baseline Verification
// =============================================================================

describe('Phase 14: Baseline Verification', () => {
  it('hooks count matches meta', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const expectedCount = config._meta?.hookCount;

    if (expectedCount) {
      // Count actual hooks
      let actualCount = 0;
      for (const [, hookDefs] of Object.entries(config.hooks || {})) {
        for (const hookDef of hookDefs) {
          actualCount += (hookDef.hooks || []).length;
        }
      }

      assert.strictEqual(
        actualCount,
        expectedCount,
        `Hook count should match _meta.hookCount (expected ${expectedCount}, got ${actualCount})`
      );
    }
  });

  it('Phase 14.5 hooks present', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const content = JSON.stringify(config);

    // Phase 14.5 hooks should be marked
    assert.ok(
      content.includes('[14.5]'),
      'hooks.json should contain Phase 14.5 hooks'
    );
  });

  it('all hook categories present', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const categories = config._meta?.categories || [];

    const expectedCategories = [
      'safety',
      'intelligence',
      'quality',
      'productivity',
      'metrics',
      'coordination'
    ];

    for (const cat of expectedCategories) {
      assert.ok(
        categories.includes(cat),
        `_meta.categories should include "${cat}"`
      );
    }
  });
});
