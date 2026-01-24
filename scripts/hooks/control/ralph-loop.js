#!/usr/bin/env node
/**
 * Ralph Loop Controller (Stop hook)
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/control/ralph-loop.py
 *
 * Implements the Ralph Wiggum pattern for continuous autonomous development.
 * When Claude attempts to stop and Ralph mode is active, this hook:
 * 1. Checks if exit criteria are met (tests pass, no errors)
 * 2. If not met, re-injects the original prompt
 * 3. Tracks progress and applies circuit breakers
 *
 * Based on: https://ghuntley.com/ralph/
 *
 * Features:
 * - Project-specific state (per cwd hash)
 * - Circuit breakers: max iterations, consecutive errors, no progress
 * - CI validation between iterations
 * - Git auto-commit checkpoints
 * - Rate limiting
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execSync, spawnSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const RALPH_DIR = path.join(HOME_DIR, '.claude', 'ralph');
const LOG_DIR = path.join(HOME_DIR, '.claude', 'logs');
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const RALPH_LOG = path.join(METRICS_DIR, 'ralph_iterations.jsonl');

// Plugin state file (markdown with YAML frontmatter)
const PLUGIN_STATE_FILENAME = '.claude/ralph-loop.local.md';

// Default configuration
const DEFAULT_CONFIG = {
  max_iterations: 15,
  max_budget_usd: 20.0,
  max_consecutive_errors: 3,
  max_no_progress: 5,
  max_ci_failures: 3,
  min_iteration_interval_secs: 10,
  max_iterations_per_hour: 100,
  estimated_cost_per_iteration: 2.0
};

// Exit detection patterns
const EXIT_PATTERNS = [
  'all tests pass',
  'tests passing',
  'no errors found',
  'task complete',
  'successfully completed',
  'done',
  'finished'
];

const ERROR_PATTERNS = [
  'error:',
  'failed',
  'exception',
  'traceback',
  'syntax error'
];

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Log to file
 */
function log(msg) {
  ensureDir(LOG_DIR);
  try {
    const entry = JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'INFO',
      module: 'ralph-loop',
      message: msg
    });
    fs.appendFileSync(path.join(LOG_DIR, 'ralph-loop.log'), entry + '\n');
  } catch (err) {
    // Ignore
  }
}

/**
 * Generate project hash from cwd
 */
function getProjectHash() {
  const cwd = process.cwd();
  return crypto.createHash('sha256').update(cwd).digest('hex').slice(0, 12);
}

/**
 * Get project-specific state path
 */
function getStatePath() {
  const hash = getProjectHash();
  return path.join(RALPH_DIR, `state_${hash}.json`);
}

/**
 * Get project-specific progress path
 */
function getProgressPath() {
  const hash = getProjectHash();
  return path.join(RALPH_DIR, `progress_${hash}.md`);
}

/**
 * Get plugin state file path (in project dir)
 */
function getPluginStatePath() {
  return path.join(process.cwd(), PLUGIN_STATE_FILENAME);
}

/**
 * Parse plugin state file (YAML frontmatter in markdown)
 */
