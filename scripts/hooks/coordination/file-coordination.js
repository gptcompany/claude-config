#!/usr/bin/env node
/**
 * File Coordination Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/coordination/file_claim.py
 * and /media/sam/1TB/claude-hooks-shared/hooks/coordination/file_release.py
 *
 * PreToolUse hook for Write|Edit|MultiEdit tools that:
 * - Claims files before edit operations to prevent conflicts
 * - Releases claims after successful edits
 * - Blocks if file is claimed by another agent
 *
 * Claims stored in ~/.claude/coordination/claims.json
 * Format: {file, agent, timestamp, expiry}
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const COORDINATION_DIR = path.join(HOME_DIR, '.claude', 'coordination');
const CLAIMS_FILE = path.join(COORDINATION_DIR, 'claims.json');
const LOG_FILE = path.join(COORDINATION_DIR, 'coordination.log');
const SESSION_STATE_FILE = path.join(COORDINATION_DIR, 'file_claims_state.json');

// Claim expiry time in milliseconds (5 minutes)
const CLAIM_EXPIRY_MS = 5 * 60 * 1000;

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
    fs.appendFileSync(LOG_FILE, `${getTimestamp()} [file-coordination] ${msg}\n`);
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
 * Load claims from file
 */
function loadClaims() {
  ensureDir(COORDINATION_DIR);
  if (fs.existsSync(CLAIMS_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(CLAIMS_FILE, 'utf8'));
    } catch (err) {
      return { claims: {} };
    }
  }
  return { claims: {} };
}

/**
 * Save claims to file
 */
function saveClaims(claims) {
  ensureDir(COORDINATION_DIR);
  fs.writeFileSync(CLAIMS_FILE, JSON.stringify(claims, null, 2));
}

/**
 * Load session state (our claimed files)
 */
function loadSessionState() {
  if (fs.existsSync(SESSION_STATE_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(SESSION_STATE_FILE, 'utf8'));
    } catch (err) {}
  }
  return { claimedFiles: {} };
}

/**
 * Save session state
 */
