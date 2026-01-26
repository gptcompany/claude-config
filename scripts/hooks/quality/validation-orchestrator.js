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
 * Returns true if config exists OR if we should use global defaults
 */
function hasValidationConfig(projectRoot) {
  const configPath = path.join(projectRoot, ".claude/validation/config.json");
  if (fs.existsSync(configPath)) {
    return true;
  }

  // Check for global config (enables validation for ALL projects)
  const globalConfig = path.join(
    process.env.HOME,
    ".claude/validation/global-config.json",
  );
  return fs.existsSync(globalConfig);
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
 * Extract modified file path from tool input
 */
function extractModifiedFile(data) {
  const toolInput = data.tool_input || {};

  // Write tool: file_path
  if (toolInput.file_path) {
    return toolInput.file_path;
  }

  // Edit tool: file_path
  if (toolInput.file_path) {
    return toolInput.file_path;
  }

  // MultiEdit: first file in edits array
  if (toolInput.edits && toolInput.edits.length > 0) {
    return toolInput.edits[0].file_path;
  }

  return null;
}

/**
 * Run validation asynchronously (fire and forget)
 */
function runValidationAsync(projectRoot, modifiedFile) {
  // Build command args
  const args = [ORCHESTRATOR_PATH, "1"];

  // Add --files if we have a modified file
  if (modifiedFile) {
    args.push("--files", modifiedFile);
  }

  // Spawn python process detached
  const child = spawn("python3", args, {
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
  const fileInfo = modifiedFile ? ` [${path.basename(modifiedFile)}]` : "";
  fs.appendFileSync(
    logPath,
    `${timestamp} Triggered Tier 1 validation for ${projectRoot}${fileInfo}\n`,
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

    // Extract modified file from tool input
    const modifiedFile = extractModifiedFile(data);

    // Run validation async (non-blocking)
    runValidationAsync(projectRoot, modifiedFile);

    // Exit successfully (don't block the tool)
    process.exit(0);
  } catch (err) {
    // On any error, exit silently (don't block workflow)
    process.exit(0);
  }
}

// Run
main();
