#!/usr/bin/env node
/**
 * DORA Metrics Tracker Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/metrics/dora-tracker.py
 *
 * PostToolUse hook that tracks DORA-inspired metrics:
 * - Cycle time (time between task start and completion)
 * - Rework rate (edits to same file within 24h)
 * - Task completion rate
 * - Test pass rate
 * - Session stats (duration, tool calls, errors)
 *
 * Logs to ~/.claude/metrics/dora/ for analysis
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');
const DORA_DIR = path.join(METRICS_DIR, 'dora');
const DAILY_LOG = path.join(DORA_DIR, 'daily.jsonl');
const FILE_EDIT_LOG = path.join(DORA_DIR, 'file_edits.json');
const SESSION_STATE = path.join(DORA_DIR, 'session_state.json');

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
 * Get project name from git or environment
 */
function getProjectName() {
  // Try environment first
  const envName = process.env.CLAUDE_PROJECT_NAME || process.env.CLAUDE_PROJECT;
  if (envName && envName !== 'unknown') {
    return envName;
  }

  // Try git repo name
  try {
    const result = execSync('git rev-parse --show-toplevel', {
      encoding: 'utf8',
      timeout: 2000,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    return path.basename(result.trim());
  } catch (err) {
    // Fallback to current directory name
    return path.basename(process.cwd());
  }
}

/**
 * Get current git commit info
 */
function getGitInfo() {
  try {
    const commitResult = execSync('git rev-parse --short HEAD', {
      encoding: 'utf8',
      timeout: 2000,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const branchResult = execSync('git rev-parse --abbrev-ref HEAD', {
      encoding: 'utf8',
      timeout: 2000,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    return {
      commit: commitResult.trim(),
      branch: branchResult.trim()
    };
  } catch (err) {
    return { commit: null, branch: null };
  }
}

/**
 * Load session state
 */
function getSessionState() {
  if (fs.existsSync(SESSION_STATE)) {
    try {
      return JSON.parse(fs.readFileSync(SESSION_STATE, 'utf8'));
    } catch (err) {
      // Ignore parse errors
    }
  }

  // Initialize new session
  return {
    sessionId: process.env.CLAUDE_SESSION_ID || `session_${new Date().toISOString().replace(/[:-]/g, '').slice(0, 15)}`,
    startTime: getTimestamp(),
    toolCalls: 0,
    errors: 0,
    model: process.env.CLAUDE_MODEL || 'unknown',
    tasksStarted: [],
    tasksCompleted: [],
    taskIterations: {}
  };
}

/**
 * Save session state
 */
function saveSessionState(state) {
  ensureDir(DORA_DIR);
  fs.writeFileSync(SESSION_STATE, JSON.stringify(state, null, 2));
}

/**
 * Update session statistics
 */
function updateSessionStats(toolName, success) {
  const state = getSessionState();
  state.toolCalls = (state.toolCalls || 0) + 1;
  if (!success) {
    state.errors = (state.errors || 0) + 1;
  }
  state.lastActivity = getTimestamp();
  saveSessionState(state);
  return state;
}

/**
 * Track task cycle time
 */
function trackTaskCycle(taskId, status) {
  const state = getSessionState();
  const now = getTimestamp();

  if (status === 'in_progress') {
    const existing = (state.tasksStarted || []).find(t => t.id === taskId);
    if (!existing) {
      state.tasksStarted = state.tasksStarted || [];
      state.tasksStarted.push({
        id: taskId,
        startTime: now
      });
      state.taskIterations = state.taskIterations || {};
      state.taskIterations[taskId] = 0;
    }
  } else if (status === 'completed') {
    const started = state.tasksStarted || [];
    const task = started.find(t => t.id === taskId);

    if (task) {
      const startDate = new Date(task.startTime);
      const endDate = new Date(now);
      const cycleTimeSeconds = (endDate - startDate) / 1000;
      const iterations = (state.taskIterations || {})[taskId] || 0;

      state.tasksCompleted = state.tasksCompleted || [];
      state.tasksCompleted.push({
        id: taskId,
        startTime: task.startTime,
        endTime: now,
        cycleTimeSeconds,
        iterations
      });

      // Log cycle time metric
      logMetric('cycle_time', {
        taskId,
        cycleTimeSeconds,
        cycleTimeMinutes: cycleTimeSeconds / 60,
        iterations
      });

      // Export to QuestDB if available
      if (metricsLib) {
        metricsLib.exportToQuestDB('claude_dora_metrics', {
          cycle_time_seconds: cycleTimeSeconds,
          iterations
        }, {
          project: getProjectName(),
          metric_type: 'cycle_time',
          task_id: taskId
        }).catch(() => {}); // Best effort
      }

      // Clean up iteration counter
      delete (state.taskIterations || {})[taskId];
    }
  }

  saveSessionState(state);
}

/**
 * Increment task iterations for all active tasks
 */
function incrementTaskIterations() {
  const state = getSessionState();
  const taskIterations = state.taskIterations || {};

  for (const taskId of Object.keys(taskIterations)) {
    taskIterations[taskId] += 1;
  }

  state.taskIterations = taskIterations;
  saveSessionState(state);
}

/**
 * Load file edit history
 */
function loadFileEdits() {
  if (fs.existsSync(FILE_EDIT_LOG)) {
    try {
      return JSON.parse(fs.readFileSync(FILE_EDIT_LOG, 'utf8'));
    } catch (err) {
      return {};
    }
  }
  return {};
}

/**
 * Save file edit history
 */
function saveFileEdits(edits) {
  ensureDir(DORA_DIR);
  fs.writeFileSync(FILE_EDIT_LOG, JSON.stringify(edits, null, 2));
}

/**
 * Calculate rework rate for a file
 */
function calculateReworkRate(filePath) {
  const edits = loadFileEdits();
  const now = Date.now() / 1000; // Unix timestamp in seconds

  if (edits[filePath]) {
    const lastEdit = edits[filePath].lastEdit;
    const hoursSince = (now - lastEdit) / 3600;

    if (hoursSince < 24) {
      edits[filePath].reworkCount = (edits[filePath].reworkCount || 0) + 1;
      edits[filePath].lastEdit = now;
      saveFileEdits(edits);
      return 1.0; // This is a rework
    }
  }

  // New file or first edit in 24h
  edits[filePath] = {
    lastEdit: now,
    reworkCount: edits[filePath]?.reworkCount || 0
  };
  saveFileEdits(edits);
  return 0.0;
}

/**
 * Log metric to daily log
 */
function logMetric(metricType, data) {
  ensureDir(DORA_DIR);

  const gitInfo = getGitInfo();
  const entry = {
    timestamp: getTimestamp(),
    type: metricType,
    project: getProjectName(),
    sessionId: process.env.CLAUDE_SESSION_ID || 'unknown',
    gitCommit: gitInfo.commit,
    gitBranch: gitInfo.branch,
    ...data
  };

  fs.appendFileSync(DAILY_LOG, JSON.stringify(entry) + '\n');
}

/**
 * Check thresholds and generate alerts
 */
function checkThresholds(sessionState) {
  const alerts = [];

  // Error rate threshold
  const toolCalls = sessionState.toolCalls || 0;
  const errors = sessionState.errors || 0;
  if (toolCalls > 10) {
    const errorRate = errors / toolCalls;
    if (errorRate > 0.15) {
      alerts.push(`High error rate: ${(errorRate * 100).toFixed(1)}% (threshold: 15%)`);
    }
  }

  // Rework rate - check file_edits.json
  try {
    const fileEdits = loadFileEdits();
    const files = Object.keys(fileEdits);
    if (files.length > 5) {
      const reworks = files.filter(f => (fileEdits[f].reworkCount || 0) > 0).length;
      const reworkRate = reworks / files.length;
      if (reworkRate > 0.3) {
        alerts.push(`High rework rate: ${(reworkRate * 100).toFixed(1)}% (threshold: 30%)`);
      }
    }
  } catch (err) {
    // Ignore
  }

  return alerts;
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
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  const toolName = inputData.tool_name || '';
  const toolInput = inputData.tool_input || {};
  const toolResponse = inputData.tool_response || {};

  // Track file edits for rework rate
  if (['Write', 'Edit', 'MultiEdit'].includes(toolName)) {
    const filePath = toolInput.file_path || '';
    if (filePath) {
      const rework = calculateReworkRate(filePath);
      logMetric('file_edit', {
        file: filePath,
        tool: toolName,
        isRework: rework > 0
      });

      // Export rework to QuestDB
      if (metricsLib && rework > 0) {
        metricsLib.exportToQuestDB('claude_dora_metrics', {
          rework: 1
        }, {
          project: getProjectName(),
          metric_type: 'rework',
          file: filePath
        }).catch(() => {});
      }
    }
  }

  // Track test runs
  if (toolName === 'Bash') {
    const command = (toolInput.command || '').toLowerCase();
    if (command.includes('pytest') || command.includes('test')) {
      const responseText = String(toolResponse);
      const passed = responseText.toLowerCase().includes('passed') &&
                    !responseText.toLowerCase().includes('failed');

      logMetric('test_run', {
        command: (toolInput.command || '').slice(0, 200),
        passed
      });
    }

    // Track git push/merge for deployment frequency
    if (command.includes('git push') || command.includes('git merge')) {
      logMetric('deployment', {
        command: (toolInput.command || '').slice(0, 200),
        type: command.includes('push') ? 'push' : 'merge'
      });

      if (metricsLib) {
        metricsLib.exportToQuestDB('claude_dora_metrics', {
          deployment_count: 1
        }, {
          project: getProjectName(),
          metric_type: 'deployment_frequency'
        }).catch(() => {});
      }
    }
  }

  // Track Task/Agent spawns
  if (toolName === 'Task') {
    const agentType = toolInput.subagent_type || 'unknown';
    const description = (toolInput.description || '').slice(0, 100);

    const responseText = String(toolResponse).toLowerCase();
    const success = !['error', 'failed', 'exception', 'traceback', 'cannot', 'unable']
      .some(err => responseText.includes(err));

    logMetric('agent_spawn', {
      agentType,
      description,
      success
    });
  }

  // Track todo completions and cycle time
  if (toolName === 'TodoWrite') {
    const todos = toolInput.todos || [];
    const completed = todos.filter(t => t.status === 'completed').length;
    const inProgress = todos.filter(t => t.status === 'in_progress');
    const total = todos.length;

    logMetric('todo_update', {
      total,
      completed,
      inProgress: inProgress.length,
      completionRate: total > 0 ? completed / total : 0
    });

    // Track cycle time for tasks
    for (const todo of todos) {
      const taskId = (todo.content || '').slice(0, 50);
      const status = todo.status || '';
      if (['in_progress', 'completed'].includes(status)) {
        trackTaskCycle(taskId, status);
      }
    }
  }

  // Update session stats for all tools
  const responseText = String(toolResponse);
  const success = !responseText.toLowerCase().includes('error');
  const sessionState = updateSessionStats(toolName, success);

  // Increment iterations for active tasks
  incrementTaskIterations();

  // Log session summary periodically (every 10 calls)
  if ((sessionState.toolCalls || 0) % 10 === 0) {
    const errorRate = (sessionState.errors || 0) / Math.max(sessionState.toolCalls || 1, 1);
    logMetric('session_stats', {
      toolCalls: sessionState.toolCalls || 0,
      errors: sessionState.errors || 0,
      errorRate,
      model: sessionState.model || 'unknown',
      tasksCompleted: (sessionState.tasksCompleted || []).length
    });

    // Export to QuestDB
    if (metricsLib) {
      metricsLib.exportToQuestDB('claude_dora_metrics', {
        error_rate: errorRate * 100
      }, {
        project: getProjectName(),
        metric_type: 'error_rate',
        session_id: sessionState.sessionId
      }).catch(() => {});
    }
  }

  // Check for threshold alerts (every 20 calls)
  let alerts = [];
  if ((sessionState.toolCalls || 0) % 20 === 0 && sessionState.toolCalls > 0) {
    alerts = checkThresholds(sessionState);
  }

  if (alerts.length > 0) {
    const alertMsg = alerts.map(a => `  ${a}`).join('\n');
    const output = {
      notification: `\n${'='.repeat(40)}\n  METRICS ALERT\n${'='.repeat(40)}\n${alertMsg}\n${'='.repeat(40)}\n`
    };
    console.log(JSON.stringify(output));
  } else {
    // Pass through - this hook doesn't modify anything
    console.log(JSON.stringify({}));
  }

  process.exit(0);
}

// Export for testing
module.exports = {
  getSessionState,
  saveSessionState,
  updateSessionStats,
  trackTaskCycle,
  calculateReworkRate,
  logMetric,
  checkThresholds,
  getProjectName,
  getGitInfo,
  DORA_DIR,
  DAILY_LOG,
  FILE_EDIT_LOG,
  SESSION_STATE
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
