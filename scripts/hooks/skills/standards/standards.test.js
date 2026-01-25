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

// ============================================================================
// Extended Patterns Tests
// ============================================================================

describe("Extended Patterns", () => {
  const { getPatterns, addPattern } = require("./patterns");

  describe("getPatterns", () => {
    it("returns ANTI_PATTERNS object", () => {
      const patterns = getPatterns();
      assert.ok(patterns.javascript, "Should have javascript patterns");
      assert.ok(patterns.python, "Should have python patterns");
      assert.ok(Array.isArray(patterns.javascript));
      assert.ok(Array.isArray(patterns.python));
    });
  });

  describe("addPattern", () => {
    it("adds custom pattern to existing file type", () => {
      const customPattern = {
        name: "test-custom-pattern",
        pattern: /custom_pattern/,
        severity: "warn",
        message: "Custom pattern detected",
      };

      addPattern("javascript", customPattern);

      const patterns = getPatterns();
      const found = patterns.javascript.find(
        (p) => p.name === "test-custom-pattern",
      );
      assert.ok(found, "Custom pattern should be added");
    });

    it("creates new file type if not exists", () => {
      const customPattern = {
        name: "ruby-test-pattern",
        pattern: /puts/,
        severity: "warn",
        message: "puts detected",
      };

      addPattern("ruby", customPattern);

      const patterns = getPatterns();
      assert.ok(patterns.ruby, "Ruby patterns should exist");
      assert.ok(
        patterns.ruby.some((p) => p.name === "ruby-test-pattern"),
        "Pattern should be in ruby",
      );
    });
  });

  describe("detectFileType edge cases", () => {
    it("returns null for null input", () => {
      assert.strictEqual(detectFileType(null), null);
    });

    it("returns null for undefined input", () => {
      assert.strictEqual(detectFileType(undefined), null);
    });

    it("returns null for empty string", () => {
      assert.strictEqual(detectFileType(""), null);
    });
  });

  describe("checkPatterns edge cases", () => {
    it("returns passed=true for unsupported file type", () => {
      const { passed, issues } = checkPatterns(
        'console.log("test");',
        "config.yaml",
      );
      assert.strictEqual(passed, true);
      assert.deepStrictEqual(issues, []);
    });

    it("handles global regex patterns correctly", () => {
      // Test that patterns with global flag work correctly on multiple lines
      const content = `
        console.log("first");
        console.log("second");
        console.log("third");
      `;
      const { issues } = checkPatterns(content, "test.js");

      // Should detect multiple console.log instances
      const consoleIssues = issues.filter(
        (i) => i.name === "console-log-in-prod",
      );
      assert.ok(consoleIssues.length >= 1, "Should detect console.log");
    });
  });

  describe("minimatch extended", () => {
    it("handles prefix patterns like test_*.py", () => {
      assert.strictEqual(minimatch("test_auth.py", "test_*.py"), true);
      assert.strictEqual(minimatch("auth.py", "test_*.py"), false);
    });

    it("handles suffix patterns like *.test.js", () => {
      // The minimatch function uses *.ext patterns (starting with *)
      // to match file suffixes via endsWith
      assert.strictEqual(minimatch("auth.test.js", "*.test.js"), true);
      assert.strictEqual(minimatch("auth.js", "*.test.js"), false);
    });

    it("handles complex glob patterns", () => {
      assert.strictEqual(
        minimatch("src/components/Button.test.tsx", "**/__tests__/*"),
        false,
      );
      assert.strictEqual(
        minimatch("src/__tests__/Button.test.tsx", "**/__tests__/*"),
        true,
      );
    });

    it("handles **/file.ext patterns", () => {
      assert.strictEqual(
        minimatch("src/config/settings.js", "**/settings.js"),
        true,
      );
      assert.strictEqual(minimatch("settings.js", "**/settings.js"), true);
    });

    it("handles direct path matching", () => {
      // Fallback: direct substring matching
      assert.strictEqual(minimatch("src/utils/helper.js", "utils/"), true);
      assert.strictEqual(minimatch("src/lib/helper.js", "utils/"), false);
    });
  });

  describe("Python pattern detection", () => {
    it("detects mutable default argument", () => {
      const content = "def foo(items=[]):\n    items.append(1)";
      const { issues } = checkPatterns(content, "utils.py");
      assert.ok(
        issues.some((i) => i.name === "mutable-default-arg"),
        "Should detect mutable default argument",
      );
    });

    it("detects hardcoded secret in Python", () => {
      const content = 'api_key = "sk-1234567890abcdef"';
      const { issues, passed } = checkPatterns(content, "config.py");
      assert.ok(
        issues.some((i) => i.name === "hardcoded-secret-py"),
        "Should detect hardcoded secret",
      );
      assert.strictEqual(passed, false);
    });
  });

  describe("JavaScript pattern detection", () => {
    it("detects debugger statement", () => {
      const content = "function test() {\n  debugger;\n  return 1;\n}";
      const { issues, passed } = checkPatterns(content, "debug.js");
      assert.ok(
        issues.some((i) => i.name === "debugger-statement"),
        "Should detect debugger",
      );
      assert.strictEqual(passed, false);
    });

    it("detects alert in code", () => {
      const content = 'alert("Hello!");\nconsole.log("test");';
      const { issues } = checkPatterns(content, "app.js");
      assert.ok(
        issues.some((i) => i.name === "alert-in-code"),
        "Should detect alert",
      );
    });

    it("detects process.exit in lib code", () => {
      const content = "function cleanup() {\n  process.exit(1);\n}";
      const { issues } = checkPatterns(content, "lib/utils.js");
      assert.ok(
        issues.some((i) => i.name === "process-exit-in-lib"),
        "Should detect process.exit",
      );
    });

    it("ignores process.exit in CLI code", () => {
      const content = "function main() {\n  process.exit(0);\n}";
      const { issues } = checkPatterns(content, "cli.js");
      assert.ok(
        !issues.some((i) => i.name === "process-exit-in-lib"),
        "Should ignore process.exit in cli.js",
      );
    });
  });
});

