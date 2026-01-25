#!/usr/bin/env node
/**
 * TDD State Manager
 *
 * Manages TDD workflow state (IDLE, RED, GREEN, REFACTOR) for GSD integration.
 * State persists in ~/.claude/tdd-state.json.
 *
 * Usage:
 *   getState() - Get current TDD state
 *   setState(phase) - Set TDD phase
 *   clearState() - Clear TDD state
 *
 * CLI:
 *   node tdd-state.js get           - Print current state as JSON
 *   node tdd-state.js set RED       - Set phase to RED
 *   node tdd-state.js set GREEN     - Set phase to GREEN
 *   node tdd-state.js set REFACTOR  - Set phase to REFACTOR
 *   node tdd-state.js clear         - Clear state to IDLE
 *
 * Part of: Skills Port (Phase 15)
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

// State file location
const STATE_FILE = path.join(os.homedir(), ".claude", "tdd-state.json");

// TDD Phases
const PHASES = {
  IDLE: "IDLE",
  RED: "RED",
  GREEN: "GREEN",
  REFACTOR: "REFACTOR",
};

// Default state
const DEFAULT_STATE = {
  phase: PHASES.IDLE,
  startedAt: null,
  testFile: null,
  implFile: null,
  attempt: 0,
};

/**
 * Load TDD state from file
 * @returns {Object} Current state
 */
function getState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      const content = fs.readFileSync(STATE_FILE, "utf8");
      const state = JSON.parse(content);
      return { ...DEFAULT_STATE, ...state };
    }
  } catch {
    // Ignore errors, return default
  }
  return { ...DEFAULT_STATE };
}

/**
 * Save TDD state to file
 * @param {string} phase - Phase to set (RED, GREEN, REFACTOR)
 * @param {Object} extra - Additional state properties
 * @returns {Object} Updated state
 */
function setState(phase, extra = {}) {
  const validPhases = Object.values(PHASES);
  if (!validPhases.includes(phase)) {
    throw new Error(
      `Invalid phase: ${phase}. Valid: ${validPhases.join(", ")}`,
    );
  }

  const currentState = getState();
  const newState = {
    ...currentState,
    phase,
    ...extra,
  };

  // Set startedAt on first non-IDLE phase
  if (phase !== PHASES.IDLE && !newState.startedAt) {
    newState.startedAt = new Date().toISOString();
  }

  // Reset startedAt on IDLE
  if (phase === PHASES.IDLE) {
    newState.startedAt = null;
    newState.testFile = null;
    newState.implFile = null;
    newState.attempt = 0;
  }

  // Increment attempt on GREEN phase
  if (phase === PHASES.GREEN && currentState.phase === PHASES.RED) {
    newState.attempt = (currentState.attempt || 0) + 1;
  }

  // Ensure directory exists
  const stateDir = path.dirname(STATE_FILE);
  if (!fs.existsSync(stateDir)) {
    fs.mkdirSync(stateDir, { recursive: true });
  }

  fs.writeFileSync(STATE_FILE, JSON.stringify(newState, null, 2));
  return newState;
}

/**
 * Clear TDD state (set to IDLE)
 * @returns {Object} Reset state
 */
function clearState() {
  return setState(PHASES.IDLE);
}

/**
 * Track test file
 * @param {string} testFile - Path to test file
 */
function setTestFile(testFile) {
  const state = getState();
  setState(state.phase, { testFile });
}

/**
 * Track implementation file
 * @param {string} implFile - Path to implementation file
 */
function setImplFile(implFile) {
  const state = getState();
  setState(state.phase, { implFile });
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0] || "get";

  try {
    switch (command) {
      case "get":
        console.log(JSON.stringify(getState(), null, 2));
        break;

      case "set":
        const phase = (args[1] || "").toUpperCase();
        if (!phase) {
          console.error("Usage: tdd-state.js set <IDLE|RED|GREEN|REFACTOR>");
          process.exit(1);
        }
        const result = setState(phase);
        console.log(JSON.stringify(result, null, 2));
        break;

      case "clear":
        console.log(JSON.stringify(clearState(), null, 2));
        break;

      default:
        console.error(`Unknown command: ${command}`);
        console.error("Usage: tdd-state.js <get|set|clear>");
        process.exit(1);
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

module.exports = {
  getState,
  setState,
  clearState,
  setTestFile,
  setImplFile,
  PHASES,
};
