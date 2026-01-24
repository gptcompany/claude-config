#!/usr/bin/env node
/**
 * Session Analyzer - Stop Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/intelligence/session_analyzer.py
 *
 * Functionality:
 * - Analyze uncommitted git changes (lines, files, categories)
 * - Parse session metrics (tool calls, errors, error rate)
 * - Get commits made during session
 * - Generate contextual suggestions based on thresholds
 * - Save stats for next session injection
 *
 * Hook: Stop
 * Output: { systemMessage: string }
 */

const path = require('path');
const {
  readFile,
  writeFile,
  ensureDir,
  readStdinJson,
  output
} = require('../../lib/utils');
const {
  getUncommittedChanges,
  getSessionCommits,
  categorizeFile
} = require('../../lib/git-utils');
const {
  loadSessionState,
  getTimestamp,
  METRICS_DIR
} = require('../../lib/metrics');

// Configuration
const SESSION_STATE_FILE = path.join(METRICS_DIR, 'session_state.json');
const LAST_SESSION_STATS_FILE = path.join(METRICS_DIR, 'last_session_stats.json');

// Suggestion Thresholds (based on distribution analysis)
const THRESHOLD_ERROR_RATE = 0.25;       // Error rate: elite <15%, typical 15-25%, concerning >25%
const THRESHOLD_MIN_ERRORS = 5;          // Prevent false positives on small sessions
const THRESHOLD_LINES_CHANGED = 50;      // Lines changed: significant changes warrant review
const THRESHOLD_CONFIG_FILES = 2;        // Config files: multiple config changes need verification
const THRESHOLD_LONG_SESSION = 60;       // Long session: context management needed
const THRESHOLD_MIN_TOOL_CALLS = 5;      // Minimum session size for suggestions

/**
 * Analyze uncommitted changes and categorize files
 * @returns {object} GitChanges object
 */
function analyzeUncommittedChanges() {
  const changes = {
    hasChanges: false,
    linesAdded: 0,
    linesDeleted: 0,
    codeFiles: [],
    testFiles: [],
    configFiles: [],
    otherFiles: []
  };

  const uncommitted = getUncommittedChanges();

  if (!uncommitted || !uncommitted.hasChanges) {
    return changes;
  }

  changes.hasChanges = true;
  changes.linesAdded = uncommitted.linesAdded || 0;
  changes.linesDeleted = uncommitted.linesDeleted || 0;

  // Categorize files
  const allFiles = uncommitted.files || [];

  for (const file of allFiles) {
    const category = categorizeFile(file);

    switch (category) {
      case 'code':
        changes.codeFiles.push(file);
        break;
      case 'test':
        changes.testFiles.push(file);
        break;
      case 'config':
        changes.configFiles.push(file);
        break;
      default:
        changes.otherFiles.push(file);
    }
  }

  return changes;
}

/**
 * Parse session metrics from hook input
 * @param {object} inputData - Hook input data
 * @returns {object} Session metrics
 */
function parseSessionMetrics(inputData) {
  const session = inputData.session || {};

  return {
    toolCalls: session.tool_calls || session.toolCalls || 0,
    errors: session.errors || 0,
    get errorRate() {
      return this.toolCalls > 0 ? this.errors / this.toolCalls : 0;
    }
  };
}

/**
 * Get commits made during this session
 * @returns {object[]} Array of commit objects
 */
function getCommitsDuringSession() {
  const state = loadSessionState();

  if (!state) {
    return [];
  }

  const startCommit = state.startCommit || state.start_commit;

  if (!startCommit) {
    return [];
  }

  const commits = getSessionCommits(startCommit);

  if (!commits) {
    return [];
  }

  // Map to simplified format
  return commits.map(c => ({
    hash: (c.hash || '').substring(0, 8),
    message: c.subject || c.message || ''
  }));
}

/**
 * Generate contextual suggestions based on session state
 * @param {object} changes - Git changes
 * @param {object} metrics - Session metrics
 * @returns {object[]} Array of suggestions
 */
function getSuggestions(changes, metrics) {
  const suggestions = [];

  // Skip if session too short (avoid false positives)
  if (metrics.toolCalls < THRESHOLD_MIN_TOOL_CALLS) {
    return [];
  }

  // Priority 1: High error rate -> checkpoint before continuing
  if (metrics.errorRate > THRESHOLD_ERROR_RATE && metrics.errors >= THRESHOLD_MIN_ERRORS) {
    suggestions.push({
      command: '/undo:checkpoint',
      trigger: 'errors',
      priority: 1
    });
  }

  // Priority 2: Multiple config changes -> verify consistency
  if (changes.configFiles.length >= THRESHOLD_CONFIG_FILES) {
    suggestions.push({
      command: '/health',
      trigger: 'config',
      priority: 2
    });
  }

  // Priority 3: Significant uncommitted changes -> review before continuing
  if (changes.hasChanges && changes.linesAdded >= THRESHOLD_LINES_CHANGED) {
    suggestions.push({
      command: '/review',
      trigger: 'uncommitted',
      priority: 3
    });
  }

  // Priority 4: Long session -> check context if resuming
  if (metrics.toolCalls >= THRESHOLD_LONG_SESSION) {
    suggestions.push({
      command: '/context',
      trigger: 'long',
      priority: 4
    });
  }

  // Sort by priority and limit to top 2
  suggestions.sort((a, b) => a.priority - b.priority);
  return suggestions.slice(0, 2);
}

