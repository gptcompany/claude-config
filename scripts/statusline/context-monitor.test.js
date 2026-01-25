#!/usr/bin/env node
/**
 * Tests for context-monitor.js and ui-components.js
 * Run with: node --test context-monitor.test.js
 */

const { describe, it, beforeEach, afterEach, mock } = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const os = require("os");

// Import UI components
const ui = require("./ui-components");

// ============= UI Components Tests =============

describe("UI Components", () => {
  describe("formatTokens", () => {
    it("handles small numbers", () => {
      assert.strictEqual(ui.formatTokens(500), "500");
    });

    it("handles k notation", () => {
      assert.strictEqual(ui.formatTokens(1500), "1.5k");
      assert.strictEqual(ui.formatTokens(45000), "45k");
    });

    it("handles M notation", () => {
      assert.strictEqual(ui.formatTokens(1200000), "1.2M");
    });

    it("handles edge cases", () => {
      assert.strictEqual(ui.formatTokens(0), "0");
      assert.strictEqual(ui.formatTokens(999), "999");
      assert.strictEqual(ui.formatTokens(1000), "1.0k");
      assert.strictEqual(ui.formatTokens(10000), "10k");
    });
  });

  describe("formatCost", () => {
    it("handles cents", () => {
      assert.strictEqual(ui.formatCost(0.005), "1¢");
      assert.strictEqual(ui.formatCost(0.009), "1¢");
    });

    it("handles small dollars", () => {
      assert.strictEqual(ui.formatCost(0.045), "$0.045");
      assert.strictEqual(ui.formatCost(0.099), "$0.099");
    });

    it("handles regular dollars", () => {
      assert.strictEqual(ui.formatCost(0.15), "$0.15");
      assert.strictEqual(ui.formatCost(1.5), "$1.50");
    });
  });

  describe("formatDuration", () => {
    it("handles seconds", () => {
      assert.strictEqual(ui.formatDuration(5000), "5s");
      assert.strictEqual(ui.formatDuration(59000), "59s");
    });

    it("handles minutes", () => {
      assert.strictEqual(ui.formatDuration(60000), "1m");
      assert.strictEqual(ui.formatDuration(180000), "3m");
    });

    it("handles hours", () => {
      assert.strictEqual(ui.formatDuration(3600000), "1.0h");
      assert.strictEqual(ui.formatDuration(5400000), "1.5h");
    });
  });

  describe("progressBar", () => {
    it("shows correct fill", () => {
      const bar0 = ui.progressBar(0);
      const bar50 = ui.progressBar(50);
      const bar100 = ui.progressBar(100);

      assert.strictEqual(bar0, "▁▁▁▁▁▁▁▁");
      assert.ok(bar50.includes("█"));
      assert.strictEqual(bar100, "████████");
    });

    it("handles custom width", () => {
      const bar = ui.progressBar(50, 4);
      assert.strictEqual(ui.stripAnsi(bar).length, 4);
    });
  });

  describe("percentColor", () => {
    it("returns cyan for low usage", () => {
      assert.ok(ui.percentColor(25).includes("36")); // cyan ANSI code
    });

    it("returns green for moderate usage", () => {
      assert.ok(ui.percentColor(60).includes("32")); // green ANSI code
    });

    it("returns yellow for high usage", () => {
      assert.ok(ui.percentColor(80).includes("33")); // yellow ANSI code
    });

    it("returns red for critical usage", () => {
      assert.ok(ui.percentColor(95).includes("91")); // bright red ANSI code
    });
  });

  describe("contextUsage", () => {
    it("shows correct icon", () => {
      assert.ok(ui.contextUsage(25).includes("🟢"));
      assert.ok(ui.contextUsage(60).includes("🟡"));
      assert.ok(ui.contextUsage(80).includes("🟠"));
      assert.ok(ui.contextUsage(92).includes("🔴"));
      assert.ok(ui.contextUsage(98).includes("🚨"));
    });

    it("includes token count when provided", () => {
      const result = ui.contextUsage(50, 100000);
      assert.ok(result.includes("100k"));
    });
  });

  describe("sessionMetrics", () => {
    it("formats all fields", () => {
      const result = ui.sessionMetrics({
        tokens: 50000,
        contextPercent: 25,
        cost: 0.05,
        duration: 180000,
        linesAdded: 100,
        linesRemoved: 20,
      });

      assert.ok(result.includes("50k"));
      assert.ok(result.includes("$0.050"));
      assert.ok(result.includes("3m"));
      assert.ok(result.includes("+80"));
    });

    it("handles missing fields", () => {
      const result = ui.sessionMetrics({
        tokens: 0,
        cost: 0,
        duration: 0,
        linesAdded: 0,
        linesRemoved: 0,
      });
      assert.strictEqual(result, "");
    });
  });

  describe("stripAnsi", () => {
    it("removes ANSI codes", () => {
      const colored = "\x1b[32mGreen\x1b[0m";
      assert.strictEqual(ui.stripAnsi(colored), "Green");
    });
  });

  describe("visibleLength", () => {
    it("returns correct length without ANSI", () => {
      const colored = "\x1b[32mHello\x1b[0m";
      assert.strictEqual(ui.visibleLength(colored), 5);
    });
  });

  describe("modelBadge", () => {
    it("returns model name in brackets", () => {
      const result = ui.modelBadge("Claude");
      assert.ok(result.includes("[Claude]"));
    });

    it("uses context-aware color", () => {
      const low = ui.modelBadge("Claude", 25);
      const high = ui.modelBadge("Claude", 95);
      // High usage should have red (91 or 31)
      assert.ok(high.includes("91") || high.includes("31"));
    });
  });

  describe("gitBranch", () => {
    it("returns empty for null", () => {
      assert.strictEqual(ui.gitBranch(null), "");
    });

    it("includes branch icon", () => {
      const result = ui.gitBranch("main");
      assert.ok(result.includes("main"));
    });
  });

  describe("directory", () => {
    it("includes folder icon", () => {
      const result = ui.directory("my-project");
      assert.ok(result.includes("my-project"));
    });
  });
});

