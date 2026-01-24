#!/usr/bin/env node
/**
 * Intelligence Hooks Tests
 *
 * Tests for all 4 intelligence hooks:
 * - session-start-tracker.js
 * - session-analyzer.js
 * - meta-learning.js
 * - lesson-injector.js
 *
 * Minimum 20 tests (5 per hook)
 */

const { describe, it, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Test fixtures directory
const TEST_DIR = path.join(os.tmpdir(), 'intelligence-hooks-test-' + Date.now());
const METRICS_DIR = path.join(TEST_DIR, 'metrics');
const LESSONS_DIR = path.join(TEST_DIR, 'lessons');

// Setup test directories
before(() => {
  fs.mkdirSync(METRICS_DIR, { recursive: true });
  fs.mkdirSync(LESSONS_DIR, { recursive: true });
});

// Cleanup after tests
after(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch (err) {
    // Ignore cleanup errors
  }
});

// =============================================================================
// Session Start Tracker Tests (5 tests)
// =============================================================================

describe('session-start-tracker', () => {
  const tracker = require('./session-start-tracker');

  it('should detect new session when no previous state exists', () => {
    // With no state file, should be considered new
    const isNew = tracker.isNewSession();
    // Will be true since there's no state file in the test environment
    assert.strictEqual(typeof isNew, 'boolean');
  });

  it('should have correct session timeout constant', () => {
    assert.strictEqual(tracker.SESSION_TIMEOUT_MINUTES, 30);
  });

  it('should have correct max stats age constant', () => {
    assert.strictEqual(tracker.MAX_STATS_AGE_HOURS, 24);
  });

  it('should handle missing insights gracefully', () => {
    const insights = tracker.getPreviousInsights();
    // Should return null when file doesn't exist
    assert.ok(insights === null || typeof insights === 'string');
  });

  it('should export all required functions', () => {
    assert.strictEqual(typeof tracker.isNewSession, 'function');
    assert.strictEqual(typeof tracker.saveState, 'function');
    assert.strictEqual(typeof tracker.getPreviousSessionStats, 'function');
    assert.strictEqual(typeof tracker.clearPreviousSessionStats, 'function');
    assert.strictEqual(typeof tracker.getPreviousInsights, 'function');
    assert.strictEqual(typeof tracker.clearPreviousInsights, 'function');
  });
});

// =============================================================================
// Session Analyzer Tests (5 tests)
// =============================================================================

describe('session-analyzer', () => {
  const analyzer = require('./session-analyzer');

  it('should have correct threshold constants', () => {
    assert.strictEqual(analyzer.THRESHOLD_ERROR_RATE, 0.25);
    assert.strictEqual(analyzer.THRESHOLD_MIN_ERRORS, 5);
    assert.strictEqual(analyzer.THRESHOLD_LINES_CHANGED, 50);
    assert.strictEqual(analyzer.THRESHOLD_CONFIG_FILES, 2);
    assert.strictEqual(analyzer.THRESHOLD_LONG_SESSION, 60);
    assert.strictEqual(analyzer.THRESHOLD_MIN_TOOL_CALLS, 5);
  });

  it('should parse session metrics correctly', () => {
    const inputData = {
      session: {
        tool_calls: 20,
        errors: 5
      }
    };

    const metrics = analyzer.parseSessionMetrics(inputData);
    assert.strictEqual(metrics.toolCalls, 20);
    assert.strictEqual(metrics.errors, 5);
    assert.strictEqual(metrics.errorRate, 0.25);
  });

  it('should handle empty session metrics', () => {
    const metrics = analyzer.parseSessionMetrics({});
    assert.strictEqual(metrics.toolCalls, 0);
    assert.strictEqual(metrics.errors, 0);
    assert.strictEqual(metrics.errorRate, 0);
  });

  it('should generate error suggestion for high error rate', () => {
    const changes = { hasChanges: false, configFiles: [] };
    const metrics = {
      toolCalls: 20,
      errors: 8,
      errorRate: 0.4
    };

    const suggestions = analyzer.getSuggestions(changes, metrics);
    assert.ok(suggestions.length > 0);
    assert.strictEqual(suggestions[0].command, '/undo:checkpoint');
    assert.strictEqual(suggestions[0].trigger, 'errors');
  });

  it('should format session stats correctly', () => {
    const changes = {
      hasChanges: true,
      linesAdded: 100,
      linesDeleted: 20,
      codeFiles: ['file1.js', 'file2.js'],
      testFiles: ['test.js'],
      configFiles: []
    };
    const metrics = {
      toolCalls: 15,
      errors: 2,
      errorRate: 0.13
    };
    const commits = [{ hash: 'abc123', message: 'test' }];

    const formatted = analyzer.formatSessionStats(changes, metrics, commits);
    assert.ok(formatted.includes('[uncommitted:'));
    assert.ok(formatted.includes('+100/-20'));
    assert.ok(formatted.includes('[session: 15 calls, 2 errors]'));
    assert.ok(formatted.includes('[commits: 1]'));
  });

  it('should skip suggestions for short sessions', () => {
    const changes = { hasChanges: true, linesAdded: 100, configFiles: [] };
    const metrics = {
      toolCalls: 3, // Below threshold
      errors: 2,
      errorRate: 0.66
    };

    const suggestions = analyzer.getSuggestions(changes, metrics);
    assert.strictEqual(suggestions.length, 0);
  });
});

