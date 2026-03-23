#!/usr/bin/env node
/**
 * Quality Score Tracker Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/metrics/quality-score-tracker.py
 *
 * PostToolUse hook that analyzes tool outputs (pytest, ruff, mypy, etc.)
 * and calculates a weighted quality score per commit/session.
 *
 * Weight Distribution:
 * - code: 25% (ruff + mypy + bandit)
 * - test: 30% (coverage + pass rate)
 * - data: 25% (pandera/schema compliance)
 * - framework: 20% (speckit/gsd verification)
 *
 * Writes to QuestDB: claude_quality_scores table
 * Returns systemMessage if score drops significantly
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const QUALITY_DIR = path.join(METRICS_DIR, 'quality');
const QUALITY_LOG = path.join(QUALITY_DIR, 'scores.jsonl');
const LATEST_SCORE_FILE = path.join(QUALITY_DIR, 'latest_score.json');

// Score weights
const WEIGHTS = {
  code: 0.25,
  test: 0.30,
  data: 0.25,
  framework: 0.20
};

// Alert threshold
const ALERT_THRESHOLD = 70;

// Try to load metrics library for QuestDB export
let metricsLib = null;
try {
  metricsLib = require('../../lib/metrics.js');
} catch (err) {
  // Fallback: library not available
}

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Get ISO timestamp
 */
function getTimestamp() {
  return new Date().toISOString();
}

/**
 * Detect project from working directory
 */
function detectProject() {
  const cwd = process.cwd();

  // Known project paths
  const projectMap = {
    '/media/sam/1TB/nautilus_dev': 'nautilus',
    '/media/sam/1TB/UTXOracle': 'utxoracle',
    '/media/sam/1TB/claude-flow': 'claudeflow',
    '/media/sam/1TB/LiquidationHeatmap': 'liquidation',
    '/media/sam/1TB/N8N_dev': 'n8n'
  };

  for (const [pathPrefix, name] of Object.entries(projectMap)) {
    if (cwd.startsWith(pathPrefix)) {
      return name;
    }
  }

  return path.basename(cwd);
}

/**
 * Get git commit and branch info
 */
