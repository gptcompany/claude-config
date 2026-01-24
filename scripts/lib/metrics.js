/**
 * Metrics Library for Claude Code Hooks
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/scripts/questdb_client.py
 *
 * Provides:
 * - LOCAL storage at ~/.claude/metrics/ (always works, offline-first)
 * - QuestDB ILP export on port 9009 (async, best-effort)
 * - QuestDB REST query on port 9000
 *
 * Tables exported:
 * - claude_sessions - session metrics
 * - claude_tool_usage - tool call stats
 * - claude_hook_invocations - hook debug data
 * - claude_tip_outcomes - tip effectiveness
 *
 * Strategy: Dual-write
 * - Always save to local JSON (guaranteed)
 * - Async export to QuestDB (best-effort, no block on failure)
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const net = require('net');
const http = require('http');

// Configuration
const HOME_DIR = os.homedir();
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const SESSION_STATE_FILE = path.join(METRICS_DIR, 'session_state.json');
const CONTEXT_STATS_FILE = path.join(METRICS_DIR, 'context_stats.json');
const METRICS_LOG_FILE = path.join(METRICS_DIR, 'metrics.jsonl');

// QuestDB configuration
const QUESTDB_HOST = process.env.QUESTDB_HOST || 'localhost';
const QUESTDB_ILP_PORT = parseInt(process.env.QUESTDB_ILP_PORT || '9009', 10);
const QUESTDB_HTTP_PORT = parseInt(process.env.QUESTDB_HTTP_PORT || '9000', 10);
const QUESTDB_ILP_TIMEOUT = 3000; // 3 second timeout for ILP
const QUESTDB_HTTP_TIMEOUT = 5000; // 5 second timeout for HTTP

/**
 * Ensure metrics directory exists
 */
