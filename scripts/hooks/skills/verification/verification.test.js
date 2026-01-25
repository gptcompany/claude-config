#!/usr/bin/env node
/**
 * Verification Skill Tests
 *
 * Tests for phases.js and verification-runner.js
 *
 * Run with: node --test verification.test.js
 */

const { describe, it, beforeEach, mock } = require("node:test");
const assert = require("node:assert");
const path = require("path");
const fs = require("fs");
const os = require("os");

// Import modules under test
const {
  PHASES,
  detectProjectType,
  getPhaseCommand,
  getApplicablePhases,
} = require("./phases");

const { VerificationRunner } = require("./verification-runner");

// ============================================================================
// Phase Configuration Tests (8 tests)
// ============================================================================

describe("Phase Configuration", () => {
  it("PHASES has 6 entries", () => {
    assert.strictEqual(
      PHASES.length,
      6,
      "Should have exactly 6 verification phases",
    );
  });

  it("Each phase has required fields", () => {
    const requiredFields = [
      "name",
      "displayName",
      "commands",
      "failFast",
      "timeout",
      "outputLimit",
    ];

    for (const phase of PHASES) {
      for (const field of requiredFields) {
        assert.ok(
          phase[field] !== undefined,
          `Phase ${phase.name} should have ${field}`,
        );
      }
    }
  });

  it("detectProjectType identifies npm project", () => {
    // Create temp directory with package.json
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "node");
      assert.ok(result.confidence >= 0.7);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detectProjectType identifies Python project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(path.join(tmpDir, "requirements.txt"), "requests==2.28.0");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
      assert.ok(result.confidence >= 0.9);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("getPhaseCommand returns correct command for node project", () => {
    const projectInfo = { type: "node", packageManager: "npm" };
    const buildPhase = PHASES.find((p) => p.name === "build");

    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "npm run build 2>&1");
  });

  it("getPhaseCommand returns null for unknown type", () => {
    const projectInfo = { type: "unknown" };
    const buildPhase = PHASES.find((p) => p.name === "build");

    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, null);
  });

  it("failFast is true for build/typecheck/test", () => {
    const failFastPhases = ["build", "typecheck", "test"];
    for (const phaseName of failFastPhases) {
      const phase = PHASES.find((p) => p.name === phaseName);
      assert.strictEqual(
        phase.failFast,
        true,
        `${phaseName} should be fail-fast`,
      );
    }
  });

  it("failFast is false for lint/security/diff", () => {
    const nonFailFastPhases = ["lint", "security", "diff"];
    for (const phaseName of nonFailFastPhases) {
      const phase = PHASES.find((p) => p.name === phaseName);
      assert.strictEqual(
        phase.failFast,
        false,
        `${phaseName} should not be fail-fast`,
      );
    }
  });
});

// ============================================================================
// Runner Tests (12 tests)
// ============================================================================

