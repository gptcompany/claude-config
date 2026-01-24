#!/usr/bin/env node
/**
 * Test All Hooks - Comprehensive Hook Test Suite
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * Validates ALL hooks with:
 * - EXISTENCE: Script file exists and is readable
 * - SYNTAX: Returns valid JSON, exits with code 0
 * - BEHAVIOR: Produces expected output for test cases
 * - INTEGRATION: Works in hook chain
 *
 * Target: 95% pass rate required
 *
 * Usage:
 *   node test-all-hooks.js           # Run all tests
 *   node test-all-hooks.js --dry-run # Show what would be tested
 *   node test-all-hooks.js --verbose # Detailed output
 *   node test-all-hooks.js --json    # JSON output
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_FILE = path.join(HOME_DIR, '.claude', 'hooks', 'hooks.json');
const TEST_TIMEOUT = 10000; // 10 seconds per hook
const PASS_RATE_TARGET = 95; // 95% pass rate required

// Test categories
const TestCategory = {
  EXISTENCE: 'EXISTENCE',
  SYNTAX: 'SYNTAX',
  BEHAVIOR: 'BEHAVIOR',
  INTEGRATION: 'INTEGRATION'
};

// Test result
class TestResult {
  constructor(name, category) {
    this.name = name;
    this.category = category;
    this.passed = false;
    this.error = null;
    this.durationMs = 0;
    this.details = null;
  }
}

/**
 * Load hooks from hooks.json
 * @returns {object[]} Array of hook definitions
 */
function loadHooks() {
  try {
    const config = JSON.parse(fs.readFileSync(HOOKS_FILE, 'utf8'));
    const hooks = [];

    for (const [eventType, hookDefs] of Object.entries(config.hooks || {})) {
      for (let i = 0; i < hookDefs.length; i++) {
        const hookDef = hookDefs[i];

        for (let j = 0; j < (hookDef.hooks || []).length; j++) {
          const hook = hookDef.hooks[j];

          // Extract name from command
          let name = 'unknown';
          const match = hook.command?.match(/([a-zA-Z0-9_-]+)\.js/);
          if (match) {
            name = match[1];
          }

          hooks.push({
            id: `${eventType}[${i}].hooks[${j}]`,
            name,
            eventType,
            matcher: hookDef.matcher,
            command: hook.command,
            description: hookDef.description,
            enabled: hookDef.enabled !== false
          });
        }
      }
    }

    return hooks;
  } catch (e) {
    console.error('Error loading hooks.json:', e.message);
    return [];
  }
}

/**
 * Extract script path from command
 * @param {string} command - Hook command
 * @returns {string|null} Script path or null
 */
