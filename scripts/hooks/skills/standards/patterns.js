#!/usr/bin/env node
/**
 * Coding Patterns Library - Anti-pattern detection for code quality
 *
 * Detects common anti-patterns in JavaScript/TypeScript and Python code.
 * Each pattern includes severity level, message, and optional exclude paths.
 *
 * Ported from: /media/sam/1TB/everything-claude-code/skills/coding-standards/SKILL.md
 */

const path = require("path");

/**
 * Simple glob-like pattern matching for exclude paths
 * Supports: *.ext, prefix_*.ext, dir/*, and double-star patterns
 */
function minimatch(filePath, pattern) {
  // Normalize path separators
  const normalizedPath = filePath.replace(/\\/g, "/");
  const normalizedPattern = pattern.replace(/\\/g, "/");
  const fileName = path.basename(normalizedPath);

  // Handle **/ patterns (matches any directory path)
  if (normalizedPattern.includes("**/")) {
    // **/__tests__/* matches anything in any __tests__ directory
    const parts = normalizedPattern.split("**/");
    if (parts.length === 2) {
      const suffix = parts[1];
      if (suffix.endsWith("/*")) {
        // **/__tests__/* - check if path contains the directory
        const dirName = suffix.slice(0, -2);
        return (
          normalizedPath.includes(`/${dirName}/`) ||
          normalizedPath.includes(`${dirName}/`)
        );
      }
      // **/file.ext - matches file anywhere
      return (
        normalizedPath.endsWith(suffix) || normalizedPath.includes(`/${suffix}`)
      );
    }
  }

  // dir/* patterns - check before prefix_* patterns
  if (normalizedPattern.endsWith("/*")) {
    // debug/* matches anything in debug/ directory
    const dir = normalizedPattern.slice(0, -2);
    return (
      normalizedPath.includes(`/${dir}/`) ||
      normalizedPath.startsWith(`${dir}/`)
    );
  }

  // Handle prefix_*.ext patterns (like test_*.py or *_test.py)
  if (normalizedPattern.includes("*") && !normalizedPattern.startsWith("*")) {
    // Convert glob to regex: test_*.py -> ^test_.*\.py$
    const regexPattern = normalizedPattern
      .replace(/[.+^${}()|[\]\\]/g, "\\$&") // Escape regex chars except *
      .replace(/\*/g, ".*"); // Replace * with .*
    const regex = new RegExp(`^${regexPattern}$`);
    return regex.test(fileName);
  }

  // Simple patterns starting with *.
  if (normalizedPattern.startsWith("*.")) {
    // *.test.js matches any file ending in .test.js
    const ext = normalizedPattern.slice(1);
    return normalizedPath.endsWith(ext) || fileName.endsWith(ext);
  }

  // Direct contains match
  return normalizedPath.includes(normalizedPattern);
}

/**
 * Anti-patterns for JavaScript/TypeScript
 */