function parsePluginState() {
  const pluginPath = getPluginStatePath();
  if (!fs.existsSync(pluginPath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(pluginPath, 'utf8');
    if (!content.startsWith('---')) {
      return null;
    }

    const parts = content.split('---');
    if (parts.length < 3) {
      return null;
    }

    const frontmatter = parts[1].trim();
    const promptText = parts.slice(2).join('---').trim();

    const state = { source: 'plugin' };

    // Parse YAML manually
    for (const line of frontmatter.split('\n')) {
      if (line.includes(':')) {
        const [key, ...valueParts] = line.split(':');
        let value = valueParts.join(':').trim().replace(/^["']|["']$/g, '');

        // Type conversion
        if (value === 'true') value = true;
        else if (value === 'false') value = false;
        else if (value === 'null') value = null;
        else if (/^\d+$/.test(value)) value = parseInt(value, 10);

        state[key.trim()] = value;
      }
    }

    state.original_prompt = promptText;
    state.active = state.active === true;

    if (state.active) {
      log(`Loaded state from plugin file: iteration=${state.iteration || 0}`);
      return state;
    }
  } catch (err) {
    log(`Failed to parse plugin state file: ${err.message}`);
  }

  return null;
}

/**
 * Calculate state checksum for validation
 */
function calculateChecksum(state) {
  const stateCopy = { ...state };
  delete stateCopy._checksum;
  const stateStr = JSON.stringify(stateCopy, Object.keys(stateCopy).sort());
  return crypto.createHash('sha256').update(stateStr).digest('hex').slice(0, 16);
}

/**
 * Get Ralph state (checks plugin file first, then JSON state)
 */
function getRalphState() {
  // Check plugin state file first
  const pluginState = parsePluginState();
  if (pluginState) {
    return pluginState;
  }

  // Fallback to our JSON state
  const statePath = getStatePath();
  if (!fs.existsSync(statePath)) {
    return null;
  }

  try {
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    state.source = 'auto-ralph';

    // Validate checksum if present
    const storedChecksum = state._checksum;
    if (storedChecksum) {
      const calculated = calculateChecksum(state);
      if (storedChecksum !== calculated) {
        log(`State checksum mismatch: stored=${storedChecksum}, calc=${calculated}`);
      }
    }

    if (state.active) {
      return state;
    }
  } catch (err) {
    log(`State file read error: ${err.message}`);
  }

  return null;
}

/**
 * Update Ralph state
 */
function updateRalphState(updates) {
  const statePath = getStatePath();
  ensureDir(RALPH_DIR);

  let state = getRalphState() || {};
  state = { ...state, ...updates };
  state.last_activity = new Date().toISOString();
  state._checksum = calculateChecksum(state);

  try {
    fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
    log(`State updated: iteration=${state.iteration || 0}`);
  } catch (err) {
    log(`Failed to write state: ${err.message}`);
  }

  return state;
}

/**
 * Deactivate Ralph mode
 */
function deactivateRalph(reason) {
  const state = getRalphState();
  if (!state) return;

  const source = state.source || 'auto-ralph';

  if (source === 'plugin') {
    // Delete plugin state file
    try {
      const pluginPath = getPluginStatePath();
      if (fs.existsSync(pluginPath)) {
        fs.unlinkSync(pluginPath);
        log(`Plugin state file removed: ${reason}`);
      }
    } catch (err) {
      log(`Failed to remove plugin state file: ${err.message}`);
    }
  } else {
    // Update our JSON state
    const statePath = getStatePath();
    const newState = {
      ...state,
      active: false,
      exit_reason: reason,
      ended_at: new Date().toISOString()
    };
    newState._checksum = calculateChecksum(newState);

    try {
      fs.writeFileSync(statePath, JSON.stringify(newState, null, 2));
      log(`Ralph deactivated: ${reason}`);
    } catch (err) {
      log(`Failed to deactivate state: ${err.message}`);
    }
  }

  // Log final state
  logIteration({
    type: 'ralph_exit',
    reason,
    source,
    iterations: state.iteration || 0
  });
}

/**
 * Log iteration to metrics
 */
function logIteration(data) {
  ensureDir(METRICS_DIR);

  const entry = {
    timestamp: new Date().toISOString(),
    ...data
  };

  try {
    fs.appendFileSync(RALPH_LOG, JSON.stringify(entry) + '\n');
  } catch (err) {
    log(`Failed to write iteration log: ${err.message}`);
  }
}

/**
 * Update progress file
 */
function updateProgress(iteration, summary) {
  const progressPath = getProgressPath();
  ensureDir(RALPH_DIR);

  const timestamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
  const entry = `\n## Iteration ${iteration} (${timestamp})\n${summary}\n`;

  try {
    fs.appendFileSync(progressPath, entry);
  } catch (err) {
    log(`Failed to update progress: ${err.message}`);
  }
}

/**
 * Run a command and return result
 */
function runCommand(cmd, args = [], timeout = 60000) {
  try {
    const result = spawnSync(cmd, args, {
      encoding: 'utf8',
      timeout,
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: process.cwd()
    });
    return {
      success: result.status === 0,
      output: (result.stdout || '') + (result.stderr || '')
    };
  } catch (err) {
    return { success: false, output: err.message };
  }
}

/**
 * Check if tests pass
 */
function checkTestsPass() {
  // Try pytest first
  let result = runCommand('pytest', ['tests/', '-x', '--tb=no', '-q'], 120000);
  if (result.success) {
    return { passed: true, message: 'All tests pass' };
  }

  // Try npm test
  result = runCommand('npm', ['test', '--', '--passWithNoTests'], 120000);
  if (result.success) {
    return { passed: true, message: 'npm tests pass' };
  }

  return { passed: false, message: `Tests failed: ${result.output.slice(-200)}` };
}

/**
 * Check if lint passes
 */
function checkLintPass() {
  // Try ruff
  let result = runCommand('ruff', ['check', '.'], 60000);
  if (result.success) {
    return { passed: true, message: 'No lint errors' };
  }

  // Try eslint
  result = runCommand('npx', ['eslint', '.', '--quiet'], 60000);
  if (result.success) {
    return { passed: true, message: 'eslint passes' };
  }

  const errorCount = (result.output.match(/error/gi) || []).length;
  return { passed: false, message: `Lint errors: ${errorCount}` };
}

/**
 * Run CI validation
 */
function runCiValidation() {
  const testsResult = checkTestsPass();
  const lintResult = checkLintPass();

  const details = {
    tests: testsResult,
    lint: lintResult
  };

  if (testsResult.passed && lintResult.passed) {
    return { passed: true, message: 'CI validation passed', details };
  }

  const failures = [];
  if (!testsResult.passed) failures.push(`Tests: ${testsResult.message}`);
  if (!lintResult.passed) failures.push(`Lint: ${lintResult.message}`);

  return { passed: false, message: `CI failed: ${failures.join('; ')}`, details };
}

/**
 * Check exit criteria from transcript
 */
function checkExitCriteria(transcript) {
  const transcriptLower = transcript.toLowerCase();

  for (const pattern of EXIT_PATTERNS) {
    if (transcriptLower.includes(pattern)) {
      // Verify with actual checks
      const testsResult = checkTestsPass();
      const lintResult = checkLintPass();

      if (testsResult.passed && lintResult.passed) {
        return { shouldExit: true, message: `Exit criteria met: ${testsResult.message}, ${lintResult.message}` };
      }
    }
  }

  return { shouldExit: false, message: 'Exit criteria not met' };
}

/**
 * Check token budget
 */
function checkTokenBudget(state) {
  const iteration = state.iteration || 0;
  const estimatedCost = iteration * DEFAULT_CONFIG.estimated_cost_per_iteration;

  if (estimatedCost >= DEFAULT_CONFIG.max_budget_usd) {
    return {
      exceeded: true,
      message: `Budget limit $${DEFAULT_CONFIG.max_budget_usd.toFixed(2)} reached (estimated $${estimatedCost.toFixed(2)})`,
      cost: estimatedCost
    };
  }

  const remaining = DEFAULT_CONFIG.max_budget_usd - estimatedCost;
  return {
    exceeded: false,
    message: `Budget OK: $${estimatedCost.toFixed(2)} / $${DEFAULT_CONFIG.max_budget_usd.toFixed(2)} ($${remaining.toFixed(2)} remaining)`,
    cost: estimatedCost
  };
}

/**
 * Check rate limit
 */
function checkRateLimit() {
  if (!fs.existsSync(RALPH_LOG)) {
    return { limited: false, message: 'Rate limit OK' };
  }

  try {
    const now = Date.now();
    const cutoff = now - 3600000; // 1 hour
    let iterationsInWindow = 0;
    let lastIterationTime = null;

    const lines = fs.readFileSync(RALPH_LOG, 'utf8').split('\n').filter(Boolean);
    for (const line of lines) {
      try {
        const entry = JSON.parse(line);
        const ts = new Date(entry.timestamp).getTime();
        if (ts > cutoff) {
          iterationsInWindow++;
          if (!lastIterationTime || ts > lastIterationTime) {
            lastIterationTime = ts;
          }
        }
      } catch (e) {}
    }

    if (iterationsInWindow >= DEFAULT_CONFIG.max_iterations_per_hour) {
      return {
        limited: true,
        message: `Rate limit: ${iterationsInWindow} iterations in last hour (max ${DEFAULT_CONFIG.max_iterations_per_hour})`
      };
    }

    if (lastIterationTime) {
      const elapsed = (now - lastIterationTime) / 1000;
      if (elapsed < DEFAULT_CONFIG.min_iteration_interval_secs) {
        return {
          limited: true,
          message: `Rate limit: ${elapsed.toFixed(0)}s since last iteration (min ${DEFAULT_CONFIG.min_iteration_interval_secs}s)`
        };
      }
    }
  } catch (err) {
    log(`Rate limit check failed: ${err.message}`);
  }

  return { limited: false, message: 'Rate limit OK' };
}

/**
 * Check circuit breaker
 */
function checkCircuitBreaker(state, transcript) {
  const iteration = state.iteration || 0;

  // Rate limit check
  const rateResult = checkRateLimit();
  if (rateResult.limited) {
    return { tripped: true, message: rateResult.message };
  }

  // Token budget check
  const budgetResult = checkTokenBudget(state);
  if (budgetResult.exceeded) {
    return { tripped: true, message: budgetResult.message };
  }

  // Max iterations
  if (iteration >= DEFAULT_CONFIG.max_iterations) {
    return { tripped: true, message: `Max iterations reached (${DEFAULT_CONFIG.max_iterations})` };
  }

  // Consecutive errors
  const transcriptLower = transcript.toLowerCase();
  const hasError = ERROR_PATTERNS.some(p => transcriptLower.includes(p));

  if (hasError) {
    const consecutiveErrors = (state.consecutive_errors || 0) + 1;
    if (consecutiveErrors >= DEFAULT_CONFIG.max_consecutive_errors) {
      return { tripped: true, message: `Too many consecutive errors (${consecutiveErrors})` };
    }
    updateRalphState({ consecutive_errors: consecutiveErrors });
  } else {
    updateRalphState({ consecutive_errors: 0 });
  }

  // No progress detection
  const lastSummary = state.last_summary || '';
  const currentSummary = transcript.slice(-500);

  if (currentSummary === lastSummary && lastSummary.length > 0) {
    const noProgress = (state.consecutive_no_progress || 0) + 1;
    if (noProgress >= DEFAULT_CONFIG.max_no_progress) {
      return { tripped: true, message: `No progress detected (${noProgress} iterations)` };
    }
    updateRalphState({ consecutive_no_progress: noProgress });
  } else {
    updateRalphState({
      consecutive_no_progress: 0,
      last_summary: currentSummary
    });
  }

  return { tripped: false, message: 'Circuit breaker OK' };
}

/**
 * Main hook function
 */
async function main() {
  // Read input from stdin
  let input = '';

  if (!process.stdin.isTTY) {
    const chunks = [];
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    input = Buffer.concat(chunks).toString('utf8');
  }

  let hookInput = {};
  try {
    hookInput = input ? JSON.parse(input) : {};
  } catch (err) {
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Get Ralph state
  const state = getRalphState();

  if (!state) {
    // Ralph not active, allow normal exit
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Get transcript summary from stop reason
  const stopReason = hookInput.stopReason || '';
  const transcript = hookInput.transcript || '';

  // Update iteration count
  const iteration = (state.iteration || 0) + 1;
  updateRalphState({ iteration });

  // Check budget status
  const budgetResult = checkTokenBudget(state);

  // Check circuit breaker
  const circuitResult = checkCircuitBreaker(state, transcript);

  // Log iteration
  logIteration({
    type: 'iteration',
    iteration,
    stop_reason: stopReason.slice(0, 100),
    estimated_cost_usd: budgetResult.cost,
    circuit_breaker_tripped: circuitResult.tripped
  });

  // Check exit criteria
  const exitResult = checkExitCriteria(transcript);
  if (exitResult.shouldExit) {
    deactivateRalph(exitResult.message);
    updateProgress(iteration, `Completed: ${exitResult.message}`);

    const output = {
      decision: 'approve',
      stopReason: `Ralph Loop Complete (iteration ${iteration}): ${exitResult.message}`
    };
    console.log(JSON.stringify(output));
    process.exit(0);
  }

  // Handle circuit breaker
  if (circuitResult.tripped) {
    deactivateRalph(circuitResult.message);
    updateProgress(iteration, `Circuit Breaker: ${circuitResult.message}`);

    const output = {
      decision: 'approve',
      stopReason: `Ralph Loop Stopped (circuit breaker): ${circuitResult.message}`
    };
    console.log(JSON.stringify(output));
    process.exit(0);
  }

  // Run CI validation
  const ciResult = runCiValidation();

  if (!ciResult.passed) {
    const ciFailures = (state.consecutive_ci_failures || 0) + 1;
    updateRalphState({ consecutive_ci_failures: ciFailures });

    logIteration({
      type: 'ci_failure',
      iteration,
      details: ciResult.details
    });

    if (ciFailures >= DEFAULT_CONFIG.max_ci_failures) {
      deactivateRalph(`CI failed ${ciFailures} times consecutively`);
      updateProgress(iteration, `CI Failure Circuit Breaker: ${ciResult.message}`);

      const output = {
        decision: 'approve',
        stopReason: `Ralph Loop Stopped (CI failures): ${ciResult.message}`
      };
      console.log(JSON.stringify(output));
      process.exit(0);
    }

    updateProgress(iteration, `CI Failed (${ciFailures}/${DEFAULT_CONFIG.max_ci_failures}): ${ciResult.message}`);
  } else {
    updateRalphState({ consecutive_ci_failures: 0 });
  }

  // Continue loop - re-inject original prompt
  const originalPrompt = state.original_prompt || '';

  updateProgress(iteration, `Iteration ${iteration} - continuing...`);

  // Build CI status
  const ciStatus = ciResult.passed
    ? 'CI OK'
    : `CI FAILED (${state.consecutive_ci_failures || 1}/${DEFAULT_CONFIG.max_ci_failures}) - Fix first!\n${ciResult.message}`;

  // Build continuation message
  const continuationPrompt = `## Ralph Loop [${iteration}/${DEFAULT_CONFIG.max_iterations}]

${ciStatus}

**Task:** ${originalPrompt}

Continue until CI passes or state "DONE".
`;

  // Stop hook output format
  const ciStatusShort = ciResult.passed ? 'OK' : 'FAIL';
  const output = {
    decision: 'block',
    reason: continuationPrompt,
    systemMessage: `Ralph [${iteration}/${DEFAULT_CONFIG.max_iterations}] CI: ${ciStatusShort}`
  };

  console.log(JSON.stringify(output));
  process.exit(0);
}

// Export for testing
module.exports = {
  getProjectHash,
  getStatePath,
  getProgressPath,
  getPluginStatePath,
  parsePluginState,
  calculateChecksum,
  getRalphState,
  updateRalphState,
  deactivateRalph,
  logIteration,
  updateProgress,
  runCommand,
  checkTestsPass,
  checkLintPass,
  runCiValidation,
  checkExitCriteria,
  checkTokenBudget,
  checkRateLimit,
  checkCircuitBreaker,
  DEFAULT_CONFIG,
  EXIT_PATTERNS,
  ERROR_PATTERNS,
  RALPH_DIR,
  RALPH_LOG
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
