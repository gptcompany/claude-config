#!/usr/bin/env node
/**
 * Session Insights Writer (Stop hook - runs LAST)
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/ux/session_insights_writer.py
 *
 * Aggregates data from multiple sources to produce unified SSOT:
 * - context-preservation -> context_stats.json
 * - session-analyzer -> last_session_stats.json
 * - session-summary -> last_session_tips.json
 *
 * Produces: ~/.claude/metrics/session_insights.json
 *
 * This SSOT is then read by:
 * - session-start-tracker.js on next session start
 * - tips-injector.js for tip injection
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HOME_DIR = os.homedir();
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const CONTEXT_STATS_FILE = path.join(METRICS_DIR, 'context_stats.json');
const TIPS_FILE = path.join(METRICS_DIR, 'last_session_tips.json');
const STATS_FILE = path.join(METRICS_DIR, 'last_session_stats.json');
const INSIGHTS_FILE = path.join(METRICS_DIR, 'session_insights.json');

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Load JSON file safely, return null on error
 */
function loadJsonSafe(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf8'));
    }
  } catch (err) {
    // Ignore errors
  }
  return null;
}

/**
 * Safe delete file
 */
function unlinkSafe(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }
  } catch (err) {
    // Ignore errors
  }
}

/**
 * Build session insights SSOT from multiple sources
 */
function buildInsights(sessionId) {
  const insights = {
    $schema: 'session_insights_v1',
    session_id: sessionId,
    ended_at: new Date().toISOString()
  };

  // 1. Read context stats (from context-preservation.py / pre-compact.js)
  const contextData = loadJsonSafe(CONTEXT_STATS_FILE);
  if (contextData) {
    insights.context = {
      tokens_used: contextData.tokens_used || 0,
      percentage: contextData.percentage || 0,
      status: contextData.status || 'normal'
    };

    // Add delegation info if critical
    if (contextData.suggested_agents && contextData.suggested_agents.length > 0) {
      insights.delegation = {
        recommended: true,
        agents: contextData.suggested_agents
      };
    }

    // Cleanup temp file (consumed)
    unlinkSafe(CONTEXT_STATS_FILE);
  }

  // 2. Read tips (from session-summary.py / tips-engine.js)
  const tipsData = loadJsonSafe(TIPS_FILE);
  if (tipsData) {
    insights.tips = tipsData.tips || [];
    insights.analysis = tipsData.analysis || {};

    if (tipsData.summary) {
      insights.summary = {
        duration_min: tipsData.summary.duration_min || 0,
        tool_calls: tipsData.summary.tool_calls || 0,
        errors: tipsData.summary.errors || 0
      };
    }
  }

  // 3. Read git stats (from session_analyzer.py / session-analyzer.js)
  const statsData = loadJsonSafe(STATS_FILE);
  if (statsData) {
    if (statsData.git) {
      insights.git = {
        uncommitted: statsData.git.has_changes || false,
        lines_added: statsData.git.lines_added || 0,
        lines_removed: statsData.git.lines_deleted || 0,
        files: {
          code: statsData.git.code_files || 0,
          test: statsData.git.test_files || 0,
          config: statsData.git.config_files || 0
        }
      };
    }
    insights.commits = statsData.commits || 0;
  }

  return insights;
}

/**
 * Write insights to SSOT file
 */
function writeInsights(insights) {
  ensureDir(METRICS_DIR);
  fs.writeFileSync(INSIGHTS_FILE, JSON.stringify(insights, null, 2));
}

/**
 * Log to stderr
 */
function log(message) {
  console.error(`[session-insights] ${message}`);
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
    // Empty input is fine for stop hook
    hookInput = {};
  }

  try {
    // Get session ID from input or generate one
    const sessionId = hookInput.session_id || `session_${Date.now()}`;

    // Build and write insights
    const insights = buildInsights(sessionId);
    writeInsights(insights);

    // Log success (optional, for debugging)
    if (process.argv.includes('--debug')) {
      log(`Session insights written for ${sessionId}`);
      log(`  Tips: ${(insights.tips || []).length}`);
      log(`  Context: ${JSON.stringify(insights.context || {})}`);
      log(`  Git: ${JSON.stringify(insights.git || {})}`);
    }

    // Stop hooks don't need to return anything special
    console.log(JSON.stringify({}));
    process.exit(0);
  } catch (err) {
    // Fail silently - don't block on hook errors
    if (process.argv.includes('--debug')) {
      log(`Error: ${err.message}`);
    }
    console.log(JSON.stringify({}));
    process.exit(0);
  }
}

// Export for testing
module.exports = {
  loadJsonSafe,
  unlinkSafe,
  buildInsights,
  writeInsights,
  ensureDir,
  METRICS_DIR,
  CONTEXT_STATS_FILE,
  TIPS_FILE,
  STATS_FILE,
  INSIGHTS_FILE
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