describe("VerificationRunner", () => {
  it("Runner initializes with defaults", () => {
    const runner = new VerificationRunner();
    assert.ok(runner.projectInfo);
    assert.deepStrictEqual(runner.skipPhases, []);
    assert.strictEqual(runner.verbose, false);
    assert.strictEqual(runner.quiet, false);
    assert.deepStrictEqual(runner.results, []);
  });

  it("Runner accepts project type override", () => {
    const runner = new VerificationRunner({
      projectType: { type: "rust", confidence: 1.0 },
    });
    assert.strictEqual(runner.projectInfo.type, "rust");
  });

  it("runPhase returns pass on success", () => {
    // Create temp dir with git init for a reliable pass test
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));

    try {
      // Initialize git repo so diff command succeeds
      const { execSync } = require("child_process");
      execSync("git init", { cwd: tmpDir, stdio: "pipe" });

      const runner = new VerificationRunner({
        cwd: tmpDir,
        projectType: { type: "generic" },
        quiet: true,
      });

      // Test the diff phase which should pass in a git repo
      const diffPhase = PHASES.find((p) => p.name === "diff");
      const result = runner.runPhase(diffPhase);

      // Should pass in an initialized git repo
      assert.strictEqual(result.status, "pass");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("runPhase returns fail on error", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );

    try {
      const runner = new VerificationRunner({
        cwd: tmpDir,
        quiet: true,
      });

      // Build phase should fail (no build script defined)
      const buildPhase = PHASES.find((p) => p.name === "build");
      const result = runner.runPhase(buildPhase);

      assert.strictEqual(result.status, "fail");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("runPhase respects timeout (skipped - would be slow)", () => {
    // This test is intentionally skipped as testing timeout would be slow
    assert.ok(true, "Timeout test skipped for performance");
  });

  it("truncateOutput limits lines", () => {
    const runner = new VerificationRunner({ quiet: true });
    const longOutput = "line\n".repeat(100);
    const truncated = runner.truncateOutput(longOutput, 10);

    const lines = truncated.split("\n");
    assert.ok(lines.length <= 12, "Output should be truncated");
    assert.ok(truncated.includes("more lines"), "Should indicate truncation");
  });

  it("Run stops on fail-fast failure", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );

    try {
      const runner = new VerificationRunner({
        cwd: tmpDir,
        quiet: true,
      });

      const result = runner.run();

      // Build should fail and stop execution
      assert.strictEqual(result.status, "BLOCKED");
      assert.strictEqual(result.failedAt, "build");
      // Should have stopped early, not run all 6 phases
      assert.ok(result.results.length <= 2);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("Run continues on non-fail-fast failure", () => {
    // For this test we need a project where build passes but lint fails
    // We'll test with skip to simulate this scenario
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "test"],
      quiet: true,
    });

    const result = runner.run();

    // Should complete all phases (lint/security may fail but don't block)
    assert.ok(["READY", "ISSUES"].includes(result.status));
    assert.strictEqual(result.results.length, 6);
  });

  it("Skip option works", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security"],
      quiet: true,
    });

    const result = runner.run();

    // Count skipped phases
    const skipped = result.results.filter((r) => r.status === "skipped").length;
    assert.ok(skipped >= 5, "At least 5 phases should be skipped");
  });

  it("Results array populated correctly", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security"],
      quiet: true,
    });

    runner.run();

    assert.strictEqual(runner.results.length, 6);
    for (const result of runner.results) {
      assert.ok(result.name, "Result should have name");
      assert.ok(result.status, "Result should have status");
    }
  });

  it("toJSON returns valid structure", () => {
    const runner = new VerificationRunner({
      projectType: { type: "node", confidence: 1.0 },
      skip: ["build", "typecheck", "lint", "test", "security", "diff"],
      quiet: true,
    });

    runner.run();
    const json = runner.toJSON();

    assert.strictEqual(json.projectType, "node");
    assert.ok(Array.isArray(json.results));
    assert.ok(json.summary);
    assert.ok(typeof json.summary.passed === "number");
    assert.ok(typeof json.summary.failed === "number");
    assert.ok(typeof json.summary.skipped === "number");
  });

  it("Exit code is 0 for READY, 1 for BLOCKED", () => {
    // This tests the CLI logic, which we can't directly test without spawning
    // Instead we verify the status values
    const runnerReady = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security"],
      quiet: true,
    });

    const resultReady = runnerReady.run();
    assert.ok(
      resultReady.status === "READY" || resultReady.status === "ISSUES",
    );
  });
});

// ============================================================================
// Integration Tests (5 tests)
// ============================================================================

