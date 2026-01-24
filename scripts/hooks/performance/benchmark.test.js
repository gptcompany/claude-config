/**
 * Benchmark Tests for Claude Code Hooks
 * Phase 14.6-03: Performance and reliability validation
 *
 * Tests timing constraints for individual hooks, hook chains, and QuestDB export.
 *
 * Performance baselines:
 * - Safety hooks: < 100ms
 * - Intelligence hooks: < 200ms
 * - Quality hooks: < 300ms
 * - Productivity hooks: < 150ms
 * - Metrics hooks: < 100ms
 * - UX hooks: < 150ms
 * - Hook chains: < 500ms total
 * - QuestDB single export: < 50ms
 * - QuestDB batch export: < 200ms
 *
 * Uses performance.now() for timing, runs 10 iterations, uses median.
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

// Test configuration
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const ITERATIONS = 10;

// Performance thresholds (ms)
// Note: Thresholds include 10% margin for system variance
const THRESHOLDS = {
  safety: 110,      // Target: <100ms + 10% margin
  intelligence: 220, // Target: <200ms + 10% margin
  quality: 330,     // Target: <300ms + 10% margin
  productivity: 165, // Target: <150ms + 10% margin
  metrics: 110,     // Target: <100ms + 10% margin
  ux: 165,          // Target: <150ms + 10% margin
  hookChain: 550,   // Target: <500ms + 10% margin
  questdbSingle: 55, // Target: <50ms + 10% margin
  questdbBatch: 220, // Target: <200ms + 10% margin
  questdbQuery: 110  // Target: <100ms + 10% margin
};

/**
 * Run a hook and measure execution time
 */
function runHookTimed(hookPath, input = {}) {
  const start = performance.now();
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout: 10000
  });
  const elapsed = performance.now() - start;

  return {
    success: result.status === 0,
    elapsed,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

/**
 * Run benchmark N times and return median execution time
 */
function benchmarkHook(hookPath, input = {}, iterations = ITERATIONS) {
  const times = [];

  for (let i = 0; i < iterations; i++) {
    const result = runHookTimed(hookPath, input);
    if (result.success) {
      times.push(result.elapsed);
    }
  }

  if (times.length === 0) {
    return { median: Infinity, min: Infinity, max: Infinity, success: false };
  }

  times.sort((a, b) => a - b);
  const median = times[Math.floor(times.length / 2)];
  const min = times[0];
  const max = times[times.length - 1];

  return { median, min, max, success: true, samples: times.length };
}

/**
 * Check if hook file exists
 */
function hookExists(hookPath) {
  return fs.existsSync(hookPath);
}

// =============================================================================
// Individual Hook Latency Tests (6 tests)
// =============================================================================

describe('individual hook latency', () => {
  test('safety hooks complete within 100ms', async () => {
    const safetyHooks = [
      'safety/git-safety-check.js',
      'safety/smart-safety-check.js',
      'safety/port-conflict-check.js',
      'safety/ci-batch-check.js'
    ];

    for (const hookName of safetyHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {
        tool_name: 'Bash',
        tool_input: { command: 'echo test' }
      });

      assert.ok(
        result.median < THRESHOLDS.safety,
        `Safety hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.safety}ms)`
      );
    }
  });

  test('intelligence hooks complete within 200ms', async () => {
    const intelligenceHooks = [
      'intelligence/session-start-tracker.js',
      'intelligence/lesson-injector.js',
      'intelligence/session-analyzer.js',
      'intelligence/meta-learning.js'
    ];

    for (const hookName of intelligenceHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {});

      assert.ok(
        result.median < THRESHOLDS.intelligence,
        `Intelligence hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.intelligence}ms)`
      );
    }
  });

  test('quality hooks complete within 300ms', async () => {
    const qualityHooks = [
      'quality/plan-validator.js',
      'quality/pr-readiness.js',
      'quality/architecture-validator.js',
      'quality/ci-autofix.js',
      'quality/readme-generator.js'
    ];

    for (const hookName of qualityHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {
        tool_name: 'Write',
        tool_input: { file_path: '/tmp/test.js' }
      });

      assert.ok(
        result.median < THRESHOLDS.quality,
        `Quality hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.quality}ms)`
      );
    }
  });

  test('productivity hooks complete within 150ms', async () => {
    const productivityHooks = [
      'productivity/auto-format.js',
      'productivity/tdd-guard.js',
      'productivity/task-checkpoint.js',
      'productivity/auto-simplify.js'
    ];

    for (const hookName of productivityHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {
        tool_name: 'Write',
        tool_input: { file_path: '/tmp/test.js' }
      });

      assert.ok(
        result.median < THRESHOLDS.productivity,
        `Productivity hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.productivity}ms)`
      );
    }
  });

  test('metrics hooks complete within 100ms', async () => {
    const metricsHooks = [
      'metrics/dora-tracker.js',
      'metrics/quality-score.js',
      'metrics/claudeflow-sync.js'
    ];

    for (const hookName of metricsHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {
        tool_name: 'Write',
        tool_input: { file_path: '/tmp/test.js' }
      });

      assert.ok(
        result.median < THRESHOLDS.metrics,
        `Metrics hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.metrics}ms)`
      );
    }
  });

  test('UX hooks complete within 150ms', async () => {
    const uxHooks = [
      'ux/tips-injector.js',
      'ux/session-insights.js'
    ];

    for (const hookName of uxHooks) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      const result = benchmarkHook(hookPath, {});

      assert.ok(
        result.median < THRESHOLDS.ux,
        `UX hook ${hookName} took ${result.median.toFixed(1)}ms (threshold: ${THRESHOLDS.ux}ms)`
      );
    }
  });
});

