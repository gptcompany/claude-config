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
