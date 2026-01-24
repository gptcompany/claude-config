#!/usr/bin/env node
/**
 * Task Checkpoint Hook - Auto-checkpoint after tool calls
 *
 * PostToolUse hook that automatically creates checkpoints after N
 * successful tool calls. Used for crash recovery and progress tracking.
 *
 * Hook type: PostToolUse
 *
 * Ported from: /media/sam/1TB/claude-hooks-shared/hooks/productivity/task-auto-checkpoint.py
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Configuration
const CHECKPOINTS_DIR = path.join(os.homedir(), '.claude', 'checkpoints');
const COUNTER_FILE = path.join(CHECKPOINTS_DIR, '.tool-counter');
const STATE_FILE = path.join(CHECKPOINTS_DIR, 'current-state.json');
const CHECKPOINT_INTERVAL = 5;  // Create checkpoint every N tool calls
const MIN_CHANGES_FOR_COMMIT = 3;  // Minimum files changed to trigger commit

/**
 * Ensure directory exists
 */
function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Get git changes statistics
 */
function getGitChanges() {
  try {
    // Check for any changes
    const statusResult = execSync('git status --porcelain', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 5000,
    });

    if (!statusResult.trim()) {
      return { hasChanges: false, files: 0, lines: 0 };
    }

    // Count changed files
    const changedFiles = statusResult.trim().split('\n').length;

    // Count changed lines
    let linesChanged = 0;
    try {
      const diffResult = execSync('git diff --stat', {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout: 5000,
      });

      // Parse lines changed from diff --stat
      const match = diffResult.match(/(\d+) insertion|(\d+) deletion/g);
      if (match) {
        for (const m of match) {
          const num = parseInt(m.match(/\d+/)[0], 10);
          linesChanged += num;
        }
      }
    } catch {
      // Ignore
    }

    return {
      hasChanges: true,
      files: changedFiles,
      lines: linesChanged,
    };
  } catch {
    return { hasChanges: false, files: 0, lines: 0 };
  }
}

/**
 * Get project name from git repo
 */
function getProjectName() {
  try {
    const result = execSync('git rev-parse --show-toplevel', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 2000,
    });
    return path.basename(result.trim());
  } catch {
    return path.basename(process.cwd());
  }
}

/**
 * Get current branch
 */
function getCurrentBranch() {
  try {
    const result = execSync('git branch --show-current', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 2000,
    });
    return result.trim();
  } catch {
    return 'unknown';
  }
}

/**
 * Get current commit hash (short)
 */
function getCurrentCommit() {
  try {
    const result = execSync('git rev-parse --short HEAD', {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 2000,
    });
    return result.trim();
  } catch {
    return 'unknown';
  }
}

/**
 * Load or initialize tool counter
 */
function loadCounter() {
  try {
    if (fs.existsSync(COUNTER_FILE)) {
      const data = fs.readFileSync(COUNTER_FILE, 'utf8');
      return parseInt(data.trim(), 10) || 0;
    }
  } catch {
    // Ignore
  }
  return 0;
}

/**
 * Save tool counter
 */
function saveCounter(count) {
  ensureDir(CHECKPOINTS_DIR);
  fs.writeFileSync(COUNTER_FILE, String(count));
}

/**
 * Load current state (files modified this session)
 */
function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      const content = fs.readFileSync(STATE_FILE, 'utf8');
      return JSON.parse(content);
    }
  } catch {
    // Ignore
  }
  return {
    toolCalls: [],
    filesModified: [],
    sessionStart: new Date().toISOString(),
  };
}

/**
 * Save current state
 */
function saveState(state) {
  ensureDir(CHECKPOINTS_DIR);
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Create checkpoint file
 */
function createCheckpoint(state, changes) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const project = getProjectName();
  const checkpointId = `checkpoint-${project}-${timestamp}`;
  const checkpointPath = path.join(CHECKPOINTS_DIR, `${checkpointId}.json`);

  const checkpoint = {
    id: checkpointId,
    timestamp: new Date().toISOString(),
    project: project,
    branch: getCurrentBranch(),
    commit: getCurrentCommit(),
    toolCallCount: state.toolCalls.length,
    filesModified: state.filesModified,
    recentTools: state.toolCalls.slice(-10),  // Last 10 tool calls
    gitChanges: changes,
  };

  fs.writeFileSync(checkpointPath, JSON.stringify(checkpoint, null, 2));
  return checkpointId;
}

/**
 * Create git commit for checkpoint
 */
function createGitCommit(checkpointId, changes) {
  try {
    // Stage all changes
    execSync('git add -A', {
      stdio: 'pipe',
      timeout: 5000,
    });

    // Create commit message
    const timestamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
    const commitMsg = `[Auto-Checkpoint] ${checkpointId}

Checkpoint created at ${timestamp}
Files changed: ${changes.files}
Lines changed: ${changes.lines}

Co-Authored-By: Claude <noreply@anthropic.com>`;

    execSync(`git commit -m "${commitMsg.replace(/"/g, '\\"')}"`, {
      stdio: 'pipe',
      timeout: 10000,
    });

    return true;
  } catch {
    return false;
  }
}

/**
 * Read JSON from stdin
 */
async function readStdinJson() {
  return new Promise((resolve, reject) => {
    let data = '';

    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => {
      data += chunk;
    });

    process.stdin.on('end', () => {
      try {
        if (data.trim()) {
          resolve(JSON.parse(data));
        } else {
          resolve({});
        }
      } catch (err) {
        reject(err);
      }
    });

    process.stdin.on('error', reject);

    // Timeout for stdin read
    setTimeout(() => {
      resolve({});
    }, 1000);
  });
}

/**
 * Main function
 */
async function main() {
  try {
    const input = await readStdinJson();

    const toolName = input.tool_name || '';
    const toolInput = input.tool_input || {};
    const toolResult = input.tool_result;

    // Skip non-modifying tools
    const modifyingTools = ['Write', 'Edit', 'MultiEdit', 'Bash', 'Task'];
    if (!modifyingTools.includes(toolName)) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Check if tool was successful (no error in result)
    let success = true;
    if (toolResult) {
      const resultStr = String(toolResult).toLowerCase();
      success = !resultStr.includes('error') && !resultStr.includes('failed');
    }

    if (!success) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Load and update state
    const state = loadState();
    const counter = loadCounter() + 1;
    saveCounter(counter);

    // Track this tool call
    state.toolCalls.push({
      tool: toolName,
      timestamp: new Date().toISOString(),
    });

    // Track modified files
    const filePath = toolInput.file_path;
    if (filePath && !state.filesModified.includes(filePath)) {
      state.filesModified.push(filePath);
    }

    // Save state
    saveState(state);

    // Check if we should create a checkpoint
    if (counter % CHECKPOINT_INTERVAL !== 0) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Get git changes
    const changes = getGitChanges();

    if (!changes.hasChanges || changes.files < MIN_CHANGES_FOR_COMMIT) {
      // Not enough changes for checkpoint
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Create checkpoint
    const checkpointId = createCheckpoint(state, changes);

    // Optionally create git commit (disabled by default - uncomment to enable)
    // const committed = createGitCommit(checkpointId, changes);

    // Output notification
    const output = {
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        message: `Checkpoint created: ${checkpointId} (${changes.files} files, ${changes.lines} lines)`,
      },
    };

    console.log(JSON.stringify(output));
    process.exit(0);
  } catch (err) {
    // Any error, fail open
    console.log(JSON.stringify({}));
    process.exit(0);
  }
}

main();