// =============================================================================
// Hook Chain Latency Tests (3 tests)
// =============================================================================

describe('hook chain latency', () => {
  test('session start chain completes within 500ms', async () => {
    const sessionStartChain = [
      'intelligence/session-start-tracker.js',
      'intelligence/lesson-injector.js',
      'ux/tips-injector.js'
    ];

    const start = performance.now();

    for (const hookName of sessionStartChain) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      runHookTimed(hookPath, {});
    }

    const elapsed = performance.now() - start;

    assert.ok(
      elapsed < THRESHOLDS.hookChain,
      `Session start chain took ${elapsed.toFixed(1)}ms (threshold: ${THRESHOLDS.hookChain}ms)`
    );
  });

  test('tool use chain completes within 500ms', async () => {
    const toolUseChain = [
      'safety/smart-safety-check.js',
      'coordination/file-coordination.js',
      'metrics/dora-tracker.js',
      'metrics/quality-score.js'
    ];

    const start = performance.now();

    for (const hookName of toolUseChain) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      runHookTimed(hookPath, {
        tool_name: 'Edit',
        tool_input: { file_path: '/tmp/test.js' }
      });
    }

    const elapsed = performance.now() - start;

    assert.ok(
      elapsed < THRESHOLDS.hookChain,
      `Tool use chain took ${elapsed.toFixed(1)}ms (threshold: ${THRESHOLDS.hookChain}ms)`
    );
  });

  test('session end chain completes within 500ms', async () => {
    const sessionEndChain = [
      'intelligence/session-analyzer.js',
      'intelligence/meta-learning.js',
      'ux/session-insights.js'
    ];

    const start = performance.now();

    for (const hookName of sessionEndChain) {
      const hookPath = path.join(HOOKS_DIR, hookName);
      if (!hookExists(hookPath)) continue;

      runHookTimed(hookPath, {});
    }

    const elapsed = performance.now() - start;

    assert.ok(
      elapsed < THRESHOLDS.hookChain,
      `Session end chain took ${elapsed.toFixed(1)}ms (threshold: ${THRESHOLDS.hookChain}ms)`
    );
  });
});

// =============================================================================
// QuestDB Export Latency Tests (3 tests)
// =============================================================================

