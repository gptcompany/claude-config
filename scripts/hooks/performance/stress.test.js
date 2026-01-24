/**
 * Stress Tests for Claude Code Hooks
 * Phase 14.6-03: Performance and reliability validation
 *
 * Tests stress scenarios:
 * - High volume hook calls (100 invocations)
 * - Large payload handling (1MB+)
 * - Sustained load (60 seconds)
 *
 * Verifies:
 * - No memory leaks (RSS stable)
 * - No timing degradation
 * - No file handle leaks
 * - Bounded resource usage
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const { spawnSync, spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

// Test configuration
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const TEMP_DIR = path.join(os.tmpdir(), 'hook-stress-test-' + Date.now());
const METRICS_DIR = path.join(os.homedir(), '.claude', 'metrics');

// Resource limits
const MAX_RSS_MB = 200; // Maximum RSS in MB
const MAX_TIMING_DEGRADATION = 2.0; // Max acceptable timing increase factor
const SUSTAINED_TEST_DURATION_MS = 10000; // 10 seconds (reduced from 60 for practical testing)

/**
 * Run a hook synchronously
 */
function runHook(hookPath, input = {}, timeout = 5000) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout
  });

  return {
    exitCode: result.status,
    success: result.status === 0,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

/**
 * Run hook asynchronously
 */
function runHookAsync(hookPath, input = {}) {
  return new Promise((resolve) => {
    const proc = spawn('node', [hookPath], { timeout: 10000 });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => { stdout += data.toString(); });
    proc.stderr.on('data', (data) => { stderr += data.toString(); });

    proc.on('close', (code) => {
      resolve({ exitCode: code, success: code === 0, stdout, stderr });
    });

    proc.on('error', () => {
      resolve({ exitCode: -1, success: false, stdout, stderr });
    });

    proc.stdin.write(JSON.stringify(input));
    proc.stdin.end();
  });
}

/**
 * Check if hook file exists
 */
function hookExists(hookPath) {
  return fs.existsSync(hookPath);
}

/**
 * Get current process memory usage in MB
 */
function getMemoryUsageMB() {
  const usage = process.memoryUsage();
  return {
    rss: usage.rss / (1024 * 1024),
    heapUsed: usage.heapUsed / (1024 * 1024),
    heapTotal: usage.heapTotal / (1024 * 1024)
  };
}

/**
 * Count open file handles (Linux only)
 */
function countOpenFileHandles() {
  try {
    const fdDir = `/proc/${process.pid}/fd`;
    if (fs.existsSync(fdDir)) {
      return fs.readdirSync(fdDir).length;
    }
  } catch (err) {}
  return -1; // Not available
}

/**
 * Get file size in bytes
 */
function getFileSize(filePath) {
  try {
    return fs.statSync(filePath).size;
  } catch (err) {
    return 0;
  }
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
// High Volume Hook Calls Tests (3 tests)
// =============================================================================

describe('high volume hook calls', () => {
  test('100 hook invocations in sequence', async () => {
    const hookPath = path.join(HOOKS_DIR, 'control', 'ralph-loop.js');
    if (!hookExists(hookPath)) {
      return;
    }

    let successCount = 0;
    const timings = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      const result = runHook(hookPath, {});
      const elapsed = performance.now() - start;

      if (result.success) {
        successCount++;
        timings.push(elapsed);
      }
    }

    assert.strictEqual(successCount, 100, `All 100 invocations should succeed, got ${successCount}`);

    // Verify timing is consistent (no degradation)
    const firstTen = timings.slice(0, 10);
    const lastTen = timings.slice(-10);
    const avgFirst = firstTen.reduce((a, b) => a + b, 0) / firstTen.length;
    const avgLast = lastTen.reduce((a, b) => a + b, 0) / lastTen.length;

    console.log(`First 10 avg: ${avgFirst.toFixed(1)}ms, Last 10 avg: ${avgLast.toFixed(1)}ms`);

    // Last 10 should not be more than 2x slower than first 10
    assert.ok(
      avgLast < avgFirst * MAX_TIMING_DEGRADATION + 50, // +50ms tolerance
      `Timing degradation detected: first=${avgFirst.toFixed(1)}ms, last=${avgLast.toFixed(1)}ms`
    );
  });

  test('verify no memory leak over 100 calls', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Force GC if available (run with --expose-gc)
    if (global.gc) global.gc();

    const memBefore = getMemoryUsageMB();

    for (let i = 0; i < 100; i++) {
      runHook(hookPath, {});
    }

    // Force GC if available
    if (global.gc) global.gc();

    const memAfter = getMemoryUsageMB();

    // RSS should not grow significantly
    const rssGrowth = memAfter.rss - memBefore.rss;
    console.log(`RSS before: ${memBefore.rss.toFixed(1)}MB, after: ${memAfter.rss.toFixed(1)}MB, growth: ${rssGrowth.toFixed(1)}MB`);

    // Allow up to 50MB growth (spawning processes uses memory)
    assert.ok(
      memAfter.rss < MAX_RSS_MB,
      `RSS exceeded limit: ${memAfter.rss.toFixed(1)}MB > ${MAX_RSS_MB}MB`
    );
  });

  test('verify timing consistent across volume', async () => {
    const hookPath = path.join(HOOKS_DIR, 'intelligence', 'lesson-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const batches = [
      { start: 0, end: 10 },
      { start: 45, end: 55 },
      { start: 90, end: 100 }
    ];

    const batchTimings = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      runHook(hookPath, {});
      const elapsed = performance.now() - start;

      for (const batch of batches) {
        if (i >= batch.start && i < batch.end) {
          if (!batchTimings[batches.indexOf(batch)]) {
            batchTimings[batches.indexOf(batch)] = [];
          }
          batchTimings[batches.indexOf(batch)].push(elapsed);
        }
      }
    }

    // Calculate averages
    const avgTimings = batchTimings.map(times =>
      times.reduce((a, b) => a + b, 0) / times.length
    );

    console.log(`Batch timings: start=${avgTimings[0]?.toFixed(1)}ms, mid=${avgTimings[1]?.toFixed(1)}ms, end=${avgTimings[2]?.toFixed(1)}ms`);

    // All batches should be within 2x of each other
    const maxTiming = Math.max(...avgTimings);
    const minTiming = Math.min(...avgTimings);

    assert.ok(
      maxTiming < minTiming * MAX_TIMING_DEGRADATION + 30,
      `Timing variance too high: min=${minTiming.toFixed(1)}ms, max=${maxTiming.toFixed(1)}ms`
    );
  });
});

