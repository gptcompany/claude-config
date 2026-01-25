/**
 * Eval Storage Library - Pass@k Metrics Tracking
 *
 * Tracks test run results across sessions, calculating pass@k metrics
 * to analyze first-attempt vs multi-attempt success rates.
 *
 * Storage: Local JSON + async QuestDB export
 * Location: ~/.claude/evals/results.json
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

// Import metrics library for QuestDB export
let exportToQuestDB;
try {
  const metrics = require("../../lib/metrics");
  exportToQuestDB = metrics.exportToQuestDB;
} catch {
  // Graceful fallback if metrics library not available
  exportToQuestDB = async () => false;
}

const EVAL_DIR = path.join(os.homedir(), ".claude", "evals");
const RESULTS_FILE = path.join(EVAL_DIR, "results.json");

/**
 * Ensure eval directory exists
 */
function ensureDir() {
  if (!fs.existsSync(EVAL_DIR)) {
    fs.mkdirSync(EVAL_DIR, { recursive: true });
  }
}

/**
 * Load results from storage
 * @returns {object} Results object with runs and summary
 */
function loadResults() {
  ensureDir();
  try {
    const content = fs.readFileSync(RESULTS_FILE, "utf8");
    return JSON.parse(content);
  } catch {
    return { runs: [], summary: {} };
  }
}

/**
 * Save results to storage
 * @param {object} results - Results object to save
 */
function saveResults(results) {
  ensureDir();
  fs.writeFileSync(RESULTS_FILE, JSON.stringify(results, null, 2));
}

/**
 * Update summary statistics with pass@k calculations
 * @param {object} results - Results object to update
 */
function updateSummary(results) {
  // Use last 100 runs for summary
  const recentRuns = results.runs.slice(-100);

  // Group runs by attempt number
  const byAttempt = {};
  recentRuns.forEach((run) => {
    const k = run.attempt || 1;
    if (!byAttempt[k]) {
      byAttempt[k] = { passed: 0, total: 0 };
    }
    byAttempt[k].total++;
    if (run.passed) {
      byAttempt[k].passed++;
    }
  });

  results.summary = {
    totalRuns: recentRuns.length,
    passAt: {},
    lastUpdated: new Date().toISOString(),
  };

  // Calculate pass@k percentages
  Object.keys(byAttempt)
    .sort((a, b) => parseInt(a) - parseInt(b))
    .forEach((k) => {
      const { passed, total } = byAttempt[k];
      const rate = total > 0 ? ((passed / total) * 100).toFixed(1) : "0.0";
      results.summary.passAt[`pass@${k}`] = `${rate}%`;
    });

  // Calculate cumulative pass rates
  let cumulativePassed = 0;
  let cumulativeTotal = 0;
  Object.keys(byAttempt)
    .sort((a, b) => parseInt(a) - parseInt(b))
    .forEach((k) => {
      cumulativePassed += byAttempt[k].passed;
      cumulativeTotal += byAttempt[k].total;
    });

  if (cumulativeTotal > 0) {
    results.summary.overallPassRate = `${((cumulativePassed / cumulativeTotal) * 100).toFixed(1)}%`;
  }
}

/**
 * Record a test run
 * @param {object} run - Run data
 * @param {string} run.project - Project name
 * @param {string} run.suite - Test suite name
 * @param {number} run.attempt - Attempt number (1, 2, 3, etc.)
 * @param {boolean} run.passed - Whether the run passed
 * @param {number} run.total - Total number of tests
 * @param {number} run.testsPassed - Number of tests that passed
 * @param {number} run.testsFailed - Number of tests that failed
 * @param {number} run.duration - Duration in milliseconds
 * @param {string} run.command - Test command used
 * @returns {object} Enriched run with ID and timestamp
 */
function recordRun(run) {
  const results = loadResults();

  // Enrich run with metadata
  const enrichedRun = {
    ...run,
    id: `run-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`,
    timestamp: new Date().toISOString(),
    sessionId: process.env.CLAUDE_SESSION_ID || "local",
  };

  results.runs.push(enrichedRun);

  // Update summary statistics
  updateSummary(results);

  // Save locally
  saveResults(results);

  // Export to QuestDB asynchronously (fire-and-forget)
  exportToQuestDB(
    "claude_eval_runs",
    {
      passed: run.passed ? 1 : 0,
      total: run.total || 0,
      tests_passed: run.testsPassed || 0,
      tests_failed: run.testsFailed || 0,
      attempt: run.attempt || 1,
      duration_ms: run.duration || 0,
    },
    {
      project: run.project || "unknown",
      test_suite: run.suite || "default",
    },
  ).catch(() => {
    // Ignore QuestDB errors - local storage is primary
  });

  return enrichedRun;
}

/**
 * Get summary statistics
 * @returns {object} Summary with pass@k rates
 */
function getSummary() {
  const results = loadResults();
  return results.summary || { totalRuns: 0, passAt: {}, lastUpdated: null };
}

/**
 * Get recent runs
 * @param {number} count - Number of runs to return (default 10)
 * @returns {object[]} Array of recent runs
 */
function getRecentRuns(count = 10) {
  const results = loadResults();
  return results.runs.slice(-count);
}

/**
 * Get runs filtered by project
 * @param {string} project - Project name to filter by
 * @param {number} limit - Maximum runs to return
 * @returns {object[]} Filtered runs
 */
function getRunsByProject(project, limit = 50) {
  const results = loadResults();
  return results.runs.filter((run) => run.project === project).slice(-limit);
}

/**
 * Get pass@k summary for a specific project
 * @param {string} project - Project name
 * @returns {object} Project-specific summary
 */
function getProjectSummary(project) {
  const projectRuns = getRunsByProject(project, 100);

  if (projectRuns.length === 0) {
    return { totalRuns: 0, passAt: {}, lastUpdated: null };
  }

  const byAttempt = {};
  projectRuns.forEach((run) => {
    const k = run.attempt || 1;
    if (!byAttempt[k]) {
      byAttempt[k] = { passed: 0, total: 0 };
    }
    byAttempt[k].total++;
    if (run.passed) {
      byAttempt[k].passed++;
    }
  });

  const summary = {
    project,
    totalRuns: projectRuns.length,
    passAt: {},
    lastUpdated: projectRuns[projectRuns.length - 1]?.timestamp,
  };

  Object.keys(byAttempt)
    .sort((a, b) => parseInt(a) - parseInt(b))
    .forEach((k) => {
      const { passed, total } = byAttempt[k];
      const rate = total > 0 ? ((passed / total) * 100).toFixed(1) : "0.0";
      summary.passAt[`pass@${k}`] = `${rate}%`;
    });

  return summary;
}

/**
 * Clear all results (for testing)
 * @returns {boolean} Success status
 */
function clearResults() {
  try {
    if (fs.existsSync(RESULTS_FILE)) {
      fs.unlinkSync(RESULTS_FILE);
    }
    return true;
  } catch {
    return false;
  }
}

module.exports = {
  recordRun,
  getSummary,
  getRecentRuns,
  getRunsByProject,
  getProjectSummary,
  loadResults,
  clearResults,
  // Exported for testing
  EVAL_DIR,
  RESULTS_FILE,
  ensureDir,
  saveResults,
  updateSummary,
};