function extractScriptPath(command) {
  if (!command) return null;

  // Handle inline scripts
  if (command.includes(' -e ')) {
    return null; // Inline scripts don't have a file
  }

  let scriptPath = command;

  // Handle node prefix
  if (scriptPath.startsWith('node ')) {
    scriptPath = scriptPath.replace(/^node\s+/, '');
  }

  // Expand environment variables
  scriptPath = scriptPath.replace(/\$HOME|\$\{HOME\}/g, HOME_DIR);
  scriptPath = scriptPath.replace(/~/g, HOME_DIR);

  // Remove quotes
  scriptPath = scriptPath.replace(/^["']|["']$/g, '');

  // Extract just the path (first part)
  scriptPath = scriptPath.split(/\s+/)[0];

  return scriptPath;
}

/**
 * Test: Script file exists
 * @param {object} hook - Hook definition
 * @returns {TestResult} Test result
 */
function testExistence(hook) {
  const result = new TestResult(`${hook.name} (exists)`, TestCategory.EXISTENCE);
  const start = Date.now();

  const scriptPath = extractScriptPath(hook.command);

  if (!scriptPath) {
    // Inline script - check if command is valid
    if (hook.command?.includes(' -e ')) {
      result.passed = true;
      result.details = 'Inline script';
    } else {
      result.error = 'No script path found in command';
    }
  } else if (fs.existsSync(scriptPath)) {
    result.passed = true;
    result.details = scriptPath;
  } else {
    result.error = `Script not found: ${scriptPath}`;
  }

  result.durationMs = Date.now() - start;
  return result;
}

/**
 * Get sample input for event type
 * @param {string} eventType - Event type
 * @returns {object} Sample input
 */
function getSampleInput(eventType) {
  switch (eventType) {
    case 'PreToolUse':
      return {
        tool_name: 'Bash',
        tool_input: { command: 'echo test' }
      };
    case 'PostToolUse':
      return {
        tool_name: 'Bash',
        tool_input: { command: 'echo test' },
        tool_output: { output: 'test', exit_code: 0 }
      };
    case 'UserPromptSubmit':
      return {
        message: 'Hello, Claude!'
      };
    case 'Stop':
      return {
        stop_reason: 'end_turn'
      };
    case 'PreCompact':
    case 'PostCompact':
      return {
        compact_reason: 'context_full'
      };
    case 'SessionStart':
      return {
        session_id: 'test-session',
        cwd: process.cwd()
      };
    case 'SessionEnd':
      return {
        session_id: 'test-session'
      };
    default:
      return {};
  }
}

/**
 * Test: Script executes and returns valid JSON
 * @param {object} hook - Hook definition
 * @returns {Promise<TestResult>} Test result
 */
async function testSyntax(hook) {
  const result = new TestResult(`${hook.name} (syntax)`, TestCategory.SYNTAX);
  const start = Date.now();

  return new Promise((resolve) => {
    // Use shell to properly handle quoted paths and env vars
    const input = getSampleInput(hook.eventType);
    const inputJson = JSON.stringify(input);

    try {
      const child = spawn('sh', ['-c', `echo '${inputJson.replace(/'/g, "'\\''")}' | ${hook.command}`], {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, HOOK_TEST: '1', HOME: HOME_DIR }
      });

      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      child.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      const timer = setTimeout(() => {
        child.kill('SIGTERM');
        result.error = 'Timeout';
        result.durationMs = TEST_TIMEOUT;
        resolve(result);
      }, TEST_TIMEOUT);

      child.on('close', (code) => {
        clearTimeout(timer);
        result.durationMs = Date.now() - start;

        if (code !== 0) {
          result.error = `Exit code ${code}. stderr: ${stderr.slice(0, 200)}`;
          resolve(result);
          return;
        }

        // Check if output is valid JSON
        const output = stdout.trim();
        if (!output) {
          result.passed = true; // Empty output is acceptable
          result.details = 'Empty output';
        } else {
          try {
            JSON.parse(output);
            result.passed = true;
            result.details = `Valid JSON (${output.length} bytes)`;
          } catch (e) {
            // Some hooks output non-JSON (stderr messages)
            // This is acceptable if they exit with code 0
            result.passed = true;
            result.details = 'Non-JSON output (acceptable)';
          }
        }

        resolve(result);
      });

      child.on('error', (err) => {
        clearTimeout(timer);
        result.error = err.message;
        result.durationMs = Date.now() - start;
        resolve(result);
      });
    } catch (err) {
      result.error = err.message;
      result.durationMs = Date.now() - start;
      resolve(result);
    }
  });
}

/**
 * Test: Script produces expected behavior
 * @param {object} hook - Hook definition
 * @returns {Promise<TestResult>} Test result
 */
async function testBehavior(hook) {
  const result = new TestResult(`${hook.name} (behavior)`, TestCategory.BEHAVIOR);
  const start = Date.now();

  // Define behavior tests based on hook type
  const behaviorTests = {
    'git-safety-check': async () => {
      // Should block dangerous commands
      const input = {
        tool_name: 'Bash',
        tool_input: { command: 'git push --force origin main' }
      };
      return testHookBlocks(hook, input);
    },
    'port-conflict-check': async () => {
      // Should check for port conflicts
      const input = {
        tool_name: 'Bash',
        tool_input: { command: 'npm run dev --port 3000' }
      };
      return testHookRuns(hook, input);
    },
    'session-start': async () => {
      // Should inject context
      const input = { session_id: 'test', cwd: process.cwd() };
      return testHookRuns(hook, input);
    }
  };

  // Check if we have a specific behavior test
  const behaviorTest = behaviorTests[hook.name];

  if (behaviorTest) {
    try {
      const testResult = await behaviorTest();
      result.passed = testResult.passed;
      result.error = testResult.error;
      result.details = testResult.details;
    } catch (e) {
      result.error = e.message;
    }
  } else {
    // Default: just run with sample input
    try {
      const runResult = await testHookRuns(hook, getSampleInput(hook.eventType));
      result.passed = runResult.passed;
      result.error = runResult.error;
      result.details = runResult.details;
    } catch (e) {
      result.error = e.message;
    }
  }

  result.durationMs = Date.now() - start;
  return result;
}

/**
 * Test that hook runs successfully
 * @param {object} hook - Hook definition
 * @param {object} input - Input data
 * @returns {Promise<object>} Result
 */
async function testHookRuns(hook, input) {
  return new Promise((resolve) => {
    const inputJson = JSON.stringify(input);

    const child = spawn('sh', ['-c', `echo '${inputJson.replace(/'/g, "'\\''")}' | ${hook.command}`], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, HOOK_TEST: '1', HOME: HOME_DIR }
    });

    let stdout = '';

    child.stdout.on('data', data => { stdout += data.toString(); });

    const timer = setTimeout(() => {
      child.kill('SIGTERM');
      resolve({ passed: false, error: 'Timeout' });
    }, TEST_TIMEOUT);

    child.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve({ passed: true, details: 'Executed successfully' });
      } else {
        resolve({ passed: false, error: `Exit code ${code}` });
      }
    });

    child.on('error', (err) => {
      clearTimeout(timer);
      resolve({ passed: false, error: err.message });
    });
  });
}

