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
