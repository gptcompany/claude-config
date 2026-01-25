#!/usr/bin/env node
/**
 * Coding Standards Hook - PreToolUse hook for code quality enforcement
 *
 * Enforces coding standards by detecting anti-patterns before Write/Edit
 * operations are allowed to proceed. Supports warn and block modes.
 *
 * Hook type: PreToolUse (for Write, Edit, MultiEdit)
 *
 * Ported from: /media/sam/1TB/everything-claude-code/skills/coding-standards/SKILL.md
 */

const fs = require("fs");
const path = require("path");
const { checkPatterns, detectFileType } = require("./patterns");

// Config path
const CONFIG_PATH = path.join(
  process.env.HOME || "",
  ".claude",
  "standards-config.json",
);

// Default configuration
const DEFAULT_CONFIG = {
  enabled: true,
  mode: "warn", // 'warn' | 'block' | 'off'
  excludePaths: [
    "node_modules",
    "dist",
    "build",
    ".git",
    "vendor",
    "venv",
    ".venv",
    "__pycache__",
    ".next",
    "coverage",
    ".claude/checkpoints",
  ],
};

/**
 * Load configuration from file
 * @returns {Object} Configuration merged with defaults
 */
function loadConfig() {
  try {
    const configData = fs.readFileSync(CONFIG_PATH, "utf8");
    const userConfig = JSON.parse(configData);
    return { ...DEFAULT_CONFIG, ...userConfig };
  } catch {
    return DEFAULT_CONFIG;
  }
}

/**
 * Check if file path should be excluded
 * @param {string} filePath - File path to check
 * @param {string[]} excludePaths - Paths to exclude
 * @returns {boolean} - True if should be excluded
 */
function isExcludedPath(filePath, excludePaths) {
  if (!filePath) return true;

  const normalizedPath = filePath.replace(/\\/g, "/");
  return excludePaths.some((excludePath) =>
    normalizedPath.includes(excludePath),
  );
}

/**
 * Read JSON from stdin
 * @returns {Promise<Object>} Parsed JSON
 */
async function readStdinJson() {
  return new Promise((resolve, reject) => {
    let data = "";

    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });

    process.stdin.on("end", () => {
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

    process.stdin.on("error", reject);

    // Timeout for stdin read
    setTimeout(() => {
      resolve({});
    }, 3000);
  });
}

/**
 * Format issues for display
 * @param {Array} issues - Array of detected issues
 * @param {string} filePath - File being checked
 * @returns {string} - Formatted issue text
 */
function formatIssues(issues, filePath) {
  const byLevel = { error: [], warn: [], info: [] };
  issues.forEach((i) => {
    if (byLevel[i.severity]) {
      byLevel[i.severity].push(i);
    }
  });

  let text = `File: ${path.basename(filePath)}\n`;

  if (byLevel.error.length > 0) {
    text += "\nERRORS (must fix):\n";
    byLevel.error.forEach((i) => {
      text += `  L${i.line}: ${i.message}\n    ${i.content}\n`;
    });
  }

  if (byLevel.warn.length > 0) {
    text += "\nWARNINGS:\n";
    byLevel.warn.forEach((i) => {
      text += `  L${i.line}: ${i.message}\n`;
    });
  }

  if (byLevel.info.length > 0) {
    text += "\nINFO:\n";
    byLevel.info.forEach((i) => {
      text += `  L${i.line}: ${i.message}\n`;
    });
  }

  return text;
}

/**
 * Get content to check based on tool type
 * @param {string} toolName - Tool being used
 * @param {Object} toolInput - Tool input parameters
 * @returns {string|null} - Content to check or null
 */
function getContentToCheck(toolName, toolInput) {
  if (toolName === "Write") {
    return toolInput.content || "";
  }

  if (toolName === "Edit") {
    return toolInput.new_string || "";
  }

  if (toolName === "MultiEdit") {
    // Check all edits
    const edits = toolInput.edits || [];
    return edits.map((e) => e.new_string || "").join("\n");
  }

  return null;
}

/**
 * Main function
 */
async function main() {
  try {
    const config = loadConfig();

    // Check if disabled
    if (!config.enabled || config.mode === "off") {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    const input = await readStdinJson();
    const { tool_name, tool_input } = input;

    // Only check Write, Edit, MultiEdit
    if (!["Write", "Edit", "MultiEdit"].includes(tool_name)) {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    const filePath = tool_input?.file_path || "";

    // Check if path is excluded
    if (isExcludedPath(filePath, config.excludePaths)) {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    // Check if file type is supported
    if (!detectFileType(filePath)) {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    // Get content to check
    const content = getContentToCheck(tool_name, tool_input);
    if (!content) {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    // Check for patterns
    const { passed, issues } = checkPatterns(content, filePath);

    // No issues - allow
    if (issues.length === 0) {
      console.log(JSON.stringify({ decision: "allow" }));
      return;
    }

    // Format issues
    const issueText = formatIssues(issues, filePath);

    // Block mode with errors
    if (!passed && config.mode === "block") {
      console.log(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            decision: "block",
            reason: `CODING STANDARDS VIOLATION\n\n${issueText}\n\nFix the error-level issues to proceed.`,
          },
        }),
      );
      return;
    }

    // Warn mode or passed with warnings
    console.log(
      JSON.stringify({
        decision: "allow",
        message: `Standards check:\n${issueText}`,
      }),
    );
  } catch (err) {
    // Fail open - any error, allow the operation
    console.log(JSON.stringify({ decision: "allow" }));
  }
}

main();
