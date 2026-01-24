#!/usr/bin/env node
/**
 * Session Start Tracker - UserPromptSubmit Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/intelligence/session_start_tracker.py
 * Merged with ECC session-start.js package manager detection
 *
 * Functionality:
 * - Detect new session vs continuation (30 min timeout)
 * - Track git state: commit, branch, repo root
 * - Inject previous session insights (from SSOT)
 * - Detect package manager, show prompt if not configured
 * - Track prompt count
 *
 * Hook: UserPromptSubmit
 * Output: { additionalContext: string }
 */

const path = require('path');
const {
  readFile,
  writeFile,
  ensureDir,
  getClaudeDir,
  readStdinJson,
  output
} = require('../../lib/utils');
const {
  getCurrentCommit,
  getCurrentBranch,
  getRepoRoot
} = require('../../lib/git-utils');
const {
  saveSessionState,
  loadSessionState,
  getTimestamp,
  METRICS_DIR
} = require('../../lib/metrics');

// Configuration
const SESSION_STATE_FILE = path.join(METRICS_DIR, 'session_state.json');
const LAST_SESSION_STATS_FILE = path.join(METRICS_DIR, 'last_session_stats.json');
const INSIGHTS_FILE = path.join(METRICS_DIR, 'session_insights.json');
const SESSION_TIMEOUT_MINUTES = 30;
const MAX_STATS_AGE_HOURS = 24;

/**
 * Check if this is a new session (vs continuation)
 * @returns {boolean} True if new session
 */
function isNewSession() {
  const state = loadSessionState();

  if (!state) {
    return true;
  }

  const lastActivity = state.lastActivity || state.last_activity;
  if (!lastActivity) {
    return true;
  }

  try {
    const lastDt = new Date(lastActivity);
    const elapsed = (Date.now() - lastDt.getTime()) / 1000 / 60; // minutes

    // New session if timeout exceeded
    if (elapsed > SESSION_TIMEOUT_MINUTES) {
      return true;
    }

    // Check if same repo
    const currentRepo = getRepoRoot();
    const stateRepo = state.repoRoot || state.repo_root;

    if (currentRepo && stateRepo && currentRepo !== stateRepo) {
      return true;
    }

    return false;
  } catch (err) {
    return true;
  }
}

/**
 * Save or update session state
 * @param {boolean} isNew - Whether this is a new session
 * @returns {object} The session state
 */
function saveState(isNew) {
  ensureDir(METRICS_DIR);

  const now = getTimestamp();
  let state;

  if (isNew) {
    // New session - record starting state
    state = {
      sessionStart: now,
      startCommit: getCurrentCommit(),
      startBranch: getCurrentBranch(),
      repoRoot: getRepoRoot(),
      lastActivity: now,
      promptCount: 1
    };
  } else {
    // Existing session - just update activity
    state = loadSessionState() || {};
    state.lastActivity = now;
    state.promptCount = (state.promptCount || 0) + 1;
  }

  saveSessionState(state);
  return state;
}

/**
 * Load stats from previous session if recent enough
 * @returns {object|null} Previous stats or null
 */
function getPreviousSessionStats() {
  try {
    const content = readFile(LAST_SESSION_STATS_FILE);
    if (!content) return null;

    const stats = JSON.parse(content);
    const timestamp = stats.timestamp;

    if (!timestamp) return null;

    // Check age
    const statsDate = new Date(timestamp);
    const ageHours = (Date.now() - statsDate.getTime()) / 1000 / 3600;

    if (ageHours > MAX_STATS_AGE_HOURS) {
      return null;
    }

    return stats;
  } catch (err) {
    return null;
  }
}

/**
 * Clear previous session stats after injection
 */
function clearPreviousSessionStats() {
  try {
    const fs = require('fs');
    if (fs.existsSync(LAST_SESSION_STATS_FILE)) {
      fs.unlinkSync(LAST_SESSION_STATS_FILE);
    }
  } catch (err) {
    // Ignore errors
  }
}

/**
 * Load SSOT insights from previous session and format compactly
 * @returns {string|null} Formatted insights or null
 */
