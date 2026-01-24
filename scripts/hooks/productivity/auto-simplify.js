#!/usr/bin/env node
/**
 * Auto-Simplify Hook - Analyze code complexity after edits
 *
 * PostToolUse hook that analyzes code complexity indicators after
 * Write/Edit operations and suggests simplification when thresholds
 * are exceeded.
 *
 * Hook type: PostToolUse (for Write, Edit)
 *
 * Ported from: /media/sam/1TB/claude-hooks-shared/hooks/productivity/auto-simplify-check.py
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Complexity thresholds
const THRESHOLDS = {
  maxFunctionLength: 50,    // Lines per function
  maxNestingDepth: 4,       // Levels of nesting
  maxParameters: 5,         // Function parameters
  maxFileLines: 300,        // Lines per file
  maxFunctionsPerFile: 15,  // Functions per file
};

// Code file extensions
const CODE_EXTENSIONS = new Set(['.js', '.ts', '.tsx', '.jsx', '.py', '.rs']);

// Patterns to detect function definitions
const FUNCTION_PATTERNS = {
  js: [
    /^\s*(async\s+)?function\s+(\w+)\s*\([^)]*\)/,
    /^\s*(const|let|var)\s+(\w+)\s*=\s*(async\s+)?\([^)]*\)\s*=>/,
    /^\s*(const|let|var)\s+(\w+)\s*=\s*(async\s+)?function\s*\([^)]*\)/,
    /^\s*(\w+)\s*\([^)]*\)\s*{/,  // Method in class
  ],
  py: [
    /^\s*(async\s+)?def\s+(\w+)\s*\([^)]*\)/,
  ],
};

/**
 * Count nesting depth at a specific line
 */
function countNestingDepth(lines, lineIndex) {
  let depth = 0;
  const countChars = (str, char) => (str.match(new RegExp(`\\${char}`, 'g')) || []).length;

  for (let i = 0; i <= lineIndex; i++) {
    const line = lines[i];
    depth += countChars(line, '{') - countChars(line, '}');
    // For Python, count indentation
    if (line.match(/:\s*$/)) {
      depth++;
    }
  }

  return Math.max(0, depth);
}

/**
 * Extract function info from code
 */
function extractFunctions(content, ext) {
  const lines = content.split('\n');
  const functions = [];
  const patterns = ext === '.py' ? FUNCTION_PATTERNS.py : FUNCTION_PATTERNS.js;

  let currentFunction = null;
  let braceCount = 0;
  let indentLevel = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Check for function start
    for (const pattern of patterns) {
      const match = line.match(pattern);
      if (match) {
        // Close previous function if exists
        if (currentFunction) {
          currentFunction.endLine = i - 1;
          currentFunction.length = currentFunction.endLine - currentFunction.startLine + 1;
          functions.push(currentFunction);
        }

        // Count parameters
        const paramsMatch = line.match(/\(([^)]*)\)/);
        const params = paramsMatch && paramsMatch[1].trim()
          ? paramsMatch[1].split(',').filter(p => p.trim()).length
          : 0;

        currentFunction = {
          name: match[2] || match[1] || 'anonymous',
          startLine: i,
          endLine: null,
          length: 0,
          params: params,
          maxNesting: 0,
        };

        if (ext === '.py') {
          // For Python, track indentation
          indentLevel = (line.match(/^\s*/)[0] || '').length;
        } else {
          braceCount = (line.match(/{/g) || []).length;
        }
        break;
      }
    }

    // Track nesting depth
    if (currentFunction) {
      const depth = countNestingDepth(lines.slice(currentFunction.startLine, i + 1), i - currentFunction.startLine);
      currentFunction.maxNesting = Math.max(currentFunction.maxNesting, depth);

      // Check for function end (JS)
      if (ext !== '.py') {
        braceCount += (line.match(/{/g) || []).length;
        braceCount -= (line.match(/}/g) || []).length;

        if (braceCount <= 0 && i > currentFunction.startLine) {
          currentFunction.endLine = i;
          currentFunction.length = currentFunction.endLine - currentFunction.startLine + 1;
          functions.push(currentFunction);
          currentFunction = null;
          braceCount = 0;
        }
      } else {
        // For Python, check indentation
        if (line.trim() && !line.match(/^\s*#/)) {
          const currentIndent = (line.match(/^\s*/)[0] || '').length;
          if (currentIndent <= indentLevel && i > currentFunction.startLine) {
            currentFunction.endLine = i - 1;
            currentFunction.length = currentFunction.endLine - currentFunction.startLine + 1;
            functions.push(currentFunction);
            currentFunction = null;
          }
        }
      }
    }
  }

  // Close last function
  if (currentFunction) {
    currentFunction.endLine = lines.length - 1;
    currentFunction.length = currentFunction.endLine - currentFunction.startLine + 1;
    functions.push(currentFunction);
  }

  return functions;
}