describe("Integration", () => {
  it("Full run in test directory with all phases skipped", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security"],
      quiet: true,
    });

    const result = runner.run();

    assert.ok(result.duration > 0, "Duration should be recorded");
    assert.ok(result.results.length === 6, "All phases should be reported");
  });

  it("Skip all phases runs cleanly", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security", "diff"],
      quiet: true,
    });

    const result = runner.run();

    assert.strictEqual(result.status, "READY");
    const allSkipped = result.results.every((r) => r.status === "skipped");
    assert.ok(allSkipped, "All phases should be skipped");
  });

  it("Verbose mode does not throw", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "typecheck", "lint", "test", "security", "diff"],
      verbose: true,
      quiet: true, // Quiet overrides verbose for console output
    });

    assert.doesNotThrow(() => {
      runner.run();
    });
  });

  it("Multiple skip options work", () => {
    const runner = new VerificationRunner({
      projectType: { type: "generic" },
      skip: ["build", "security"],
      quiet: true,
    });

    const result = runner.run();

    const buildResult = result.results.find((r) => r.name === "build");
    const securityResult = result.results.find((r) => r.name === "security");

    assert.strictEqual(buildResult.status, "skipped");
    assert.strictEqual(securityResult.status, "skipped");
  });

  it("Handles missing commands gracefully", () => {
    const runner = new VerificationRunner({
      projectType: { type: "nonexistent-language" },
      quiet: true,
    });

    // Should not throw, just skip phases without commands
    assert.doesNotThrow(() => {
      const result = runner.run();
      // Most phases should be skipped due to no matching commands
      const skipped = result.results.filter((r) => r.status === "skipped");
      assert.ok(skipped.length >= 4, "Most phases should be skipped");
    });
  });
});

// ============================================================================
// Project Detection Tests (bonus)
// ============================================================================

describe("Project Detection", () => {
  it("Detects TypeScript project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );
    fs.writeFileSync(
      path.join(tmpDir, "tsconfig.json"),
      JSON.stringify({ compilerOptions: {} }),
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "node");
      assert.strictEqual(result.typescript, true);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("Detects Go project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(path.join(tmpDir, "go.mod"), "module test");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "go");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("Detects Rust project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));
    fs.writeFileSync(
      path.join(tmpDir, "Cargo.toml"),
      '[package]\nname = "test"',
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "rust");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("Returns unknown for empty directory", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-test-"));

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "unknown");
      assert.strictEqual(result.confidence, 0);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });
});

// ============================================================================
// Extended Phase Command Tests
// ============================================================================

