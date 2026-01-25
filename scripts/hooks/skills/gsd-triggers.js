#!/usr/bin/env node
/**
 * GSD Triggers Hook
 *
 * PostToolUse hook that triggers skills based on GSD workflow events.
 * Integrates TDD, verification, coding standards, and eval skills.
 *
 * Triggers:
 * - plan-created: When PLAN.md written -> suggest TDD workflow
 * - test-written: When test file written -> track as eval attempt
 * - impl-written: When impl file written in GREEN phase -> run tests
 * - plan-complete: When SUMMARY.md created -> run verification
 *
 * Hook type: PostToolUse (for Write, Edit)
 *
 * Part of: Skills Port (Phase 15)
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// Import TDD state
let tddState;
try {
  tddState = require("./tdd/tdd-state");
} catch {
  // Fallback if module not found
  tddState = {
    PHASES: { IDLE: "IDLE", RED: "RED", GREEN: "GREEN", REFACTOR: "REFACTOR" },
    getState: () => ({ phase: "IDLE" }),
    setState: () => {},
  };
}

// Import verification runner
let VerificationRunner;
try {
  VerificationRunner =
    require("./verification/verification-runner").VerificationRunner;
} catch {
  // Fallback if module not found
  VerificationRunner = null;
}

// Import eval harness (may not exist yet - 15-04 parallel)
let EvalHarness;
try {
  EvalHarness = require("./eval/eval-harness").EvalHarness;
} catch {
  // Expected during 15-05 if 15-04 not complete
  EvalHarness = null;
}

const { PHASES } = tddState;

/**
 * Trigger definitions
 */
const TRIGGERS = {
  // When a PLAN.md file is written -> suggest TDD workflow
  "plan-created": {
    match: (filePath) => filePath.includes("PLAN.md"),
    action: "suggest-tdd",
  },

  // When test file written -> track as eval attempt
  "test-written": {
    match: (filePath) => isTestFile(filePath),
    action: "track-eval",
  },

  // When implementation file written in TDD mode -> run tests
  "impl-written": {
    match: (filePath, state) =>
      state.phase === PHASES.GREEN &&
      !isTestFile(filePath) &&
      isCodeFile(filePath),
    action: "run-tests",
  },

  // When SUMMARY.md created -> run verification
  "plan-complete": {
    match: (filePath) => filePath.includes("SUMMARY.md"),
    action: "run-verification",
  },
};

/**
 * Check if file is a test file
 * @param {string} filePath - File path to check
 * @returns {boolean} True if test file
 */
function isTestFile(filePath) {
  const patterns = [
    /\.(test|spec)\.(js|ts|jsx|tsx|mjs)$/,
    /test_.*\.py$/,
    /_test\.py$/,
    /_test\.go$/,
    /Test\.java$/,
    /_spec\.rb$/,
  ];
  return patterns.some((pattern) => pattern.test(filePath));
}

/**
 * Check if file is a code file (not config, docs, etc.)
 * @param {string} filePath - File path to check
 * @returns {boolean} True if code file
 */
function isCodeFile(filePath) {
  const codeExtensions = [
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".mjs",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".rb",
  ];
  const ext = path.extname(filePath).toLowerCase();
  return codeExtensions.includes(ext);
}

/**
 * Read JSON from stdin
 */
async function readStdinJson() {
  return new Promise((resolve, reject) => {
    let data = "";

    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
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
    setTimeout(() => resolve({}), 1000);
  });
}

/**
 * Handle a trigger action
 * @param {string} name - Trigger name
 * @param {string} action - Action to perform
 * @param {string} filePath - File that triggered
 * @param {Object} state - TDD state
 */
