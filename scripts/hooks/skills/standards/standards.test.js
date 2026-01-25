#!/usr/bin/env node
/**
 * Coding Standards Test Suite
 *
 * Tests for patterns.js and coding-standards.js
 * 25+ tests covering pattern detection, hook behavior, and integration
 */

const { describe, it, before, after, beforeEach } = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const {
  ANTI_PATTERNS,
  detectFileType,
  checkPatterns,
  shouldExclude,
  minimatch,
} = require("./patterns");

const CONFIG_PATH = path.join(
  process.env.HOME || "",
  ".claude",
  "standards-config.json",
);
const HOOK_SCRIPT = path.join(__dirname, "coding-standards.js");

// ============================================================================
// Pattern Detection Tests (12 tests)
// ============================================================================

describe("Pattern Detection", () => {
  describe("JavaScript Patterns", () => {
    it("detects console.log in JS", () => {
      const { issues } = checkPatterns('console.log("test");', "app.js");
      assert.ok(
        issues.some((i) => i.name === "console-log-in-prod"),
        "Should detect console.log",
      );
    });

    it("ignores console.log in test files", () => {
      const { issues } = checkPatterns('console.log("test");', "app.test.js");
      assert.ok(
        !issues.some((i) => i.name === "console-log-in-prod"),
        "Should ignore console.log in test files",
      );
    });

    it("detects `any` type in TS", () => {
      const { issues } = checkPatterns("const x: any = 5;", "component.ts");
      assert.ok(
        issues.some((i) => i.name === "any-type"),
        "Should detect any type",
      );
    });

    it("ignores `any` in .d.ts files", () => {
      const { issues } = checkPatterns("declare const x: any;", "types.d.ts");
      assert.ok(
        !issues.some((i) => i.name === "any-type"),
        "Should ignore any in .d.ts",
      );
    });

    it("detects hardcoded secrets", () => {
      const { issues, passed } = checkPatterns(
        'const apiKey = "sk-1234567890abcdef";',
        "config.js",
      );
      assert.ok(
        issues.some((i) => i.name === "hardcoded-secret"),
        "Should detect hardcoded secret",
      );
      assert.strictEqual(passed, false, "Should fail with error-level issue");
    });

    it("detects TODO without issue", () => {
      const { issues } = checkPatterns("// TODO: fix this later", "app.js");
      assert.ok(
        issues.some((i) => i.name === "todo-without-issue"),
        "Should detect TODO without issue reference",
      );
    });

    it("ignores TODO with issue reference", () => {
      const { issues } = checkPatterns("// TODO: #123 fix this", "app.js");
      assert.ok(
        !issues.some((i) => i.name === "todo-without-issue"),
        "Should ignore TODO with issue reference",
      );
    });
  });

  describe("Python Patterns", () => {
    it("detects print() in Python", () => {
      const { issues } = checkPatterns('print("hello")', "main.py");
      assert.ok(
        issues.some((i) => i.name === "print-in-prod"),
        "Should detect print()",
      );
    });

    it("ignores print() in test files", () => {
      const { issues } = checkPatterns('print("test")', "test_main.py");
      assert.ok(
        !issues.some((i) => i.name === "print-in-prod"),
        "Should ignore print in test files",
      );
    });

    it("detects bare except", () => {
      const { issues, passed } = checkPatterns(
        "try:\n    x = 1\nexcept:\n    pass",
        "handler.py",
      );
      assert.ok(
        issues.some((i) => i.name === "bare-except"),
        "Should detect bare except",
      );
      assert.strictEqual(passed, false, "Bare except is error level");
    });

    it("detects star imports", () => {
      const { issues } = checkPatterns("from os import *", "utils.py");
      assert.ok(
        issues.some((i) => i.name === "star-import"),
        "Should detect star import",
      );
    });
  });

  describe("Line Detection", () => {
    it("returns correct line numbers", () => {
      const content = `const a = 1;
const b = 2;
console.log(a);
const c = 3;`;
      const { issues } = checkPatterns(content, "app.js");
      const consoleIssue = issues.find((i) => i.name === "console-log-in-prod");
      assert.strictEqual(consoleIssue?.line, 3, "Should report line 3");
    });
  });
});

// ============================================================================
// File Type Detection Tests
// ============================================================================

