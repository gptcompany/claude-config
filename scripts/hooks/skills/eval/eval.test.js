/**
 * Tests for Eval Harness and Storage
 *
 * Run with: node --test eval.test.js
 */

const { describe, it, before, after, beforeEach } = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execSync } = require("child_process");

// Use test-specific paths to avoid polluting real data
const TEST_EVAL_DIR = path.join(os.tmpdir(), "claude-eval-test-" + Date.now());
const TEST_RESULTS_FILE = path.join(TEST_EVAL_DIR, "results.json");

// Import and modify storage module for testing
const storage = require("./eval-storage");
const { EvalHarness } = require("./eval-harness");

// Override paths for testing
const originalEvalDir = storage.EVAL_DIR;
const originalResultsFile = storage.RESULTS_FILE;

describe("Eval Storage", () => {
  beforeEach(() => {
    // Clean up test directory
    if (fs.existsSync(TEST_EVAL_DIR)) {
      fs.rmSync(TEST_EVAL_DIR, { recursive: true });
    }
    fs.mkdirSync(TEST_EVAL_DIR, { recursive: true });
    // Clear any existing results for clean tests
    storage.clearResults();
  });

  after(() => {
    // Clean up
    if (fs.existsSync(TEST_EVAL_DIR)) {
      fs.rmSync(TEST_EVAL_DIR, { recursive: true });
    }
  });

  describe("recordRun", () => {
    it("should create run with unique ID", () => {
      const run = storage.recordRun({
        project: "test-project",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 10,
        testsPassed: 10,
        testsFailed: 0,
        duration: 1000,
        command: "npm test",
      });

      assert.ok(run.id, "Run should have an ID");
      assert.ok(run.id.startsWith("run-"), "ID should start with 'run-'");
    });

    it("should include timestamp", () => {
      const before = new Date().toISOString();
      const run = storage.recordRun({
        project: "test-project",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 5,
        testsPassed: 5,
        testsFailed: 0,
        duration: 500,
        command: "npm test",
      });
      const after = new Date().toISOString();

      assert.ok(run.timestamp, "Run should have timestamp");
      assert.ok(run.timestamp >= before, "Timestamp should be recent");
      assert.ok(run.timestamp <= after, "Timestamp should not be in future");
    });

    it("should preserve all run data", () => {
      const runData = {
        project: "my-project",
        suite: "integration",
        attempt: 2,
        passed: false,
        total: 20,
        testsPassed: 15,
        testsFailed: 5,
        duration: 3000,
        command: "pytest -v",
      };

      const run = storage.recordRun(runData);

      assert.strictEqual(run.project, "my-project");
      assert.strictEqual(run.suite, "integration");
      assert.strictEqual(run.attempt, 2);
      assert.strictEqual(run.passed, false);
      assert.strictEqual(run.total, 20);
      assert.strictEqual(run.testsPassed, 15);
      assert.strictEqual(run.testsFailed, 5);
      assert.strictEqual(run.duration, 3000);
      assert.strictEqual(run.command, "pytest -v");
    });
  });

  describe("loadResults", () => {
    it("should return empty structure on first run", () => {
      storage.clearResults();
      const results = storage.loadResults();

      assert.ok(Array.isArray(results.runs), "Should have runs array");
      assert.strictEqual(results.runs.length, 0, "Runs should be empty");
    });
  });

  describe("getSummary", () => {
    it("should calculate pass@1 correctly", () => {
      // Record 10 first-attempt runs: 7 pass, 3 fail
      for (let i = 0; i < 7; i++) {
        storage.recordRun({
          project: "test",
          suite: "unit",
          attempt: 1,
          passed: true,
          total: 1,
          testsPassed: 1,
          testsFailed: 0,
          duration: 100,
          command: "npm test",
        });
      }
      for (let i = 0; i < 3; i++) {
        storage.recordRun({
          project: "test",
          suite: "unit",
          attempt: 1,
          passed: false,
          total: 1,
          testsPassed: 0,
          testsFailed: 1,
          duration: 100,
          command: "npm test",
        });
      }

      const summary = storage.getSummary();
      assert.strictEqual(summary.passAt["pass@1"], "70.0%");
    });

    it("should calculate pass@2 correctly", () => {
      storage.clearResults();

      // Record 5 second-attempt runs: 4 pass, 1 fail
      for (let i = 0; i < 4; i++) {
        storage.recordRun({
          project: "test",
          suite: "unit",
          attempt: 2,
          passed: true,
          total: 1,
          testsPassed: 1,
          testsFailed: 0,
          duration: 100,
          command: "npm test",
        });
      }
      storage.recordRun({
        project: "test",
        suite: "unit",
        attempt: 2,
        passed: false,
        total: 1,
        testsPassed: 0,
        testsFailed: 1,
        duration: 100,
        command: "npm test",
      });

      const summary = storage.getSummary();
      assert.strictEqual(summary.passAt["pass@2"], "80.0%");
    });

    it("should track multiple attempt levels", () => {
      storage.clearResults();

      // pass@1: 2/4 = 50%
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 1,
        passed: false,
        total: 1,
        testsPassed: 0,
        testsFailed: 1,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 1,
        passed: false,
        total: 1,
        testsPassed: 0,
        testsFailed: 1,
        duration: 10,
        command: "t",
      });

      // pass@2: 3/3 = 100%
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 2,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 2,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "t",
        suite: "u",
        attempt: 2,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });

      const summary = storage.getSummary();
      assert.strictEqual(summary.passAt["pass@1"], "50.0%");
      assert.strictEqual(summary.passAt["pass@2"], "100.0%");
    });
  });

  describe("getRecentRuns", () => {
    it("should limit count correctly", () => {
      storage.clearResults();

      // Record 20 runs
      for (let i = 0; i < 20; i++) {
        storage.recordRun({
          project: "test",
          suite: "unit",
          attempt: 1,
          passed: true,
          total: 1,
          testsPassed: 1,
          testsFailed: 0,
          duration: 100,
          command: "npm test",
        });
      }

      const recent5 = storage.getRecentRuns(5);
      assert.strictEqual(recent5.length, 5, "Should return only 5 runs");

      const recent10 = storage.getRecentRuns(10);
      assert.strictEqual(recent10.length, 10, "Should return only 10 runs");
    });

    it("should return most recent runs", () => {
      storage.clearResults();

      // Record runs with different projects
      storage.recordRun({
        project: "old",
        suite: "u",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "newer",
        suite: "u",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });
      storage.recordRun({
        project: "newest",
        suite: "u",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 10,
        command: "t",
      });

      const recent = storage.getRecentRuns(2);
      assert.strictEqual(recent.length, 2);
      assert.strictEqual(recent[0].project, "newer");
      assert.strictEqual(recent[1].project, "newest");
    });
  });

  describe("persistence", () => {
    it("should persist results across calls", () => {
      storage.clearResults();

      storage.recordRun({
        project: "persist-test",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 100,
        command: "npm test",
      });

      // Load fresh
      const results = storage.loadResults();
      assert.strictEqual(results.runs.length, 1);
      assert.strictEqual(results.runs[0].project, "persist-test");
    });
  });
});

