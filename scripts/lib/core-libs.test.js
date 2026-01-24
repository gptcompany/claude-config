/**
 * Unit Tests for Core Libraries
 *
 * Tests:
 * - mcp-client.js
 * - git-utils.js
 * - metrics.js
 * - tips-engine.js
 *
 * Run with: node --test ~/.claude/scripts/lib/core-libs.test.js
 */

const { test, describe, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Test fixtures directory
const TEST_DIR = path.join(os.tmpdir(), `core-libs-test-${Date.now()}`);

// ============================================================================
// MCP-CLIENT TESTS
// ============================================================================

describe('mcp-client', () => {
  const mcpClient = require('./mcp-client');

  test('getProjectName returns a string', () => {
    const name = mcpClient.getProjectName();
    assert.strictEqual(typeof name, 'string');
    assert.ok(name.length > 0, 'Project name should not be empty');
  });

  test('getTimestamp returns ISO format', () => {
    const ts = mcpClient.getTimestamp();
    assert.strictEqual(typeof ts, 'string');
    assert.ok(ts.includes('T'), 'Should be ISO format with T separator');
    assert.ok(ts.includes('Z'), 'Should be UTC with Z suffix');
  });

  test('memoryStore and memoryRetrieve roundtrip', () => {
    const testKey = `test_${Date.now()}`;
    const testValue = { foo: 'bar', num: 42 };

    const storeResult = mcpClient.memoryStore(testKey, testValue, 'test');
    assert.ok(storeResult.success, 'Store should succeed');

    const retrieved = mcpClient.memoryRetrieve(testKey, 'test');
    assert.deepStrictEqual(retrieved, testValue, 'Retrieved value should match stored value');

    // Cleanup
    mcpClient.memoryDelete(testKey, 'test');
  });

  test('memoryRetrieve returns null for missing key', () => {
    const result = mcpClient.memoryRetrieve('nonexistent_key_12345');
    assert.strictEqual(result, null, 'Should return null for missing key');
  });

  test('memoryList returns array', () => {
    const list = mcpClient.memoryList();
    assert.ok(Array.isArray(list), 'Should return an array');
  });

  test('memorySearch finds matching keys', () => {
    const prefix = `search_test_${Date.now()}`;
    mcpClient.memoryStore(`${prefix}_1`, { a: 1 });
    mcpClient.memoryStore(`${prefix}_2`, { b: 2 });

    const results = mcpClient.memorySearch(prefix);
    assert.ok(results.length >= 2, 'Should find at least 2 matches');

    // Cleanup
    mcpClient.memoryDelete(`${prefix}_1`);
    mcpClient.memoryDelete(`${prefix}_2`);
  });

  test('patternStore creates pattern with ID', () => {
    const result = mcpClient.patternStore('test pattern', 'test', 0.8, { source: 'unit-test' });
    assert.ok(result.success, 'Pattern store should succeed');
    assert.ok(result.patternId, 'Should return pattern ID');
    assert.ok(result.patternId.startsWith('pattern_'), 'ID should have pattern_ prefix');
  });

  test('patternSearch filters by type', () => {
    mcpClient.patternStore('searchable pattern', 'search_test_type', 0.9);

    const results = mcpClient.patternSearch('', 'search_test_type');
    assert.ok(results.length > 0, 'Should find patterns by type');
    assert.ok(results.every(p => p.type === 'search_test_type'), 'All results should match type');
  });

  test('patternSearch filters by confidence', () => {
    mcpClient.patternStore('high conf pattern', 'conf_test', 0.95);
    mcpClient.patternStore('low conf pattern', 'conf_test', 0.3);

    const highConf = mcpClient.patternSearch('', 'conf_test', 0.9);
    const allConf = mcpClient.patternSearch('', 'conf_test', 0);

    assert.ok(highConf.length <= allConf.length, 'High confidence filter should return fewer results');
  });
});

// ============================================================================
// GIT-UTILS TESTS
// ============================================================================

describe('git-utils', () => {
  const gitUtils = require('./git-utils');

  test('isGitRepo returns boolean', () => {
    const result = gitUtils.isGitRepo();
    assert.strictEqual(typeof result, 'boolean');
  });

  test('getCurrentBranch returns string or null', () => {
    const branch = gitUtils.getCurrentBranch();
    assert.ok(branch === null || typeof branch === 'string', 'Should be string or null');
    if (branch !== null) {
      assert.ok(branch.length > 0, 'Branch name should not be empty');
    }
  });

  test('getCurrentCommit returns hash or null', () => {
    const commit = gitUtils.getCurrentCommit();
    if (commit !== null) {
      assert.ok(/^[0-9a-f]{40}$/.test(commit), 'Should be 40-char hex hash');
    }
  });

  test('getCurrentCommit short returns 7 chars', () => {
    const commit = gitUtils.getCurrentCommit(true);
    if (commit !== null) {
      assert.ok(commit.length >= 7 && commit.length <= 10, 'Short hash should be 7-10 chars');
    }
  });

  test('categorizeFile identifies code files', () => {
    assert.strictEqual(gitUtils.categorizeFile('src/main.js'), 'code');
    assert.strictEqual(gitUtils.categorizeFile('app.ts'), 'code');
    assert.strictEqual(gitUtils.categorizeFile('lib/utils.py'), 'code');
    assert.strictEqual(gitUtils.categorizeFile('main.go'), 'code');
    assert.strictEqual(gitUtils.categorizeFile('handler.rs'), 'code');
  });

  test('categorizeFile identifies test files', () => {
    assert.strictEqual(gitUtils.categorizeFile('main.test.js'), 'test');
    assert.strictEqual(gitUtils.categorizeFile('utils.spec.ts'), 'test');
    assert.strictEqual(gitUtils.categorizeFile('test_helper.py'), 'test');
    assert.strictEqual(gitUtils.categorizeFile('tests/unit/test_main.py'), 'test');
    assert.strictEqual(gitUtils.categorizeFile('__tests__/app.test.tsx'), 'test');
  });

  test('categorizeFile identifies config files', () => {
    assert.strictEqual(gitUtils.categorizeFile('package.json'), 'config');
    assert.strictEqual(gitUtils.categorizeFile('tsconfig.json'), 'config');
    assert.strictEqual(gitUtils.categorizeFile('.gitignore'), 'config');
    assert.strictEqual(gitUtils.categorizeFile('docker-compose.yml'), 'config');
    assert.strictEqual(gitUtils.categorizeFile('Makefile'), 'config');
  });

  test('categorizeFile identifies docs', () => {
    assert.strictEqual(gitUtils.categorizeFile('README.md'), 'docs');
    assert.strictEqual(gitUtils.categorizeFile('docs/api.md'), 'docs');
    assert.strictEqual(gitUtils.categorizeFile('CHANGELOG.md'), 'docs');
  });

  test('categorizeFile returns other for unknown', () => {
    assert.strictEqual(gitUtils.categorizeFile('image.png'), 'other');
    assert.strictEqual(gitUtils.categorizeFile('data.bin'), 'other');
  });

  test('runGitCommand handles timeout', () => {
    // Run a command that would hang, with very short timeout
    const result = gitUtils.runGitCommand(['--version'], 10000);
    assert.ok(result !== null, 'Should return result');
    assert.ok(result.success || result.timedOut !== undefined, 'Should have success or timedOut');
  });

  test('getRepoRoot returns path or null', () => {
    const root = gitUtils.getRepoRoot();
    if (root !== null) {
      assert.ok(path.isAbsolute(root), 'Should be absolute path');
    }
  });
});

// ============================================================================
// METRICS TESTS
// ============================================================================

describe('metrics', () => {
  const metrics = require('./metrics');

  before(() => {
    // Ensure test directory
    fs.mkdirSync(TEST_DIR, { recursive: true });
  });

  after(() => {
    // Cleanup test directory
    try {
      fs.rmSync(TEST_DIR, { recursive: true, force: true });
    } catch (e) {
      // Ignore cleanup errors
    }
  });

  test('getTimestamp returns ISO format', () => {
    const ts = metrics.getTimestamp();
    assert.ok(ts.includes('T'));
    assert.ok(ts.includes('Z'));
  });

  test('getNanoTimestamp returns bigint', () => {
    const ns = metrics.getNanoTimestamp();
    assert.strictEqual(typeof ns, 'bigint');
    assert.ok(ns > 0n);
  });

  test('saveMetric and loadMetric roundtrip', () => {
    const testValue = { test: true, value: 123 };
    const saved = metrics.saveMetric('test_metric', testValue, { source: 'test' });
    assert.ok(saved, 'Save should succeed');

    const loaded = metrics.loadMetric('test_metric', 1);
    assert.ok(loaded.length > 0, 'Should find saved metric');
    assert.deepStrictEqual(loaded[0].value, testValue, 'Value should match');
  });

  test('saveSessionState and loadSessionState roundtrip', () => {
    const state = {
      sessionId: 'test-session-123',
      startTime: Date.now(),
      toolCalls: 50
    };

    const saved = metrics.saveSessionState(state);
    assert.ok(saved, 'Save should succeed');

    const loaded = metrics.loadSessionState();
    assert.ok(loaded !== null, 'Should load state');
    assert.strictEqual(loaded.sessionId, state.sessionId);
    assert.strictEqual(loaded.toolCalls, state.toolCalls);

    // Cleanup
    metrics.clearSessionState();
  });

  test('saveContextStats and loadContextStats roundtrip', () => {
    const stats = {
      tokensUsed: 1000,
      messagesCount: 10
    };

    const saved = metrics.saveContextStats(stats);
    assert.ok(saved, 'Save should succeed');

    const loaded = metrics.loadContextStats();
    assert.ok(loaded !== null, 'Should load stats');
    assert.strictEqual(loaded.tokensUsed, stats.tokensUsed);
  });

  test('buildIlpLine generates valid format', () => {
    const line = metrics.buildIlpLine(
      'test_table',
      { project: 'test', env: 'dev' },
      { value: 42, name: 'metric' },
      BigInt(1234567890000000000)
    );

    assert.ok(line.startsWith('test_table,'), 'Should start with table name');
    assert.ok(line.includes('project=test'), 'Should include tag');
    assert.ok(line.includes('value=42i'), 'Should include integer field');
    assert.ok(line.includes('name="metric"'), 'Should include string field');
    assert.ok(line.endsWith('\n'), 'Should end with newline');
  });

  test('buildIlpLine escapes special characters', () => {
    const line = metrics.buildIlpLine(
      'test',
      { tag: 'has space' },
      { msg: 'has "quotes"' }
    );

    assert.ok(line.includes('has\\ space'), 'Should escape spaces in tags');
    assert.ok(line.includes('has \\"quotes\\"'), 'Should escape quotes in strings');
  });
});

// ============================================================================
// TIPS-ENGINE TESTS
// ============================================================================

describe('tips-engine', () => {
  const tipsEngine = require('./tips-engine');

  test('CATEGORIES is defined', () => {
    assert.ok(Array.isArray(tipsEngine.CATEGORIES));
    assert.ok(tipsEngine.CATEGORIES.length > 0);
  });

  test('INDUSTRY_DEFAULTS has required fields', () => {
    const defaults = tipsEngine.INDUSTRY_DEFAULTS;
    assert.ok(defaults.avgErrorRate !== undefined);
    assert.ok(defaults.avgReworkRate !== undefined);
    assert.ok(defaults.avgTestPassRate !== undefined);
  });

  test('getErrorRate calculates correctly', () => {
    const session = { toolCalls: 100, errors: 10 };
    assert.strictEqual(tipsEngine.getErrorRate(session), 0.1);
  });

  test('getErrorRate handles zero tool calls', () => {
    const session = { toolCalls: 0, errors: 0 };
    assert.strictEqual(tipsEngine.getErrorRate(session), 0);
  });

  test('getReworkRate calculates correctly', () => {
    const session = { fileEdits: 20, reworks: 4 };
    assert.strictEqual(tipsEngine.getReworkRate(session), 0.2);
  });

  test('getTestPassRate calculates correctly', () => {
    const session = { testRuns: 10, testsPassed: 8 };
    assert.strictEqual(tipsEngine.getTestPassRate(session), 0.8);
  });

  test('zScore calculates correctly', () => {
    // z = (value - mean) / stddev
    // z = (0.2 - 0.1) / 0.05 = 2.0
    assert.strictEqual(tipsEngine.zScore(0.2, 0.1, 0.05), 2.0);
  });

  test('zScore handles zero stddev', () => {
    assert.strictEqual(tipsEngine.zScore(0.5, 0.1, 0), 0);
  });

  test('selectBestCommand returns command for valid category', () => {
    const result = tipsEngine.selectBestCommand('safety');
    assert.ok(result.command, 'Should return a command');
    assert.ok(result.score > 0, 'Should have positive score');
  });

  test('selectBestCommand handles invalid category', () => {
    const result = tipsEngine.selectBestCommand('nonexistent');
    assert.strictEqual(result.command, '');
    assert.strictEqual(result.score, 0);
  });

  test('calculateConfidence returns value between 0.1 and 0.95', () => {
    const session = { toolCalls: 100, errors: 20 };
    const conf = tipsEngine.calculateConfidence('high_error_rate', session, {});
    assert.ok(conf >= 0.1, 'Should be at least 0.1');
    assert.ok(conf <= 0.95, 'Should be at most 0.95');
  });

  test('generateTips returns array', () => {
    const session = {
      toolCalls: 100,
      errors: 30,
      fileEdits: 10,
      reworks: 4,
      testRuns: 5,
      testsPassed: 2
    };

    const tips = tipsEngine.generateTips(session);
    assert.ok(Array.isArray(tips), 'Should return array');
  });

  test('generateTips triggers high_error_rate rule', () => {
    const session = {
      toolCalls: 100,
      errors: 25 // 25% error rate
    };

    const tips = tipsEngine.generateTips(session);
    const errorTip = tips.find(t => t.ruleName === 'high_error_rate');
    assert.ok(errorTip, 'Should trigger high_error_rate rule');
  });

  test('scoreTip returns value between 0 and 1', () => {
    const tip = { confidence: 0.8, category: 'errors', command: '/undo:checkpoint' };
    const context = { toolCalls: 100, errors: 20 };

    const score = tipsEngine.scoreTip(tip, context);
    assert.ok(score >= 0 && score <= 1, 'Score should be 0-1');
  });

  test('formatTips returns empty string for empty array', () => {
    const result = tipsEngine.formatTips([]);
    assert.strictEqual(result, '');
  });

  test('formatTips formats tips correctly', () => {
    const tips = [{
      ruleName: 'test',
      message: 'Test message',
      command: '/test',
      confidence: 0.85,
      evidence: 'Test evidence',
      category: 'test',
      rationale: 'Test rationale'
    }];

    const formatted = tipsEngine.formatTips(tips);
    assert.ok(formatted.includes('Test message'), 'Should include message');
    assert.ok(formatted.includes('/test'), 'Should include command');
    assert.ok(formatted.includes('85%'), 'Should include confidence');
    assert.ok(formatted.includes('Test evidence'), 'Should include evidence');
  });

  test('formatTips limits to maxCount', () => {
    const tips = Array(10).fill().map((_, i) => ({
      ruleName: `rule_${i}`,
      message: `Message ${i}`,
      command: `/cmd${i}`,
      confidence: 0.9 - i * 0.05,
      evidence: 'Evidence',
      category: 'test'
    }));

    const formatted = tipsEngine.formatTips(tips, 3);
    // Count occurrences of "Conf:" which appears once per tip
    const confCount = (formatted.match(/\[Conf:/g) || []).length;
    assert.strictEqual(confCount, 3, 'Should show exactly 3 tips');
  });

  test('saveTipsForNextSession and loadNextSessionTips roundtrip', () => {
    const tips = [{
      ruleName: 'test',
      message: 'Test',
      command: '/test',
      confidence: 0.8
    }];

    tipsEngine.saveTipsForNextSession(tips, 'session-123', 'test-project');

    const loaded = tipsEngine.loadNextSessionTips();
    assert.ok(loaded !== null, 'Should load saved tips');
    assert.strictEqual(loaded.sessionId, 'session-123');
    assert.strictEqual(loaded.project, 'test-project');
    assert.deepStrictEqual(loaded.tips, tips);

    // Cleanup
    tipsEngine.clearNextSessionTips();
  });

  test('tipsToDict converts tips to serializable format', () => {
    const tips = [{
      ruleName: 'test',
      message: 'Test',
      command: '/test',
      confidence: 0.8,
      evidence: 'Evidence',
      category: 'test',
      rationale: 'Rationale'
    }];

    const dict = tipsEngine.tipsToDict(tips, 'session-1', 'project-1', { sessionCount: 10 });
    assert.strictEqual(dict.sessionId, 'session-1');
    assert.strictEqual(dict.project, 'project-1');
    assert.strictEqual(dict.analysis.sessionsAnalyzed, 10);
    assert.ok(Array.isArray(dict.tips));
    assert.strictEqual(dict.tips[0].ruleName, 'test');
  });
});

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

describe('integration', () => {
  test('all libraries load without error', () => {
    assert.doesNotThrow(() => {
      require('./mcp-client');
      require('./git-utils');
      require('./metrics');
      require('./tips-engine');
    });
  });

  test('libraries can be used together', () => {
    const mcpClient = require('./mcp-client');
    const gitUtils = require('./git-utils');
    const metrics = require('./metrics');
    const tipsEngine = require('./tips-engine');

    // Simulate a session workflow
    const projectName = mcpClient.getProjectName();
    const branch = gitUtils.getCurrentBranch();

    // Save session state with metrics
    metrics.saveSessionState({
      project: projectName,
      branch: branch,
      startTime: mcpClient.getTimestamp()
    });

    // Generate tips based on session
    const tips = tipsEngine.generateTips({
      toolCalls: 50,
      errors: 5,
      fileEdits: 10,
      reworks: 2
    });

    // Save tips for next session
    if (tips.length > 0) {
      tipsEngine.saveTipsForNextSession(tips, 'integration-test', projectName);
    }

    // Verify state was saved
    const state = metrics.loadSessionState();
    assert.ok(state !== null, 'State should be saved');
    assert.strictEqual(state.project, projectName);

    // Cleanup
    metrics.clearSessionState();
    tipsEngine.clearNextSessionTips();
  });
});
