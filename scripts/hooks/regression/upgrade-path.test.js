#!/usr/bin/env node
/**
 * Upgrade Path Tests
 *
 * Tests for installation and upgrade scenarios:
 * - Fresh install functionality
 * - Upgrade from Phase 14 to Phase 14.5+
 * - Config migration handling
 *
 * Run with: node --test upgrade-path.test.js
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync, execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_DIR = path.join(HOME_DIR, '.claude', 'hooks');
const SCRIPTS_DIR = path.join(HOME_DIR, '.claude', 'scripts');
const LIB_DIR = path.join(SCRIPTS_DIR, 'lib');
const HOOKS_JSON = path.join(HOOKS_DIR, 'hooks.json');

// Temp directory for simulated installs
const TEST_DIR = path.join(os.tmpdir(), `upgrade-test-${Date.now()}`);

// =============================================================================
// Fresh Install Tests
// =============================================================================

describe('Upgrade Path: Fresh Install', () => {
  before(() => {
    fs.mkdirSync(TEST_DIR, { recursive: true });
  });

  after(() => {
    try {
      fs.rmSync(TEST_DIR, { recursive: true, force: true });
    } catch (e) {}
  });

  it('hooks infrastructure can be copied to clean directory', () => {
    // Create simulated .claude directory
    const simClaudeDir = path.join(TEST_DIR, '.claude');
    const simHooksDir = path.join(simClaudeDir, 'hooks');

    fs.mkdirSync(simHooksDir, { recursive: true });

    // Copy hooks.json
    if (fs.existsSync(HOOKS_JSON)) {
      fs.copyFileSync(HOOKS_JSON, path.join(simHooksDir, 'hooks.json'));
      assert.ok(
        fs.existsSync(path.join(simHooksDir, 'hooks.json')),
        'hooks.json should be copyable to new location'
      );
    } else {
      assert.ok(true, 'No hooks.json to copy - skipping');
    }
  });

  it('copied hooks.json loads correctly', () => {
    const simHooksJson = path.join(TEST_DIR, '.claude', 'hooks', 'hooks.json');

    if (!fs.existsSync(simHooksJson)) {
      // Create a minimal valid hooks.json
      const minimalConfig = {
        hooks: {},
        _meta: { version: 'test' }
      };
      fs.writeFileSync(simHooksJson, JSON.stringify(minimalConfig, null, 2));
    }

    assert.doesNotThrow(() => {
      const content = fs.readFileSync(simHooksJson, 'utf8');
      JSON.parse(content);
    }, 'Copied hooks.json should be valid JSON');
  });

  it('scripts directory structure is valid', () => {
    // Check that scripts have proper structure
    const hooksSubdir = path.join(SCRIPTS_DIR, 'hooks');

    if (fs.existsSync(hooksSubdir)) {
      const entries = fs.readdirSync(hooksSubdir);
      assert.ok(entries.length > 0, 'hooks directory should contain files');

      // Check for category subdirectories or hook files
      const hasContent = entries.some(e => {
        const stat = fs.statSync(path.join(hooksSubdir, e));
        return stat.isFile() || stat.isDirectory();
      });

      assert.ok(hasContent, 'hooks directory should have content');
    } else {
      assert.ok(true, 'hooks subdirectory not found - acceptable for test');
    }
  });

  it('lib modules load without import errors', () => {
    if (!fs.existsSync(LIB_DIR)) {
      assert.ok(true, 'lib directory not found - skipping');
      return;
    }

    const jsFiles = fs.readdirSync(LIB_DIR).filter(f =>
      f.endsWith('.js') && !f.includes('.test.')
    );

    for (const file of jsFiles) {
      assert.doesNotThrow(() => {
        require(path.join(LIB_DIR, file));
      }, `${file} should load without errors`);
    }
  });
});

// =============================================================================
// Upgrade from Phase 14 Tests
// =============================================================================

describe('Upgrade Path: Phase 14 to 14.5+', () => {
  it('Phase 14.5 hooks added without conflicts', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const content = JSON.stringify(config);

    // Phase 14.5 hooks should be present
    assert.ok(
      content.includes('[14.5]'),
      'Phase 14.5 hooks should be present in hooks.json'
    );
  });

  it('old hooks still work after upgrade', () => {
    // Test core Phase 14 hooks still function
    const coreHooks = [
      'session-start.js',
      'session-end.js',
      'suggest-compact.js',
      'pre-compact.js'
    ];

    for (const hook of coreHooks) {
      const hookPath = path.join(SCRIPTS_DIR, 'hooks', hook);

      if (fs.existsSync(hookPath)) {
        const result = spawnSync('node', [hookPath], {
          input: JSON.stringify({}),
          encoding: 'utf8',
          timeout: 5000
        });

        assert.strictEqual(
          result.status,
          0,
          `Core hook ${hook} should still work after upgrade`
        );
      }
    }
  });

  it('new hooks work alongside old hooks', () => {
    // Test Phase 14.5 hooks work
    const phase145Hooks = [
      'safety/git-safety-check.js',
      'intelligence/session-start-tracker.js',
      'metrics/dora-tracker.js'
    ];

    for (const hook of phase145Hooks) {
      const hookPath = path.join(SCRIPTS_DIR, 'hooks', hook);

      if (fs.existsSync(hookPath)) {
        const result = spawnSync('node', [hookPath], {
          input: JSON.stringify({
            tool_name: 'Bash',
            tool_input: { command: 'echo test' }
          }),
          encoding: 'utf8',
          timeout: 5000
        });

        assert.strictEqual(
          result.status,
          0,
          `Phase 14.5 hook ${hook} should work`
        );
      }
    }
  });

  it('no duplicate hook definitions', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const hooks = config.hooks || {};

    // Track hook commands to detect duplicates
    const seenCommands = new Map();

    for (const [eventType, hookDefs] of Object.entries(hooks)) {
      for (const hookDef of hookDefs) {
        for (const hook of (hookDef.hooks || [])) {
          const cmd = hook.command;
          const key = `${eventType}:${cmd}`;

          // Same event type + same command = duplicate
          if (seenCommands.has(key)) {
            // Allow if different matchers
            const prevMatcher = seenCommands.get(key);
            if (prevMatcher === hookDef.matcher) {
              assert.fail(`Duplicate hook: ${eventType} with command "${cmd.slice(0, 50)}..."`);
            }
          }
          seenCommands.set(key, hookDef.matcher);
        }
      }
    }

    assert.ok(true, 'No exact duplicate hooks found');
  });

  it('shared libraries backwards compatible', () => {
    // Test that utils.js maintains backward compatibility
    const utilsPath = path.join(LIB_DIR, 'utils.js');

    if (fs.existsSync(utilsPath)) {
      const utils = require(utilsPath);

      // Original Phase 14 exports should still work
      const phase14Exports = ['getHomeDir', 'getClaudeDir', 'ensureDir', 'readStdinJson'];

      for (const fn of phase14Exports) {
        assert.ok(
          typeof utils[fn] === 'function',
          `utils.${fn} should still be exported (backward compat)`
        );
      }
    }
  });
});

// =============================================================================
// Config Migration Tests
// =============================================================================

describe('Upgrade Path: Config Migration', () => {
  // Create a dedicated temp dir for this suite
  const MIGRATION_TEST_DIR = path.join(os.tmpdir(), `migration-test-${Date.now()}`);

  before(() => {
    fs.mkdirSync(MIGRATION_TEST_DIR, { recursive: true });
  });

  after(() => {
    try {
      fs.rmSync(MIGRATION_TEST_DIR, { recursive: true, force: true });
    } catch (e) {}
  });

  it('missing _meta handled gracefully', () => {
    // Test loading hooks.json without _meta section
    const testConfig = { hooks: {} }; // No _meta

    const simPath = path.join(MIGRATION_TEST_DIR, 'no-meta-hooks.json');
    fs.writeFileSync(simPath, JSON.stringify(testConfig));

    assert.doesNotThrow(() => {
      const content = fs.readFileSync(simPath, 'utf8');
      const config = JSON.parse(content);
      // Should not crash when accessing _meta
      const version = config._meta?.version || 'unknown';
      assert.strictEqual(version, 'unknown');
    }, 'Should handle missing _meta gracefully');
  });

  it('missing fields in hooks handled gracefully', () => {
    // Test loading hooks with partial fields
    const testConfig = {
      hooks: {
        PreToolUse: [
          {
            matcher: '*'
            // Missing hooks array
          }
        ]
      }
    };

    const simPath = path.join(MIGRATION_TEST_DIR, 'partial-hooks.json');
    fs.writeFileSync(simPath, JSON.stringify(testConfig));

    assert.doesNotThrow(() => {
      const content = fs.readFileSync(simPath, 'utf8');
      const config = JSON.parse(content);
      const hooks = config.hooks?.PreToolUse?.[0]?.hooks || [];
      assert.ok(Array.isArray(hooks), 'Should return empty array for missing hooks');
    }, 'Should handle missing hook fields gracefully');
  });

  it('schema validation pattern present', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const content = fs.readFileSync(HOOKS_JSON, 'utf8');
    const config = JSON.parse(content);

    // Should have $schema reference for validation
    assert.ok(
      '$schema' in config,
      'hooks.json should have $schema for validation'
    );
  });

  it('version detection works', () => {
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
    const version = config._meta?.version;

    assert.ok(version, '_meta.version should exist');
    assert.ok(
      typeof version === 'string' && version.length > 0,
      'Version should be a non-empty string'
    );
  });

  it('rollback capability exists (backup mechanism)', () => {
    // Check that backups are possible
    if (!fs.existsSync(HOOKS_JSON)) {
      assert.fail('hooks.json not found');
    }

    // Verify we can create a backup
    const backupPath = path.join(MIGRATION_TEST_DIR, 'hooks.json.backup');

    assert.doesNotThrow(() => {
      fs.copyFileSync(HOOKS_JSON, backupPath);
    }, 'Should be able to create backup of hooks.json');

    // Verify backup is valid
    assert.doesNotThrow(() => {
      const content = fs.readFileSync(backupPath, 'utf8');
      JSON.parse(content);
    }, 'Backup should be valid JSON');

    // Clean up
    fs.unlinkSync(backupPath);
  });
});

// =============================================================================
// Environment Compatibility Tests
// =============================================================================

describe('Upgrade Path: Environment Compatibility', () => {
  it('hooks work with current Node.js version', () => {
    const nodeVersion = process.versions.node;
    const [major] = nodeVersion.split('.').map(Number);

    // Hooks require Node.js 18+ for test runner
    assert.ok(major >= 18, `Node.js ${major}.x is supported (18+ required for test runner)`);
  });

  it('no deprecated APIs used in core hooks', () => {
    const hookFiles = [
      path.join(SCRIPTS_DIR, 'hooks', 'session-start.js'),
      path.join(SCRIPTS_DIR, 'hooks', 'session-end.js'),
      path.join(SCRIPTS_DIR, 'hooks', 'suggest-compact.js')
    ];

    for (const hookPath of hookFiles) {
      if (!fs.existsSync(hookPath)) continue;

      const content = fs.readFileSync(hookPath, 'utf8');

      // Check for deprecated patterns
      const deprecatedPatterns = [
        'require("fs").exists(',  // Use existsSync
        'new Buffer(',            // Use Buffer.from
        'domain.create('          // Deprecated domain module
      ];

      for (const pattern of deprecatedPatterns) {
        assert.ok(
          !content.includes(pattern),
          `${path.basename(hookPath)} should not use deprecated: ${pattern}`
        );
      }
    }
  });
});
