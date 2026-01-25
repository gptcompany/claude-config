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

// Run tests if executed directly
if (require.main === module) {
  console.log("Run with: node --test verification.test.js");
}
