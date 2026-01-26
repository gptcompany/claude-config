#!/usr/bin/env node
/**
 * Validation Orchestrator Hook
 *
 * PostToolUse hook that runs ValidationOrchestrator on code changes.
 * Triggers on Write/Edit tools, runs Tier 1 (blockers) validation.
 *
 * Behavior:
 * - Runs async (non-blocking) to avoid slowing down workflow
 * - Warns on failures (doesn't block the tool)
 * - Only validates if .claude/validation/config.json exists
 * - Debounces multiple rapid edits (5 second cooldown)
 */

const fs = require("fs");
const path = require("path");
const { execSync, spawn } = require("child_process");

// Configuration
const ORCHESTRATOR_PATH = path.join(
  process.env.HOME,
  ".claude/templates/validation/orchestrator.py",
);
const DEBOUNCE_MS = 5000; // 5 second cooldown between validations
const LAST_RUN_FILE = "/tmp/validation-orchestrator-lastrun";

/**
 * Check if validation config exists in project
 */
function hasValidationConfig(projectRoot) {
  const configPath = path.join(projectRoot, ".claude/validation/config.json");
  return fs.existsSync(configPath);
}

/**
 * Get project root from git or cwd
 */
function getProjectRoot() {
  try {
    const result = execSync("git rev-parse --show-toplevel", {
      encoding: "utf8",
      timeout: 3000,
      stdio: ["pipe", "pipe", "pipe"],
    });
    return result.trim();
  } catch (err) {
    return process.cwd();
  }
}

/**
 * Check debounce - don't run too frequently
 */
function shouldRunValidation() {
  try {
    if (fs.existsSync(LAST_RUN_FILE)) {
      const lastRun = parseInt(fs.readFileSync(LAST_RUN_FILE, "utf8"), 10);
      const now = Date.now();
      if (now - lastRun < DEBOUNCE_MS) {
        return false; // Too soon
      }
    }
  } catch (err) {
    // Ignore errors, proceed with validation
  }
  return true;
}

/**
 * Update last run timestamp
 */
function updateLastRun() {
  try {
    fs.writeFileSync(LAST_RUN_FILE, Date.now().toString());
  } catch (err) {
    // Ignore
  }
}

/**
 * Run validation asynchronously (fire and forget)
 */
function runValidationAsync(projectRoot) {
  // Spawn python process detached
  const child = spawn("python3", [ORCHESTRATOR_PATH, "1"], {
    cwd: projectRoot,
    stdio: "ignore",
    detached: true,
  });

  child.unref(); // Don't wait for it

  // Log that we triggered validation
  const logPath = path.join(
    process.env.HOME,
    ".claude/logs/validation-hook.log",
  );
  const logDir = path.dirname(logPath);
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }

  const timestamp = new Date().toISOString();
  fs.appendFileSync(
    logPath,
    `${timestamp} Triggered Tier 1 validation for ${projectRoot}\n`,
  );
}

/**
 * Main hook logic
 */
function main() {
  try {
    // Read hook input from stdin
    let input = "";
    const stdin = fs.readFileSync(0, "utf8");
    input = stdin;

    const data = JSON.parse(input);

    // Only trigger on Write/Edit tools
    const toolName = data.tool_name || "";
    if (!["Write", "Edit", "MultiEdit"].includes(toolName)) {
      // Not a code modification tool
      process.exit(0);
    }

    // Get project root
    const projectRoot = getProjectRoot();

    // Check if project has validation config
    if (!hasValidationConfig(projectRoot)) {
      // No validation config, skip silently
      process.exit(0);
    }

    // Check debounce
    if (!shouldRunValidation()) {
      // Too soon since last run
      process.exit(0);
    }

    // Update last run timestamp
    updateLastRun();

    // Run validation async (non-blocking)
    runValidationAsync(projectRoot);

    // Exit successfully (don't block the tool)
    process.exit(0);
  } catch (err) {
    // On any error, exit silently (don't block workflow)
    process.exit(0);
  }
}

// Run
main();