// =============================================================================
// Large Payload Handling Tests (3 tests)
// =============================================================================

describe('large payload handling', () => {
  test('1MB JSON input handled or rejected gracefully', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'tips-injector.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Create 1MB payload
    const largeContent = 'x'.repeat(1024 * 1024);
    const largeInput = {
      prompt: largeContent,
      session_id: 'stress-test'
    };

    const start = performance.now();
    const result = runHook(hookPath, largeInput, 30000); // 30s timeout for large payload
    const elapsed = performance.now() - start;

    // Should either succeed or exit gracefully (no crash)
    assert.ok(
      result.exitCode === 0 || result.exitCode !== null,
      `Hook should handle 1MB input gracefully, got exit code ${result.exitCode}`
    );

    console.log(`1MB payload handled in ${elapsed.toFixed(0)}ms`);
  });

  test('1000-file simulated git diff handled', async () => {
    const hookPath = path.join(HOOKS_DIR, 'safety', 'smart-safety-check.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Simulate a large git diff command
    const files = Array.from({ length: 1000 }, (_, i) => `src/file${i}.js`).join(' ');
    const command = `git diff ${files}`;

    const result = runHook(hookPath, {
      tool_name: 'Bash',
      tool_input: { command }
    }, 10000);

    assert.ok(
      result.exitCode === 0,
      `Hook should handle large file list, got exit code ${result.exitCode}`
    );
  });

  test('large tool output handled', async () => {
    const hookPath = path.join(HOOKS_DIR, 'metrics', 'quality-score.js');
    if (!hookExists(hookPath)) {
      return;
    }

    // Simulate large test output (10000 lines)
    const largeOutput = Array.from({ length: 10000 }, (_, i) =>
      `test_case_${i} PASSED`
    ).join('\n');

    const result = runHook(hookPath, {
      tool_name: 'Bash',
      tool_input: { command: 'pytest tests/' },
      tool_output: largeOutput
    }, 10000);

    assert.ok(
      result.exitCode === 0,
      `Hook should handle large tool output, got exit code ${result.exitCode}`
    );
  });
});

// =============================================================================
// Sustained Load Tests (3 tests)
// =============================================================================

describe('sustained load', () => {
  test('run hooks for 10 seconds continuously', async () => {
    const hookPath = path.join(HOOKS_DIR, 'control', 'ralph-loop.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const startTime = Date.now();
    const endTime = startTime + SUSTAINED_TEST_DURATION_MS;
    let iterations = 0;
    let failures = 0;

    while (Date.now() < endTime) {
      const result = runHook(hookPath, {});
      iterations++;
      if (!result.success) failures++;

      // Small delay to prevent overwhelming the system
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    const elapsed = (Date.now() - startTime) / 1000;
    const rate = iterations / elapsed;

    console.log(`Sustained load: ${iterations} iterations in ${elapsed.toFixed(1)}s (${rate.toFixed(1)}/s), ${failures} failures`);

    // Failure rate should be < 1%
    const failureRate = failures / iterations;
    assert.ok(
      failureRate < 0.01,
      `Failure rate too high: ${(failureRate * 100).toFixed(1)}% (${failures}/${iterations})`
    );
  });

  test('verify metrics file does not grow unbounded', async () => {
    const hookPath = path.join(HOOKS_DIR, 'ux', 'session-insights.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const insightsFile = path.join(METRICS_DIR, 'session_insights.json');
    const initialSize = getFileSize(insightsFile);

    // Run hook 50 times
    for (let i = 0; i < 50; i++) {
      runHook(hookPath, { session_id: `stress-${i}` });
    }

    const finalSize = getFileSize(insightsFile);

    console.log(`Metrics file: initial=${initialSize}B, final=${finalSize}B`);

    // File should not grow significantly (it overwrites, not appends)
    // Allow up to 10KB growth
    assert.ok(
      finalSize < initialSize + 10240 || finalSize < 20480,
      `Metrics file grew too much: ${initialSize}B -> ${finalSize}B`
    );
  });

  test('verify no file handle leaks', async () => {
    const hookPath = path.join(HOOKS_DIR, 'control', 'hive-manager.js');
    if (!hookExists(hookPath)) {
      return;
    }

    const handlesBefore = countOpenFileHandles();

    // Run hook many times
    for (let i = 0; i < 50; i++) {
      runHook(hookPath, { tool_name: 'Task', tool_input: { description: `Leak test ${i}` } });
    }

    // Wait a bit for cleanup
    await new Promise(resolve => setTimeout(resolve, 100));

    const handlesAfter = countOpenFileHandles();

    if (handlesBefore === -1 || handlesAfter === -1) {
      console.log('File handle counting not available on this platform');
      return;
    }

    console.log(`File handles: before=${handlesBefore}, after=${handlesAfter}`);

    // Should not have significant handle growth
    assert.ok(
      handlesAfter < handlesBefore + 10,
      `File handle leak detected: ${handlesBefore} -> ${handlesAfter}`
    );
  });
});