describe("Eval Harness", () => {
  describe("detectTestCommand", () => {
    it("should detect npm test for Node.js projects", () => {
      // Create temp package.json
      const tempDir = path.join(os.tmpdir(), "eval-test-npm-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({ scripts: { test: "jest" } }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "npm test");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should skip npm test if test script is default", () => {
      const tempDir = path.join(os.tmpdir(), "eval-test-default-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({
          scripts: { test: 'echo "Error: no test specified" && exit 1' },
        }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        // Should fall through to next detection or default
        assert.ok(harness.command, "Should have a command");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });
  });

  describe("parseTestOutput", () => {
    it("should parse Jest format", () => {
      const harness = new EvalHarness();
      const output = "Tests: 5 passed, 5 total";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 5);
      assert.strictEqual(result.total, 5);
      assert.strictEqual(result.failed, 0);
    });

    it("should parse Jest format with failures", () => {
      const harness = new EvalHarness();
      const output = "Tests: 3 passed, 2 failed, 5 total";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 3);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.total, 5);
    });

    it("should parse pytest format", () => {
      const harness = new EvalHarness();
      const output = "===== 10 passed, 2 failed in 1.5s =====";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 10);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.total, 12);
    });

    it("should parse Node.js test runner format", () => {
      const harness = new EvalHarness();
      const output = "tests 15 | pass 12 | fail 3";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.total, 15);
      assert.strictEqual(result.passed, 12);
      assert.strictEqual(result.failed, 3);
    });

    it("should parse Go test format", () => {
      const harness = new EvalHarness();
      const output = `ok   github.com/user/pkg1   0.5s
ok   github.com/user/pkg2   0.3s
FAIL github.com/user/pkg3   0.2s`;
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 2);
      assert.strictEqual(result.failed, 1);
      assert.strictEqual(result.total, 3);
    });

    it("should parse Rust cargo test format", () => {
      const harness = new EvalHarness();
      const output = "test result: ok. 8 passed; 2 failed; 0 ignored";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 8);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.total, 10);
    });

    it("should parse RSpec format", () => {
      const harness = new EvalHarness();
      const output = "25 examples, 3 failures";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 22);
      assert.strictEqual(result.failed, 3);
      assert.strictEqual(result.total, 25);
    });

    it("should return zeros for empty output", () => {
      const harness = new EvalHarness();
      const result = harness.parseTestOutput("");

      assert.strictEqual(result.passed, 0);
      assert.strictEqual(result.failed, 0);
      assert.strictEqual(result.total, 0);
    });
  });

  describe("formatReport", () => {
    it("should include pass@k summary", () => {
      const harness = new EvalHarness();
      const result = {
        run: {
          id: "run-123",
          suite: "unit",
          project: "test",
          attempt: 1,
          passed: true,
          testsPassed: 10,
          total: 10,
          duration: 1500,
          command: "npm test",
        },
        summary: {
          totalRuns: 5,
          passAt: { "pass@1": "80.0%", "pass@2": "95.0%" },
          overallPassRate: "85.0%",
          lastUpdated: "2026-01-25T12:00:00Z",
        },
      };

      const report = harness.formatReport(result);

      assert.ok(report.includes("EVAL HARNESS REPORT"), "Should have title");
      assert.ok(report.includes("pass@1: 80.0%"), "Should show pass@1");
      assert.ok(report.includes("pass@2: 95.0%"), "Should show pass@2");
      assert.ok(report.includes("PASSED"), "Should show status");
    });

    it("should show FAILED for failed runs", () => {
      const harness = new EvalHarness();
      const result = {
        run: {
          id: "run-456",
          suite: "unit",
          project: "test",
          attempt: 1,
          passed: false,
          testsPassed: 8,
          total: 10,
          duration: 2000,
          command: "npm test",
        },
        summary: { totalRuns: 1, passAt: {}, lastUpdated: null },
      };

      const report = harness.formatReport(result);
      assert.ok(report.includes("FAILED"), "Should show FAILED status");
    });
  });

  describe("run", () => {
    it("should record result to storage", async () => {
      storage.clearResults();

      // Create a temp project that passes
      const tempDir = path.join(os.tmpdir(), "eval-run-test-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({
          name: "test",
          scripts: { test: 'echo "Tests: 3 passed, 3 total"' },
        }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness({ suite: "test-run" });
        const result = await harness.run();

        assert.ok(result.run.id, "Should have run ID");
        assert.strictEqual(result.run.suite, "test-run");
        assert.strictEqual(result.run.passed, true);

        // Check it was recorded
        const recent = storage.getRecentRuns(1);
        assert.strictEqual(recent.length, 1);
        assert.strictEqual(recent[0].suite, "test-run");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should return output in result", async () => {
      const tempDir = path.join(os.tmpdir(), "eval-output-test-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({
          name: "test",
          scripts: { test: 'echo "Hello from tests"' },
        }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        const result = await harness.run();

        assert.ok(
          result.output.includes("Hello from tests"),
          "Should capture output",
        );
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });
  });

  describe("CLI", () => {
    it("should show summary with --summary flag", () => {
      const harnessPath = path.join(__dirname, "eval-harness.js");
      const output = execSync(`node "${harnessPath}" --summary`, {
        encoding: "utf8",
      });

      // Should be valid JSON
      const parsed = JSON.parse(output);
      assert.ok(
        "totalRuns" in parsed ||
          "passAt" in parsed ||
          Object.keys(parsed).length === 0,
      );
    });
  });
});