function getPreviousInsights() {
  try {
    const content = readFile(INSIGHTS_FILE);
    if (!content) return null;

    const data = JSON.parse(content);
    const timestamp = data.ended_at || data.endedAt;

    // Check age
    if (timestamp) {
      const endedDate = new Date(timestamp);
      const ageHours = (Date.now() - endedDate.getTime()) / 1000 / 3600;

      if (ageHours > MAX_STATS_AGE_HOURS) {
        return null;
      }
    }

    // Format compact output
    const parts = [];

    // Context percentage
    const ctx = data.context;
    if (ctx) {
      const pct = ctx.percentage || 0;
      const status = ctx.status || 'normal';

      if (status === 'critical') {
        parts.push(`${pct}% ctx!`);
      } else if (status === 'warning') {
        parts.push(`${pct}% ctx`);
      }
    }

    // Summary stats
    const summary = data.summary;
    if (summary) {
      const calls = summary.tool_calls || summary.toolCalls || 0;
      const errors = summary.errors || 0;

      if (calls) parts.push(`${calls} calls`);
      if (errors) parts.push(`${errors} err`);
    }

    // Git status
    const git = data.git;
    if (git && git.uncommitted) {
      const added = git.lines_added || git.linesAdded || 0;
      const removed = git.lines_removed || git.linesRemoved || 0;
      parts.push(`uncommitted +${added}/-${removed}`);
    }

    // Delegation recommendation
    if (data.delegation && data.delegation.recommended) {
      parts.push('DELEGATE!');
    }

    // High-confidence tips with category breakdown + top command
    const tips = data.tips || [];
    const highConfTips = tips.filter(t => (t.confidence || 0) >= 0.7);

    if (highConfTips.length > 0) {
      // Compact format: category counts + top command suggestion
      const categories = {};
      for (const t of highConfTips) {
        const cat = t.category || 'general';
        categories[cat] = (categories[cat] || 0) + 1;
      }

      const catSummary = Object.entries(categories)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([c, n]) => `${c}:${n}`)
        .join('/');

      const topCmd = highConfTips[0].command || '';

      parts.push(`${highConfTips.length} tips (${catSummary})`);
      if (topCmd) {
        parts.push(`try: ${topCmd}`);
      }
    }

    return parts.length > 0 ? parts.join(', ') : null;
  } catch (err) {
    return null;
  }
}

/**
 * Clear SSOT after injecting (prevent repeated injection)
 */
function clearPreviousInsights() {
  try {
    const fs = require('fs');
    if (fs.existsSync(INSIGHTS_FILE)) {
      fs.unlinkSync(INSIGHTS_FILE);
    }
  } catch (err) {
    // Ignore errors
  }
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    // Read input (required by hook protocol)
    const inputData = await readStdinJson();

    // Check if new session
    const isNew = isNewSession();

    // Save state
    const state = saveState(isNew);

    // Build output
    const contextParts = [];

    // For new sessions, inject previous session insights
    if (isNew) {
      // Try SSOT first
      const insightsSummary = getPreviousInsights();

      if (insightsSummary) {
        contextParts.push(`[prev: ${insightsSummary}]`);
        clearPreviousInsights(); // One-time injection
      } else {
        // Fallback to legacy format
        const prevStats = getPreviousSessionStats();

        if (prevStats && prevStats.formatted) {
          contextParts.push(`[prev session: ${prevStats.formatted}]`);
          clearPreviousSessionStats(); // One-time injection
        }
      }

      // Add git tracking info
      if (state.startCommit) {
        const branch = state.startBranch || 'unknown';
        const shortCommit = state.startCommit.substring(0, 8);
        contextParts.push(`[tracking: ${branch}@${shortCommit}]`);
      }
    }

    // Output
    if (contextParts.length > 0) {
      output({
        additionalContext: contextParts.join(' ')
      });
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
  isNewSession,
  saveState,
  getPreviousSessionStats,
  clearPreviousSessionStats,
  getPreviousInsights,
  clearPreviousInsights,
  SESSION_TIMEOUT_MINUTES,
  MAX_STATS_AGE_HOURS
};

// Run if executed directly
if (require.main === module) {
  main();
}