function ensureMetricsDir() {
  try {
    if (!fs.existsSync(METRICS_DIR)) {
      fs.mkdirSync(METRICS_DIR, { recursive: true });
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Get ISO timestamp with nanosecond precision for QuestDB
 * @returns {string} ISO timestamp
 */
function getTimestamp() {
  return new Date().toISOString();
}

/**
 * Get nanosecond timestamp for QuestDB ILP
 * @returns {bigint} Nanoseconds since epoch
 */
function getNanoTimestamp() {
  return BigInt(Date.now()) * BigInt(1000000);
}

// ============================================================================
// LOCAL STORAGE (Always works, offline-first)
// ============================================================================

/**
 * Save a metric to local storage
 * @param {string} name - Metric name
 * @param {any} value - Metric value
 * @param {object} [tags={}] - Additional tags
 * @returns {boolean} Success status
 */
function saveMetric(name, value, tags = {}) {
  ensureMetricsDir();
  try {
    const entry = {
      timestamp: getTimestamp(),
      name,
      value,
      tags
    };

    // Append to JSONL file (one JSON object per line)
    fs.appendFileSync(METRICS_LOG_FILE, JSON.stringify(entry) + '\n');
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load metrics by name from local storage
 * @param {string} name - Metric name to filter by
 * @param {number} [limit=100] - Maximum entries to return
 * @returns {object[]} Array of metric entries
 */
function loadMetric(name, limit = 100) {
  try {
    if (!fs.existsSync(METRICS_LOG_FILE)) {
      return [];
    }

    const content = fs.readFileSync(METRICS_LOG_FILE, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);
    const results = [];

    // Read from end (most recent first)
    for (let i = lines.length - 1; i >= 0 && results.length < limit; i--) {
      try {
        const entry = JSON.parse(lines[i]);
        if (!name || entry.name === name) {
          results.push(entry);
        }
      } catch {
        // Skip malformed lines
      }
    }

    return results;
  } catch (err) {
    return [];
  }
}

/**
 * Save session state
 * @param {object} state - Session state object
 * @returns {boolean} Success status
 */
function saveSessionState(state) {
  ensureMetricsDir();
  try {
    const data = {
      ...state,
      savedAt: getTimestamp()
    };
    fs.writeFileSync(SESSION_STATE_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load session state
 * @returns {object|null} Session state or null if not found
 */
function loadSessionState() {
  try {
    if (!fs.existsSync(SESSION_STATE_FILE)) {
      return null;
    }
    const content = fs.readFileSync(SESSION_STATE_FILE, 'utf8');
    return JSON.parse(content);
  } catch (err) {
    return null;
  }
}

/**
 * Clear session state
 * @returns {boolean} Success status
 */
function clearSessionState() {
  try {
    if (fs.existsSync(SESSION_STATE_FILE)) {
      fs.unlinkSync(SESSION_STATE_FILE);
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Save context statistics
 * @param {object} stats - Context stats object
 * @returns {boolean} Success status
 */
function saveContextStats(stats) {
  ensureMetricsDir();
  try {
    const data = {
      ...stats,
      savedAt: getTimestamp()
    };
    fs.writeFileSync(CONTEXT_STATS_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load context statistics
 * @returns {object|null} Context stats or null if not found
 */
function loadContextStats() {
  try {
    if (!fs.existsSync(CONTEXT_STATS_FILE)) {
      return null;
    }
    const content = fs.readFileSync(CONTEXT_STATS_FILE, 'utf8');
    return JSON.parse(content);
  } catch (err) {
    return null;
  }
}

// ============================================================================
// QUESTDB ILP EXPORT (Async, best-effort)
// ============================================================================

/**
 * Escape a string value for ILP protocol
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeIlpString(str) {
  if (typeof str !== 'string') {
    str = String(str);
  }
  return str
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r');
}

/**
 * Escape a tag key/value for ILP protocol
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeIlpTag(str) {
  if (typeof str !== 'string') {
    str = String(str);
  }
  return str
    .replace(/\\/g, '\\\\')
    .replace(/,/g, '\\,')
    .replace(/=/g, '\\=')
    .replace(/ /g, '\\ ');
}

/**
 * Format a value for ILP protocol
 * @param {any} value - Value to format
 * @returns {string} Formatted value
 */
function formatIlpValue(value) {
  if (typeof value === 'boolean') {
    return value ? 't' : 'f';
  }
  if (typeof value === 'number') {
    if (Number.isInteger(value)) {
      return `${value}i`;
    }
    return String(value);
  }
  if (typeof value === 'string') {
    return `"${escapeIlpString(value)}"`;
  }
  if (value === null || value === undefined) {
    return '""';
  }
  // Complex objects: serialize to JSON string
  return `"${escapeIlpString(JSON.stringify(value))}"`;
}

/**
 * Build ILP line protocol string
 * @param {string} table - Table name
 * @param {object} tags - Tag key-value pairs
 * @param {object} fields - Field key-value pairs
 * @param {bigint} [timestamp] - Nanosecond timestamp
 * @returns {string} ILP line
 */
function buildIlpLine(table, tags, fields, timestamp) {
  let line = escapeIlpTag(table);

  // Add tags (sorted for consistency)
  const tagKeys = Object.keys(tags).sort();
  for (const key of tagKeys) {
    const value = tags[key];
    if (value !== null && value !== undefined && value !== '') {
      line += `,${escapeIlpTag(key)}=${escapeIlpTag(String(value))}`;
    }
  }

  // Add fields
  line += ' ';
  const fieldEntries = [];
  for (const [key, value] of Object.entries(fields)) {
    if (value !== null && value !== undefined) {
      fieldEntries.push(`${escapeIlpTag(key)}=${formatIlpValue(value)}`);
    }
  }
  line += fieldEntries.join(',');

  // Add timestamp if provided
  if (timestamp) {
    line += ` ${timestamp}`;
  }

  return line + '\n';
}

/**
 * Export data to QuestDB via ILP protocol (async, non-blocking)
 * @param {string} table - Table name
 * @param {object} values - Field values
 * @param {object} [tags={}] - Tag values
 * @returns {Promise<boolean>} Success status
 */
function exportToQuestDB(table, values, tags = {}) {
  return new Promise((resolve) => {
    try {
      const timestamp = getNanoTimestamp();
      const line = buildIlpLine(table, tags, values, timestamp);

      const socket = new net.Socket();
      let resolved = false;

      const cleanup = () => {
        if (!resolved) {
          resolved = true;
          socket.destroy();
          resolve(false);
        }
      };

      const timer = setTimeout(cleanup, QUESTDB_ILP_TIMEOUT);

      socket.connect(QUESTDB_ILP_PORT, QUESTDB_HOST, () => {
        socket.write(line, () => {
          clearTimeout(timer);
          resolved = true;
          socket.end();
          resolve(true);
        });
      });

      socket.on('error', () => {
        clearTimeout(timer);
        cleanup();
      });

      socket.on('timeout', cleanup);
    } catch (err) {
      resolve(false);
    }
  });
}

/**
 * Export multiple rows to QuestDB via ILP (batch)
 * @param {string} table - Table name
 * @param {object[]} rows - Array of {values, tags} objects
 * @returns {Promise<number>} Number of successful exports
 */
async function exportBatchToQuestDB(table, rows) {
  let successCount = 0;
  const batchLines = [];

  for (const row of rows) {
    const timestamp = getNanoTimestamp();
    const line = buildIlpLine(table, row.tags || {}, row.values, timestamp);
    batchLines.push(line);
  }

  return new Promise((resolve) => {
    try {
      const socket = new net.Socket();
      let resolved = false;

      const cleanup = () => {
        if (!resolved) {
          resolved = true;
          socket.destroy();
          resolve(successCount);
        }
      };

      const timer = setTimeout(cleanup, QUESTDB_ILP_TIMEOUT * 2);

      socket.connect(QUESTDB_ILP_PORT, QUESTDB_HOST, () => {
        const batch = batchLines.join('');
        socket.write(batch, () => {
          clearTimeout(timer);
          resolved = true;
          successCount = rows.length;
          socket.end();
          resolve(successCount);
        });
      });

      socket.on('error', () => {
        clearTimeout(timer);
        cleanup();
      });
    } catch (err) {
      resolve(successCount);
    }
  });
}

// ============================================================================
// QUESTDB REST QUERY
// ============================================================================

/**
 * Query QuestDB via REST API
 * @param {string} sql - SQL query
 * @param {number} [timeout=5000] - Timeout in milliseconds
 * @returns {Promise<object|null>} Query result or null on error
 */
function queryQuestDB(sql, timeout = QUESTDB_HTTP_TIMEOUT) {
  return new Promise((resolve) => {
    try {
      const url = new URL(`http://${QUESTDB_HOST}:${QUESTDB_HTTP_PORT}/exec`);
      url.searchParams.set('query', sql);

      const req = http.get(url.toString(), { timeout }, (res) => {
        let data = '';

        res.on('data', chunk => {
          data += chunk;
        });

        res.on('end', () => {
          try {
            const result = JSON.parse(data);
            resolve(result);
          } catch {
            resolve(null);
          }
        });
      });

      req.on('error', () => resolve(null));
      req.on('timeout', () => {
        req.destroy();
        resolve(null);
      });
    } catch (err) {
      resolve(null);
    }
  });
}

/**
 * Check QuestDB health
 * @returns {Promise<object>} Health status object
 */
async function checkQuestDBHealth() {
  const status = {
    available: false,
    latencyMs: null,
    sessionCount: 0,
    error: null
  };

  try {
    const start = Date.now();
    const result = await queryQuestDB('SELECT COUNT(*) FROM claude_sessions', 2000);
    status.latencyMs = Date.now() - start;
    status.available = true;

    if (result && result.dataset && result.dataset[0]) {
      status.sessionCount = result.dataset[0][0];
    }
  } catch (err) {
    status.error = err.message;
  }

  return status;
}

// ============================================================================
// DUAL-WRITE HELPERS (Local + QuestDB)
// ============================================================================

/**
 * Record session metrics (dual-write)
 * @param {object} data - Session data
 * @returns {Promise<object>} Result with local and remote status
 */
async function recordSession(data) {
  const result = { local: false, remote: false };

  // Always save locally first
  result.local = saveMetric('session', data, { type: 'session' });

  // Async export to QuestDB
  const tags = {
    project: data.project || 'unknown',
    session_id: data.sessionId || 'unknown'
  };

  const values = {
    error_rate: data.errorRate || 0,
    rework_rate: data.reworkRate || 0,
    test_pass_rate: data.testPassRate || 0,
    tool_calls: data.toolCalls || 0,
    duration_seconds: data.durationSeconds || 0,
    outcome: data.outcome || 'unknown'
  };

  result.remote = await exportToQuestDB('claude_sessions', values, tags);
  return result;
}

/**
 * Record tool usage (dual-write)
 * @param {object} data - Tool usage data
 * @returns {Promise<object>} Result with local and remote status
 */
async function recordToolUsage(data) {
  const result = { local: false, remote: false };

  result.local = saveMetric('tool_usage', data, { type: 'tool_usage' });

  const tags = {
    project: data.project || 'unknown',
    tool_name: data.toolName || 'unknown'
  };

  const values = {
    success: data.success || false,
    duration_ms: data.durationMs || 0,
    error_message: data.errorMessage || ''
  };

  result.remote = await exportToQuestDB('claude_tool_usage', values, tags);
  return result;
}

/**
 * Record hook invocation (dual-write)
 * @param {object} data - Hook invocation data
 * @returns {Promise<object>} Result with local and remote status
 */
async function recordHookInvocation(data) {
  const result = { local: false, remote: false };

  result.local = saveMetric('hook_invocation', data, { type: 'hook' });

  const tags = {
    hook_type: data.hookType || 'unknown',
    project: data.project || 'unknown'
  };

  const values = {
    duration_ms: data.durationMs || 0,
    success: data.success || false,
    payload_size: data.payloadSize || 0
  };

  result.remote = await exportToQuestDB('claude_hook_invocations', values, tags);
  return result;
}

/**
 * Record tip outcome (dual-write)
 * @param {object} data - Tip outcome data
 * @returns {Promise<object>} Result with local and remote status
 */
async function recordTipOutcome(data) {
  const result = { local: false, remote: false };

  result.local = saveMetric('tip_outcome', data, { type: 'tip' });

  const tags = {
    project: data.project || 'unknown',
    rule_name: data.ruleName || 'unknown'
  };

  const values = {
    tip_id: data.tipId || '',
    command_suggested: data.commandSuggested || '',
    outcome: data.outcome || 'unknown'
  };

  result.remote = await exportToQuestDB('claude_tip_outcomes', values, tags);
  return result;
}

module.exports = {
  // Local storage
  saveMetric,
  loadMetric,
  saveSessionState,
  loadSessionState,
  clearSessionState,
  saveContextStats,
  loadContextStats,

  // QuestDB export
  exportToQuestDB,
  exportBatchToQuestDB,
  queryQuestDB,
  checkQuestDBHealth,

  // Dual-write helpers
  recordSession,
  recordToolUsage,
  recordHookInvocation,
  recordTipOutcome,

  // Utilities
  getTimestamp,
  getNanoTimestamp,
  buildIlpLine,
  ensureMetricsDir,

  // Constants
  METRICS_DIR,
  SESSION_STATE_FILE,
  CONTEXT_STATS_FILE,
  METRICS_LOG_FILE,
  QUESTDB_HOST,
  QUESTDB_ILP_PORT,
  QUESTDB_HTTP_PORT
};
