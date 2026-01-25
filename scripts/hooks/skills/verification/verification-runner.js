#!/usr/bin/env node
/**
 * Verification Runner
 *
 * Sequential verification runner with 6-phase pipeline:
 * 1. Build - Compile/transpile code
 * 2. Type Check - Static type analysis
 * 3. Lint - Code quality checks
 * 4. Tests - Run test suites
 * 5. Security - Vulnerability scanning
 * 6. Diff - Show pending changes
 *
 * Features:
 * - Fail-fast on critical phases (build, typecheck, test)
 * - Rich terminal output with colors and progress
 * - Multi-language support via phases.js
 * - Skip phases via --skip=<phase> option
 *
 * Part of: Skills Port (Phase 15)
 * Source: ECC verification-loop skill
 */

const { execSync } = require("child_process");
const { PHASES, detectProjectType, getPhaseCommand } = require("./phases");

// ANSI color codes
const COLORS = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  white: "\x1b[37m",
  bgRed: "\x1b[41m",
  bgGreen: "\x1b[42m",
  bgYellow: "\x1b[43m",
};

// Status icons
const ICONS = {
  pass: "\u2713", // checkmark
  fail: "\u2717", // X
  skip: "\u25cb", // circle
  running: "\u25cf", // filled circle
};

/**
 * Verification Runner Class
 *
 * Runs verification phases sequentially with fail-fast logic.
 */
class VerificationRunner {
  /**
   * Create a new verification runner
   *
   * @param {Object} options - Runner options
   * @param {Object} options.projectType - Override project type detection
   * @param {Array} options.skip - Phase names to skip
   * @param {boolean} options.verbose - Show full output
   * @param {boolean} options.quiet - Suppress all output except errors
   * @param {boolean} options.noColor - Disable ANSI colors
   * @param {string} options.cwd - Working directory
   */
  constructor(options = {}) {
    this.cwd = options.cwd || process.cwd();
    this.projectInfo = options.projectType || detectProjectType(this.cwd);
    this.skipPhases = options.skip || [];
    this.verbose = options.verbose || false;
    this.quiet = options.quiet || false;
    this.noColor = options.noColor || false;
    this.results = [];
    this.startTime = null;
  }

  /**
   * Apply color to text if colors are enabled
   */
  color(colorName, text) {
    if (this.noColor) return text;
    return `${COLORS[colorName]}${text}${COLORS.reset}`;
  }

  /**
   * Run a single verification phase
   *
   * @param {Object} phase - Phase configuration
   * @returns {Object} Phase result { name, status, output, duration, exitCode }
   */
  runPhase(phase) {
    // Check if phase should be skipped
    if (this.skipPhases.includes(phase.name)) {
      return {
        name: phase.name,
        displayName: phase.displayName,
        status: "skipped",
        output: "Skipped by user",
        duration: 0,
      };
    }

    // Get command for this project type
    const command = getPhaseCommand(phase, this.projectInfo);
    if (!command) {
      return {
        name: phase.name,
        displayName: phase.displayName,
        status: "skipped",
        output: `No command for project type: ${this.projectInfo.type}`,
        duration: 0,
      };
    }

    const startTime = Date.now();

    try {
      const output = execSync(command, {
        cwd: this.cwd,
        encoding: "utf8",
        timeout: phase.timeout,
        stdio: ["pipe", "pipe", "pipe"],
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer
        shell: true,
      });

      return {
        name: phase.name,
        displayName: phase.displayName,
        status: "pass",
        output: this.truncateOutput(output, phase.outputLimit),
        duration: Date.now() - startTime,
        command,
      };
    } catch (err) {
      // Handle different error types
      const output = err.stdout
        ? err.stdout.toString()
        : err.stderr
          ? err.stderr.toString()
          : err.message;

      return {
        name: phase.name,
        displayName: phase.displayName,
        status: "fail",
        output: this.truncateOutput(output, phase.outputLimit),
        duration: Date.now() - startTime,
        exitCode: err.status || 1,
        command,
      };
    }
  }

