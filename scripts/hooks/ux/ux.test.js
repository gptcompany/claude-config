/**
 * UX and Control Hooks Tests
 *
 * Tests for:
 * - tips-injector.js
 * - session-insights.js
 * - ralph-loop.js
 * - hive-manager.js
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Test directories
const TEST_DIR = path.join(os.tmpdir(), 'ux-test-' + Date.now());
const METRICS_DIR = path.join(TEST_DIR, 'metrics');
const RALPH_DIR = path.join(TEST_DIR, 'ralph');
const HIVE_DIR = path.join(TEST_DIR, 'hive');

// Setup/teardown
beforeEach(() => {
  fs.mkdirSync(METRICS_DIR, { recursive: true });
  fs.mkdirSync(RALPH_DIR, { recursive: true });
  fs.mkdirSync(HIVE_DIR, { recursive: true });
});

afterEach(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch (e) {}
});

// =============================================================================
// tips-injector.js tests
// =============================================================================

describe('tips-injector', () => {
  const tipsInjector = require('./tips-injector.js');

  test('MAX_TIPS_AGE_HOURS is 24', () => {
    assert.strictEqual(tipsInjector.MAX_TIPS_AGE_HOURS, 24);
  });

  test('MAX_TIPS is 3', () => {
    assert.strictEqual(tipsInjector.MAX_TIPS, 3);
  });

  test('isTipsFresh returns false for stale tips', () => {
    const yesterday = new Date(Date.now() - 25 * 60 * 60 * 1000);
    const staleTips = { timestamp: yesterday.toISOString() };
    assert.strictEqual(tipsInjector.isTipsFresh(staleTips), false);
  });

  test('isTipsFresh returns true for fresh tips', () => {
    const freshTips = { timestamp: new Date().toISOString() };
    assert.strictEqual(tipsInjector.isTipsFresh(freshTips), true);
  });

  test('isTipsFresh handles ended_at field (SSOT format)', () => {
    const freshTips = { ended_at: new Date().toISOString() };
    assert.strictEqual(tipsInjector.isTipsFresh(freshTips), true);
  });

  test('formatTipsForInjection returns empty for no tips', () => {
    const result = tipsInjector.formatTipsForInjection({ tips: [] });
    assert.strictEqual(result.contextText, '');
    assert.strictEqual(result.userNotification, '');
  });

  test('formatTipsForInjection formats tips correctly', () => {
    const tipsData = {
      tips: [
        { confidence: 0.85, message: 'High error rate', command: '/undo:checkpoint' },
        { confidence: 0.70, message: 'No tests', command: '/tdd:red' }
      ],
      summary: { duration_min: 30, tool_calls: 50, errors: 5 }
    };

    const result = tipsInjector.formatTipsForInjection(tipsData);

    assert.ok(result.contextText.includes('[Previous Session Tips]'));
    assert.ok(result.contextText.includes('85%'));
    assert.ok(result.contextText.includes('/undo:checkpoint'));
    assert.ok(result.userNotification.includes('2 suggestions'));
  });

  test('formatTipsForInjection limits to MAX_TIPS', () => {
    const tipsData = {
      tips: [
        { confidence: 0.9, message: 'Tip 1', command: '/cmd1' },
        { confidence: 0.8, message: 'Tip 2', command: '/cmd2' },
        { confidence: 0.7, message: 'Tip 3', command: '/cmd3' },
        { confidence: 0.6, message: 'Tip 4', command: '/cmd4' },
        { confidence: 0.5, message: 'Tip 5', command: '/cmd5' }
      ]
    };

    const result = tipsInjector.formatTipsForInjection(tipsData);

    // Should only contain 3 tips (MAX_TIPS)
    const tipMatches = result.contextText.match(/\d\.\s+\[\d+%\]/g) || [];
    assert.strictEqual(tipMatches.length, 3);
  });
});

// =============================================================================
// session-insights.js tests
// =============================================================================

describe('session-insights', () => {
  const sessionInsights = require('./session-insights.js');

  test('loadJsonSafe returns null for missing file', () => {
    const result = sessionInsights.loadJsonSafe('/nonexistent/file.json');
    assert.strictEqual(result, null);
  });

  test('loadJsonSafe returns null for invalid JSON', () => {
    const testFile = path.join(TEST_DIR, 'invalid.json');
    fs.writeFileSync(testFile, 'not json');
    const result = sessionInsights.loadJsonSafe(testFile);
    assert.strictEqual(result, null);
  });

  test('loadJsonSafe loads valid JSON', () => {
    const testFile = path.join(TEST_DIR, 'valid.json');
    fs.writeFileSync(testFile, JSON.stringify({ key: 'value' }));
    const result = sessionInsights.loadJsonSafe(testFile);
    assert.deepStrictEqual(result, { key: 'value' });
  });

  test('buildInsights creates basic structure', () => {
    const insights = sessionInsights.buildInsights('test-session');

    assert.strictEqual(insights.$schema, 'session_insights_v1');
    assert.strictEqual(insights.session_id, 'test-session');
    assert.ok(insights.ended_at);
  });

  test('unlinkSafe does not throw for missing file', () => {
    assert.doesNotThrow(() => {
      sessionInsights.unlinkSafe('/nonexistent/file.json');
    });
  });
});

// =============================================================================
// ralph-loop.js tests
// =============================================================================

describe('ralph-loop', () => {
  const ralphLoop = require('../control/ralph-loop.js');

  test('DEFAULT_CONFIG has required fields', () => {
    const config = ralphLoop.DEFAULT_CONFIG;

    assert.ok(config.max_iterations);
    assert.ok(config.max_budget_usd);
    assert.ok(config.max_consecutive_errors);
    assert.ok(config.max_no_progress);
    assert.ok(config.max_ci_failures);
    assert.ok(config.min_iteration_interval_secs);
    assert.ok(config.max_iterations_per_hour);
    assert.ok(config.estimated_cost_per_iteration);
  });

  test('EXIT_PATTERNS contains expected patterns', () => {
    const patterns = ralphLoop.EXIT_PATTERNS;

    assert.ok(patterns.includes('all tests pass'));
    assert.ok(patterns.includes('done'));
    assert.ok(patterns.includes('finished'));
  });

  test('ERROR_PATTERNS contains expected patterns', () => {
    const patterns = ralphLoop.ERROR_PATTERNS;

    assert.ok(patterns.includes('error:'));
    assert.ok(patterns.includes('failed'));
    assert.ok(patterns.includes('exception'));
  });

  test('getProjectHash returns consistent hash', () => {
    const hash1 = ralphLoop.getProjectHash();
    const hash2 = ralphLoop.getProjectHash();

    assert.strictEqual(hash1, hash2);
    assert.strictEqual(hash1.length, 12);
  });

  test('calculateChecksum returns consistent checksum', () => {
    const state = { iteration: 5, active: true };
    const checksum1 = ralphLoop.calculateChecksum(state);
    const checksum2 = ralphLoop.calculateChecksum(state);

    assert.strictEqual(checksum1, checksum2);
    assert.strictEqual(checksum1.length, 16);
  });

  test('calculateChecksum ignores _checksum field', () => {
    const state1 = { iteration: 5 };
    const state2 = { iteration: 5, _checksum: 'abc123' };

    const checksum1 = ralphLoop.calculateChecksum(state1);
    const checksum2 = ralphLoop.calculateChecksum(state2);

    assert.strictEqual(checksum1, checksum2);
  });

  test('checkTokenBudget returns not exceeded for low iterations', () => {
    const state = { iteration: 2 };
    const result = ralphLoop.checkTokenBudget(state);

    assert.strictEqual(result.exceeded, false);
    assert.ok(result.message.includes('Budget OK'));
  });

  test('checkTokenBudget returns exceeded for high iterations', () => {
    const state = { iteration: 20 }; // 20 * $2 = $40 > $20 budget
    const result = ralphLoop.checkTokenBudget(state);

    assert.strictEqual(result.exceeded, true);
    assert.ok(result.message.includes('Budget limit'));
  });
});

// =============================================================================
// hive-manager.js tests
// =============================================================================

describe('hive-manager', () => {
  const hiveManager = require('../control/hive-manager.js');

  test('AGENT_TIMEOUT_MS is 10 minutes', () => {
    assert.strictEqual(hiveManager.AGENT_TIMEOUT_MS, 10 * 60 * 1000);
  });

  test('MAX_AGENTS is 10', () => {
    assert.strictEqual(hiveManager.MAX_AGENTS, 10);
  });

  test('generateAgentId returns unique IDs', () => {
    const id1 = hiveManager.generateAgentId();
    const id2 = hiveManager.generateAgentId();

    assert.notStrictEqual(id1, id2);
    assert.ok(id1.startsWith('agent_'));
    assert.ok(id2.startsWith('agent_'));
  });

  test('generateTaskId returns unique IDs', () => {
    const id1 = hiveManager.generateTaskId();
    const id2 = hiveManager.generateTaskId();

    assert.notStrictEqual(id1, id2);
    assert.ok(id1.startsWith('task_'));
    assert.ok(id2.startsWith('task_'));
  });

  test('loadState returns default state for missing file', () => {
    const state = hiveManager.loadState();

    assert.strictEqual(state.hive_id, null);
    assert.strictEqual(state.topology, 'hierarchical-mesh');
    assert.deepStrictEqual(state.agents, {});
    assert.deepStrictEqual(state.tasks, {});
  });

  test('getStatus returns correct structure', () => {
    const status = hiveManager.getStatus();

    assert.ok('hive_id' in status);
    assert.ok('topology' in status);
    assert.ok('agents' in status);
    assert.ok('tasks' in status);
    assert.ok('stuck_agents' in status);
    assert.ok('updated_at' in status);

    // Check nested structure
    assert.ok('total' in status.agents);
    assert.ok('active' in status.agents);
    assert.ok('busy' in status.agents);
    assert.ok('idle' in status.agents);
    assert.ok('stuck' in status.agents);

    assert.ok('total' in status.tasks);
    assert.ok('pending' in status.tasks);
    assert.ok('in_progress' in status.tasks);
    assert.ok('completed' in status.tasks);
    assert.ok('failed' in status.tasks);
  });
});

// =============================================================================
// Integration tests
// =============================================================================

describe('integration', () => {
  test('tips-injector and session-insights use same SSOT file', () => {
    const tipsInjector = require('./tips-injector.js');
    const sessionInsights = require('./session-insights.js');

    assert.strictEqual(
      tipsInjector.SSOT_FILE,
      sessionInsights.INSIGHTS_FILE
    );
  });

  test('ralph-loop state path uses project hash', () => {
    const ralphLoop = require('../control/ralph-loop.js');

    const statePath = ralphLoop.getStatePath();
    const hash = ralphLoop.getProjectHash();

    assert.ok(statePath.includes(hash));
    assert.ok(statePath.includes('state_'));
  });

  test('hive-manager handleTaskToolUse tracks tasks', () => {
    const hiveManager = require('../control/hive-manager.js');

    const result = hiveManager.handleTaskToolUse(
      { description: 'Test task' },
      ''
    );

    assert.strictEqual(result.tracked, true);
    assert.strictEqual(result.action, 'task_registered');
    assert.ok(result.task_id.startsWith('task_'));
  });
});