/**
 * Format suggestions for output
 * @param {object[]} suggestions - Array of suggestions
 * @returns {string} Formatted suggestions
 */
function formatSuggestions(suggestions) {
  if (!suggestions || suggestions.length === 0) {
    return '';
  }

  const commands = suggestions.map(s => s.command);
  return `[suggest: ${commands.join(', ')}]`;
}

/**
 * Format session stats with optional suggestions
 * @param {object} changes - Git changes
 * @param {object} metrics - Session metrics
 * @param {object[]} commits - Session commits
 * @param {object[]} suggestions - Contextual suggestions
 * @returns {string} Formatted stats
 */
function formatSessionStats(changes, metrics, commits, suggestions = null) {
  const parts = [];

  // Git changes - compact format
  if (changes.hasChanges) {
    const gitParts = [`+${changes.linesAdded}/-${changes.linesDeleted}`];

    if (changes.codeFiles.length > 0) {
      gitParts.push(`${changes.codeFiles.length} code`);
    }
    if (changes.testFiles.length > 0) {
      gitParts.push(`${changes.testFiles.length} test`);
    }
    if (changes.configFiles.length > 0) {
      gitParts.push(`${changes.configFiles.length} config`);
    }

    parts.push(`[uncommitted: ${gitParts.join(', ')}]`);
  }

  // Session metrics
  if (metrics.toolCalls > 0) {
    parts.push(`[session: ${metrics.toolCalls} calls, ${metrics.errors} errors]`);
  }

  // Commits this session
  if (commits && commits.length > 0) {
    parts.push(`[commits: ${commits.length}]`);
  }

  // Contextual suggestions
  if (suggestions && suggestions.length > 0) {
    parts.push(formatSuggestions(suggestions));
  }

  return parts.length > 0 ? parts.join(' ') : '';
}

/**
 * Save session stats and suggestions for injection into next session
 * @param {object} changes - Git changes
 * @param {object} metrics - Session metrics
 * @param {object[]} commits - Session commits
 * @param {object[]} suggestions - Contextual suggestions
 */
function saveStatsForNextSession(changes, metrics, commits, suggestions) {
  const stats = {
    timestamp: getTimestamp(),
    git: {
      hasChanges: changes.hasChanges,
      linesAdded: changes.linesAdded,
      linesDeleted: changes.linesDeleted,
      codeFiles: changes.codeFiles.length,
      testFiles: changes.testFiles.length,
      configFiles: changes.configFiles.length
    },
    session: {
      toolCalls: metrics.toolCalls,
      errors: metrics.errors,
      errorRate: Math.round(metrics.errorRate * 100) / 100
    },
    commits: commits.length,
    suggestions: suggestions.map(s => ({
      command: s.command,
      trigger: s.trigger,
      priority: s.priority
    })),
    formatted: formatSessionStats(changes, metrics, commits, suggestions)
  };

  try {
    ensureDir(METRICS_DIR);
    writeFile(LAST_SESSION_STATS_FILE, JSON.stringify(stats, null, 2));
  } catch (err) {
    // Ignore errors
  }
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    // Read input
    const inputData = await readStdinJson();

    // Analyze
    const changes = analyzeUncommittedChanges();
    const metrics = parseSessionMetrics(inputData);
    const commits = getCommitsDuringSession();

    // Generate contextual suggestions
    const suggestions = getSuggestions(changes, metrics);

    // Always save stats for next session (even if minimal)
    saveStatsForNextSession(changes, metrics, commits, suggestions);

    // Skip output if nothing interesting (but stats are saved)
    if (!changes.hasChanges && metrics.toolCalls < THRESHOLD_MIN_TOOL_CALLS) {
      output({});
      process.exit(0);
    }

    // Format stats with suggestions
    const formatted = formatSessionStats(changes, metrics, commits, suggestions);

    if (formatted) {
      output({ systemMessage: formatted });
    } else {
      output({});
    }

    process.exit(0);
  } catch (err) {
    // Graceful failure - don't block
    output({});
    process.exit(0);
  }
}

// Export for testing
module.exports = {
  analyzeUncommittedChanges,
  parseSessionMetrics,
  getCommitsDuringSession,
  getSuggestions,
  formatSuggestions,
  formatSessionStats,
  saveStatsForNextSession,
  THRESHOLD_ERROR_RATE,
  THRESHOLD_MIN_ERRORS,
  THRESHOLD_LINES_CHANGED,
  THRESHOLD_CONFIG_FILES,
  THRESHOLD_LONG_SESSION,
  THRESHOLD_MIN_TOOL_CALLS
};

// Run if executed directly
if (require.main === module) {
  main();
}