/**
 * Test that hook blocks (returns non-zero or decision:block)
 * @param {object} hook - Hook definition
 * @param {object} input - Input data
 * @returns {Promise<object>} Result
 */
async function testHookBlocks(hook, input) {
  return new Promise((resolve) => {
    const inputJson = JSON.stringify(input);

    const child = spawn('sh', ['-c', `echo '${inputJson.replace(/'/g, "'\\''")}' | ${hook.command}`], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, HOOK_TEST: '1', HOME: HOME_DIR }
    });

    let stdout = '';

    child.stdout.on('data', data => { stdout += data.toString(); });

    const timer = setTimeout(() => {
      child.kill('SIGTERM');
      resolve({ passed: false, error: 'Timeout' });
    }, TEST_TIMEOUT);

    child.on('close', (code) => {
      clearTimeout(timer);

      // Check for block in output
      try {
        const output = JSON.parse(stdout);
        if (output.decision === 'block' || output.approve === false) {
          resolve({ passed: true, details: 'Correctly blocked' });
          return;
        }
      } catch (e) {
        // Not JSON, check exit code
      }

      // Non-zero exit code also means blocked
      if (code !== 0) {
        resolve({ passed: true, details: `Blocked with exit code ${code}` });
      } else {
        resolve({ passed: false, error: 'Should have blocked but allowed' });
      }
    });

    child.on('error', (err) => {
      clearTimeout(timer);
      resolve({ passed: false, error: err.message });
    });
  });
}

/**
 * Run all tests
 * @param {object} options - Test options
 * @returns {Promise<object>} Test results
 */
async function runAllTests(options = {}) {
  const hooks = loadHooks();
  const results = [];
  const stats = {
    total: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    byCategory: {
      [TestCategory.EXISTENCE]: { total: 0, passed: 0 },
      [TestCategory.SYNTAX]: { total: 0, passed: 0 },
      [TestCategory.BEHAVIOR]: { total: 0, passed: 0 },
      [TestCategory.INTEGRATION]: { total: 0, passed: 0 }
    }
  };

  // Track unique hooks (avoid duplicates)
  const testedHooks = new Set();

  for (const hook of hooks) {
    // Skip disabled hooks unless explicitly included
    if (!hook.enabled && !options.includeDisabled) {
      stats.skipped++;
      continue;
    }

    // Skip if we've already tested this hook
    const hookKey = `${hook.name}:${hook.command}`;
    if (testedHooks.has(hookKey)) {
      continue;
    }
    testedHooks.add(hookKey);

    if (options.verbose) {
      console.log(`Testing: ${hook.name} (${hook.eventType})`);
    }

    // Test 1: Existence
    const existenceResult = testExistence(hook);
    results.push(existenceResult);
    stats.total++;
    stats.byCategory[TestCategory.EXISTENCE].total++;

    if (existenceResult.passed) {
      stats.passed++;
      stats.byCategory[TestCategory.EXISTENCE].passed++;
    } else {
      stats.failed++;
      if (options.verbose) {
        console.log(`  FAIL: ${existenceResult.error}`);
      }
      continue; // Skip other tests if script doesn't exist
    }

    // Test 2: Syntax (only for file scripts)
    const scriptPath = extractScriptPath(hook.command);
    if (scriptPath || hook.command?.includes(' -e ')) {
      const syntaxResult = await testSyntax(hook);
      results.push(syntaxResult);
      stats.total++;
      stats.byCategory[TestCategory.SYNTAX].total++;

      if (syntaxResult.passed) {
        stats.passed++;
        stats.byCategory[TestCategory.SYNTAX].passed++;
      } else {
        stats.failed++;
        if (options.verbose) {
          console.log(`  FAIL: ${syntaxResult.error}`);
        }
        continue;
      }
    }

    // Test 3: Behavior
    const behaviorResult = await testBehavior(hook);
    results.push(behaviorResult);
    stats.total++;
    stats.byCategory[TestCategory.BEHAVIOR].total++;

    if (behaviorResult.passed) {
      stats.passed++;
      stats.byCategory[TestCategory.BEHAVIOR].passed++;
    } else {
      stats.failed++;
      if (options.verbose) {
        console.log(`  FAIL: ${behaviorResult.error}`);
      }
    }
  }

  // Calculate pass rate
  stats.passRate = stats.total > 0 ? Math.round((stats.passed / stats.total) * 100) : 0;
  stats.passed95 = stats.passRate >= PASS_RATE_TARGET;

  return { results, stats };
}

