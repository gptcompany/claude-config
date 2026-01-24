#!/usr/bin/env node
/**
 * Tips Injector Hook (UserPromptSubmit)
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/ux/tips-auto-inject.py
 *
 * Injects optimization tips from previous session into context.
 * Only triggers once per session (first prompt after session start).
 *
 * Uses tips-engine.js for tip loading and scoring.
 * Reads from SSOT: ~/.claude/metrics/session_insights.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HOME_DIR = os.homedir();
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const SESSION_STATE_FILE = path.join(METRICS_DIR, 'session_state.json');
const TIPS_FILE = path.join(METRICS_DIR, 'last_session_tips.json');
const SSOT_FILE = path.join(METRICS_DIR, 'session_insights.json');
const INJECTED_MARKER = path.join(METRICS_DIR, '.tips_injected');

// Max age for tips to be considered relevant (hours)
const MAX_TIPS_AGE_HOURS = 24;

// Max tips to inject
const MAX_TIPS = 3;

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Get current session ID from session state
 */
function getSessionId() {
  if (!fs.existsSync(SESSION_STATE_FILE)) {
    return '';
  }
  try {
    const data = JSON.parse(fs.readFileSync(SESSION_STATE_FILE, 'utf8'));
    // Try session_id first, fallback to session_start timestamp
    const sessionId = data.session_id;
    if (sessionId) {
      return sessionId;
    }
    // Use session_start as unique identifier
    const sessionStart = data.session_start;
    if (sessionStart) {
      return `session_${sessionStart}`;
    }
    return '';
  } catch (err) {
    return '';
  }
}

/**
 * Check if tips were already injected for this session
 */
function wasAlreadyInjected(sessionId) {
  if (!fs.existsSync(INJECTED_MARKER)) {
    return false;
  }
  try {
    const marker = JSON.parse(fs.readFileSync(INJECTED_MARKER, 'utf8'));
    return marker.session_id === sessionId;
  } catch (err) {
    return false;
  }
}

/**
 * Mark tips as injected for this session
 */
function markInjected(sessionId) {
  try {
    ensureDir(METRICS_DIR);
    const marker = {
      session_id: sessionId,
      timestamp: new Date().toISOString()
    };
    fs.writeFileSync(INJECTED_MARKER, JSON.stringify(marker));
  } catch (err) {
    // Ignore write errors
  }
}

/**
 * Load tips from SSOT or fallback to legacy file
 */
function loadTips() {
  // Try SSOT first
  if (fs.existsSync(SSOT_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(SSOT_FILE, 'utf8'));
      if (data.tips && data.tips.length > 0) {
        return data;
      }
    } catch (err) {
      // Try fallback
    }
  }

  // Fallback to legacy tips file
  if (fs.existsSync(TIPS_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(TIPS_FILE, 'utf8'));
      if (data.tips && data.tips.length > 0) {
        return data;
      }
    } catch (err) {
      // No tips
    }
  }

  return null;
}

/**
 * Check if tips are recent enough to be relevant
 */
function isTipsFresh(tipsData) {
  // Check both timestamp (legacy) and ended_at (SSOT)
  const timestampStr = tipsData.timestamp || tipsData.ended_at;
  if (!timestampStr) {
    return false;
  }

  try {
    const timestamp = new Date(timestampStr);
    const now = new Date();
    const ageMs = now - timestamp;
    const ageHours = ageMs / (1000 * 60 * 60);
    return ageHours < MAX_TIPS_AGE_HOURS;
  } catch (err) {
    return false;
  }
}

/**
 * Format tips for context injection
 * @returns {object} {contextText, userNotification}
 */
function formatTipsForInjection(tipsData) {
  const tips = tipsData.tips || [];
  if (tips.length === 0) {
    return { contextText: '', userNotification: '' };
  }

  const lines = [];
  lines.push('[Previous Session Tips]');

  // Add summary if available
  const summary = tipsData.summary || {};
  if (summary && Object.keys(summary).length > 0) {
    const duration = summary.duration_min || 0;
    const toolCalls = summary.tool_calls || 0;
    const errors = summary.errors || 0;
    lines.push(`Session: ${Math.round(duration)}min, ${toolCalls} calls, ${errors} errors`);
  }

  // Format each tip for context (max MAX_TIPS)
  const displayTips = tips.slice(0, MAX_TIPS);
  for (let i = 0; i < displayTips.length; i++) {
    const tip = displayTips[i];
    const confidence = tip.confidence || 0;
    const message = tip.message || '';
    const command = tip.command || '';

    const confPct = confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence);
    lines.push(`${i + 1}. [${confPct}%] ${message} -> ${command}`);
  }

  const contextText = lines.join(' | ');

  // User notification (shorter)
  const tipCommands = displayTips.map(t => t.command || '').filter(Boolean);
  const userNotification = `[Tips Injected] ${tips.length} suggestions: ${tipCommands.join(', ')}`;

  return { contextText, userNotification };
}

/**
 * Log to stderr (visible to user)
 */
function log(message) {
  console.error(message);
}

/**
 * Debug log (only if --debug flag)
 */
function debugLog(msg) {
  if (process.argv.includes('--debug')) {
    console.error(`[tips-injector] ${msg}`);
  }
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

  try {
    // Parse input (hook protocol)
    const hookInput = input ? JSON.parse(input) : {};
  } catch (err) {
    debugLog('Failed to parse stdin JSON or empty input');
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Get current session ID
  const sessionId = getSessionId();
  debugLog(`Session ID: ${sessionId}`);
  if (!sessionId) {
    // No session yet, skip
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Check if already injected this session
  if (wasAlreadyInjected(sessionId)) {
    debugLog('Tips already injected this session');
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Load tips
  const tipsData = loadTips();
  debugLog(`Tips data loaded: ${Boolean(tipsData)}`);
  if (!tipsData) {
    debugLog('No tips data found');
    markInjected(sessionId);
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Check freshness
  if (!isTipsFresh(tipsData)) {
    debugLog('Tips are stale (>24h)');
    markInjected(sessionId);
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Skip if tips are from the same session
  const tipsSession = tipsData.session_id || '';
  debugLog(`Tips session: ${tipsSession}, current: ${sessionId}`);
  if (tipsSession === sessionId) {
    debugLog('Tips are from current session, skipping');
    markInjected(sessionId);
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Format and inject
  const { contextText, userNotification } = formatTipsForInjection(tipsData);
  if (!contextText) {
    markInjected(sessionId);
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  // Mark as injected
  markInjected(sessionId);

  // Notify user via stderr (visible to user)
  log(userNotification);

  // Output for context injection (visible to Claude)
  const output = { additionalContext: contextText };
  console.log(JSON.stringify(output));
  process.exit(0);
}

// Export for testing
module.exports = {
  getSessionId,
  wasAlreadyInjected,
  markInjected,
  loadTips,
  isTipsFresh,
  formatTipsForInjection,
  MAX_TIPS_AGE_HOURS,
  MAX_TIPS,
  METRICS_DIR,
  SESSION_STATE_FILE,
  TIPS_FILE,
  SSOT_FILE,
  INJECTED_MARKER
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