  /**
   * Truncate output to a maximum number of lines
   */
  truncateOutput(output, limit) {
    if (!output) return "";
    const lines = output.split("\n");
    if (lines.length <= limit) return output.trim();

    const truncated = lines.slice(0, limit).join("\n");
    return `${truncated}\n... (${lines.length - limit} more lines)`;
  }

  /**
   * Run all verification phases
   *
   * @returns {Object} Overall result { status, failedAt, results, duration }
   */
  run() {
    this.startTime = Date.now();
    this.results = [];

    if (!this.quiet) {
      this.printHeader();
    }

    for (const phase of PHASES) {
      // Print running status
      if (!this.quiet) {
        this.printPhaseStart(phase);
      }

      // Execute phase
      const result = this.runPhase(phase);
      this.results.push(result);

      // Print result
      if (!this.quiet) {
        this.printPhaseResult(result);
      }

      // Handle fail-fast
      if (result.status === "fail" && phase.failFast) {
        if (!this.quiet) {
          this.printFailure(result);
        }

        return {
          status: "BLOCKED",
          failedAt: phase.name,
          results: this.results,
          duration: Date.now() - this.startTime,
        };
      }
    }

    // Print summary
    if (!this.quiet) {
      this.printSummary();
    }

    // Determine overall status
    const hasFails = this.results.some((r) => r.status === "fail");

    return {
      status: hasFails ? "ISSUES" : "READY",
      results: this.results,
      duration: Date.now() - this.startTime,
    };
  }

  /**
   * Format header with project info
   */
  printHeader() {
    const typeInfo = this.projectInfo.typescript
      ? `${this.projectInfo.type}+ts`
      : this.projectInfo.type;

    const line = "=".repeat(50);
    console.log("");
    console.log(this.color("cyan", line));
    console.log(
      this.color("cyan", `   VERIFICATION LOOP`) +
        this.color("dim", ` (${typeInfo})`),
    );
    console.log(this.color("cyan", line));
    console.log("");
  }

  /**
   * Print phase start indicator
   */
  printPhaseStart(phase) {
    const icon = this.color("yellow", ICONS.running);
    process.stderr.write(`${icon} ${phase.displayName}... `);
  }

  /**
   * Print phase result
   */
  printPhaseResult(result) {
    // Clear the "running" line
    process.stderr.write("\r\x1b[K");

    let icon, colorName;

    switch (result.status) {
      case "pass":
        icon = ICONS.pass;
        colorName = "green";
        break;
      case "fail":
        icon = ICONS.fail;
        colorName = "red";
        break;
      case "skipped":
        icon = ICONS.skip;
        colorName = "yellow";
        break;
      default:
        icon = "?";
        colorName = "white";
    }

    const duration =
      result.duration > 0 ? this.color("dim", ` (${result.duration}ms)`) : "";
    console.log(
      `${this.color(colorName, icon)} ${result.displayName}${duration}`,
    );

    // Show output in verbose mode for all results, or always for failures
    if (this.verbose && result.output && result.status !== "skipped") {
      const lines = result.output.split("\n").slice(0, 10);
      lines.forEach((line) => {
        console.log(this.color("dim", `   ${line}`));
      });
    }
  }

  /**
   * Print failure details
   */
  printFailure(result) {
    console.log("");
    console.log(this.color("red", `${"=".repeat(50)}`));
    console.log(
      this.color("red", `   FAILED: ${result.displayName}`) +
        (result.exitCode
          ? this.color("dim", ` (exit ${result.exitCode})`)
          : ""),
    );
    console.log(this.color("red", `${"=".repeat(50)}`));
    console.log("");

    if (result.command) {
      console.log(this.color("dim", `Command: ${result.command}`));
      console.log("");
    }

    if (result.output) {
      console.log(result.output);
    }

    console.log("");
    console.log(this.color("yellow", "Fix this issue before continuing."));
    console.log("");
  }

