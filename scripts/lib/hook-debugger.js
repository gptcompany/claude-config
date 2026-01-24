/**
 * Hook Debugger Library for Claude Code Hooks
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * Provides:
 * - LOCAL logging at ~/.claude/debug/hooks/
 * - Per-hook debug enable/disable
 * - Invocation tracking with input/output
 * - Statistics and metrics
 * - Automatic log rotation
 * - QuestDB export for Grafana visibility
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Import metrics for QuestDB export
let metrics;
try {
  metrics = require('./metrics');
} catch (e) {
  metrics = null;
}

// Configuration
const HOME_DIR = os.homedir();
const DEBUG_DIR = path.join(HOME_DIR, '.claude', 'debug', 'hooks');
const CONFIG_FILE = path.join(DEBUG_DIR, 'debug-config.json');
const MAX_LOG_ENTRIES = 1000;
const STATS_EXPORT_INTERVAL = 100; // Export stats every N invocations

// In-memory stats tracking
const statsCache = new Map();

/**
 * Ensure debug directory exists
 * @returns {boolean} Success status
 */
function ensureDebugDir() {
  try {
    if (!fs.existsSync(DEBUG_DIR)) {
      fs.mkdirSync(DEBUG_DIR, { recursive: true });
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Get log file path for a hook
 * @param {string} hookName - Hook name
 * @returns {string} Log file path
 */
function getLogPath(hookName) {
  const safeName = hookName.replace(/[^a-zA-Z0-9-_]/g, '_');
  return path.join(DEBUG_DIR, `${safeName}.jsonl`);
}

/**
 * Load debug configuration
 * @returns {object} Debug config
 */
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
    }
  } catch (e) {
    // Ignore errors, return default
  }
  return {
    enabledHooks: {},
    globalDebug: false
  };
}

/**
 * Save debug configuration
 * @param {object} config - Config object
 * @returns {boolean} Success status
 */