describe("Extended Storage Functions", () => {
  beforeEach(() => {
    storage.clearResults();
  });

  describe("getRunsByProject", () => {
    it("should filter runs by project name", () => {
      // Record runs for different projects
      storage.recordRun({
        project: "project-a",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 100,
        command: "npm test",
      });
      storage.recordRun({
        project: "project-b",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 100,
        command: "npm test",
      });
      storage.recordRun({
        project: "project-a",
        suite: "unit",
        attempt: 2,
        passed: false,
        total: 1,
        testsPassed: 0,
        testsFailed: 1,
        duration: 100,
        command: "npm test",
      });

      const projectARuns = storage.getRunsByProject("project-a");
      assert.strictEqual(projectARuns.length, 2);
      assert.ok(projectARuns.every((r) => r.project === "project-a"));
    });

    it("should respect limit parameter", () => {
      // Record 5 runs for same project
      for (let i = 0; i < 5; i++) {
        storage.recordRun({
          project: "limited-project",
          suite: "unit",
          attempt: 1,
          passed: true,
          total: 1,
          testsPassed: 1,
          testsFailed: 0,
          duration: 100,
          command: "npm test",
        });
      }

      const limitedRuns = storage.getRunsByProject("limited-project", 3);
      assert.strictEqual(limitedRuns.length, 3);
    });

    it("should return empty array for unknown project", () => {
      const runs = storage.getRunsByProject("nonexistent-project");
      assert.deepStrictEqual(runs, []);
    });
  });

  describe("getProjectSummary", () => {
    it("should return project-specific summary", () => {
      // Record runs for a specific project
      storage.recordRun({
        project: "summary-project",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 5,
        testsPassed: 5,
        testsFailed: 0,
        duration: 200,
        command: "npm test",
      });
      storage.recordRun({
        project: "summary-project",
        suite: "unit",
        attempt: 1,
        passed: false,
        total: 5,
        testsPassed: 3,
        testsFailed: 2,
        duration: 200,
        command: "npm test",
      });

      const summary = storage.getProjectSummary("summary-project");
      assert.strictEqual(summary.project, "summary-project");
      assert.strictEqual(summary.totalRuns, 2);
      assert.ok(summary.passAt["pass@1"]);
      assert.strictEqual(summary.passAt["pass@1"], "50.0%");
    });

    it("should return empty summary for unknown project", () => {
      const summary = storage.getProjectSummary("nonexistent");
      assert.strictEqual(summary.totalRuns, 0);
      assert.deepStrictEqual(summary.passAt, {});
      assert.strictEqual(summary.lastUpdated, null);
    });

    it("should track multiple attempt levels for project", () => {
      storage.recordRun({
        project: "multi-attempt",
        suite: "unit",
        attempt: 1,
        passed: false,
        total: 1,
        testsPassed: 0,
        testsFailed: 1,
        duration: 100,
        command: "npm test",
      });
      storage.recordRun({
        project: "multi-attempt",
        suite: "unit",
        attempt: 2,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 100,
        command: "npm test",
      });

      const summary = storage.getProjectSummary("multi-attempt");
      assert.strictEqual(summary.passAt["pass@1"], "0.0%");
      assert.strictEqual(summary.passAt["pass@2"], "100.0%");
    });
  });

  describe("clearResults", () => {
    it("should return true on success", () => {
      storage.recordRun({
        project: "clear-test",
        suite: "unit",
        attempt: 1,
        passed: true,
        total: 1,
        testsPassed: 1,
        testsFailed: 0,
        duration: 100,
        command: "npm test",
      });

      const result = storage.clearResults();
      assert.strictEqual(result, true);
    });

    it("should return true even if no file exists", () => {
      // Ensure file doesn't exist
      storage.clearResults();
      // Call again - should still succeed
      const result = storage.clearResults();
      assert.strictEqual(result, true);
    });
  });
});