function saveSessionState(state) {
  ensureDir(COORDINATION_DIR);
  fs.writeFileSync(SESSION_STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Clean up expired claims
 */
function cleanExpiredClaims(claims) {
  const now = Date.now();
  const cleaned = { claims: {} };

  for (const [file, claim] of Object.entries(claims.claims || {})) {
    const expiry = new Date(claim.expiry).getTime();
    if (expiry > now) {
      cleaned.claims[file] = claim;
    } else {
      log(`Expired claim removed: ${file} (was held by ${claim.agent})`);
    }
  }

  return cleaned;
}

/**
 * Extract and normalize file path from tool input
 */
function extractFilePath(toolInput) {
  const filePath = toolInput.file_path || toolInput.path;
  if (!filePath) return null;
  return path.resolve(filePath);
}

/**
 * Claim a file
 */
function claimFile(filePath, sessionId) {
  const claims = cleanExpiredClaims(loadClaims());
  const sessionState = loadSessionState();
  const now = new Date();
  const expiry = new Date(now.getTime() + CLAIM_EXPIRY_MS);

  // Check if file is already claimed by us
  if (sessionState.claimedFiles && sessionState.claimedFiles[filePath]) {
    log(`Already claimed by us: ${filePath}`);
    // Refresh the claim expiry
    claims.claims[filePath] = {
      file: filePath,
      agent: `agent:${sessionId}:editor`,
      timestamp: getTimestamp(),
      expiry: expiry.toISOString()
    };
    saveClaims(claims);
    return { success: true, reason: 'already_claimed_by_us' };
  }

  // Check if file is claimed by another agent
  const existingClaim = claims.claims[filePath];
  if (existingClaim) {
    const claimAgent = existingClaim.agent || 'unknown';
    const ourAgent = `agent:${sessionId}:editor`;

    if (claimAgent !== ourAgent) {
      log(`File claimed by another agent: ${filePath} -> ${claimAgent}`);
      return { success: false, reason: `File is claimed by ${claimAgent}`, existingClaim };
    }
  }

  // Claim the file
  claims.claims[filePath] = {
    file: filePath,
    agent: `agent:${sessionId}:editor`,
    timestamp: getTimestamp(),
    expiry: expiry.toISOString()
  };
  saveClaims(claims);

  // Update session state
  sessionState.claimedFiles = sessionState.claimedFiles || {};
  sessionState.claimedFiles[filePath] = {
    claimedAt: getTimestamp(),
    sessionId
  };
  saveSessionState(sessionState);

  log(`Claimed file: ${filePath}`);
  return { success: true, reason: 'claimed' };
}

/**
 * Release a file claim
 */
function releaseFile(filePath, sessionId) {
  const claims = loadClaims();
  const sessionState = loadSessionState();

  // Check if we have this file claimed
  if (!sessionState.claimedFiles || !sessionState.claimedFiles[filePath]) {
    log(`File not in our claims, skipping release: ${filePath}`);
    return { success: false, reason: 'not_our_claim' };
  }

  // Remove from global claims
  if (claims.claims[filePath]) {
    delete claims.claims[filePath];
    saveClaims(claims);
  }

  // Remove from session state
  delete sessionState.claimedFiles[filePath];
  saveSessionState(sessionState);

  log(`Released file: ${filePath}`);
  return { success: true, reason: 'released' };
}

/**
 * Get all active claims
 */
function getActiveClaims() {
  const claims = cleanExpiredClaims(loadClaims());
  return Object.values(claims.claims || {});
}

/**
 * Get files claimed by this session
 */
function getSessionClaims() {
  const sessionState = loadSessionState();
  return Object.keys(sessionState.claimedFiles || {});
}

/**
 * Handle PreToolUse - claim file before edit
 */
function handlePreToolUse(toolInput) {
  const filePath = extractFilePath(toolInput);
  if (!filePath) {
    log('No file_path found in tool_input, allowing operation');
    return {};
  }

  const sessionId = getSessionId();
  const result = claimFile(filePath, sessionId);

  if (!result.success) {
    // Block the edit
    return {
      decision: 'block',
      reason: result.reason
    };
  }

  // Allow the edit
  return {};
}

/**
 * Handle PostToolUse - release file after edit (optional)
 */
function handlePostToolUse(toolInput, autoRelease = false) {
  if (!autoRelease) {
    // Don't auto-release by default - let claims expire
    return {};
  }

  const filePath = extractFilePath(toolInput);
  if (!filePath) {
    return {};
  }

  const sessionId = getSessionId();
  releaseFile(filePath, sessionId);
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
  const hookType = hookInput.hook_type || 'pre'; // 'pre' or 'post'

  // Only process Edit/Write/MultiEdit
  if (!['Write', 'Edit', 'MultiEdit'].includes(toolName)) {
    console.log(JSON.stringify({}));
    process.exit(0);
  }

  let result;
  if (hookType === 'post') {
    result = handlePostToolUse(toolInput, false);
  } else {
    result = handlePreToolUse(toolInput);
  }

  console.log(JSON.stringify(result));
  process.exit(0);
}

// Export for testing
module.exports = {
  getSessionId,
  loadClaims,
  saveClaims,
  loadSessionState,
  saveSessionState,
  cleanExpiredClaims,
  claimFile,
  releaseFile,
  getActiveClaims,
  getSessionClaims,
  handlePreToolUse,
  handlePostToolUse,
  extractFilePath,
  COORDINATION_DIR,
  CLAIMS_FILE,
  SESSION_STATE_FILE,
  CLAIM_EXPIRY_MS
};

// Run if executed directly
if (require.main === module) {
  main().catch(err => {
    console.error(err);
    console.log(JSON.stringify({}));
    process.exit(0);
  });
}