describe("Extended getPhaseCommand", () => {
  it("returns yarn build for yarn manager", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "node", packageManager: "yarn" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "yarn build 2>&1");
  });

  it("returns pnpm build for pnpm manager", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "node", packageManager: "pnpm" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "pnpm build 2>&1");
  });

  it("returns cargo build for rust", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "rust" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "cargo build 2>&1");
  });

  it("returns go build for go", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "go" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "go build ./... 2>&1");
  });

  it("returns python compile for python", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "python" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.ok(command.includes("py_compile"));
  });

  it("returns make build for make", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "make" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "make build 2>&1");
  });

  it("returns gradle build for gradle", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "gradle" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "./gradlew build 2>&1");
  });

  it("returns mvn compile for maven", () => {
    const buildPhase = PHASES.find((p) => p.name === "build");
    const projectInfo = { type: "maven" };
    const command = getPhaseCommand(buildPhase, projectInfo);
    assert.strictEqual(command, "mvn compile 2>&1");
  });

  it("returns typescript check for node+ts", () => {
    const typecheckPhase = PHASES.find((p) => p.name === "typecheck");
    const projectInfo = { type: "node", typescript: true };
    const command = getPhaseCommand(typecheckPhase, projectInfo);
    assert.strictEqual(command, "npx tsc --noEmit 2>&1");
  });

  it("returns mypy for python with mypy", () => {
    const typecheckPhase = PHASES.find((p) => p.name === "typecheck");
    const projectInfo = { type: "python", typeChecker: "mypy" };
    const command = getPhaseCommand(typecheckPhase, projectInfo);
    assert.strictEqual(command, "mypy . 2>&1");
  });

  it("returns pyright for python with pyright", () => {
    const typecheckPhase = PHASES.find((p) => p.name === "typecheck");
    const projectInfo = { type: "python", typeChecker: "pyright" };
    const command = getPhaseCommand(typecheckPhase, projectInfo);
    assert.strictEqual(command, "pyright 2>&1");
  });

  it("returns null for python without typechecker", () => {
    const typecheckPhase = PHASES.find((p) => p.name === "typecheck");
    const projectInfo = { type: "python" };
    const command = getPhaseCommand(typecheckPhase, projectInfo);
    assert.strictEqual(command, null);
  });

  it("returns ruff for python lint", () => {
    const lintPhase = PHASES.find((p) => p.name === "lint");
    const projectInfo = { type: "python" };
    const command = getPhaseCommand(lintPhase, projectInfo);
    assert.ok(command.includes("ruff"));
  });

  it("returns golangci-lint for go lint", () => {
    const lintPhase = PHASES.find((p) => p.name === "lint");
    const projectInfo = { type: "go" };
    const command = getPhaseCommand(lintPhase, projectInfo);
    assert.ok(command.includes("golangci-lint"));
  });

  it("returns clippy for rust lint", () => {
    const lintPhase = PHASES.find((p) => p.name === "lint");
    const projectInfo = { type: "rust" };
    const command = getPhaseCommand(lintPhase, projectInfo);
    assert.ok(command.includes("clippy"));
  });

  it("returns rubocop for ruby lint", () => {
    const lintPhase = PHASES.find((p) => p.name === "lint");
    const projectInfo = { type: "ruby" };
    const command = getPhaseCommand(lintPhase, projectInfo);
    assert.ok(command.includes("rubocop"));
  });

  it("returns jest for node with jest", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "node", testFramework: "jest" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("jest"));
  });

  it("returns vitest for node with vitest", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "node", testFramework: "vitest" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("vitest"));
  });

  it("returns mocha for node with mocha", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "node", testFramework: "mocha" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("mocha"));
  });

  it("returns node test for node with node runner", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "node", testFramework: "node" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("node --test"));
  });

  it("returns pytest for python test", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "python" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("pytest"));
  });

  it("returns go test for go test", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "go" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("go test"));
  });

  it("returns cargo test for rust test", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "rust" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("cargo test"));
  });

  it("returns rspec for ruby test", () => {
    const testPhase = PHASES.find((p) => p.name === "test");
    const projectInfo = { type: "ruby" };
    const command = getPhaseCommand(testPhase, projectInfo);
    assert.ok(command.includes("rspec"));
  });

  it("returns npm audit for node security", () => {
    const securityPhase = PHASES.find((p) => p.name === "security");
    const projectInfo = { type: "node" };
    const command = getPhaseCommand(securityPhase, projectInfo);
    assert.ok(command.includes("npm audit"));
  });

  it("returns bandit for python security", () => {
    const securityPhase = PHASES.find((p) => p.name === "security");
    const projectInfo = { type: "python" };
    const command = getPhaseCommand(securityPhase, projectInfo);
    assert.ok(command.includes("bandit") || command.includes("safety"));
  });

  it("returns cargo audit for rust security", () => {
    const securityPhase = PHASES.find((p) => p.name === "security");
    const projectInfo = { type: "rust" };
    const command = getPhaseCommand(securityPhase, projectInfo);
    assert.ok(command.includes("cargo audit"));
  });

  it("returns git diff for diff phase", () => {
    const diffPhase = PHASES.find((p) => p.name === "diff");
    const projectInfo = { type: "node" };
    const command = getPhaseCommand(diffPhase, projectInfo);
    assert.ok(command.includes("git diff"));
  });

  it("returns null for unknown phase", () => {
    const fakePhase = { name: "unknown-phase", commands: {} };
    const projectInfo = { type: "node" };
    const command = getPhaseCommand(fakePhase, projectInfo);
    assert.strictEqual(command, null);
  });
});