function getGitInfo() {
  try {
    const commit = execSync('git rev-parse --short HEAD', {
      encoding: 'utf8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim();

    const branch = execSync('git rev-parse --abbrev-ref HEAD', {
      encoding: 'utf8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim();

    return { commit: commit || 'unknown', branch: branch || 'unknown' };
  } catch (err) {
    return { commit: 'unknown', branch: 'unknown' };
  }
}

/**
 * Parse pytest output for pass rate and coverage
 */
function parsePytestOutput(output) {
  const result = { passRate: 100, coverage: 0, passed: 0, failed: 0 };

  // Parse test results: "5 passed, 2 failed"
  let match = output.match(/(\d+)\s+passed/);
  if (match) {
    result.passed = parseInt(match[1], 10);
  }

  match = output.match(/(\d+)\s+failed/);
  if (match) {
    result.failed = parseInt(match[1], 10);
  }

  const total = result.passed + result.failed;
  if (total > 0) {
    result.passRate = (result.passed / total) * 100;
  }

  // Parse coverage: "TOTAL ... 85%"
  match = output.match(/TOTAL\s+\d+\s+\d+\s+(\d+)%/);
  if (match) {
    result.coverage = parseInt(match[1], 10);
  }

  // Alternative: "Coverage: 85%"
  match = output.match(/Coverage[:\s]+(\d+)%/i);
  if (match) {
    result.coverage = parseInt(match[1], 10);
  }

  return result;
}

/**
 * Parse ruff output for linting score
 */
function parseRuffOutput(output) {
  const result = { errors: 0, warnings: 0, score: 100 };

  // Count errors/warnings
  const errorMatches = output.match(/^.+:\d+:\d+: [EF]\d+/gm) || [];
  const warningMatches = output.match(/^.+:\d+:\d+: [WC]\d+/gm) || [];

  result.errors = errorMatches.length;
  result.warnings = warningMatches.length;

  // Score: 100 - (errors * 5 + warnings * 1)
  result.score = Math.max(0, 100 - (result.errors * 5 + result.warnings * 1));

  // Alternative: "Found X errors"
  const foundMatch = output.match(/Found (\d+) errors?/);
  if (foundMatch) {
    result.errors = parseInt(foundMatch[1], 10);
    result.score = Math.max(0, 100 - result.errors * 5);
  }

  // If "All checks passed" or similar
  if (output.includes('All checks passed') || output.toLowerCase().includes('no issues found')) {
    result.score = 100;
  }

  return result;
}

/**
 * Parse mypy output for type checking score
 */
function parseMypyOutput(output) {
  const result = { errors: 0, score: 100 };

  // "Found X errors"
  let match = output.match(/Found (\d+) errors?/);
  if (match) {
    result.errors = parseInt(match[1], 10);
    result.score = Math.max(0, 100 - result.errors * 3);
  }

  // Count error lines
  const errorLines = output.match(/^.+:\d+: error:/gm) || [];
  if (errorLines.length > 0 && !match) {
    result.errors = errorLines.length;
    result.score = Math.max(0, 100 - result.errors * 3);
  }

  // Success message
  if (output.includes('Success') || output.toLowerCase().includes('no issues found')) {
    result.score = 100;
  }

  return result;
}

/**
 * Calculate quality scores from tool output
 */
function calculateScores(toolOutput, command) {
  const scores = {
    code: null,
    test: null,
    data: null,
    framework: null
  };

  const commandLower = command.toLowerCase();

  // Test score (pytest)
  if (commandLower.includes('pytest')) {
    const pytestData = parsePytestOutput(toolOutput);
    const passRate = pytestData.passRate || 100;
    const coverage = pytestData.coverage;
    if (coverage > 0) {
      // Both pass rate and coverage available
      scores.test = (passRate * 0.6) + (coverage * 0.4);
    } else {
      // No coverage data (pytest without --cov): score on pass rate only
      scores.test = passRate;
    }
  }

  // Code score (ruff)
  if (commandLower.includes('ruff')) {
    const ruffData = parseRuffOutput(toolOutput);
    scores.code = ruffData.score;
  }

  // Code score (mypy) - combine with ruff if both present
  if (commandLower.includes('mypy')) {
    const mypyData = parseMypyOutput(toolOutput);
    if (scores.code !== null) {
      scores.code = (scores.code + mypyData.score) / 2;
    } else {
      scores.code = mypyData.score;
    }
  }

  // Data score (pandera)
  if (toolOutput.toLowerCase().includes('pandera') || commandLower.includes('schema')) {
    if (toolOutput.includes('SchemaError') || toolOutput.includes('ValidationError')) {
      scores.data = 50;
    } else {
      scores.data = 100;
    }
  }

  // Framework score (speckit/gsd)
  if (commandLower.includes('speckit') || commandLower.includes('gsd')) {
    if (toolOutput.toLowerCase().includes('error') || toolOutput.toLowerCase().includes('failed')) {
      scores.framework = 70;
    } else {
      scores.framework = 100;
    }
  }

  return scores;
}

/**
 * Log quality score to file
 */
function logQualityScore(scoreData) {
  ensureDir(QUALITY_DIR);
  fs.appendFileSync(QUALITY_LOG, JSON.stringify(scoreData) + '\n');
}

/**
 * Save latest score for quick access
 */
function saveLatestScore(scoreData) {
  ensureDir(QUALITY_DIR);
  fs.writeFileSync(LATEST_SCORE_FILE, JSON.stringify(scoreData, null, 2));
}

/**
 * Get latest score
 */
function getLatestScore() {
  try {
    if (fs.existsSync(LATEST_SCORE_FILE)) {
      return JSON.parse(fs.readFileSync(LATEST_SCORE_FILE, 'utf8'));
    }
  } catch (err) {
    // Ignore
  }
  return null;
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

  let inputData = {};
  try {
    inputData = input ? JSON.parse(input) : {};
  } catch (err) {
    console.log(JSON.stringify({ status: 'error', reason: 'invalid JSON' }));
    return;
  }

  const toolName = inputData.tool_name || '';
  const toolOutput = inputData.tool_output || '';
  const toolInput = inputData.tool_input || {};

  // Only process Bash tool outputs
  if (toolName !== 'Bash') {
    console.log(JSON.stringify({ status: 'skipped', reason: 'not Bash tool' }));
    return;
  }

  const command = toolInput.command || '';

  // Check if command is relevant for quality scoring
  const relevantCommands = ['pytest', 'ruff', 'mypy', 'bandit', 'speckit', 'gsd'];
  if (!relevantCommands.some(cmd => command.toLowerCase().includes(cmd))) {
    console.log(JSON.stringify({ status: 'skipped', reason: 'not quality-related command' }));
    return;
  }

  // Calculate scores
  const scores = calculateScores(toolOutput, command);

  // Filter out null values
  const activeScores = Object.fromEntries(
    Object.entries(scores).filter(([k, v]) => v !== null)
  );

  if (Object.keys(activeScores).length === 0) {
    console.log(JSON.stringify({ status: 'skipped', reason: 'no scores calculated' }));
    return;
  }

  // Calculate weighted total
  const totalWeight = Object.keys(activeScores).reduce((sum, k) => sum + WEIGHTS[k], 0);
  const totalScore = totalWeight > 0
    ? Object.entries(activeScores).reduce((sum, [k, v]) => sum + v * WEIGHTS[k], 0) / totalWeight
    : 0;

  // Get project and git info
  const project = detectProject();
  const { commit, branch } = getGitInfo();
  const sessionId = process.env.CLAUDE_SESSION_ID || 'unknown';

  // Determine block/category
  let block = 'general';
  if (command.toLowerCase().includes('pytest')) {
    block = 'test';
  } else if (['ruff', 'mypy', 'bandit'].some(x => command.toLowerCase().includes(x))) {
    block = 'code';
  } else if (command.toLowerCase().includes('speckit') || command.toLowerCase().includes('gsd')) {
    block = 'framework';
  }

  // Build score data
  const scoreData = {
    timestamp: getTimestamp(),
    project,
    block,
    branch,
    commit,
    sessionId,
    totalScore: Math.round(totalScore * 100) / 100,
    scores: Object.fromEntries(
      Object.entries(activeScores).map(([k, v]) => [k, Math.round(v * 100) / 100])
    )
  };

  // Log to file
  logQualityScore(scoreData);
  saveLatestScore(scoreData);

  // Export to QuestDB if available
  let sentToQuestDB = false;
  if (metricsLib) {
    try {
      await metricsLib.exportToQuestDB('claude_quality_scores', {
        score_total: totalScore,
        score_code: scores.code || 0,
        score_test: scores.test || 0,
        score_data: scores.data || 0,
        score_framework: scores.framework || 0,
        commit_hash: commit,
        session_id: sessionId
      }, {
        project,
        block,
        branch
      });
      sentToQuestDB = true;
    } catch (err) {
      // Best effort
    }
  }

  // Prepare output
  const result = {
    status: 'tracked',
    project,
    block,
    totalScore: Math.round(totalScore * 100) / 100,
    scores: Object.fromEntries(
      Object.entries(activeScores).map(([k, v]) => [k, Math.round(v * 100) / 100])
    ),
    sentToQuestDB,
    alertTriggered: totalScore < ALERT_THRESHOLD
  };

  // Add system message if score is low
  if (totalScore < ALERT_THRESHOLD) {
    result.systemMessage = `Quality Score Alert: ${totalScore.toFixed(1)} (threshold: ${ALERT_THRESHOLD}). Check test coverage and linting.`;
  }

  console.log(JSON.stringify(result));
}

// Export for testing
module.exports = {
  parsePytestOutput,
  parseRuffOutput,
  parseMypyOutput,
  calculateScores,
  detectProject,
  getGitInfo,
  getLatestScore,
  WEIGHTS,
  ALERT_THRESHOLD,
  QUALITY_DIR,
  QUALITY_LOG,
  LATEST_SCORE_FILE
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({ status: 'error', reason: err.message }));
  });
}