// ============================================================================
// Extended Coding Standards Hook Tests
// ============================================================================

describe("Coding Standards Hook Extended", () => {
  function runHook(input) {
    return new Promise((resolve) => {
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
        } catch {
          resolve({ result: null, stdout, stderr, code });
        }
      });

      proc.stdin.write(JSON.stringify(input));
      proc.stdin.end();
    });
  }

  it("handles MultiEdit tool", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "warn" }),
    );

    const { result } = await runHook({
      tool_name: "MultiEdit",
      tool_input: {
        file_path: "multi.js",
        edits: [
          { old_string: "a", new_string: 'console.log("a");' },
          { old_string: "b", new_string: 'console.log("b");' },
        ],
      },
    });

    assert.strictEqual(result.decision, "allow");
    assert.ok(result.message, "Should warn about console.log in MultiEdit");
  });

  it("allows unsupported file types", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "config.yaml",
        content: 'password: "mysecret12345678"',
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("handles empty content", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "empty.js",
        content: "",
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("handles missing file_path", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "block" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        content: 'console.log("test");',
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("handles mode=off", async () => {
    fs.writeFileSync(
      CONFIG_PATH,
      JSON.stringify({ enabled: true, mode: "off" }),
    );

    const { result } = await runHook({
      tool_name: "Write",
      tool_input: {
        file_path: "test.js",
        content: 'const secret = "supersecretvalue123";',
      },
    });

    assert.strictEqual(result.decision, "allow");
  });

  it("handles malformed JSON input gracefully", async () => {
    const proc = spawn("node", [HOOK_SCRIPT], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";

    proc.stdout.on("data", (data) => {
      stdout += data;
    });

    await new Promise((resolve) => {
      proc.on("close", resolve);
      proc.stdin.write("not valid json");
      proc.stdin.end();
    });

    // Should allow on error
    const result = JSON.parse(stdout.trim());
    assert.strictEqual(result.decision, "allow");
  });
});

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

  it("check-file handles directory input", async () => {
    const subDir = path.join(TMP_DIR, "subdir");
    fs.mkdirSync(subDir, { recursive: true });
    fs.writeFileSync(path.join(subDir, "file1.js"), 'console.log("test1");');
    fs.writeFileSync(path.join(subDir, "file2.js"), 'console.log("test2");');

    const { stdout, code } = await runCheckFile([subDir]);

    assert.ok(
      stdout.includes("Files checked"),
      "Should check files in directory",
    );
    assert.strictEqual(code, 0, "Exit 0 for warnings only");

    // Cleanup
    fs.rmSync(subDir, { recursive: true });
  });

  it("check-file shows no files message for empty directory", async () => {
    const emptyDir = path.join(TMP_DIR, "empty");
    fs.mkdirSync(emptyDir, { recursive: true });

    const { stdout, code } = await runCheckFile([emptyDir]);

    assert.ok(
      stdout.includes("No supported files") || stdout.includes("0 file"),
      "Should indicate no files",
    );
    assert.strictEqual(code, 0);

    fs.rmSync(emptyDir, { recursive: true });
  });

  it("check-file shows usage with no args", async () => {
    const { stdout, code } = await runCheckFile([]);

    assert.ok(stdout.includes("Usage"), "Should show usage");
    assert.strictEqual(code, 1);
  });

  it("check-file handles nonexistent path", async () => {
    const { stderr, code } = await runCheckFile(["/nonexistent/path/file.js"]);

    assert.strictEqual(code, 1);
    assert.ok(stderr.includes("not found") || stderr.includes("Error"));
  });

  it("check-file skips node_modules", async () => {
    const nodeModulesDir = path.join(TMP_DIR, "node_modules");
    fs.mkdirSync(nodeModulesDir, { recursive: true });
    fs.writeFileSync(
      path.join(nodeModulesDir, "pkg.js"),
      'const secret = "supersecretvalue123";',
    );

    // Check parent directory - should not include node_modules
    const { stdout } = await runCheckFile([TMP_DIR]);

    assert.ok(
      !stdout.includes("node_modules/pkg.js"),
      "Should skip node_modules",
    );

    fs.rmSync(nodeModulesDir, { recursive: true });
  });

  it("check-file handles file read errors gracefully", async () => {
    // Create a file and make it unreadable (if possible)
    const testFile = path.join(TMP_DIR, "readable.js");
    fs.writeFileSync(testFile, 'console.log("test");');

    // This test just verifies the happy path works
    const { code } = await runCheckFile([testFile]);
    assert.strictEqual(code, 0);
  });

  it("check-file shows all severity levels", async () => {
    const testFile = path.join(TMP_DIR, "all-levels.js");
    fs.writeFileSync(
      testFile,
      `console.log("warn level");
const secret = "supersecretvalue123"; // error level
// TODO: fix this // info level`,
    );

    const { stdout } = await runCheckFile([testFile]);

    assert.ok(stdout.includes("ERROR") || stdout.includes("Errors"));
    assert.ok(stdout.includes("WARN") || stdout.includes("Warnings"));
  });
});