  /**
   * Print summary at the end
   */
  printSummary() {
    const passed = this.results.filter((r) => r.status === "pass").length;
    const failed = this.results.filter((r) => r.status === "fail").length;
    const skipped = this.results.filter((r) => r.status === "skipped").length;
    const duration = Date.now() - this.startTime;

    console.log("");
    console.log(this.color("dim", "-".repeat(50)));

    const parts = [];
    if (passed > 0) parts.push(this.color("green", `${passed} passed`));
    if (failed > 0) parts.push(this.color("red", `${failed} failed`));
    if (skipped > 0) parts.push(this.color("yellow", `${skipped} skipped`));

    console.log(`Summary: ${parts.join(", ")}`);
    console.log(this.color("dim", `Duration: ${duration}ms`));

    if (failed === 0) {
      console.log("");
      console.log(this.color("green", `${ICONS.pass} READY for commit`));
    } else {
      console.log("");
      console.log(
        this.color("yellow", `${ICONS.fail} Issues found - review above`),
      );
    }

    console.log("");
  }

  /**
   * Get results as JSON
   */
  toJSON() {
    return {
      projectType: this.projectInfo.type,
      results: this.results.map((r) => ({
        name: r.name,
        status: r.status,
        duration: r.duration,
        exitCode: r.exitCode,
      })),
      summary: {
        passed: this.results.filter((r) => r.status === "pass").length,
        failed: this.results.filter((r) => r.status === "fail").length,
        skipped: this.results.filter((r) => r.status === "skipped").length,
        duration: Date.now() - this.startTime,
      },
    };
  }
}

/**
 * Parse command line arguments
 */
function parseArgs(args) {
  const options = {
    skip: [],
    verbose: false,
    quiet: false,
    noColor: false,
    json: false,
    help: false,
  };

  for (const arg of args) {
    if (arg.startsWith("--skip=")) {
      options.skip.push(arg.split("=")[1]);
    } else if (arg === "--skip-security") {
      options.skip.push("security");
    } else if (arg === "--verbose" || arg === "-v") {
      options.verbose = true;
    } else if (arg === "--quiet" || arg === "-q") {
      options.quiet = true;
    } else if (arg === "--no-color") {
      options.noColor = true;
    } else if (arg === "--json") {
      options.json = true;
      options.quiet = true;
    } else if (arg === "--help" || arg === "-h") {
      options.help = true;
    }
  }

  return options;
}

/**
 * Print help message
 */
function printHelp() {
  console.log(`
Verification Runner - 6-phase sequential verification

Usage: verification-runner [options]

Options:
  --skip=<phase>      Skip a specific phase (build, typecheck, lint, test, security, diff)
  --skip-security     Shortcut for --skip=security
  --verbose, -v       Show command output for all phases
  --quiet, -q         Suppress all output except errors
  --no-color          Disable ANSI colors
  --json              Output results as JSON
  --help, -h          Show this help message

Phases:
  1. build      Compile/transpile code (fail-fast)
  2. typecheck  Static type analysis (fail-fast)
  3. lint       Code quality checks
  4. test       Run test suite (fail-fast)
  5. security   Vulnerability scanning
  6. diff       Show pending git changes

Examples:
  verification-runner                   # Run all phases
  verification-runner --skip=security   # Skip security scan
  verification-runner --verbose         # Show detailed output
  verification-runner --json            # Output as JSON

Exit codes:
  0   All phases passed (READY)
  1   One or more phases failed (BLOCKED or ISSUES)
`);
}

// CLI entry point
if (require.main === module) {
  const args = process.argv.slice(2);
  const options = parseArgs(args);

  if (options.help) {
    printHelp();
    process.exit(0);
  }

  const runner = new VerificationRunner(options);
  const result = runner.run();

  if (options.json) {
    console.log(JSON.stringify(runner.toJSON(), null, 2));
  }

  process.exit(result.status === "READY" ? 0 : 1);
}

module.exports = { VerificationRunner };