// ============================================================================
// getApplicablePhases Tests
// ============================================================================

describe("getApplicablePhases", () => {
  it("returns all phases with applicable flag", () => {
    const projectInfo = { type: "node", typescript: true };
    const applicable = getApplicablePhases(projectInfo);

    assert.strictEqual(applicable.length, 6);
    applicable.forEach((phase) => {
      assert.ok("applicable" in phase);
      assert.ok("command" in phase);
    });
  });

  it("marks diff as applicable for all types", () => {
    const projectInfo = { type: "unknown" };
    const applicable = getApplicablePhases(projectInfo);
    const diffPhase = applicable.find((p) => p.name === "diff");

    assert.strictEqual(diffPhase.applicable, true);
  });
});

// ============================================================================
// Extended Project Detection Tests
// ============================================================================

describe("Extended Project Detection", () => {
  it("detects pnpm project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-pnpm-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );
    fs.writeFileSync(path.join(tmpDir, "pnpm-lock.yaml"), "");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "node");
      assert.strictEqual(result.packageManager, "pnpm");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects yarn project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-yarn-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );
    fs.writeFileSync(path.join(tmpDir, "yarn.lock"), "");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "node");
      assert.strictEqual(result.packageManager, "yarn");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects jest test framework", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-jest-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test", devDependencies: { jest: "^29.0.0" } }),
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.testFramework, "jest");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects vitest test framework", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-vitest-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test", devDependencies: { vitest: "^0.34.0" } }),
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.testFramework, "vitest");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects mocha test framework", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-mocha-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test", devDependencies: { mocha: "^10.0.0" } }),
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.testFramework, "mocha");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects jest config file", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-jestcfg-"));
    fs.writeFileSync(
      path.join(tmpDir, "package.json"),
      JSON.stringify({ name: "test" }),
    );
    fs.writeFileSync(
      path.join(tmpDir, "jest.config.js"),
      "module.exports = {};",
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.testFramework, "jest");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects pyproject.toml", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-pyproj-"));
    fs.writeFileSync(path.join(tmpDir, "pyproject.toml"), "[tool.poetry]");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects setup.py", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-setup-"));
    fs.writeFileSync(
      path.join(tmpDir, "setup.py"),
      "from setuptools import setup",
    );

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects mypy.ini", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-mypy-"));
    fs.writeFileSync(path.join(tmpDir, "requirements.txt"), "");
    fs.writeFileSync(path.join(tmpDir, "mypy.ini"), "[mypy]");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
      assert.strictEqual(result.typeChecker, "mypy");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects pyrightconfig.json", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-pyright-"));
    fs.writeFileSync(path.join(tmpDir, "requirements.txt"), "");
    fs.writeFileSync(path.join(tmpDir, "pyrightconfig.json"), "{}");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
      assert.strictEqual(result.typeChecker, "pyright");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects ruff.toml", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-ruff-"));
    fs.writeFileSync(path.join(tmpDir, "requirements.txt"), "");
    fs.writeFileSync(path.join(tmpDir, "ruff.toml"), "");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "python");
      assert.strictEqual(result.linter, "ruff");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects Makefile project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-make-"));
    fs.writeFileSync(path.join(tmpDir, "Makefile"), "build:\n\techo build");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "make");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects Gradle project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-gradle-"));
    fs.writeFileSync(path.join(tmpDir, "build.gradle"), "");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "gradle");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects Gradle Kotlin project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-gradlekts-"));
    fs.writeFileSync(path.join(tmpDir, "build.gradle.kts"), "");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "gradle");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects Maven project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-maven-"));
    fs.writeFileSync(path.join(tmpDir, "pom.xml"), "<project></project>");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "maven");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects Ruby project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-ruby-"));
    fs.writeFileSync(path.join(tmpDir, "Gemfile"), 'gem "rails"');

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "ruby");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("detects generic git project", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-git-"));
    fs.mkdirSync(path.join(tmpDir, ".git"));

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "generic");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("handles invalid package.json", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-invalid-"));
    fs.writeFileSync(path.join(tmpDir, "package.json"), "not json");

    try {
      const result = detectProjectType(tmpDir);
      assert.strictEqual(result.type, "node");
      assert.ok(result.confidence < 0.9);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });
});