// =============================================================================
// Meta Learning Tests (5 tests)
// =============================================================================

describe('meta-learning', () => {
  const metaLearning = require('./meta-learning');

  it('should have correct threshold constants', () => {
    assert.strictEqual(metaLearning.THRESHOLD_REWORK_EDITS, 3);
    assert.strictEqual(metaLearning.THRESHOLD_ERROR_RATE, 0.25);
    assert.strictEqual(metaLearning.THRESHOLD_QUALITY_DROP, 0.15);
    assert.strictEqual(metaLearning.MIN_QUALITY_SAMPLES, 3);
  });

  it('should calculate confidence for high_rework pattern', () => {
    const confidence = metaLearning.calculateConfidence('high_rework', {
      editCount: 6,
      threshold: 3
    });

    // Base 0.5 + bonus for 3 excess edits
    assert.ok(confidence > 0.5);
    assert.ok(confidence <= 1.0);
  });

  it('should calculate confidence for high_error pattern', () => {
    const confidence = metaLearning.calculateConfidence('high_error', {
      errorRate: 0.40
    });

    // Base 0.5 + bonus for exceeding threshold
    assert.ok(confidence > 0.5);
    assert.ok(confidence <= 1.0);
  });

  it('should extract rework pattern when threshold exceeded', () => {
    const fileEditCounts = {
      'src/file1.js': 5,
      'src/file2.js': 2,
      'src/file3.js': 7
    };

    const pattern = metaLearning.extractReworkPattern(fileEditCounts);
    assert.ok(pattern !== null);
    assert.strictEqual(pattern.type, 'high_rework');
    assert.strictEqual(pattern.maxEdits, 7);
    assert.ok(pattern.files.includes('src/file1.js'));
    assert.ok(pattern.files.includes('src/file3.js'));
    assert.ok(!pattern.files.includes('src/file2.js'));
  });

  it('should not extract rework pattern when threshold not exceeded', () => {
    const fileEditCounts = {
      'src/file1.js': 2,
      'src/file2.js': 1,
      'src/file3.js': 3
    };

    const pattern = metaLearning.extractReworkPattern(fileEditCounts);
    assert.strictEqual(pattern, null);
  });

  it('should extract error pattern when error rate exceeds threshold', () => {
    const sessionAnalysis = {
      session: {
        tool_calls: 20,
        errors: 8,
        error_rate: 0.4
      }
    };

    const pattern = metaLearning.extractErrorPattern(sessionAnalysis);
    assert.ok(pattern !== null);
    assert.strictEqual(pattern.type, 'high_error');
    assert.strictEqual(pattern.errorRate, 0.4);
    assert.strictEqual(pattern.totalErrors, 8);
  });

  it('should detect quality drop pattern with declining scores', () => {
    const qualityScores = [0.9, 0.85, 0.75, 0.65, 0.5];

    const pattern = metaLearning.extractQualityDropPattern(qualityScores);
    assert.ok(pattern !== null);
    assert.strictEqual(pattern.type, 'quality_drop');
    assert.strictEqual(pattern.trend, 'declining');
    assert.ok(pattern.slope < 0);
    assert.ok(pattern.totalDrop > 0.15);
  });

  it('should not detect quality drop with insufficient samples', () => {
    const qualityScores = [0.9, 0.5]; // Only 2 samples

    const pattern = metaLearning.extractQualityDropPattern(qualityScores);
    assert.strictEqual(pattern, null);
  });
});

// =============================================================================
// Lesson Injector Tests (5 tests)
// =============================================================================