async function handleTrigger(name, action, filePath, state) {
  const messages = [];

  switch (action) {
    case "suggest-tdd":
      // Only suggest if not already in TDD mode
      if (state.phase === PHASES.IDLE) {
        messages.push(
          "New plan detected. Consider starting TDD workflow: /tdd:red",
        );
      }
      break;

    case "track-eval":
      // Record as eval attempt if in TDD mode
      if (state.phase !== PHASES.IDLE) {
        const baseName = path.basename(filePath);
        messages.push(`Test written: ${baseName}`);

        // Track with eval harness if available
        if (EvalHarness) {
          try {
            const harness = new EvalHarness({ attempt: state.attempt || 1 });
            // Just note the test file, don't run yet
            harness.setTestFile(filePath);
          } catch {
            // Ignore eval harness errors
          }
        }
      }
      break;

    case "run-tests":
      // Auto-run tests when implementation written in GREEN phase
      messages.push(`Implementation updated. Running tests...`);

      // Try to run tests
      let testsPassed = false;
      let testOutput = "";

      try {
        // Detect project type and run appropriate test command
        const cwd = process.cwd();
        let testCmd = null;

        if (fs.existsSync(path.join(cwd, "package.json"))) {
          testCmd = "npm test --if-present 2>&1 || true";
        } else if (
          fs.existsSync(path.join(cwd, "pytest.ini")) ||
          fs.existsSync(path.join(cwd, "setup.py")) ||
          fs.existsSync(path.join(cwd, "pyproject.toml"))
        ) {
          testCmd = "python -m pytest -x --tb=short 2>&1 || true";
        } else if (fs.existsSync(path.join(cwd, "go.mod"))) {
          testCmd = "go test ./... 2>&1 || true";
        }

        if (testCmd) {
          testOutput = execSync(testCmd, {
            cwd,
            encoding: "utf8",
            timeout: 60000,
            stdio: ["pipe", "pipe", "pipe"],
          });

          // Check if tests passed (heuristic)
          testsPassed =
            /passed|ok|success/i.test(testOutput) &&
            !/failed|error/i.test(testOutput);
        }
      } catch (err) {
        testOutput = err.stdout || err.stderr || err.message;
        testsPassed = false;
      }

      if (testsPassed) {
        messages.push("Tests passing! Ready to: /tdd:refactor");

        // Track with eval harness
        if (EvalHarness) {
          try {
            const harness = new EvalHarness({ attempt: state.attempt || 1 });
            harness.recordPass();
          } catch {
            // Ignore
          }
        }
      } else {
        // Extract failure count if possible
        const failMatch = testOutput.match(/(\d+)\s+(failed|failures)/i);
        const failCount = failMatch ? failMatch[1] : "some";
        messages.push(`Tests failing: ${failCount} failed. Keep implementing.`);
      }
      break;

    case "run-verification":
      messages.push("Plan complete. Running verification loop...");

      if (VerificationRunner) {
        try {
          const runner = new VerificationRunner({
            skip: ["security"], // Quick verify
            quiet: true,
          });
          const result = runner.run();

          if (result.status === "READY") {
            messages.push("Verification passed!");
          } else if (result.status === "BLOCKED") {
            messages.push(`Verification blocked at: ${result.failedAt}`);
          } else {
            messages.push(`Verification has issues (${result.status})`);
          }
        } catch (err) {
          messages.push(`Could not run verification: ${err.message}`);
        }
      } else {
        messages.push("Verification runner not available. Run manually:");
        messages.push(
          "  node ~/.claude/scripts/hooks/skills/verification/verification-runner.js",
        );
      }
      break;
  }

  return messages;
}

/**
 * Main hook function
 */
async function main() {
  try {
    const input = await readStdinJson();
    const { tool_name, tool_input, tool_result } = input;

    // Only trigger on successful Write/Edit/MultiEdit
    if (!["Write", "Edit", "MultiEdit"].includes(tool_name)) {
      console.log(JSON.stringify({}));
      return;
    }

    // Check for errors in tool result
    if (tool_result?.error) {
      console.log(JSON.stringify({}));
      return;
    }

    const filePath = tool_input?.file_path || "";
    if (!filePath) {
      console.log(JSON.stringify({}));
      return;
    }

    // Get TDD state
    const state = tddState.getState();

    // Check each trigger
    const allMessages = [];

    for (const [name, trigger] of Object.entries(TRIGGERS)) {
      try {
        if (trigger.match(filePath, state)) {
          const messages = await handleTrigger(
            name,
            trigger.action,
            filePath,
            state,
          );
          allMessages.push(...messages);
          break; // Only one trigger per event
        }
      } catch {
        // Ignore individual trigger errors
      }
    }

    // Output messages to stderr (hook messages)
    if (allMessages.length > 0) {
      const prefix = "[GSD]";
      allMessages.forEach((msg) => {
        console.error(`${prefix} ${msg}`);
      });
    }

    // Output empty response (pass-through)
    console.log(JSON.stringify({}));
  } catch (err) {
    // Fail silently, pass through
    console.log(JSON.stringify({}));
  }
}

// Run main if called directly
if (require.main === module) {
  main().catch(() => {
    console.log(JSON.stringify({}));
  });
}

module.exports = { TRIGGERS, isTestFile, isCodeFile, handleTrigger };
