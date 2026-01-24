#!/usr/bin/env node
/**
 * Hive Manager Hook (PostToolUse for Task tool)
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/swarm/hive_manager.py
 *
 * Multi-agent coordination for parallel task execution:
 * - Track spawned agents
 * - Monitor agent status
 * - Detect stuck/failed agents
 * - Coordinate shared resources via file-coordination
 *
 * Uses file-coordination.js for file locking.
 * Saves hive state to ~/.claude/hive/state.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HIVE_DIR = path.join(HOME_DIR, '.claude', 'hive');
const STATE_FILE = path.join(HIVE_DIR, 'state.json');
const LOG_FILE = path.join(HIVE_DIR, 'hive.log');
const METRICS_DIR = path.join(HOME_DIR, '.claude', 'metrics');

// Agent timeout (consider stuck after this)
const AGENT_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

// Max agents
const MAX_AGENTS = 10;

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Get timestamp
 */
function getTimestamp() {
  return new Date().toISOString();
}

/**
 * Log to file
 */
function log(msg) {
  ensureDir(HIVE_DIR);
  try {
    fs.appendFileSync(LOG_FILE, `${getTimestamp()} [hive-manager] ${msg}\n`);
  } catch (err) {
    // Ignore
  }
}

/**
 * Load hive state
 */
function loadState() {
  ensureDir(HIVE_DIR);
  if (fs.existsSync(STATE_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    } catch (err) {
      log(`Failed to load state: ${err.message}`);
    }
  }
  return {
    agents: {},
    tasks: {},
    hive_id: null,
    topology: 'hierarchical-mesh',
    created_at: null,
    updated_at: null
  };
}

/**
 * Save hive state
 */
function saveState(state) {
  ensureDir(HIVE_DIR);
  state.updated_at = getTimestamp();
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  } catch (err) {
    log(`Failed to save state: ${err.message}`);
  }
}

/**
 * Generate unique agent ID
 */