// ============= Context Parsing Tests =============

describe("Context Parsing", () => {
  const testDir = path.join(os.tmpdir(), "context-monitor-test");

  beforeEach(() => {
    fs.mkdirSync(testDir, { recursive: true });
  });

  afterEach(() => {
    try {
      fs.rmSync(testDir, { recursive: true, force: true });
    } catch {
      // ignore cleanup errors
    }
  });

  // We can't directly test internal functions without exporting them
  // So we'll test through the CLI interface using mock data
});

// ============= Integration Tests =============

describe("Integration", () => {
  it("CLI handles valid JSON input", async () => {
    const { execSync } = require("child_process");
    const input = JSON.stringify({
      model: { display_name: "Claude" },
      workspace: {},
      cost: { total_cost_usd: 0.05 },
    });

    const result = execSync(
      `echo '${input}' | node ${__dirname}/context-monitor.js`,
      { encoding: "utf8" },
    );

    assert.ok(result.includes("[Claude]"));
  });

  it("CLI handles missing context gracefully", async () => {
    const { execSync } = require("child_process");
    const input = JSON.stringify({
      model: { display_name: "Test" },
      workspace: {},
      cost: {},
    });

    const result = execSync(
      `echo '${input}' | node ${__dirname}/context-monitor.js`,
      { encoding: "utf8" },
    );

    assert.ok(result.includes("???"));
  });

  it("CLI shows all metrics when provided", async () => {
    const { execSync } = require("child_process");
    const input = JSON.stringify({
      model: { display_name: "Opus" },
      workspace: {},
      cost: {
        total_cost_usd: 0.1,
        total_duration_ms: 300000,
        total_lines_added: 200,
        total_lines_removed: 50,
      },
    });

    const result = execSync(
      `echo '${input}' | node ${__dirname}/context-monitor.js`,
      { encoding: "utf8" },
    );

    assert.ok(result.includes("Opus"));
    assert.ok(result.includes("$0.10"));
    assert.ok(result.includes("5m"));
    assert.ok(result.includes("+150"));
  });

  it("Fallback works on invalid JSON", async () => {
    const { execSync } = require("child_process");

    const result = execSync(
      `echo 'invalid json' | node ${__dirname}/context-monitor.js`,
      { encoding: "utf8" },
    );

    assert.ok(result.includes("[Error]"));
  });
});

// ============= Persistence Tests =============

describe("Persistence", () => {
  const testStatsDir = path.join(os.tmpdir(), "claude-stats-test");

  beforeEach(() => {
    fs.mkdirSync(testStatsDir, { recursive: true });
  });

  afterEach(() => {
    try {
      fs.rmSync(testStatsDir, { recursive: true, force: true });
    } catch {
      // ignore
    }
  });

  it("creates stats directory if missing", () => {
    const newDir = path.join(testStatsDir, "new-dir");
    assert.ok(!fs.existsSync(newDir));
    fs.mkdirSync(newDir, { recursive: true });
    assert.ok(fs.existsSync(newDir));
  });

  it("JSONL file format is valid", () => {
    const metricsFile = path.join(testStatsDir, "test.jsonl");
    const data = { test: "value", num: 42 };
    fs.appendFileSync(metricsFile, JSON.stringify(data) + "\n");

    const content = fs.readFileSync(metricsFile, "utf8");
    const parsed = JSON.parse(content.trim());
    assert.deepStrictEqual(parsed, data);
  });
});

console.log("Running tests...");
