#!/usr/bin/env node
/**
 * Eval Harness - Test Runner with Pass@k Metrics
 *
 * Runs test suites and tracks pass@k metrics to analyze
 * first-attempt vs multi-attempt success rates.
 *
 * Usage:
 *   node eval-harness.js              # Run tests with auto-detected command
 *   node eval-harness.js --suite=api  # Name this test suite
 *   node eval-harness.js --attempt=2  # Mark as second attempt
 *   node eval-harness.js --summary    # Show pass@k summary
 *   node eval-harness.js --recent     # Show recent runs
 */

const { execSync, spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");
const { recordRun, getSummary, getRecentRuns } = require("./eval-storage");

/**
 * Eval Harness class for running tests and tracking metrics
 */
class EvalHarness {
  /**
   * Create an eval harness instance
   * @param {object} options - Configuration options
   * @param {string} [options.suite='default'] - Test suite name
   * @param {string} [options.project] - Project name (defaults to cwd basename)
   * @param {number} [options.attempt=1] - Attempt number
   * @param {string} [options.command] - Override test command
   * @param {number} [options.timeout=300000] - Timeout in ms (default 5 min)
   */
  constructor(options = {}) {
    this.suite = options.suite || "default";
    this.project = options.project || path.basename(process.cwd());
    this.attempt = options.attempt || 1;
    this.timeout = options.timeout || 300000;
    this.command = options.command || this.detectTestCommand();
  }

  /**
   * Detect the appropriate test command for the current project
   * @returns {string} Test command to run
   */
  detectTestCommand() {
    // Check for package.json with test script
    try {
      const pkgPath = path.join(process.cwd(), "package.json");
      if (fs.existsSync(pkgPath)) {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
        if (
          pkg.scripts?.test &&
          pkg.scripts.test !== 'echo "Error: no test specified" && exit 1'
        ) {
          return "npm test";
        }
      }
    } catch {
      // Continue to other detections
    }

    // Check for pytest (Python)
    try {
      const result = spawnSync("which", ["pytest"], { encoding: "utf8" });
      if (result.status === 0) {
        // Check for Python files
        const files = fs.readdirSync(process.cwd());
        const hasPyTests = files.some(
          (f) => f.endsWith(".py") || f === "pytest.ini" || f === "setup.py",
        );
        if (hasPyTests) {
          return "pytest -v";
        }
      }
    } catch {
      // Continue
    }

    // Check for Go tests
    try {
      const result = spawnSync("which", ["go"], { encoding: "utf8" });
      if (
        result.status === 0 &&
        fs.existsSync(path.join(process.cwd(), "go.mod"))
      ) {
        return "go test ./...";
      }
    } catch {
      // Continue
    }

    // Check for Rust tests
    try {
      if (fs.existsSync(path.join(process.cwd(), "Cargo.toml"))) {
        return "cargo test";
      }
    } catch {
      // Continue
    }

    // Check for Ruby tests
    try {
      if (fs.existsSync(path.join(process.cwd(), "Gemfile"))) {
        const gemfile = fs.readFileSync(
          path.join(process.cwd(), "Gemfile"),
          "utf8",
        );
        if (gemfile.includes("rspec")) {
          return "bundle exec rspec";
        }
        if (gemfile.includes("minitest")) {
          return "bundle exec ruby -Itest test/**/*_test.rb";
        }
      }
    } catch {
      // Continue
    }

    // Check for Java tests
    try {
      if (fs.existsSync(path.join(process.cwd(), "pom.xml"))) {
        return "mvn test";
      }
      if (fs.existsSync(path.join(process.cwd(), "build.gradle"))) {
        return "./gradlew test";
      }
    } catch {
      // Continue
    }

    // Default to npm test
    return "npm test";
  }

  /**
   * Run the test suite and record results
   * @returns {Promise<object>} Run result with output and summary
   */
  async run() {
    const startTime = Date.now();
    let passed = false;
    let output = "";
    let stderr = "";
    let testCount = { passed: 0, failed: 0, total: 0 };

    try {
      // Run tests with captured output
      output = execSync(this.command, {
        encoding: "utf8",
        timeout: this.timeout,
        stdio: ["pipe", "pipe", "pipe"],
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer
        cwd: process.cwd(),
      });
      passed = true;
      testCount = this.parseTestOutput(output);
    } catch (err) {
      // Test command failed - capture output
      output = err.stdout || "";
      stderr = err.stderr || "";
      const combinedOutput = output + "\n" + stderr;
      testCount = this.parseTestOutput(combinedOutput);

      // Check if it was a test failure vs execution error
      if (err.status !== undefined && testCount.total > 0) {
        // Tests ran but some failed
        passed = false;
      } else if (err.killed) {
        // Timeout
        output = `TIMEOUT after ${this.timeout}ms\n${output}`;
        passed = false;
      } else {
        // Execution error
        output = `ERROR: ${err.message}\n${output}`;
        passed = false;
      }
    }

    const duration = Date.now() - startTime;

    // Record the run
    const run = recordRun({
      project: this.project,
      suite: this.suite,
      attempt: this.attempt,
      passed,
      total: testCount.total,
      testsPassed: testCount.passed,
      testsFailed: testCount.failed,
      duration,
      command: this.command,
    });

    return {
      run,
      output: this.truncateOutput(output, 50),
      stderr: stderr ? this.truncateOutput(stderr, 20) : undefined,
      summary: getSummary(),
    };
  }

  /**
   * Parse test output to extract pass/fail counts
   * @param {string} output - Test command output
   * @returns {object} Object with passed, failed, total counts
   */
  parseTestOutput(output) {
    if (!output) {
      return { passed: 0, failed: 0, total: 0 };
    }

    // Jest / npm test format: "Tests: X passed, Y total"
    let match = output.match(/Tests:\s*(\d+)\s*passed.*?(\d+)\s*total/i);
    if (match) {
      const passed = parseInt(match[1], 10);
      const total = parseInt(match[2], 10);
      return { passed, total, failed: total - passed };
    }

    // Jest alternative: "X passed, Y failed, Z total"
    match = output.match(/(\d+)\s*passed,?\s*(\d+)\s*failed.*?(\d+)\s*total/i);
    if (match) {
      return {
        passed: parseInt(match[1], 10),
        failed: parseInt(match[2], 10),
        total: parseInt(match[3], 10),
      };
    }

    // Node.js test runner: "tests X | pass Y | fail Z"
    match = output.match(
      /tests\s+(\d+)\s*\|\s*pass\s+(\d+)\s*\|\s*fail\s+(\d+)/i,
    );
    if (match) {
      return {
        total: parseInt(match[1], 10),
        passed: parseInt(match[2], 10),
        failed: parseInt(match[3], 10),
      };
    }

    // Pytest format: "X passed, Y failed" or "X passed"
    match = output.match(/(\d+)\s*passed(?:.*?(\d+)\s*failed)?/i);
    if (match) {
      const passed = parseInt(match[1], 10);
      const failed = match[2] ? parseInt(match[2], 10) : 0;
      return { passed, failed, total: passed + failed };
    }

    // Go test format: "ok" or "FAIL"
    const okMatches = output.match(/^ok\s+/gm);
    const failMatches = output.match(/^FAIL\s+/gm);
    if (okMatches || failMatches) {
      const passed = okMatches ? okMatches.length : 0;
      const failed = failMatches ? failMatches.length : 0;
      return { passed, failed, total: passed + failed };
    }

    // Rust cargo test: "test result: ok. X passed; Y failed"
    match = output.match(/test result:.*?(\d+)\s*passed;\s*(\d+)\s*failed/i);
    if (match) {
      const passed = parseInt(match[1], 10);
      const failed = parseInt(match[2], 10);
      return { passed, failed, total: passed + failed };
    }

    // RSpec: "X examples, Y failures"
    match = output.match(/(\d+)\s*examples?,\s*(\d+)\s*failures?/i);
    if (match) {
      const total = parseInt(match[1], 10);
      const failed = parseInt(match[2], 10);
      return { passed: total - failed, failed, total };
    }

    // Maven/JUnit: "Tests run: X, Failures: Y"
    match = output.match(/Tests\s+run:\s*(\d+),\s*Failures:\s*(\d+)/i);
    if (match) {
      const total = parseInt(match[1], 10);
      const failed = parseInt(match[2], 10);
      return { passed: total - failed, failed, total };
    }

    // Generic: count "PASS" and "FAIL" lines
    const passLines = (output.match(/\bPASS\b/gi) || []).length;
    const failLines = (output.match(/\bFAIL\b/gi) || []).length;
    if (passLines > 0 || failLines > 0) {
      return {
        passed: passLines,
        failed: failLines,
        total: passLines + failLines,
      };
    }

    return { passed: 0, failed: 0, total: 0 };
  }

  /**
   * Truncate output to a maximum number of lines
   * @param {string} output - Output to truncate
   * @param {number} maxLines - Maximum lines to keep
   * @returns {string} Truncated output
   */
  truncateOutput(output, maxLines) {
    if (!output) return "";
    const lines = output.split("\n");
    if (lines.length <= maxLines) return output;

    const kept = lines.slice(-maxLines);
    return `... (${lines.length - maxLines} lines truncated)\n${kept.join("\n")}`;
  }

  /**
   * Format a rich terminal report for the run result
   * @param {object} result - Run result from run()
   * @returns {string} Formatted report
   */
  formatReport(result) {
    const { run, summary } = result;
    const statusIcon = run.passed ? "\u2713" : "\u2717";
    const statusText = run.passed ? "PASSED" : "FAILED";

    const passAtLines =
      Object.entries(summary.passAt || {})
        .map(([k, v]) => `  ${k}: ${v}`)
        .join("\n") || "  No data yet";

    return `
+=============================================+
|           EVAL HARNESS REPORT               |
+=============================================+

Run: ${run.id}
Suite: ${run.suite}
Project: ${run.project}
Attempt: ${run.attempt}
Status: ${statusIcon} ${statusText}

Tests: ${run.testsPassed}/${run.total} passed
Duration: ${run.duration}ms
Command: ${run.command}

--- Pass@K Summary (last 100 runs) ---
${passAtLines}

Overall pass rate: ${summary.overallPassRate || "N/A"}
Total runs tracked: ${summary.totalRuns || 0}
Last updated: ${summary.lastUpdated || "Never"}
`;
  }
}

// CLI entry point
if (require.main === module) {
  const args = process.argv.slice(2);

  // Parse CLI arguments
  const getArg = (prefix) => {
    const arg = args.find((a) => a.startsWith(prefix));
    return arg ? arg.split("=")[1] : undefined;
  };

  // Handle --summary flag
  if (args.includes("--summary")) {
    console.log(JSON.stringify(getSummary(), null, 2));
    process.exit(0);
  }

  // Handle --recent flag
  if (args.includes("--recent")) {
    const count = parseInt(getArg("--count=") || "10", 10);
    console.log(JSON.stringify(getRecentRuns(count), null, 2));
    process.exit(0);
  }

  // Handle --help flag
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`
Eval Harness - Test Runner with Pass@k Metrics

Usage:
  node eval-harness.js [options]

Options:
  --suite=<name>     Name this test suite (default: 'default')
  --attempt=<n>      Which attempt this is (default: 1)
  --command=<cmd>    Override test command (auto-detected by default)
  --timeout=<ms>     Test timeout in ms (default: 300000)
  --summary          Show pass@k summary
  --recent           Show recent runs
  --count=<n>        Number of recent runs to show (default: 10)
  --help             Show this help

Examples:
  node eval-harness.js                    # Run tests, first attempt
  node eval-harness.js --attempt=2        # Run tests, second attempt
  node eval-harness.js --suite=unit       # Name the test suite
  node eval-harness.js --command="pytest" # Override test command
  node eval-harness.js --summary          # View pass@k metrics
`);
    process.exit(0);
  }

  // Create harness with options
  const options = {
    suite: getArg("--suite="),
    attempt: parseInt(getArg("--attempt=") || "1", 10),
    command: getArg("--command="),
    timeout: parseInt(getArg("--timeout=") || "300000", 10),
  };

  const harness = new EvalHarness(options);

  // Run tests
  harness.run().then((result) => {
    console.log(harness.formatReport(result));
    process.exit(result.run.passed ? 0 : 1);
  });
}

module.exports = { EvalHarness };