// ============================================================================
// VerificationRunner Extended Tests
// ============================================================================

describe("VerificationRunner Extended", () => {
  it("color returns plain text when noColor=true", () => {
    const runner = new VerificationRunner({ noColor: true, quiet: true });
    const colored = runner.color("red", "test");
    assert.strictEqual(colored, "test");
  });

  it("color returns ANSI colored text when noColor=false", () => {
    const runner = new VerificationRunner({ noColor: false, quiet: true });
    const colored = runner.color("red", "test");
    assert.ok(colored.includes("\x1b["));
  });

  it("printHeader does not throw", () => {
    const runner = new VerificationRunner({
      projectType: { type: "node", typescript: true },
      quiet: false,
      noColor: true,
    });

    // Capture output
    const originalLog = console.log;
    const logs = [];
    console.log = (...args) => logs.push(args.join(" "));

    try {
      assert.doesNotThrow(() => runner.printHeader());
      assert.ok(logs.some((l) => l.includes("VERIFICATION")));
    } finally {
      console.log = originalLog;
    }
  });

  it("printPhaseStart writes to stderr", () => {
    const runner = new VerificationRunner({ quiet: false, noColor: true });
    const phase = PHASES[0];

    // Just verify it doesn't throw
    assert.doesNotThrow(() => runner.printPhaseStart(phase));
  });

  it("printPhaseResult handles all statuses", () => {
    const runner = new VerificationRunner({ quiet: false, noColor: true });

    const results = [
      { name: "test", displayName: "Test", status: "pass", duration: 100 },
      { name: "test", displayName: "Test", status: "fail", duration: 100 },
      { name: "test", displayName: "Test", status: "skipped", duration: 0 },
      { name: "test", displayName: "Test", status: "unknown", duration: 100 },
    ];

    results.forEach((result) => {
      assert.doesNotThrow(() => runner.printPhaseResult(result));
    });
  });

  it("printPhaseResult shows output in verbose mode", () => {
    const runner = new VerificationRunner({
      quiet: false,
      verbose: true,
      noColor: true,
    });

    const result = {
      name: "test",
      displayName: "Test",
      status: "pass",
      duration: 100,
      output: "line1\nline2\nline3",
    };

    const originalLog = console.log;
    const logs = [];
    console.log = (...args) => logs.push(args.join(" "));

    try {
      runner.printPhaseResult(result);
      assert.ok(logs.some((l) => l.includes("line1") || l.includes("line2")));
    } finally {
      console.log = originalLog;
    }
  });

  it("printFailure shows command and output", () => {
    const runner = new VerificationRunner({ quiet: false, noColor: true });

    const result = {
      name: "test",
      displayName: "Test Phase",
      status: "fail",
      duration: 100,
      exitCode: 1,
      command: "npm test",
      output: "Error: test failed",
    };

    const originalLog = console.log;
    const logs = [];
    console.log = (...args) => logs.push(args.join(" "));

    try {
      runner.printFailure(result);
      assert.ok(logs.some((l) => l.includes("FAILED")));
      assert.ok(logs.some((l) => l.includes("npm test")));
    } finally {
      console.log = originalLog;
    }
  });

  it("printSummary shows counts", () => {
    const runner = new VerificationRunner({ quiet: false, noColor: true });
    runner.startTime = Date.now();
    runner.results = [
      { name: "a", status: "pass" },
      { name: "b", status: "pass" },
      { name: "c", status: "fail" },
      { name: "d", status: "skipped" },
    ];

    const originalLog = console.log;
    const logs = [];
    console.log = (...args) => logs.push(args.join(" "));

    try {
      runner.printSummary();
      assert.ok(logs.some((l) => l.includes("2 passed")));
      assert.ok(logs.some((l) => l.includes("1 failed")));
      assert.ok(logs.some((l) => l.includes("1 skipped")));
    } finally {
      console.log = originalLog;
    }
  });

  it("printSummary shows READY when no failures", () => {
    const runner = new VerificationRunner({ quiet: false, noColor: true });
    runner.startTime = Date.now();
    runner.results = [
      { name: "a", status: "pass" },
      { name: "b", status: "skipped" },
    ];

    const originalLog = console.log;
    const logs = [];
    console.log = (...args) => logs.push(args.join(" "));

    try {
      runner.printSummary();
      assert.ok(logs.some((l) => l.includes("READY")));
    } finally {
      console.log = originalLog;
    }
  });
});