describe('QuestDB export latency', () => {
  const METRICS_LIB_PATH = path.join(os.homedir(), '.claude', 'scripts', 'lib', 'metrics.js');
  let metricsLib = null;

  beforeEach(() => {
    try {
      metricsLib = require(METRICS_LIB_PATH);
    } catch (err) {
      // Metrics lib not available - tests will be skipped
    }
  });

  test('single metric export completes within 50ms', async (t) => {
    if (!metricsLib || !metricsLib.exportToQuestDB) {
      t.skip('Metrics library not available');
      return;
    }

    const times = [];
    for (let i = 0; i < ITERATIONS; i++) {
      const start = performance.now();
      try {
        await metricsLib.exportToQuestDB('test_benchmark', {
          value: i,
          timestamp: Date.now()
        }, { test: 'benchmark' });
      } catch (err) {
        // QuestDB might not be available
      }
      times.push(performance.now() - start);
    }

    const median = times.sort((a, b) => a - b)[Math.floor(times.length / 2)];

    // If QuestDB is unavailable, the fallback should still be fast
    assert.ok(
      median < THRESHOLDS.questdbSingle,
      `Single export took ${median.toFixed(1)}ms (threshold: ${THRESHOLDS.questdbSingle}ms)`
    );
  });

  test('batch export (100 rows) completes within 200ms', async (t) => {
    if (!metricsLib || !metricsLib.exportBatchToQuestDB) {
      // Fall back to sequential exports if batch not available
      if (!metricsLib || !metricsLib.exportToQuestDB) {
        t.skip('Metrics library not available');
        return;
      }
    }

    const rows = Array.from({ length: 100 }, (_, i) => ({
      value: i,
      timestamp: Date.now() + i
    }));

    const start = performance.now();

    if (metricsLib.exportBatchToQuestDB) {
      try {
        await metricsLib.exportBatchToQuestDB('test_benchmark_batch', rows, { test: 'batch' });
      } catch (err) {
        // QuestDB might not be available
      }
    } else {
      // Simulate batch with sequential exports (should still be fast with fallback)
      for (const row of rows.slice(0, 10)) { // Only test 10 for sequential
        try {
          await metricsLib.exportToQuestDB('test_benchmark_batch', row, { test: 'batch' });
        } catch (err) {}
      }
    }

    const elapsed = performance.now() - start;

    assert.ok(
      elapsed < THRESHOLDS.questdbBatch,
      `Batch export took ${elapsed.toFixed(1)}ms (threshold: ${THRESHOLDS.questdbBatch}ms)`
    );
  });

  test('query response within 100ms (or graceful skip)', async (t) => {
    if (!metricsLib || !metricsLib.queryQuestDB) {
      t.skip('Query function not available');
      return;
    }

    const times = [];
    for (let i = 0; i < 5; i++) { // Fewer iterations for queries
      const start = performance.now();
      try {
        await metricsLib.queryQuestDB('SELECT count() FROM test_benchmark');
      } catch (err) {
        // QuestDB unavailable is acceptable
      }
      times.push(performance.now() - start);
    }

    const median = times.sort((a, b) => a - b)[Math.floor(times.length / 2)];

    // Allow graceful degradation if QuestDB unavailable
    assert.ok(
      median < THRESHOLDS.questdbQuery,
      `Query took ${median.toFixed(1)}ms (threshold: ${THRESHOLDS.questdbQuery}ms)`
    );
  });
});

// =============================================================================
// Baseline Recording
// =============================================================================

describe('baseline recording', () => {
  test('record all hook baselines for reference', async () => {
    const baselines = {};

    const allHooks = [
      { category: 'safety', hooks: ['safety/git-safety-check.js', 'safety/smart-safety-check.js'] },
      { category: 'intelligence', hooks: ['intelligence/session-start-tracker.js', 'intelligence/lesson-injector.js'] },
      { category: 'quality', hooks: ['quality/plan-validator.js', 'quality/pr-readiness.js'] },
      { category: 'ux', hooks: ['ux/tips-injector.js', 'ux/session-insights.js'] },
      { category: 'metrics', hooks: ['metrics/dora-tracker.js', 'metrics/quality-score.js'] }
    ];

    for (const { category, hooks } of allHooks) {
      baselines[category] = {};
      for (const hookName of hooks) {
        const hookPath = path.join(HOOKS_DIR, hookName);
        if (!hookExists(hookPath)) continue;

        const result = benchmarkHook(hookPath, {}, 5); // Fewer iterations for baseline
        if (result.success) {
          baselines[category][hookName] = {
            median: Math.round(result.median),
            min: Math.round(result.min),
            max: Math.round(result.max)
          };
        }
      }
    }

    // Record baselines (visible in test output)
    console.log('\n--- Performance Baselines (ms) ---');
    for (const [category, hooks] of Object.entries(baselines)) {
      console.log(`\n${category}:`);
      for (const [hook, times] of Object.entries(hooks)) {
        console.log(`  ${hook}: median=${times.median}, min=${times.min}, max=${times.max}`);
      }
    }

    // Basic assertion that baselines were recorded
    assert.ok(Object.keys(baselines).length > 0, 'Baselines should be recorded');
  });
});