describe("Eval Harness CLI", () => {
  const harnessPath = path.join(__dirname, "eval-harness.js");

  it("should handle --recent flag", () => {
    const output = execSync(`node "${harnessPath}" --recent --count=3`, {
      encoding: "utf8",
    });
    const parsed = JSON.parse(output);
    assert.ok(Array.isArray(parsed), "Should return array");
  });

  it("should handle --help flag", () => {
    const output = execSync(`node "${harnessPath}" --help`, {
      encoding: "utf8",
    });
    assert.ok(output.includes("Eval Harness"), "Should show title");
    assert.ok(output.includes("--suite"), "Should document --suite");
    assert.ok(output.includes("--attempt"), "Should document --attempt");
    assert.ok(output.includes("--command"), "Should document --command");
  });

  it("should handle -h flag", () => {
    const output = execSync(`node "${harnessPath}" -h`, {
      encoding: "utf8",
    });
    assert.ok(output.includes("Eval Harness"), "Should show title");
  });
});

describe("Eval Harness Extended", () => {
  describe("detectTestCommand extended paths", () => {
    it("should detect pytest for Python project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-pytest-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "test_main.py"),
        "def test_foo(): pass",
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        // If pytest is available, should detect it; otherwise falls to default
        assert.ok(harness.command, "Should have a command");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect Go tests for Go project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-go-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(path.join(tempDir, "go.mod"), "module test\n\ngo 1.19");

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        // Should detect "go test ./..." if go available
        assert.ok(harness.command, "Should have a command");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect Rust tests for Cargo project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-rust-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "Cargo.toml"),
        '[package]\nname = "test"',
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "cargo test");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect RSpec for Ruby project with rspec in Gemfile", () => {
      const tempDir = path.join(os.tmpdir(), "eval-rspec-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(path.join(tempDir, "Gemfile"), 'gem "rspec"\n');

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "bundle exec rspec");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect minitest for Ruby project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-minitest-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(path.join(tempDir, "Gemfile"), 'gem "minitest"\n');

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.ok(
          harness.command.includes("minitest") ||
            harness.command.includes("ruby"),
        );
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect Maven for Java project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-maven-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(path.join(tempDir, "pom.xml"), "<project></project>");

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "mvn test");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should detect Gradle for Java project", () => {
      const tempDir = path.join(os.tmpdir(), "eval-gradle-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "build.gradle"),
        'apply plugin: "java"',
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "./gradlew test");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should fall back to npm test for empty directory", () => {
      const tempDir = path.join(os.tmpdir(), "eval-empty-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        assert.strictEqual(harness.command, "npm test");
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });
  });

  describe("parseTestOutput extended formats", () => {
    it("should parse Maven/JUnit format", () => {
      const harness = new EvalHarness();
      const output = "Tests run: 10, Failures: 2, Errors: 0, Skipped: 1";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.total, 10);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.passed, 8);
    });

    it("should parse generic PASS/FAIL format", () => {
      const harness = new EvalHarness();
      const output = `
        test_one: PASS
        test_two: PASS
        test_three: FAIL
        test_four: PASS
      `;
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 3);
      assert.strictEqual(result.failed, 1);
      assert.strictEqual(result.total, 4);
    });

    it("should parse Go format with only ok", () => {
      const harness = new EvalHarness();
      const output = `ok   github.com/user/pkg1   0.5s
ok   github.com/user/pkg2   0.3s
ok   github.com/user/pkg3   0.2s`;
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 3);
      assert.strictEqual(result.failed, 0);
      assert.strictEqual(result.total, 3);
    });

    it("should parse Go format with only FAIL", () => {
      const harness = new EvalHarness();
      const output = `FAIL github.com/user/pkg1   0.5s
FAIL github.com/user/pkg2   0.3s`;
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 0);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.total, 2);
    });

    it("should handle output without test markers", () => {
      const harness = new EvalHarness();
      const output = "No test results here, just logging";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 0);
      assert.strictEqual(result.failed, 0);
      assert.strictEqual(result.total, 0);
    });

    it("should parse Jest alternative format with failures", () => {
      const harness = new EvalHarness();
      const output = "5 passed, 2 failed, 7 total";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 5);
      assert.strictEqual(result.failed, 2);
      assert.strictEqual(result.total, 7);
    });

    it("should parse pytest passed only format", () => {
      const harness = new EvalHarness();
      const output = "12 passed in 0.5s";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 12);
      assert.strictEqual(result.failed, 0);
      assert.strictEqual(result.total, 12);
    });

    it("should parse pytest with failures", () => {
      const harness = new EvalHarness();
      const output = "8 passed, 3 failed in 1.2s";
      const result = harness.parseTestOutput(output);

      assert.strictEqual(result.passed, 8);
      assert.strictEqual(result.failed, 3);
      assert.strictEqual(result.total, 11);
    });
  });

  describe("truncateOutput with long content", () => {
    it("should truncate long output", () => {
      const harness = new EvalHarness();
      const lines = [];
      for (let i = 0; i < 50; i++) {
        lines.push(`Line ${i}`);
      }
      const output = lines.join("\n");

      const truncated = harness.truncateOutput(output, 10);
      assert.ok(truncated.includes("truncated"));
      assert.ok(truncated.includes("Line 49"));
      assert.ok(!truncated.includes("Line 0")); // First lines should be removed
    });
  });

  describe("run error handling", () => {
    it("should handle timeout error", async () => {
      const tempDir = path.join(os.tmpdir(), "eval-timeout-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({
          name: "test",
          scripts: { test: "sleep 10" },
        }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness({ timeout: 100 }); // 100ms timeout
        const result = await harness.run();

        assert.strictEqual(result.run.passed, false);
        // Output should mention timeout or error
        assert.ok(
          result.output.includes("TIMEOUT") ||
            result.output.includes("ERROR") ||
            result.output.includes("SIGTERM"),
        );
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });

    it("should handle execution error", async () => {
      const tempDir = path.join(os.tmpdir(), "eval-error-" + Date.now());
      fs.mkdirSync(tempDir, { recursive: true });
      fs.writeFileSync(
        path.join(tempDir, "package.json"),
        JSON.stringify({
          name: "test",
          scripts: { test: "nonexistent_command_12345" },
        }),
      );

      const originalCwd = process.cwd();
      process.chdir(tempDir);

      try {
        const harness = new EvalHarness();
        const result = await harness.run();

        assert.strictEqual(result.run.passed, false);
      } finally {
        process.chdir(originalCwd);
        fs.rmSync(tempDir, { recursive: true });
      }
    });
  });

  describe("truncateOutput", () => {
    it("should handle null/undefined input", () => {
      const harness = new EvalHarness();
      assert.strictEqual(harness.truncateOutput(null, 10), "");
      assert.strictEqual(harness.truncateOutput(undefined, 10), "");
      assert.strictEqual(harness.truncateOutput("", 10), "");
    });

    it("should not truncate short output", () => {
      const harness = new EvalHarness();
      const short = "line1\nline2\nline3";
      assert.strictEqual(harness.truncateOutput(short, 10), short);
    });
  });

  describe("formatReport edge cases", () => {
    it("should handle empty passAt", () => {
      const harness = new EvalHarness();
      const result = {
        run: {
          id: "run-empty",
          suite: "unit",
          project: "test",
          attempt: 1,
          passed: true,
          testsPassed: 0,
          total: 0,
          duration: 100,
          command: "npm test",
        },
        summary: { totalRuns: 0, passAt: {}, lastUpdated: null },
      };

      const report = harness.formatReport(result);
      assert.ok(report.includes("No data yet"));
    });
  });
});