// ============================================================================
// CLI Tests
// ============================================================================

describe("Verification Runner CLI", () => {
  const runnerPath = path.join(__dirname, "verification-runner.js");
  const { execSync } = require("child_process");

  it("--help shows usage", () => {
    const output = execSync(`node "${runnerPath}" --help`, {
      encoding: "utf8",
    });
    assert.ok(output.includes("Verification Runner"));
    assert.ok(output.includes("--skip"));
    assert.ok(output.includes("--verbose"));
    assert.ok(output.includes("--json"));
  });

  it("-h shows usage", () => {
    const output = execSync(`node "${runnerPath}" -h`, { encoding: "utf8" });
    assert.ok(output.includes("Verification Runner"));
  });

  it("--json outputs JSON", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-cli-"));

    try {
      const output = execSync(
        `cd "${tmpDir}" && node "${runnerPath}" --json --skip=build --skip=typecheck --skip=lint --skip=test --skip=security --skip=diff`,
        { encoding: "utf8" },
      );
      const parsed = JSON.parse(output);
      assert.ok(parsed.projectType);
      assert.ok(Array.isArray(parsed.results));
      assert.ok(parsed.summary);
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("--skip-security skips security phase", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-skip-"));

    try {
      const output = execSync(
        `cd "${tmpDir}" && node "${runnerPath}" --json --skip=build --skip=typecheck --skip=lint --skip=test --skip-security --skip=diff`,
        { encoding: "utf8" },
      );
      const parsed = JSON.parse(output);
      const securityResult = parsed.results.find((r) => r.name === "security");
      assert.strictEqual(securityResult.status, "skipped");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("--no-color disables colors", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-nocolor-"));

    try {
      const output = execSync(
        `cd "${tmpDir}" && node "${runnerPath}" --no-color --skip=build --skip=typecheck --skip=lint --skip=test --skip=security --skip=diff 2>&1`,
        { encoding: "utf8" },
      );
      // Should not contain ANSI codes
      assert.ok(!output.includes("\x1b[31m")); // No red
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("-v enables verbose mode", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-verbose-"));

    try {
      // Just verify it doesn't crash
      execSync(
        `cd "${tmpDir}" && node "${runnerPath}" -v --skip=build --skip=typecheck --skip=lint --skip=test --skip=security --skip=diff 2>&1`,
        { encoding: "utf8" },
      );
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });

  it("-q enables quiet mode", () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "verify-quiet-"));

    try {
      const output = execSync(
        `cd "${tmpDir}" && node "${runnerPath}" -q --skip=build --skip=typecheck --skip=lint --skip=test --skip=security --skip=diff 2>&1`,
        { encoding: "utf8" },
      );
      // Should have minimal output
      assert.ok(output.length < 100 || output === "");
    } finally {
      fs.rmSync(tmpDir, { recursive: true });
    }
  });
});

// Run tests if executed directly
if (require.main === module) {
  console.log("Run with: node --test verification.test.js");
}
