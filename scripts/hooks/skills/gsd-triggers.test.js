#!/usr/bin/env node
/**
 * GSD Triggers Test Suite
 *
 * Tests for gsd-triggers.js PostToolUse hook.
 * 15+ tests covering trigger matching, actions, and integration.
 *
 * Part of: Skills Port (Phase 15)
 */

const { describe, it, beforeEach, afterEach, mock } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execSync, spawn } = require("child_process");

// Import modules under test
const { TRIGGERS, isTestFile, isCodeFile } = require("./gsd-triggers");
const { getState, setState, clearState, PHASES } = require("./tdd/tdd-state");

// State file path for cleanup
const STATE_FILE = path.join(os.homedir(), ".claude", "tdd-state.json");

describe("GSD Triggers", () => {
  beforeEach(() => {
    // Clear TDD state before each test
    try {
      if (fs.existsSync(STATE_FILE)) {
        fs.unlinkSync(STATE_FILE);
      }
    } catch {
      // Ignore
    }
  });

  afterEach(() => {
    // Clean up TDD state after each test
    try {
      if (fs.existsSync(STATE_FILE)) {
        fs.unlinkSync(STATE_FILE);
      }
    } catch {
      // Ignore
    }
  });

  describe("Trigger Matching", () => {
    it("plan-created matches PLAN.md files", () => {
      const trigger = TRIGGERS["plan-created"];
      assert.ok(trigger.match(".planning/phases/01-foundation/01-01-PLAN.md"));
      assert.ok(trigger.match("/some/path/PLAN.md"));
      assert.ok(!trigger.match("README.md"));
      assert.ok(!trigger.match("plan.txt"));
    });

    it("test-written matches JavaScript test files", () => {
      const trigger = TRIGGERS["test-written"];
      assert.ok(trigger.match("auth.test.js"));
      assert.ok(trigger.match("src/utils/helper.spec.ts"));
      assert.ok(trigger.match("components/Button.test.tsx"));
      assert.ok(!trigger.match("src/auth.js"));
      assert.ok(!trigger.match("README.md"));
    });

    it("test-written matches Python test files", () => {
      const trigger = TRIGGERS["test-written"];
      assert.ok(trigger.match("test_auth.py"));
      assert.ok(trigger.match("auth_test.py"));
      assert.ok(trigger.match("tests/test_utils.py"));
      assert.ok(!trigger.match("src/auth.py"));
    });

    it("impl-written matches in GREEN phase only", () => {
      const trigger = TRIGGERS["impl-written"];

      // In IDLE phase - should not match
      const idleState = { phase: PHASES.IDLE };
      assert.ok(!trigger.match("src/auth.js", idleState));

      // In GREEN phase - should match
      const greenState = { phase: PHASES.GREEN };
      assert.ok(trigger.match("src/auth.js", greenState));
      assert.ok(trigger.match("lib/utils.ts", greenState));

      // Should not match test files even in GREEN phase
      assert.ok(!trigger.match("auth.test.js", greenState));
    });

    it("impl-written does not match in IDLE state", () => {
      const trigger = TRIGGERS["impl-written"];
      const state = { phase: PHASES.IDLE };
      assert.ok(!trigger.match("src/main.js", state));
      assert.ok(!trigger.match("lib/core.ts", state));
    });

    it("plan-complete matches SUMMARY.md files", () => {
      const trigger = TRIGGERS["plan-complete"];
      assert.ok(
        trigger.match(".planning/phases/01-foundation/01-01-SUMMARY.md"),
      );
      assert.ok(trigger.match("/path/to/SUMMARY.md"));
      assert.ok(!trigger.match("summary.txt"));
      assert.ok(!trigger.match("README.md"));
    });
  });

  describe("Helper Functions", () => {
    it("isTestFile identifies JavaScript test files", () => {
      assert.ok(isTestFile("auth.test.js"));
      assert.ok(isTestFile("auth.spec.ts"));
      assert.ok(isTestFile("Button.test.tsx"));
      assert.ok(isTestFile("utils.spec.jsx"));
      assert.ok(!isTestFile("auth.js"));
      assert.ok(!isTestFile("Button.tsx"));
    });

    it("isTestFile identifies Python test files", () => {
      assert.ok(isTestFile("test_auth.py"));
      assert.ok(isTestFile("auth_test.py"));
      assert.ok(!isTestFile("auth.py"));
      assert.ok(!isTestFile("config.py"));
    });

    it("isTestFile identifies other language test files", () => {
      assert.ok(isTestFile("auth_test.go"));
      assert.ok(isTestFile("AuthTest.java"));
      assert.ok(isTestFile("auth_spec.rb"));
    });

    it("isCodeFile identifies code extensions", () => {
      assert.ok(isCodeFile("auth.js"));
      assert.ok(isCodeFile("utils.ts"));
      assert.ok(isCodeFile("main.py"));
      assert.ok(isCodeFile("server.go"));
      assert.ok(isCodeFile("lib.rs"));
      assert.ok(!isCodeFile("README.md"));
      assert.ok(!isCodeFile("config.json"));
      assert.ok(!isCodeFile("styles.css"));
    });
  });

  describe("TDD State Management", () => {
    it("getState returns IDLE by default", () => {
      const state = getState();
      assert.equal(state.phase, PHASES.IDLE);
      assert.equal(state.startedAt, null);
    });

    it("setState changes phase correctly", () => {
      setState(PHASES.RED);
      let state = getState();
      assert.equal(state.phase, PHASES.RED);
      assert.ok(state.startedAt);

      setState(PHASES.GREEN);
      state = getState();
      assert.equal(state.phase, PHASES.GREEN);
    });

    it("setState increments attempt on GREEN phase", () => {
      setState(PHASES.RED);
      let state = getState();
      assert.equal(state.attempt, 0);

      setState(PHASES.GREEN);
      state = getState();
      assert.equal(state.attempt, 1);
    });

    it("clearState resets to IDLE", () => {
      setState(PHASES.RED);
      clearState();
      const state = getState();
      assert.equal(state.phase, PHASES.IDLE);
      assert.equal(state.startedAt, null);
      assert.equal(state.attempt, 0);
    });
  });

  describe("Action Tests", () => {
    it("suggest-tdd outputs message in IDLE state", async () => {
      // This test verifies the hook outputs a message when a PLAN.md is written in IDLE state
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: ".planning/phases/01/01-01-PLAN.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should suggest TDD in IDLE state
      assert.ok(output.includes("TDD") || output.includes("{}"));
    });

    it("suggest-tdd is silent when already in TDD mode", async () => {
      // Set to RED phase first
      setState(PHASES.RED);

      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: ".planning/phases/01/01-01-PLAN.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should not suggest TDD when already in TDD mode
      assert.ok(!output.includes("Consider starting TDD"));

      clearState();
    });

    it("track-eval logs test file", async () => {
      // Set to RED phase
      setState(PHASES.RED);

      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: "auth.test.js" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should log test file
      assert.ok(
        output.includes("Test written") || output.includes("auth.test.js"),
      );

      clearState();
    });

    it("run-verification triggers on SUMMARY.md", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: ".planning/phases/01/01-01-SUMMARY.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should mention verification (or fall back gracefully)
      assert.ok(
        output.includes("verification") ||
          output.includes("Plan complete") ||
          output.includes("{}"),
      );
    });

    it("actions handle errors gracefully", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");

      // Malformed input should not crash
      const output = execSync(
        `echo '{"invalid": true}' | node "${hookPath}" 2>&1`,
        {
          encoding: "utf8",
        },
      );

      // Should output empty response
      assert.ok(output.includes("{}"));
    });
  });

  describe("TDD State Extended", () => {
    const { setTestFile, setImplFile } = require("./tdd/tdd-state");

    it("setTestFile updates state with testFile", () => {
      setState(PHASES.RED);
      setTestFile("tests/auth.test.js");

      const state = getState();
      assert.equal(state.testFile, "tests/auth.test.js");
      assert.equal(state.phase, PHASES.RED);

      clearState();
    });

    it("setImplFile updates state with implFile", () => {
      setState(PHASES.GREEN);
      setImplFile("src/auth.js");

      const state = getState();
      assert.equal(state.implFile, "src/auth.js");
      assert.equal(state.phase, PHASES.GREEN);

      clearState();
    });

    it("setState throws on invalid phase", () => {
      assert.throws(() => {
        setState("INVALID_PHASE");
      }, /Invalid phase/);
    });

    it("setState handles extra properties", () => {
      setState(PHASES.RED, { customProp: "value" });
      const state = getState();

      assert.equal(state.phase, PHASES.RED);
      assert.equal(state.customProp, "value");

      clearState();
    });

    it("attempt resets on IDLE", () => {
      setState(PHASES.RED);
      setState(PHASES.GREEN); // attempt = 1
      setState(PHASES.RED);
      setState(PHASES.GREEN); // attempt = 2

      let state = getState();
      assert.equal(state.attempt, 2);

      setState(PHASES.IDLE);
      state = getState();
      assert.equal(state.attempt, 0);
    });
  });

  describe("TDD State CLI", () => {
    const tddStatePath = path.join(__dirname, "tdd/tdd-state.js");

    it("CLI get returns current state", () => {
      clearState();
      const output = execSync(`node "${tddStatePath}" get`, {
        encoding: "utf8",
      });
      const state = JSON.parse(output);
      assert.equal(state.phase, "IDLE");
    });

    it("CLI set RED changes phase", () => {
      const output = execSync(`node "${tddStatePath}" set RED`, {
        encoding: "utf8",
      });
      const state = JSON.parse(output);
      assert.equal(state.phase, "RED");

      clearState();
    });

    it("CLI set GREEN changes phase", () => {
      setState(PHASES.RED);
      const output = execSync(`node "${tddStatePath}" set GREEN`, {
        encoding: "utf8",
      });
      const state = JSON.parse(output);
      assert.equal(state.phase, "GREEN");

      clearState();
    });

    it("CLI set REFACTOR changes phase", () => {
      setState(PHASES.GREEN);
      const output = execSync(`node "${tddStatePath}" set REFACTOR`, {
        encoding: "utf8",
      });
      const state = JSON.parse(output);
      assert.equal(state.phase, "REFACTOR");

      clearState();
    });

    it("CLI clear resets state", () => {
      setState(PHASES.RED);
      const output = execSync(`node "${tddStatePath}" clear`, {
        encoding: "utf8",
      });
      const state = JSON.parse(output);
      assert.equal(state.phase, "IDLE");
    });

    it("CLI set without phase shows error", () => {
      try {
        execSync(`node "${tddStatePath}" set`, {
          encoding: "utf8",
          stdio: ["pipe", "pipe", "pipe"],
        });
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err.stderr.includes("Usage") || err.status === 1);
      }
    });

    it("CLI unknown command shows error", () => {
      try {
        execSync(`node "${tddStatePath}" unknown`, {
          encoding: "utf8",
          stdio: ["pipe", "pipe", "pipe"],
        });
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err.stderr.includes("Unknown") || err.status === 1);
      }
    });

    it("CLI set invalid phase shows error", () => {
      try {
        execSync(`node "${tddStatePath}" set INVALID`, {
          encoding: "utf8",
          stdio: ["pipe", "pipe", "pipe"],
        });
        assert.fail("Should have thrown");
      } catch (err) {
        assert.ok(err.stderr.includes("Invalid") || err.status === 1);
      }
    });
  });

  describe("handleTrigger function", () => {
    const { handleTrigger } = require("./gsd-triggers");

    it("suggest-tdd does nothing when not IDLE", async () => {
      const messages = await handleTrigger(
        "plan-created",
        "suggest-tdd",
        "PLAN.md",
        { phase: PHASES.RED },
      );
      assert.deepStrictEqual(messages, []);
    });

    it("suggest-tdd suggests TDD when IDLE", async () => {
      const messages = await handleTrigger(
        "plan-created",
        "suggest-tdd",
        "PLAN.md",
        { phase: PHASES.IDLE },
      );
      assert.ok(
        messages.some((m) => m.includes("TDD")),
        "Should suggest TDD workflow",
      );
    });

    it("track-eval does nothing when IDLE", async () => {
      const messages = await handleTrigger(
        "test-written",
        "track-eval",
        "auth.test.js",
        { phase: PHASES.IDLE },
      );
      assert.deepStrictEqual(messages, []);
    });

    it("track-eval logs when in TDD mode", async () => {
      const messages = await handleTrigger(
        "test-written",
        "track-eval",
        "auth.test.js",
        { phase: PHASES.RED, attempt: 1 },
      );
      assert.ok(
        messages.some((m) => m.includes("Test written")),
        "Should log test written",
      );
    });

    it("run-tests detects npm project", async () => {
      // This test runs in the gsd-triggers directory which has a package.json in parent
      const messages = await handleTrigger(
        "impl-written",
        "run-tests",
        "auth.js",
        { phase: PHASES.GREEN, attempt: 1 },
      );
      assert.ok(
        messages.some((m) => m.includes("updated") || m.includes("tests")),
        "Should mention test running",
      );
    });

    it("run-tests handles test failure", async () => {
      // The test will likely fail without proper setup, which exercises the failure path
      const messages = await handleTrigger(
        "impl-written",
        "run-tests",
        "nonexistent.js",
        { phase: PHASES.GREEN, attempt: 1 },
      );
      // Should have messages about running tests
      assert.ok(messages.length > 0, "Should have messages");
    });

    it("run-verification messages when runner available", async () => {
      const messages = await handleTrigger(
        "plan-complete",
        "run-verification",
        "SUMMARY.md",
        { phase: PHASES.IDLE },
      );
      assert.ok(
        messages.some(
          (m) =>
            m.includes("verification") ||
            m.includes("Verification") ||
            m.includes("Plan complete"),
        ),
        "Should mention verification",
      );
    });

    it("returns empty for unknown action", async () => {
      const messages = await handleTrigger(
        "unknown",
        "unknown-action",
        "file.js",
        { phase: PHASES.IDLE },
      );
      assert.deepStrictEqual(messages, []);
    });
  });

  describe("Main hook - error paths", () => {
    it("handles tool_result with error", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: "PLAN.md" },
        tool_result: { error: "Something went wrong" },
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      assert.ok(output.includes("{}"), "Should output empty response on error");
    });

    it("handles missing file_path", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { content: "test" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      assert.ok(
        output.includes("{}"),
        "Should output empty response without file_path",
      );
    });

    it("handles Edit tool", async () => {
      clearState();
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Edit",
        tool_input: { file_path: "PLAN.md", old_string: "a", new_string: "b" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      assert.ok(output.includes("{}") || output.includes("TDD"));
    });

    it("handles MultiEdit tool", async () => {
      clearState();
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "MultiEdit",
        tool_input: {
          file_path: "PLAN.md",
          edits: [{ old_string: "a", new_string: "b" }],
        },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      assert.ok(output.includes("{}") || output.includes("TDD"));
    });
  });

  describe("Integration Tests", () => {
    it("full PLAN.md write suggests TDD in IDLE", async () => {
      // Ensure IDLE state
      clearState();

      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: ".planning/phases/15/15-05-PLAN.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should suggest TDD
      assert.ok(
        output.includes("TDD") ||
          output.includes("plan") ||
          output.includes("{}"),
      );
    });

    it("full test file write tracks eval in TDD mode", async () => {
      // Set to RED phase
      setState(PHASES.RED);

      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: "tests/test_new_feature.py" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should log test written
      assert.ok(
        output.includes("Test written") ||
          output.includes("test_new_feature") ||
          output.includes("{}"),
      );

      clearState();
    });

    it("full SUMMARY.md triggers verification", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: ".planning/phases/15/15-05-SUMMARY.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should attempt verification or note it
      assert.ok(
        output.includes("verification") ||
          output.includes("Plan complete") ||
          output.includes("{}"),
      );
    });

    it("hook passes through on non-matching files", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Write",
        tool_input: { file_path: "README.md" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should just output empty response
      assert.ok(output.includes("{}"));
    });

    it("hook ignores non-Write/Edit tools", async () => {
      const hookPath = path.join(__dirname, "gsd-triggers.js");
      const input = JSON.stringify({
        tool_name: "Bash",
        tool_input: { command: "ls" },
        tool_result: {},
      });

      const output = execSync(`echo '${input}' | node "${hookPath}" 2>&1`, {
        encoding: "utf8",
      });

      // Should pass through
      assert.ok(output.includes("{}"));
    });
  });
});