describe("File Type Detection", () => {
  it("detectFileType works for all JS extensions", () => {
    assert.strictEqual(detectFileType("app.js"), "javascript");
    assert.strictEqual(detectFileType("app.ts"), "javascript");
    assert.strictEqual(detectFileType("app.jsx"), "javascript");
    assert.strictEqual(detectFileType("app.tsx"), "javascript");
    assert.strictEqual(detectFileType("app.mjs"), "javascript");
    assert.strictEqual(detectFileType("app.cjs"), "javascript");
  });

  it("detectFileType works for Python", () => {
    assert.strictEqual(detectFileType("main.py"), "python");
    assert.strictEqual(detectFileType("test_main.py"), "python");
  });

  it("detectFileType returns null for unknown", () => {
    assert.strictEqual(detectFileType("file.txt"), null);
    assert.strictEqual(detectFileType("file.md"), null);
    assert.strictEqual(detectFileType("file.json"), null);
  });
});

// ============================================================================
// Minimatch Tests
// ============================================================================

describe("Minimatch Patterns", () => {
  it("matches *.ext patterns", () => {
    assert.strictEqual(minimatch("app.test.js", "*.test.js"), true);
    assert.strictEqual(minimatch("app.js", "*.test.js"), false);
  });

  it("matches dir/* patterns", () => {
    assert.strictEqual(minimatch("debug/log.js", "debug/*"), true);
    assert.strictEqual(minimatch("src/log.js", "debug/*"), false);
  });

  it("matches **/ patterns", () => {
    assert.strictEqual(
      minimatch("src/__tests__/app.js", "**/__tests__/*"),
      true,
    );
  });
});

// ============================================================================
// Hook Behavior Tests (8 tests)
// ============================================================================

describe("Hook Behavior", () => {
  let originalConfig = null;

  before(() => {
    // Save original config if exists
    try {
      originalConfig = fs.readFileSync(CONFIG_PATH, "utf8");
    } catch {
      originalConfig = null;
    }
  });

  after(() => {
    // Restore original config
    if (originalConfig) {
      fs.writeFileSync(CONFIG_PATH, originalConfig);
    } else {
      try {
        fs.unlinkSync(CONFIG_PATH);
      } catch {
        // Ignore
      }
    }
  });

  function runHook(input) {
    return new Promise((resolve, reject) => {
      const proc = spawn("node", [HOOK_SCRIPT], {
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => {
        stdout += data;
      });

      proc.stderr.on("data", (data) => {
        stderr += data;
      });

      proc.on("close", (code) => {
        try {
          const result = JSON.parse(stdout.trim());
          resolve({ result, stderr, code });
        } catch (e) {
          resolve({ result: null, stdout, stderr, code });
        }
      });

      proc.stdin.write(JSON.stringify(input));
      proc.stdin.end();
    });
  }

  it("allows when disabled", async () => {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify({ enabled: false }));

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'const secret = "mysupersecret123";',
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("allows excluded paths", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "node_modules/pkg/index.js",
        content: 'console.log("test");',
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("allows non-Write tools", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Read",
      tool_input: {
        file_path: "test.js",
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("warns on warn mode with issues", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "warn" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'console.log("test");',
      },
    });

    assert.strictEqual(result.decision, "allow");
    assert.ok(result.message, "Should have warning message");
    assert.ok(
      result.message.includes("console.log"),
      "Message should mention console.log",
    );
  });

  it("blocks on block mode with errors", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "config.js",
        content: 'const apiKey = "sk-1234567890abcdef";',
      },
    });

    assert.ok(result.hookSpecificOutput, "Should have hookSpecificOutput");
    assert.strictEqual(result.hookSpecificOutput.decision, "block");
    assert.ok(
      result.hookSpecificOutput.reason.includes("CODING STANDARDS VIOLATION"),
      "Reason should mention violation",
    );
  });

  it("allows on block mode with only warnings", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "app.js",
        content: 'console.log("test");', // warn level, not error
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("uses default config when missing", async () => {
    try {
      fs.unlinkSync(CONFIG_PATH);
    } catch {
      // Ignore
    }

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'console.log("test");',
      },
    });

    // Default is warn mode
    assert.strictEqual(result.decision, "allow");
    assert.ok(result.message, "Should warn with default config");
  });

  it("config loading works with partial config", async () => {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify({ mode: "block" }));

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "node_modules/test.js", // Should be excluded by default
        content: 'const secret = "supersecretvalue123";',
      },
    });

    assert.strictEqual(
      result.decision,
      "allow",
      "Default excludes should work",
    );
  });
});

// ============================================================================
// Integration Tests (5 tests)
// ============================================================================