function generateAgentId() {
  return `agent_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Generate unique task ID
 */
function generateTaskId() {
  return `task_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Initialize hive
 */
function initHive(topology = 'hierarchical-mesh') {
  const state = loadState();

  if (state.hive_id) {
    log(`Hive already initialized: ${state.hive_id}`);
    return { success: true, hive_id: state.hive_id, existing: true };
  }

  state.hive_id = `hive_${Date.now().toString(36)}`;
  state.topology = topology;
  state.created_at = getTimestamp();
  state.agents = {};
  state.tasks = {};

  saveState(state);
  log(`Hive initialized: ${state.hive_id} with topology ${topology}`);

  return { success: true, hive_id: state.hive_id, existing: false };
}

/**
 * Register agent
 */
function registerAgent(agentId = null, role = 'worker') {
  const state = loadState();

  if (!state.hive_id) {
    initHive();
  }

  const id = agentId || generateAgentId();
  const agentCount = Object.keys(state.agents).length;

  if (agentCount >= MAX_AGENTS) {
    log(`Max agents reached (${MAX_AGENTS}), cannot register ${id}`);
    return { success: false, reason: 'max_agents_reached' };
  }

  state.agents[id] = {
    id,
    role,
    status: 'active',
    registered_at: getTimestamp(),
    last_activity: getTimestamp(),
    tasks_completed: 0,
    tasks_failed: 0
  };

  saveState(state);
  log(`Agent registered: ${id} (role: ${role})`);

  return { success: true, agent_id: id };
}

/**
 * Update agent status
 */
function updateAgentStatus(agentId, status, metadata = {}) {
  const state = loadState();

  if (!state.agents[agentId]) {
    log(`Unknown agent: ${agentId}`);
    return { success: false, reason: 'unknown_agent' };
  }

  state.agents[agentId] = {
    ...state.agents[agentId],
    status,
    last_activity: getTimestamp(),
    ...metadata
  };

  saveState(state);
  log(`Agent ${agentId} status: ${status}`);

  return { success: true };
}

/**
 * Register task
 */
function registerTask(description, priority = 'normal', assignedTo = null) {
  const state = loadState();
  const taskId = generateTaskId();

  state.tasks[taskId] = {
    id: taskId,
    description,
    priority,
    status: assignedTo ? 'assigned' : 'pending',
    assigned_to: assignedTo,
    created_at: getTimestamp(),
    started_at: null,
    completed_at: null
  };

  saveState(state);
  log(`Task registered: ${taskId} (${description.slice(0, 50)}...)`);

  return { success: true, task_id: taskId };
}

/**
 * Start task
 */
function startTask(taskId, agentId) {
  const state = loadState();

  if (!state.tasks[taskId]) {
    return { success: false, reason: 'unknown_task' };
  }

  if (!state.agents[agentId]) {
    return { success: false, reason: 'unknown_agent' };
  }

  state.tasks[taskId] = {
    ...state.tasks[taskId],
    status: 'in_progress',
    assigned_to: agentId,
    started_at: getTimestamp()
  };

  state.agents[agentId].last_activity = getTimestamp();
  state.agents[agentId].status = 'busy';

  saveState(state);
  log(`Task ${taskId} started by ${agentId}`);

  return { success: true };
}

/**
 * Complete task
 */
function completeTask(taskId, success = true, result = null) {
  const state = loadState();

  if (!state.tasks[taskId]) {
    return { success: false, reason: 'unknown_task' };
  }

  const agentId = state.tasks[taskId].assigned_to;
  state.tasks[taskId] = {
    ...state.tasks[taskId],
    status: success ? 'completed' : 'failed',
    completed_at: getTimestamp(),
    result
  };

  if (agentId && state.agents[agentId]) {
    state.agents[agentId].last_activity = getTimestamp();
    state.agents[agentId].status = 'idle';
    if (success) {
      state.agents[agentId].tasks_completed++;
    } else {
      state.agents[agentId].tasks_failed++;
    }
  }

  saveState(state);
  log(`Task ${taskId} ${success ? 'completed' : 'failed'}`);

  return { success: true };
}

/**
 * Get hive status
 */
function getStatus() {
  const state = loadState();
  const now = Date.now();

  const agents = Object.values(state.agents || {});
  const tasks = Object.values(state.tasks || {});

  // Check for stuck agents
  const stuckAgents = [];
  for (const agent of agents) {
    if (agent.status === 'busy' || agent.status === 'active') {
      const lastActivity = new Date(agent.last_activity).getTime();
      if (now - lastActivity > AGENT_TIMEOUT_MS) {
        stuckAgents.push(agent.id);
      }
    }
  }

  return {
    hive_id: state.hive_id,
    topology: state.topology,
    agents: {
      total: agents.length,
      active: agents.filter(a => a.status === 'active').length,
      busy: agents.filter(a => a.status === 'busy').length,
      idle: agents.filter(a => a.status === 'idle').length,
      stuck: stuckAgents.length
    },
    tasks: {
      total: tasks.length,
      pending: tasks.filter(t => t.status === 'pending').length,
      in_progress: tasks.filter(t => t.status === 'in_progress').length,
      completed: tasks.filter(t => t.status === 'completed').length,
      failed: tasks.filter(t => t.status === 'failed').length
    },
    stuck_agents: stuckAgents,
    updated_at: state.updated_at
  };
}

/**
 * Detect stuck agents and mark them
 */
function detectStuckAgents() {
  const state = loadState();
  const now = Date.now();
  const stuckAgents = [];

  for (const [agentId, agent] of Object.entries(state.agents || {})) {
    if (agent.status === 'busy' || agent.status === 'active') {
      const lastActivity = new Date(agent.last_activity).getTime();
      if (now - lastActivity > AGENT_TIMEOUT_MS) {
        state.agents[agentId].status = 'stuck';
        stuckAgents.push(agentId);
        log(`Agent ${agentId} marked as stuck (inactive for ${Math.round((now - lastActivity) / 60000)}min)`);
      }
    }
  }

  if (stuckAgents.length > 0) {
    saveState(state);
  }

  return stuckAgents;
}

/**
 * Shutdown hive
 */
function shutdownHive(graceful = true) {
  const state = loadState();

  if (!state.hive_id) {
    return { success: false, reason: 'no_hive' };
  }

  if (graceful) {
    // Check for in-progress tasks
    const inProgress = Object.values(state.tasks || {}).filter(t => t.status === 'in_progress');
    if (inProgress.length > 0) {
      return {
        success: false,
        reason: 'tasks_in_progress',
        tasks: inProgress.map(t => t.id)
      };
    }
  }

  // Mark all agents as terminated
  for (const agentId of Object.keys(state.agents || {})) {
    state.agents[agentId].status = 'terminated';
  }

  // Clear hive ID to mark as shutdown
  const hiveId = state.hive_id;
  state.hive_id = null;
  state.shutdown_at = getTimestamp();

  saveState(state);
  log(`Hive ${hiveId} shutdown (graceful=${graceful})`);

  return { success: true, hive_id: hiveId };
}

/**
 * Handle PostToolUse for Task tool
 */
function handleTaskToolUse(toolInput, toolOutput) {
  const state = loadState();

  // Extract task info from tool input/output
  const description = toolInput.description || toolInput.task || '';
  const mode = toolInput.mode || 'async';

  // Check if this is spawning a new agent
  if (description.toLowerCase().includes('spawn') || mode === 'spawn') {
    const result = registerAgent(null, 'worker');
    if (result.success) {
      return {
        tracked: true,
        action: 'agent_spawned',
        agent_id: result.agent_id
      };
    }
  }

  // Register the task
  const taskResult = registerTask(description, 'normal', null);

  // Detect stuck agents periodically
  const stuckAgents = detectStuckAgents();

  return {
    tracked: true,
    action: 'task_registered',
    task_id: taskResult.task_id,
    stuck_agents: stuckAgents.length > 0 ? stuckAgents : undefined
  };
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
  const toolOutput = hookInput.tool_output || '';

  // Only process Task tool
  if (toolName !== 'Task') {
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  const result = handleTaskToolUse(toolInput, toolOutput);
  console.log(JSON.stringify(result));
  process.exit(0);
}

// Export for testing
module.exports = {
  loadState,
  saveState,
  generateAgentId,
  generateTaskId,
  initHive,
  registerAgent,
  updateAgentStatus,
  registerTask,
  startTask,
  completeTask,
  getStatus,
  detectStuckAgents,
  shutdownHive,
  handleTaskToolUse,
  HIVE_DIR,
  STATE_FILE,
  AGENT_TIMEOUT_MS,
  MAX_AGENTS
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
