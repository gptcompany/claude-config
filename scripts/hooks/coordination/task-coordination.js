#!/usr/bin/env node
/**
 * Task Coordination Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/coordination/task_claim.py
 * and /media/sam/1TB/claude-hooks-shared/hooks/coordination/task_release.py
 *
 * Tracks task assignments across agents:
 * - Claims tasks when subagents spawn
 * - Prevents duplicate work
 * - Auto-releases stale claims (>1 hour)
 * - Broadcasts task completion
 *
 * Claims stored in ~/.claude/coordination/task-claims.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// Configuration
const HOME_DIR = os.homedir();
const COORDINATION_DIR = path.join(HOME_DIR, '.claude', 'coordination');
const TASK_CLAIMS_FILE = path.join(COORDINATION_DIR, 'task-claims.json');
const ACTIVE_CLAIMS_FILE = path.join(COORDINATION_DIR, 'active_task_claims.json');
const LOG_FILE = path.join(COORDINATION_DIR, 'coordination.log');

// Stale claim threshold (1 hour in milliseconds)
const STALE_THRESHOLD_MS = 60 * 60 * 1000;

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
 * Log message to file
 */
function log(msg) {
  ensureDir(COORDINATION_DIR);
  try {
    fs.appendFileSync(LOG_FILE, `${getTimestamp()} [task-coordination] ${msg}\n`);
  } catch (err) {
    // Ignore
  }
}

/**
 * Get or create session ID
 */
function getSessionId() {
  if (process.env.CLAUDE_SESSION_ID) {
    return process.env.CLAUDE_SESSION_ID;
  }

  const sessionFile = path.join(COORDINATION_DIR, 'session_id');
  ensureDir(COORDINATION_DIR);

  if (fs.existsSync(sessionFile)) {
    try {
      return fs.readFileSync(sessionFile, 'utf8').trim();
    } catch (err) {}
  }

  // Generate new session ID
  const sessionId = `session-${Date.now().toString(36)}-${Math.random().toString(36).substr(2, 8)}`;
  fs.writeFileSync(sessionFile, sessionId);
  return sessionId;
}

/**
 * Generate task ID from description
 */
function generateTaskId(description) {
  const hash = crypto.createHash('sha256')
    .update(description)
    .digest('hex')
    .slice(0, 8);
  const timeComponent = new Date().toISOString().replace(/[-:T]/g, '').slice(8, 14);
  return `task-${hash}-${timeComponent}`;
}

/**
 * Load task claims
 */
function loadTaskClaims() {
  ensureDir(COORDINATION_DIR);
  if (fs.existsSync(TASK_CLAIMS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(TASK_CLAIMS_FILE, 'utf8'));
    } catch (err) {
      return { claims: {} };
    }
  }
  return { claims: {} };
}

/**
 * Save task claims
 */
function saveTaskClaims(claims) {
  ensureDir(COORDINATION_DIR);
  fs.writeFileSync(TASK_CLAIMS_FILE, JSON.stringify(claims, null, 2));
}

/**
 * Load active claims for this session
 */
function loadActiveClaims() {
  if (fs.existsSync(ACTIVE_CLAIMS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(ACTIVE_CLAIMS_FILE, 'utf8'));
    } catch (err) {}
  }
  return { claims: [] };
}

/**
 * Save active claims
 */
function saveActiveClaims(claims) {
  ensureDir(COORDINATION_DIR);
  fs.writeFileSync(ACTIVE_CLAIMS_FILE, JSON.stringify(claims, null, 2));
}

/**
 * Clean up stale claims
 */
function cleanStaleClaims(claims) {
  const now = Date.now();
  const cleaned = { claims: {} };

  for (const [taskId, claim] of Object.entries(claims.claims || {})) {
    const claimedAt = new Date(claim.claimedAt).getTime();
    const age = now - claimedAt;

    if (age < STALE_THRESHOLD_MS) {
      cleaned.claims[taskId] = claim;
    } else {
      log(`Stale claim removed: ${taskId} (was held by ${claim.claimant})`);
    }
  }

  return cleaned;
}

/**
 * Check if a similar task is already claimed
 */
function findSimilarClaim(description, claims) {
  // Simple similarity: check if description prefix matches
  const prefix = description.slice(0, 50).toLowerCase();

  for (const [taskId, claim] of Object.entries(claims.claims || {})) {
    const claimPrefix = (claim.description || '').slice(0, 50).toLowerCase();
    if (claimPrefix === prefix && prefix.length > 10) {
      return { taskId, claim };
    }
  }

  return null;
}

/**
 * Claim a task
 */