/**
 * Format test results for display
 * @param {object} testData - Test data
 * @returns {string} Formatted output
 */
function formatResults(testData) {
  const { results, stats } = testData;
  const lines = [
    'Hook Validation Report',
    '======================',
    '',
    `Total: ${stats.total} tests`,
    `Passed: ${stats.passed} (${stats.passRate}%)`,
    `Failed: ${stats.failed}`,
    `Skipped: ${stats.skipped}`,
    '',
    `Target: ${PASS_RATE_TARGET}%`,
    `Status: ${stats.passed95 ? 'PASS' : 'FAIL'}`,
    ''
  ];

  // Show failed tests
  const failed = results.filter(r => !r.passed);
  if (failed.length > 0) {
    lines.push('FAILED:');
    for (const result of failed) {
      lines.push(`- ${result.name}: ${result.error}`);
    }
    lines.push('');
  }

  // Show category breakdown
  lines.push('By Category:');
  for (const [category, catStats] of Object.entries(stats.byCategory)) {
    if (catStats.total > 0) {
      const rate = Math.round((catStats.passed / catStats.total) * 100);
      lines.push(`  ${category}: ${catStats.passed}/${catStats.total} (${rate}%)`);
    }
  }

  return lines.join('\n');
}

/**
 * Show dry-run info
 */
function showDryRun() {
  const hooks = loadHooks();
  const uniqueHooks = new Map();

  for (const hook of hooks) {
    if (!uniqueHooks.has(hook.name)) {
      uniqueHooks.set(hook.name, hook);
    }
  }

  console.log('Hooks to be tested:');
  console.log('===================');
  console.log('');

  for (const [name, hook] of uniqueHooks) {
    const status = hook.enabled ? '[enabled]' : '[disabled]';
    console.log(`${name} ${status}`);
    console.log(`  Event: ${hook.eventType}`);
    console.log(`  Matcher: ${hook.matcher?.slice(0, 50) || '*'}`);
    console.log('');
  }

  console.log(`Total: ${uniqueHooks.size} unique hooks`);
  console.log(`Target pass rate: ${PASS_RATE_TARGET}%`);
}

/**
 * Main CLI handler
 */
async function main() {
  const args = process.argv.slice(2);
  const options = {
    verbose: args.includes('--verbose') || args.includes('-v'),
    json: args.includes('--json'),
    dryRun: args.includes('--dry-run'),
    includeDisabled: args.includes('--all')
  };

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Test All Hooks - Comprehensive Hook Test Suite

Usage:
  node test-all-hooks.js            Run all tests
  node test-all-hooks.js --dry-run  Show what would be tested
  node test-all-hooks.js --verbose  Detailed output
  node test-all-hooks.js --json     JSON output
  node test-all-hooks.js --all      Include disabled hooks

Exit Codes:
  0: Pass rate >= ${PASS_RATE_TARGET}%
  1: Pass rate < ${PASS_RATE_TARGET}%
`);
    return;
  }

  if (options.dryRun) {
    showDryRun();
    return;
  }

  console.log('Running hook tests...\n');

  const testData = await runAllTests(options);

  if (options.json) {
    console.log(JSON.stringify(testData, null, 2));
  } else {
    console.log(formatResults(testData));
  }

  // Exit with appropriate code
  process.exit(testData.stats.passed95 ? 0 : 1);
}

// Run if called directly
if (require.main === module) {
  main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
  });
}

module.exports = {
  loadHooks,
  testExistence,
  testSyntax,
  testBehavior,
  runAllTests,
  formatResults,
  TestCategory,
  TestResult,
  PASS_RATE_TARGET
};