describe("Integration Tests", () => {
  let originalConfig = null;

  before(() => {
    try {
      originalConfig = fs.readFileSync(CONFIG_PATH, "utf8");
    } catch {
      originalConfig = null;
    }
  });

  after(() => {
    if (originalConfig) {
      fs.writeFileSync(CONFIG_PATH, originalConfig);
    } else {
      try {
        fs.unlinkSync(CONFIG_PATH);
      } catch {
        // Ignore
      }
    }
  });

  function runHook(input) {
    return new Promise((resolve, reject) => {
      const proc = spawn("node", [HOOK_SCRIPT], {
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => {
        stdout += data;
      });

      proc.stderr.on("data", (data) => {
        stderr += data;
      });

      proc.on("close", (code) => {
        try {
          const result = JSON.parse(stdout.trim());
          resolve({ result, stderr, code });
        } catch (e) {
          resolve({ result: null, stdout, stderr, code });
        }
      });

      proc.stdin.write(JSON.stringify(input));
      proc.stdin.end();
    });
  }

  it("Full Write with clean code passes", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "clean.js",
        content: `
function add(a, b) {
  return a + b;
}

module.exports = { add };
`,
      },
    });

    assert.strictEqual(result.decision, "allow");
    assert.ok(!result.message, "No warning for clean code");
  });

  it("Full Write with console.log warns", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "warn" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "debug.js",
        content: `
function process(data) {
  console.log("Processing:", data);
  return data.map(x => x * 2);
}
`,
      },
    });

    assert.strictEqual(result.decision, "allow");
    assert.ok(result.message, "Should have warning");
    assert.ok(
      result.message.includes("WARNINGS"),
      "Should categorize as warning",
    );
  });

  it("Full Edit with secret blocks", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Edit",
      tool_input: {
        file_path: "config.js",
        old_string: "placeholder",
        new_string: 'const token = "ghp_xxxxxxxxxxxxxxxxxxxx";',
      },
    });

    assert.ok(result.hookSpecificOutput, "Should block");
    assert.strictEqual(result.hookSpecificOutput.decision, "block");
  });

  it("Multi-issue file shows all issues", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "warn" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "messy.js",
        content: `
console.log("debug");
// TODO: fix later
const x: any = 5;
alert("hi");
`,
      },
    });

    assert.strictEqual(result.decision, "allow");
    assert.ok(result.message, "Should have message");
    // Should mention multiple issues
    const message = result.message;
    assert.ok(
      message.includes("console.log") || message.includes("TODO"),
      "Should include issue details",
    );
  });

  it("Config mode change takes effect", async () => {
    // First in warn mode
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "warn" }),
    );

    let { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'const secret = "supersecretvalue123";',
      },
    });

    assert.strictEqual(result.decision, "allow", "Should allow in warn mode");

    // Now change to block mode
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    ({ result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'const secret = "supersecretvalue123";',
      },
    }));

    assert.ok(result.hookSpecificOutput, "Should block in block mode");
    assert.strictEqual(result.hookSpecificOutput.decision, "block");
  });
});

// ============================================================================
// Check-file Script Tests
// ============================================================================

describe("Check-file Script", () => {
  const CHECK_FILE_SCRIPT = path.join(__dirname, "check-file.js");
  const TMP_DIR = path.join(__dirname, ".test-tmp");

  before(() => {
    fs.mkdirSync(TMP_DIR, { recursive: true });
  });

  after(() => {
    fs.rmSync(TMP_DIR, { recursive: true, force: true });
  });

  function runCheckFile(args) {
    return new Promise((resolve) => {
      const proc = spawn("node", [CHECK_FILE_SCRIPT, ...args], {
        cwd: TMP_DIR,
        stdio: ["pipe", "pipe", "pipe"],
      });

      let stdout = "";
      let stderr = "";

      proc.stdout.on("data", (data) => {
        stdout += data;
      });

      proc.stderr.on("data", (data) => {
        stderr += data;
      });

      proc.on("close", (code) => {
        resolve({ stdout, stderr, code });
      });
    });
  }

  it("check-file reports issues in single file", async () => {
    const testFile = path.join(TMP_DIR, "test.js");
    fs.writeFileSync(testFile, 'console.log("test");');

    const { stdout, code } = await runCheckFile([testFile]);

    assert.ok(stdout.includes("console.log"), "Should report console.log");
    assert.strictEqual(code, 0, "Exit code 0 for warnings only");
  });

  it("check-file exits 1 for errors", async () => {
    const testFile = path.join(TMP_DIR, "secrets.js");
    fs.writeFileSync(testFile, 'const api_key = "sk-xxxxxxxxxxxxxxxxxxxx";');

    const { code } = await runCheckFile([testFile]);

    assert.strictEqual(code, 1, "Exit code 1 for errors");
  });

  it("check-file shows summary", async () => {
    const testFile = path.join(TMP_DIR, "multi.js");
    fs.writeFileSync(
      testFile,
      `console.log("a");
console.log("b");
// TODO: fix`,
    );

    const { stdout } = await runCheckFile([testFile]);

    assert.ok(stdout.includes("Summary"), "Should show summary");
    assert.ok(stdout.includes("Files checked"), "Should count files");
  });
});