function claimTask(description, sessionId) {
  const claims = cleanStaleClaims(loadTaskClaims());
  const activeClaims = loadActiveClaims();

  // Generate task ID
  const taskId = generateTaskId(description);
  const issueId = `task:${taskId}`;
  const claimant = `agent:${sessionId}:task`;

  // Check for similar existing claim
  const similar = findSimilarClaim(description, claims);
  if (similar && similar.claim.claimant !== claimant) {
    log(`Similar task already claimed: ${similar.taskId} by ${similar.claim.claimant}`);
    // Still allow - just log warning (tasks are informational)
  }

  // Create the claim
  claims.claims[taskId] = {
    taskId,
    issueId,
    claimant,
    description: description.slice(0, 200),
    claimedAt: getTimestamp(),
    sessionId,
    status: 'running'
  };
  saveTaskClaims(claims);

  // Add to active claims for this session
  activeClaims.claims = activeClaims.claims || [];
  activeClaims.claims.push({
    taskId,
    issueId,
    claimant,
    description: description.slice(0, 200),
    claimedAt: getTimestamp(),
    claimSuccess: true
  });
  saveActiveClaims(activeClaims);

  log(`Task claimed: ${taskId} - ${description.slice(0, 50)}...`);

  return {
    success: true,
    taskId,
    issueId,
    claimant
  };
}

/**
 * Release a task claim
 */
function releaseTask(taskId, sessionId) {
  const claims = loadTaskClaims();
  const activeClaims = loadActiveClaims();

  const claimant = `agent:${sessionId}:task`;

  // Check if task exists and belongs to us
  const claim = claims.claims[taskId];
  if (!claim) {
    log(`Task not found: ${taskId}`);
    return { success: false, reason: 'not_found' };
  }

  if (claim.claimant !== claimant) {
    log(`Task not owned by us: ${taskId} (owned by ${claim.claimant})`);
    return { success: false, reason: 'not_owner' };
  }

  // Update claim status
  claim.status = 'completed';
  claim.completedAt = getTimestamp();
  saveTaskClaims(claims);

  // Remove from active claims
  activeClaims.claims = (activeClaims.claims || []).filter(c => c.taskId !== taskId);
  saveActiveClaims(activeClaims);

  log(`Task released: ${taskId}`);

  return { success: true, taskId };
}

/**
 * Release all tasks for this session (on SubagentStop)
 */
function releaseAllTasks(sessionId) {
  const claims = loadTaskClaims();
  const activeClaims = loadActiveClaims();

  const claimant = `agent:${sessionId}:task`;
  let releasedCount = 0;

  // Release all claims owned by this session
  for (const [taskId, claim] of Object.entries(claims.claims || {})) {
    if (claim.claimant === claimant && claim.status !== 'completed') {
      claim.status = 'completed';
      claim.completedAt = getTimestamp();
      releasedCount++;
      log(`Auto-released task: ${taskId}`);
    }
  }

  saveTaskClaims(claims);

  // Clear active claims
  saveActiveClaims({ claims: [] });

  log(`Released ${releasedCount} tasks for session ${sessionId}`);

  return { success: true, releasedCount };
}

/**
 * Get all active tasks
 */
function getActiveTasks() {
  const claims = cleanStaleClaims(loadTaskClaims());
  return Object.values(claims.claims || {}).filter(c => c.status === 'running');
}

/**
 * Get tasks for this session
 */
function getSessionTasks() {
  const activeClaims = loadActiveClaims();
  return activeClaims.claims || [];
}

/**
 * Handle PreToolUse for Task tool
 */
function handlePreTask(toolInput) {
  const description = toolInput.description || toolInput.prompt || 'unknown task';
  const sessionId = getSessionId();

  const result = claimTask(description, sessionId);

  // Task claims are INFORMATIONAL - never block
  return {};
}

/**
 * Handle SubagentStop - release all claims
 */
function handleSubagentStop(hookInput) {
  const agentId = hookInput.agent_id || 'unknown';
  const sessionId = getSessionId();

  log(`SubagentStop received for agent: ${agentId}, session: ${sessionId}`);

  const result = releaseAllTasks(sessionId);

  return {};
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
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  const toolName = hookInput.tool_name || '';
  const toolInput = hookInput.tool_input || {};
  const hookType = hookInput.hook_type || '';

  let result = {};

  // Handle Task tool (PreToolUse)
  if (toolName === 'Task') {
    result = handlePreTask(toolInput);
  }
  // Handle SubagentStop
  else if (hookType === 'subagent_stop' || hookInput.agent_id) {
    result = handleSubagentStop(hookInput);
  }
  // Handle TaskList tool
  else if (toolName === 'TaskList') {
    const tasks = getActiveTasks();
    result = {
      activeTasks: tasks.length,
      tasks: tasks.map(t => ({
        taskId: t.taskId,
        description: t.description,
        claimant: t.claimant,
        status: t.status
      }))
    };
  }

  console.log(JSON.stringify(result));
  process.exit(0);
}

// Export for testing
module.exports = {
  getSessionId,
  generateTaskId,
  loadTaskClaims,
  saveTaskClaims,
  loadActiveClaims,
  saveActiveClaims,
  cleanStaleClaims,
  findSimilarClaim,
  claimTask,
  releaseTask,
  releaseAllTasks,
  getActiveTasks,
  getSessionTasks,
  handlePreTask,
  handleSubagentStop,
  COORDINATION_DIR,
  TASK_CLAIMS_FILE,
  ACTIVE_CLAIMS_FILE,
  STALE_THRESHOLD_MS
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