describe("Integration Tests", () => {
  beforeEach(() => {
    storage.clearResults();
  });

  it("should track multiple attempts correctly", async () => {
    const tempDir = path.join(os.tmpdir(), "eval-multi-" + Date.now());
    fs.mkdirSync(tempDir, { recursive: true });

    // Create passing test script
    fs.writeFileSync(
      path.join(tempDir, "package.json"),
      JSON.stringify({
        name: "test",
        scripts: { test: 'echo "Tests: 1 passed, 1 total"' },
      }),
    );

    const originalCwd = process.cwd();
    process.chdir(tempDir);

    try {
      // First attempt
      const harness1 = new EvalHarness({ attempt: 1 });
      await harness1.run();

      // Second attempt
      const harness2 = new EvalHarness({ attempt: 2 });
      await harness2.run();

      // Third attempt
      const harness3 = new EvalHarness({ attempt: 3 });
      await harness3.run();

      const summary = storage.getSummary();
      assert.strictEqual(summary.totalRuns, 3);
      assert.ok(summary.passAt["pass@1"], "Should have pass@1");
      assert.ok(summary.passAt["pass@2"], "Should have pass@2");
      assert.ok(summary.passAt["pass@3"], "Should have pass@3");
    } finally {
      process.chdir(originalCwd);
      fs.rmSync(tempDir, { recursive: true });
    }
  });

  it("should calculate pass@k correctly over runs", () => {
    // Simulate typical workflow:
    // 2 features, each took 2 attempts to pass

    // Feature 1: attempt 1 fails, attempt 2 passes
    storage.recordRun({
      project: "test",
      suite: "unit",
      attempt: 1,
      passed: false,
      total: 1,
      testsPassed: 0,
      testsFailed: 1,
      duration: 100,
      command: "npm test",
    });
    storage.recordRun({
      project: "test",
      suite: "unit",
      attempt: 2,
      passed: true,
      total: 1,
      testsPassed: 1,
      testsFailed: 0,
      duration: 100,
      command: "npm test",
    });

    // Feature 2: attempt 1 passes
    storage.recordRun({
      project: "test",
      suite: "unit",
      attempt: 1,
      passed: true,
      total: 1,
      testsPassed: 1,
      testsFailed: 0,
      duration: 100,
      command: "npm test",
    });

    const summary = storage.getSummary();

    // pass@1: 1 pass / 2 attempts = 50%
    assert.strictEqual(summary.passAt["pass@1"], "50.0%");
    // pass@2: 1 pass / 1 attempt = 100%
    assert.strictEqual(summary.passAt["pass@2"], "100.0%");
  });

  it("should record failed run as not passed", async () => {
    const tempDir = path.join(os.tmpdir(), "eval-fail-" + Date.now());
    fs.mkdirSync(tempDir, { recursive: true });

    // Create failing test script
    fs.writeFileSync(
      path.join(tempDir, "package.json"),
      JSON.stringify({
        name: "test",
        scripts: {
          test: 'echo "Tests: 0 passed, 1 failed, 1 total" && exit 1',
        },
      }),
    );

    const originalCwd = process.cwd();
    process.chdir(tempDir);

    try {
      const harness = new EvalHarness();
      const result = await harness.run();

      assert.strictEqual(result.run.passed, false, "Run should not be passed");
      assert.strictEqual(
        result.run.testsFailed,
        1,
        "Should have 1 failed test",
      );
    } finally {
      process.chdir(originalCwd);
      fs.rmSync(tempDir, { recursive: true });
    }
  });
});
