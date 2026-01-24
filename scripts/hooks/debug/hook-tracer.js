#!/usr/bin/env node
/**
 * Hook Tracer - Debug Hook for Tracing All Invocations
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * This is a meta-hook that traces all hook invocations.
 * It logs every hook call to a trace file for debugging.
 *
 * Enable via: CLAUDE_HOOK_TRACE=1
 *
 * Output format (JSON Lines):
 * {
 *   "ts": "2026-01-24T12:00:00Z",
 *   "event": "PreToolUse",
 *   "hook": "git-safety-check",
 *   "input": {...},
 *   "output": {},
 *   "duration_ms": 12,
 *   "success": true
 * }
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HOME_DIR = os.homedir();
const DEBUG_DIR = path.join(HOME_DIR, '.claude', 'debug', 'hooks');
const TRACE_FILE = path.join(DEBUG_DIR, 'trace.jsonl');
const MAX_TRACE_LINES = 10000;

// Check if tracing is enabled
const TRACE_ENABLED = process.env.CLAUDE_HOOK_TRACE === '1' ||
                       process.env.CLAUDE_HOOK_TRACE === 'true';

/**
 * Ensure debug directory exists
 */
function ensureDebugDir() {
  try {
    if (!fs.existsSync(DEBUG_DIR)) {
      fs.mkdirSync(DEBUG_DIR, { recursive: true });
    }
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Rotate trace file if it exceeds max lines
 */
function rotateTraceIfNeeded() {
  try {
    if (!fs.existsSync(TRACE_FILE)) return;

    const stat = fs.statSync(TRACE_FILE);
    // Rotate if file exceeds 5MB
    if (stat.size > 5 * 1024 * 1024) {
      const backupPath = TRACE_FILE.replace('.jsonl', '.backup.jsonl');
      fs.renameSync(TRACE_FILE, backupPath);
    }
  } catch (e) {
    // Ignore rotation errors
  }
}

/**
 * Write a trace entry (async, non-blocking)
 * @param {object} entry - Trace entry
 */
function writeTrace(entry) {
  if (!TRACE_ENABLED) return;

  ensureDebugDir();
  rotateTraceIfNeeded();

  try {
    const line = JSON.stringify(entry) + '\n';
    fs.appendFileSync(TRACE_FILE, line);
  } catch (e) {
    // Non-blocking, ignore errors
  }
}

/**
 * Truncate data for logging (limit size)
 * @param {any} data - Data to truncate
 * @param {number} maxLen - Maximum length
 * @returns {any} Truncated data
 */
function truncateData(data, maxLen = 500) {
  if (data === null || data === undefined) return null;

  if (typeof data === 'string') {
    return data.length > maxLen ? data.slice(0, maxLen) + '...' : data;
  }

  if (typeof data === 'object') {
    const str = JSON.stringify(data);
    if (str.length > maxLen) {
      return { _truncated: true, _preview: str.slice(0, maxLen) };
    }
    return data;
  }

  return data;
}

/**
 * Extract hook name from process or environment
 * @returns {string} Hook name
 */
function getHookName() {
  // Try to get from environment
  if (process.env.HOOK_NAME) return process.env.HOOK_NAME;

  // Try to get from argv
  const scriptPath = process.argv[1];
  if (scriptPath) {
    return path.basename(scriptPath, '.js');
  }

  return 'unknown';
}

/**
 * Get event type from environment or input
 * @param {object} input - Hook input
 * @returns {string} Event type
 */
function getEventType(input) {
  if (process.env.HOOK_EVENT) return process.env.HOOK_EVENT;

  // Try to infer from input structure
  if (input?.tool_name) {
    return input.tool_output ? 'PostToolUse' : 'PreToolUse';
  }
  if (input?.message) return 'UserPromptSubmit';
  if (input?.stop_reason) return 'Stop';
  if (input?.compact_reason) return 'PreCompact';
  if (input?.session_id) return 'SessionStart';

  return 'Unknown';
}

/**
 * Main trace function
 */
async function main() {
  const startTime = Date.now();
  const chunks = [];

  process.stdin.on('data', chunk => chunks.push(chunk));

  process.stdin.on('end', () => {
    const rawInput = Buffer.concat(chunks).toString('utf8');

    let input = null;
    try {
      input = JSON.parse(rawInput);
    } catch (e) {
      input = { _raw: truncateData(rawInput) };
    }

    const hookName = getHookName();
    const eventType = getEventType(input);
    const duration = Date.now() - startTime;

    // Create trace entry
    const entry = {
      ts: new Date().toISOString(),
      event: eventType,
      hook: hookName,
      input: truncateData(input),
      output: {},
      duration_ms: duration,
      success: true,
      pid: process.pid,
      cwd: process.cwd(),
      trace_enabled: TRACE_ENABLED
    };

    // Write trace
    writeTrace(entry);

    // Pass through the input unchanged (this hook doesn't modify anything)
    console.log(rawInput);
  });
}

// Run if called directly
if (require.main === module) {
  main().catch(err => {
    // Log error but don't fail
    writeTrace({
      ts: new Date().toISOString(),
      event: 'TracerError',
      hook: 'hook-tracer',
      error: err.message,
      success: false
    });
    // Still pass through
    process.stdin.pipe(process.stdout);
  });
}

// Export for testing
module.exports = {
  writeTrace,
  truncateData,
  getHookName,
  getEventType,
  TRACE_FILE,
  DEBUG_DIR,
  TRACE_ENABLED
};