const JAVASCRIPT_PATTERNS = [
  {
    name: "console-log-in-prod",
    pattern: /console\.(log|debug|info)\s*\(/,
    severity: "warn",
    message: "console.log detected - remove or use logger",
    exclude: [
      "*.test.js",
      "*.test.ts",
      "*.spec.js",
      "*.spec.ts",
      "debug/*",
      "**/__tests__/*",
    ],
  },
  {
    name: "any-type",
    pattern: /:\s*any\b/,
    severity: "warn",
    message: "Avoid `any` type - use specific types",
    exclude: ["*.d.ts"],
  },
  {
    name: "hardcoded-secret",
    pattern:
      /(password|secret|api[_-]?key|token|credential|auth[_-]?key)\s*[:=]\s*['"][^'"]{8,}['"]/i,
    severity: "error",
    message: "Possible hardcoded secret detected",
    exclude: [
      "*.test.js",
      "*.test.ts",
      "*.spec.js",
      "*.spec.ts",
      "**/__tests__/*",
      "*.example.*",
    ],
  },
  {
    name: "todo-without-issue",
    pattern: /\/\/\s*TODO(?!:?\s*[#@]\d+|:?\s*\[#?\d+\])/i,
    severity: "info",
    message: "TODO without issue reference - consider linking to issue",
  },
  {
    name: "debugger-statement",
    pattern: /^\s*debugger\s*;?\s*$/,
    severity: "error",
    message: "debugger statement found - remove before committing",
  },
  {
    name: "alert-in-code",
    pattern: /\balert\s*\(/,
    severity: "warn",
    message: "alert() detected - use proper UI feedback",
    exclude: ["*.test.js", "*.test.ts"],
  },
  {
    name: "process-exit-in-lib",
    pattern: /process\.exit\s*\(/,
    severity: "warn",
    message: "process.exit() in library code - should throw error instead",
    exclude: ["cli.js", "cli.ts", "**/bin/*", "**/*.cli.*"],
  },
];

/**
 * Anti-patterns for Python
 */
const PYTHON_PATTERNS = [
  {
    name: "print-in-prod",
    pattern: /^\s*print\s*\(/,
    severity: "warn",
    message: "print() detected - use logging module instead",
    exclude: ["test_*.py", "*_test.py", "**/__tests__/*", "conftest.py"],
  },
  {
    name: "bare-except",
    pattern: /except\s*:/,
    severity: "error",
    message: "Bare except clause - specify exception type",
  },
  {
    name: "star-import",
    pattern: /from\s+\S+\s+import\s+\*/,
    severity: "warn",
    message: "Star import - use explicit imports",
  },
  {
    name: "hardcoded-secret-py",
    pattern:
      /(password|secret|api[_-]?key|token|credential|auth[_-]?key)\s*=\s*['"][^'"]{8,}['"]/i,
    severity: "error",
    message: "Possible hardcoded secret detected",
    exclude: ["test_*.py", "*_test.py", "**/__tests__/*", "*.example.*"],
  },
  {
    name: "mutable-default-arg",
    pattern: /def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})/,
    severity: "warn",
    message: "Mutable default argument - use None and check in function body",
  },
  {
    name: "pass-only-except",
    pattern: /except.*:\s*\n\s*pass\s*$/m,
    severity: "warn",
    message: "Exception silently ignored with pass - at least log it",
  },
];

/**
 * Anti-patterns indexed by file type
 */
const ANTI_PATTERNS = {
  javascript: JAVASCRIPT_PATTERNS,
  python: PYTHON_PATTERNS,
};

/**
 * Detect file type from path
 * @param {string} filePath - Path to file
 * @returns {string|null} - File type: 'javascript' | 'python' | null
 */
function detectFileType(filePath) {
  if (!filePath) return null;

  const ext = path.extname(filePath).toLowerCase();

  // JavaScript/TypeScript
  if ([".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"].includes(ext)) {
    return "javascript";
  }

  // Python
  if (ext === ".py") {
    return "python";
  }

  return null;
}

/**
 * Check if pattern should be excluded for this file
 * @param {Object} pattern - Pattern with optional exclude array
 * @param {string} filePath - Path to file
 * @returns {boolean} - True if should be excluded
 */
function shouldExclude(pattern, filePath) {
  if (!pattern.exclude || !Array.isArray(pattern.exclude)) {
    return false;
  }

  const normalizedPath = filePath.replace(/\\/g, "/");
  return pattern.exclude.some((glob) => minimatch(normalizedPath, glob));
}

/**
 * Check content against patterns for a specific file
 * @param {string} content - File content to check
 * @param {string} filePath - Path to file (for type detection and exclusions)
 * @returns {Object} - { passed: boolean, issues: Array }
 */
function checkPatterns(content, filePath) {
  const fileType = detectFileType(filePath);

  if (!fileType) {
    return { passed: true, issues: [] };
  }

  const patterns = ANTI_PATTERNS[fileType] || [];
  const issues = [];

  for (const pattern of patterns) {
    if (shouldExclude(pattern, filePath)) {
      continue;
    }

    const lines = content.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Reset regex lastIndex for global patterns
      if (pattern.pattern.global) {
        pattern.pattern.lastIndex = 0;
      }

      if (pattern.pattern.test(line)) {
        issues.push({
          name: pattern.name,
          line: i + 1,
          severity: pattern.severity,
          message: pattern.message,
          content:
            line.trim().substring(0, 60) +
            (line.trim().length > 60 ? "..." : ""),
        });
      }
    }
  }

  // passed = no error-level issues
  const passed = !issues.some((i) => i.severity === "error");

  return { passed, issues };
}

/**
 * Get all available patterns
 * @returns {Object} - Anti-patterns by file type
 */
function getPatterns() {
  return ANTI_PATTERNS;
}

/**
 * Add custom pattern for a file type
 * @param {string} fileType - 'javascript' | 'python'
 * @param {Object} pattern - Pattern object with name, pattern, severity, message
 */
function addPattern(fileType, pattern) {
  if (!ANTI_PATTERNS[fileType]) {
    ANTI_PATTERNS[fileType] = [];
  }
  ANTI_PATTERNS[fileType].push(pattern);
}

module.exports = {
  ANTI_PATTERNS,
  detectFileType,
  checkPatterns,
  shouldExclude,
  getPatterns,
  addPattern,
  minimatch,
};