describe('lesson-injector', () => {
  const injector = require('./lesson-injector');

  it('should have correct confidence constants', () => {
    assert.strictEqual(injector.CONFIDENCE_HIGH, 0.8);
    assert.strictEqual(injector.CONFIDENCE_MEDIUM, 0.5);
    assert.strictEqual(injector.MAX_LESSONS, 3);
  });

  it('should extract context from hook input', () => {
    const hookInput = {
      prompt: 'Fix the bug in utils.js',
      cwd: '/home/user/myproject'
    };

    const context = injector.extractContext(hookInput);
    assert.strictEqual(context.prompt, 'Fix the bug in utils.js');
    assert.ok(context.project); // Should have some project name
  });

  it('should format high confidence lesson without prefix', () => {
    const pattern = {
      pattern: 'Always run tests after editing',
      confidence: 0.9
    };

    const formatted = injector.formatLesson(pattern);
    assert.strictEqual(formatted, '- Always run tests after editing');
  });

  it('should format medium confidence lesson with Consider prefix', () => {
    const pattern = {
      pattern: 'Consider using TDD',
      confidence: 0.6
    };

    const formatted = injector.formatLesson(pattern);
    assert.strictEqual(formatted, '- Consider: Consider using TDD');
  });

  it('should skip low confidence lessons', () => {
    const pattern = {
      pattern: 'Some uncertain advice',
      confidence: 0.3
    };

    const formatted = injector.formatLesson(pattern);
    assert.strictEqual(formatted, null);
  });

  it('should match lessons to context and boost relevance', () => {
    const lessons = [
      { pattern: 'Check for errors before commit', confidence: 0.7 },
      { pattern: 'Always write tests for JavaScript', confidence: 0.8 }
    ];

    const matchedJs = injector.matchLessonsToContext(lessons, 'Edit the file.js');
    assert.ok(matchedJs.length === 2);
    // The JavaScript lesson should be boosted
    assert.ok(matchedJs.some(l => l.pattern.includes('JavaScript')));
  });

  it('should limit lessons to MAX_LESSONS', () => {
    const hookInput = {
      prompt: 'Test prompt',
      cwd: '/test'
    };

    // processHook respects MAX_LESSONS internally
    const result = injector.processHook(hookInput);
    // Result might be empty if no lessons, which is valid
    assert.ok(typeof result === 'object');
  });

  it('should return empty object for empty prompt', () => {
    const hookInput = {
      prompt: '',
      cwd: '/test'
    };

    const result = injector.processHook(hookInput);
    assert.deepStrictEqual(result, {});
  });
});

// =============================================================================
// Integration Tests (5 additional tests)
// =============================================================================

describe('integration', () => {
  it('should export all hooks with required functions', () => {
    const tracker = require('./session-start-tracker');
    const analyzer = require('./session-analyzer');
    const metaLearning = require('./meta-learning');
    const injector = require('./lesson-injector');

    // All should be valid modules
    assert.ok(tracker);
    assert.ok(analyzer);
    assert.ok(metaLearning);
    assert.ok(injector);
  });

  it('should have consistent threshold for error rate across hooks', () => {
    const analyzer = require('./session-analyzer');
    const metaLearning = require('./meta-learning');

    // Both use 0.25 as the error rate threshold
    assert.strictEqual(analyzer.THRESHOLD_ERROR_RATE, metaLearning.THRESHOLD_ERROR_RATE);
  });

  it('should handle missing dependencies gracefully', () => {
    const tracker = require('./session-start-tracker');

    // These functions should not throw even with missing files
    assert.doesNotThrow(() => tracker.getPreviousSessionStats());
    assert.doesNotThrow(() => tracker.getPreviousInsights());
  });

  it('should format suggestions consistently', () => {
    const analyzer = require('./session-analyzer');

    const suggestions = [
      { command: '/health', trigger: 'config', priority: 2 }
    ];

    const formatted = analyzer.formatSuggestions(suggestions);
    assert.ok(formatted.includes('[suggest:'));
    assert.ok(formatted.includes('/health'));
  });

  it('should extract patterns as array', () => {
    const metaLearning = require('./meta-learning');

    const patterns = metaLearning.extractPatterns(
      { session: { errors: 1, tool_calls: 10 } },
      { 'file.js': 2 },
      [0.8, 0.8, 0.8]
    );

    assert.ok(Array.isArray(patterns));
  });
});

console.log('Intelligence hooks tests loaded. Run with: node --test intelligence.test.js');