function saveConfig(config) {
  ensureDebugDir();
  try {
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Enable debug for a specific hook
 * @param {string} hookName - Hook name
 * @returns {boolean} Success status
 */
function enableDebug(hookName) {
  const config = loadConfig();
  config.enabledHooks[hookName] = true;
  return saveConfig(config);
}

/**
 * Disable debug for a specific hook
 * @param {string} hookName - Hook name
 * @returns {boolean} Success status
 */
function disableDebug(hookName) {
  const config = loadConfig();
  delete config.enabledHooks[hookName];
  return saveConfig(config);
}

/**
 * Enable global debug (all hooks)
 * @returns {boolean} Success status
 */
function enableGlobalDebug() {
  const config = loadConfig();
  config.globalDebug = true;
  return saveConfig(config);
}

/**
 * Disable global debug
 * @returns {boolean} Success status
 */
function disableGlobalDebug() {
  const config = loadConfig();
  config.globalDebug = false;
  return saveConfig(config);
}

/**
 * Check if debug is enabled for a hook
 * @param {string} hookName - Hook name
 * @returns {boolean} Debug enabled
 */
function isDebugEnabled(hookName) {
  const config = loadConfig();
  return config.globalDebug || config.enabledHooks[hookName] === true;
}

/**
 * Rotate log file if it exceeds max entries
 * @param {string} logPath - Log file path
 */
function rotateLogIfNeeded(logPath) {
  try {
    if (!fs.existsSync(logPath)) return;

    const content = fs.readFileSync(logPath, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);

    if (lines.length > MAX_LOG_ENTRIES) {
      // Keep only the most recent entries
      const recentLines = lines.slice(-MAX_LOG_ENTRIES);
      fs.writeFileSync(logPath, recentLines.join('\n') + '\n');
    }
  } catch (e) {
    // Ignore rotation errors
  }
}

/**
 * Log a hook invocation
 * @param {string} hookName - Hook name
 * @param {object} input - Input data
 * @param {Date} [timestamp] - Optional timestamp
 * @returns {boolean} Success status
 */
function logInvocation(hookName, input, timestamp = new Date()) {
  ensureDebugDir();

  try {
    const logPath = getLogPath(hookName);
    const entry = {
      ts: timestamp.toISOString(),
      hook: hookName,
      event: 'invoke',
      data: {
        input: input ? JSON.stringify(input).slice(0, 1000) : null, // Limit size
        inputSize: input ? JSON.stringify(input).length : 0
      }
    };

    fs.appendFileSync(logPath, JSON.stringify(entry) + '\n');
    rotateLogIfNeeded(logPath);

    // Update stats cache
    updateStats(hookName, 'invoke');

    // Export to QuestDB (async, non-blocking)
    exportInvocationToQuestDB(hookName, 'invoke', null, true).catch(() => {});

    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Log a hook output
 * @param {string} hookName - Hook name
 * @param {object} output - Output data
 * @param {number} durationMs - Duration in milliseconds
 * @param {boolean} [success=true] - Whether hook succeeded
 * @param {string} [errorType] - Error type if failed
 * @returns {boolean} Success status
 */
function logOutput(hookName, output, durationMs, success = true, errorType = null) {
  ensureDebugDir();

  try {
    const logPath = getLogPath(hookName);
    const entry = {
      ts: new Date().toISOString(),
      hook: hookName,
      event: 'output',
      data: {
        output: output ? JSON.stringify(output).slice(0, 1000) : null,
        outputSize: output ? JSON.stringify(output).length : 0,
        durationMs,
        success,
        errorType
      }
    };

    fs.appendFileSync(logPath, JSON.stringify(entry) + '\n');
    rotateLogIfNeeded(logPath);

    // Update stats cache
    updateStats(hookName, 'output', { durationMs, success, errorType });

    // Export to QuestDB (async, non-blocking)
    exportInvocationToQuestDB(hookName, 'output', durationMs, success, errorType).catch(() => {});

    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Log an error from a hook
 * @param {string} hookName - Hook name
 * @param {Error|string} error - Error object or message
 * @param {number} [durationMs] - Duration before error
 * @returns {boolean} Success status
 */
function logError(hookName, error, durationMs = 0) {
  ensureDebugDir();

  try {
    const logPath = getLogPath(hookName);
    const errorMessage = error instanceof Error ? error.message : String(error);
    const errorType = error instanceof Error ? error.constructor.name : 'Error';

    const entry = {
      ts: new Date().toISOString(),
      hook: hookName,
      event: 'error',
      data: {
        error: errorMessage.slice(0, 500),
        errorType,
        durationMs,
        stack: error instanceof Error ? error.stack?.slice(0, 1000) : null
      }
    };

    fs.appendFileSync(logPath, JSON.stringify(entry) + '\n');
    rotateLogIfNeeded(logPath);

    // Update stats cache
    updateStats(hookName, 'error', { durationMs, errorType });

    // Export to QuestDB
    exportInvocationToQuestDB(hookName, 'error', durationMs, false, errorType).catch(() => {});

    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Update in-memory stats cache
 * @param {string} hookName - Hook name
 * @param {string} event - Event type
 * @param {object} [data] - Additional data
 */
function updateStats(hookName, event, data = {}) {
  if (!statsCache.has(hookName)) {
    statsCache.set(hookName, {
      calls: 0,
      outputs: 0,
      errors: 0,
      totalDuration: 0,
      durations: [],
      lastCall: null,
      lastSuccess: null,
      lastError: null
    });
  }

  const stats = statsCache.get(hookName);
  const now = new Date().toISOString();

  switch (event) {
    case 'invoke':
      stats.calls++;
      stats.lastCall = now;
      break;
    case 'output':
      stats.outputs++;
      if (data.durationMs) {
        stats.totalDuration += data.durationMs;
        stats.durations.push(data.durationMs);
        // Keep only last 100 durations for percentile calc
        if (stats.durations.length > 100) {
          stats.durations.shift();
        }
      }
      if (data.success) {
        stats.lastSuccess = now;
      }
      break;
    case 'error':
      stats.errors++;
      stats.lastError = now;
      break;
  }

  // Export aggregated stats periodically
  if (stats.calls % STATS_EXPORT_INTERVAL === 0) {
    exportStatsToQuestDB(hookName, stats).catch(() => {});
  }
}

/**
 * Get invocation log for a hook
 * @param {string} hookName - Hook name
 * @param {number} [last=100] - Number of recent entries
 * @returns {object[]} Array of log entries
 */
function getInvocationLog(hookName, last = 100) {
  try {
    const logPath = getLogPath(hookName);
    if (!fs.existsSync(logPath)) {
      return [];
    }

    const content = fs.readFileSync(logPath, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);
    const entries = [];

    // Read from end (most recent first)
    const start = Math.max(0, lines.length - last);
    for (let i = lines.length - 1; i >= start; i--) {
      try {
        entries.push(JSON.parse(lines[i]));
      } catch (e) {
        // Skip malformed lines
      }
    }

    return entries;
  } catch (e) {
    return [];
  }
}

/**
 * Get statistics for a hook
 * @param {string} hookName - Hook name
 * @returns {object} Hook statistics
 */
function getHookStats(hookName) {
  // First check cache
  if (statsCache.has(hookName)) {
    const cached = statsCache.get(hookName);
    return formatStats(hookName, cached);
  }

  // Otherwise compute from log
  const logs = getInvocationLog(hookName, MAX_LOG_ENTRIES);
  const stats = {
    calls: 0,
    outputs: 0,
    errors: 0,
    totalDuration: 0,
    durations: [],
    lastCall: null,
    lastSuccess: null,
    lastError: null
  };

  for (const log of logs) {
    switch (log.event) {
      case 'invoke':
        stats.calls++;
        if (!stats.lastCall || log.ts > stats.lastCall) {
          stats.lastCall = log.ts;
        }
        break;
      case 'output':
        stats.outputs++;
        if (log.data?.durationMs) {
          stats.totalDuration += log.data.durationMs;
          stats.durations.push(log.data.durationMs);
        }
        if (log.data?.success && (!stats.lastSuccess || log.ts > stats.lastSuccess)) {
          stats.lastSuccess = log.ts;
        }
        break;
      case 'error':
        stats.errors++;
        if (!stats.lastError || log.ts > stats.lastError) {
          stats.lastError = log.ts;
        }
        break;
    }
  }

  statsCache.set(hookName, stats);
  return formatStats(hookName, stats);
}

/**
 * Format stats for output
 * @param {string} hookName - Hook name
 * @param {object} stats - Raw stats
 * @returns {object} Formatted stats
 */
function formatStats(hookName, stats) {
  const avgDuration = stats.outputs > 0 ? Math.round(stats.totalDuration / stats.outputs) : 0;
  const p95Duration = calculatePercentile(stats.durations, 95);
  const errorRate = stats.calls > 0 ? (stats.errors / stats.calls) : 0;

  return {
    hook: hookName,
    calls: stats.calls,
    outputs: stats.outputs,
    errors: stats.errors,
    errorRate: Math.round(errorRate * 1000) / 1000,
    avgDuration,
    p95Duration,
    lastCall: stats.lastCall,
    lastSuccess: stats.lastSuccess,
    lastError: stats.lastError
  };
}

/**
 * Calculate percentile from an array of values
 * @param {number[]} arr - Array of values
 * @param {number} p - Percentile (0-100)
 * @returns {number} Percentile value
 */
function calculatePercentile(arr, p) {
  if (!arr || arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, idx)];
}

/**
 * Get stats for all hooks
 * @returns {object[]} Array of hook stats
 */
function getAllHookStats() {
  const allStats = [];

  try {
    const files = fs.readdirSync(DEBUG_DIR);
    for (const file of files) {
      if (file.endsWith('.jsonl')) {
        const hookName = file.replace('.jsonl', '');
        allStats.push(getHookStats(hookName));
      }
    }
  } catch (e) {
    // Directory might not exist
  }

  return allStats.sort((a, b) => b.calls - a.calls);
}

/**
 * Clear logs for a hook
 * @param {string} hookName - Hook name
 * @returns {boolean} Success status
 */
function clearLogs(hookName) {
  try {
    const logPath = getLogPath(hookName);
    if (fs.existsSync(logPath)) {
      fs.unlinkSync(logPath);
    }
    statsCache.delete(hookName);
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Clear all logs
 * @returns {boolean} Success status
 */
function clearAllLogs() {
  try {
    const files = fs.readdirSync(DEBUG_DIR);
    for (const file of files) {
      if (file.endsWith('.jsonl')) {
        fs.unlinkSync(path.join(DEBUG_DIR, file));
      }
    }
    statsCache.clear();
    return true;
  } catch (e) {
    return false;
  }
}

// ============================================================================
// QuestDB EXPORT
// ============================================================================

/**
 * Export hook invocation to QuestDB
 * @param {string} hookName - Hook name
 * @param {string} event - Event type (invoke/output/error)
 * @param {number} [durationMs] - Duration in ms
 * @param {boolean} [success=true] - Success status
 * @param {string} [errorType] - Error type if failed
 * @returns {Promise<boolean>} Export success
 */
async function exportInvocationToQuestDB(hookName, event, durationMs = null, success = true, errorType = null) {
  if (!metrics) return false;

  try {
    const project = process.env.PROJECT_NAME || detectProject();
    const sessionId = process.env.CLAUDE_SESSION_ID || 'unknown';

    const tags = {
      hook: hookName,
      event,
      project,
      session_id: sessionId
    };

    const values = {
      duration_ms: durationMs || 0,
      success: success ? 1 : 0,
      error_type: errorType || ''
    };

    return await metrics.exportToQuestDB('claude_hook_invocations', values, tags);
  } catch (e) {
    return false;
  }
}

/**
 * Export aggregated stats to QuestDB
 * @param {string} hookName - Hook name
 * @param {object} stats - Stats object
 * @returns {Promise<boolean>} Export success
 */
async function exportStatsToQuestDB(hookName, stats) {
  if (!metrics) return false;

  try {
    const project = process.env.PROJECT_NAME || detectProject();

    const tags = {
      hook: hookName,
      project
    };

    const avgDuration = stats.outputs > 0 ? Math.round(stats.totalDuration / stats.outputs) : 0;
    const p95Duration = calculatePercentile(stats.durations, 95);
    const errorRate = stats.calls > 0 ? (stats.errors / stats.calls) : 0;

    const values = {
      calls: stats.calls,
      errors: stats.errors,
      avg_duration_ms: avgDuration,
      p95_duration_ms: p95Duration,
      error_rate: errorRate
    };

    return await metrics.exportToQuestDB('claude_hook_stats', values, tags);
  } catch (e) {
    return false;
  }
}

/**
 * Detect project name from cwd
 * @returns {string} Project name
 */
function detectProject() {
  try {
    const cwd = process.cwd();
    return path.basename(cwd);
  } catch (e) {
    return 'unknown';
  }
}

/**
 * Force export all stats to QuestDB
 * @returns {Promise<number>} Number of successful exports
 */
async function forceExportAllStats() {
  const allStats = getAllHookStats();
  let success = 0;

  for (const stat of allStats) {
    const rawStats = statsCache.get(stat.hook) || {
      calls: stat.calls,
      outputs: stat.outputs,
      errors: stat.errors,
      totalDuration: stat.avgDuration * stat.outputs,
      durations: []
    };

    if (await exportStatsToQuestDB(stat.hook, rawStats)) {
      success++;
    }
  }

  return success;
}

// ============================================================================
// WRAPPER FOR HOOKS
// ============================================================================

/**
 * Create a debug wrapper for a hook function
 * @param {string} hookName - Hook name
 * @param {Function} hookFn - Hook function to wrap
 * @returns {Function} Wrapped function
 */
function wrapHook(hookName, hookFn) {
  return async function wrappedHook(...args) {
    const startTime = Date.now();

    // Log invocation
    logInvocation(hookName, args[0]);

    try {
      const result = await hookFn(...args);
      const duration = Date.now() - startTime;

      // Log output
      logOutput(hookName, result, duration, true);

      return result;
    } catch (error) {
      const duration = Date.now() - startTime;

      // Log error
      logError(hookName, error, duration);

      throw error;
    }
  };
}

/**
 * Wrap stdin hook execution
 * @param {string} hookName - Hook name
 * @param {Function} processFn - Function to process input
 * @returns {Promise<void>}
 */
async function runWithDebug(hookName, processFn) {
  const chunks = [];

  return new Promise((resolve, reject) => {
    process.stdin.on('data', chunk => chunks.push(chunk));
    process.stdin.on('end', async () => {
      const startTime = Date.now();
      const input = Buffer.concat(chunks).toString('utf8');

      let parsedInput;
      try {
        parsedInput = JSON.parse(input);
      } catch (e) {
        parsedInput = { raw: input.slice(0, 200) };
      }

      // Log invocation
      logInvocation(hookName, parsedInput);

      try {
        const result = await processFn(input);
        const duration = Date.now() - startTime;

        // Log output
        logOutput(hookName, result, duration, true);

        // Output result
        if (result !== undefined) {
          console.log(typeof result === 'string' ? result : JSON.stringify(result));
        }

        resolve();
      } catch (error) {
        const duration = Date.now() - startTime;

        // Log error
        logError(hookName, error, duration);

        reject(error);
      }
    });
  });
}

module.exports = {
  // Debug enable/disable
  enableDebug,
  disableDebug,
  enableGlobalDebug,
  disableGlobalDebug,
  isDebugEnabled,

  // Logging
  logInvocation,
  logOutput,
  logError,

  // Retrieval
  getInvocationLog,
  getHookStats,
  getAllHookStats,

  // Cleanup
  clearLogs,
  clearAllLogs,

  // QuestDB export
  exportInvocationToQuestDB,
  exportStatsToQuestDB,
  forceExportAllStats,

  // Wrappers
  wrapHook,
  runWithDebug,

  // Utilities
  ensureDebugDir,
  getLogPath,
  loadConfig,

  // Constants
  DEBUG_DIR,
  MAX_LOG_ENTRIES,
  STATS_EXPORT_INTERVAL
};