/**
 * Analyze code complexity
 */
function analyzeComplexity(filePath) {
  const ext = path.extname(filePath).toLowerCase();

  if (!CODE_EXTENSIONS.has(ext)) {
    return { complex: false };
  }

  try {
    if (!fs.existsSync(filePath)) {
      return { complex: false };
    }

    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    const lineCount = lines.length;

    // Extract functions
    const functions = extractFunctions(content, ext);
    const functionCount = functions.length;

    // Find complexity issues
    const issues = [];

    // Check file-level issues
    if (lineCount > THRESHOLDS.maxFileLines) {
      issues.push({
        type: 'file_too_long',
        message: `File has ${lineCount} lines (max: ${THRESHOLDS.maxFileLines})`,
        severity: 'warning',
      });
    }

    if (functionCount > THRESHOLDS.maxFunctionsPerFile) {
      issues.push({
        type: 'too_many_functions',
        message: `File has ${functionCount} functions (max: ${THRESHOLDS.maxFunctionsPerFile})`,
        severity: 'warning',
      });
    }

    // Check function-level issues
    for (const func of functions) {
      if (func.length > THRESHOLDS.maxFunctionLength) {
        issues.push({
          type: 'function_too_long',
          message: `Function '${func.name}' has ${func.length} lines (max: ${THRESHOLDS.maxFunctionLength})`,
          severity: 'warning',
          function: func.name,
          line: func.startLine + 1,
        });
      }

      if (func.maxNesting > THRESHOLDS.maxNestingDepth) {
        issues.push({
          type: 'deep_nesting',
          message: `Function '${func.name}' has nesting depth ${func.maxNesting} (max: ${THRESHOLDS.maxNestingDepth})`,
          severity: 'warning',
          function: func.name,
          line: func.startLine + 1,
        });
      }

      if (func.params > THRESHOLDS.maxParameters) {
        issues.push({
          type: 'too_many_params',
          message: `Function '${func.name}' has ${func.params} parameters (max: ${THRESHOLDS.maxParameters})`,
          severity: 'info',
          function: func.name,
          line: func.startLine + 1,
        });
      }
    }

    return {
      complex: issues.length > 0,
      file: filePath,
      lines: lineCount,
      functions: functionCount,
      issues: issues,
    };
  } catch (err) {
    return { complex: false };
  }
}

/**
 * Format complexity issues for output
 */
function formatIssues(analysis) {
  if (!analysis.complex || !analysis.issues.length) {
    return null;
  }

  const filename = path.basename(analysis.file);
  const warnings = analysis.issues.filter(i => i.severity === 'warning');

  if (warnings.length === 0) {
    return null;
  }

  let message = `Code Complexity Notice for '${filename}':\n`;

  for (const issue of warnings.slice(0, 3)) {  // Max 3 issues
    message += `  - ${issue.message}\n`;
  }

  if (warnings.length > 3) {
    message += `  ... and ${warnings.length - 3} more issues\n`;
  }

  message += '\nConsider refactoring to improve maintainability.';

  return message;
}

/**
 * Read JSON from stdin
 */
async function readStdinJson() {
  return new Promise((resolve, reject) => {
    let data = '';

    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => {
      data += chunk;
    });

    process.stdin.on('end', () => {
      try {
        if (data.trim()) {
          resolve(JSON.parse(data));
        } else {
          resolve({});
        }
      } catch (err) {
        reject(err);
      }
    });

    process.stdin.on('error', reject);

    // Timeout for stdin read
    setTimeout(() => {
      resolve({});
    }, 1000);
  });
}

/**
 * Main function
 */
async function main() {
  try {
    const input = await readStdinJson();

    const toolName = input.tool_name || '';
    const toolInput = input.tool_input || {};
    const filePath = toolInput.file_path || '';

    // Only trigger on Write/Edit
    if (!['Write', 'Edit', 'MultiEdit'].includes(toolName)) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    if (!filePath) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Analyze complexity
    const analysis = analyzeComplexity(filePath);

    if (!analysis.complex) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Format message
    const message = formatIssues(analysis);

    if (!message) {
      console.log(JSON.stringify({}));
      process.exit(0);
    }

    // Output suggestion
    const output = {
      hookSpecificOutput: {
        hookEventName: 'PostToolUse',
        message: message,
      },
    };

    console.log(JSON.stringify(output));
    process.exit(0);
  } catch (err) {
    // Any error, fail open
    console.log(JSON.stringify({}));
    process.exit(0);
  }
}

main();
