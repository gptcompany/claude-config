#!/usr/bin/env node
/**
 * CI Auto-Fix Hook for Claude Code
 *
 * Detects CI failures from pytest/gh run output and handles:
 * 1. Auto-retry up to 3 times with exponential backoff
 * 2. If retries exhausted, provide detailed fix instructions
 *
 * Hook Type: PostToolUse
 * Matcher: Bash (when command contains test/CI commands)
 * Timeout: 10s
 *
 * Ported from: claude-hooks-shared/hooks/quality/ci-autofix.py
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output, getClaudeDir, ensureDir, getDateTimeString } = require('../../lib/utils');

// Configuration
const MAX_RETRIES = 3;
const STATE_DIR = path.join(getClaudeDir(), 'state');
const RETRY_STATE_FILE = path.join(STATE_DIR, 'ci_retry_state.json');
const METRICS_DIR = path.join(getClaudeDir(), 'metrics');
const CI_LOG = path.join(METRICS_DIR, 'ci_autofix.jsonl');

// Patterns to detect CI commands
const CI_COMMAND_PATTERNS = [
  /\bpytest\b/i,
  /\bnpm\s+test\b/i,
  /\bgh\s+run\b/i,
  /\bmake\s+test\b/i,
  /\bcargo\s+test\b/i,
  /\bgo\s+test\b/i,
  /\bnode\s+--test\b/i,
  /\bjest\b/i,
  /\bvitest\b/i,
  /\bmocha\b/i
];

// Patterns to detect failures
const FAILURE_PATTERNS = [
  /FAILED/i,
  /ERRORS?:/i,
  /AssertionError/i,
  /Error:/,
  /error\[/,
  /npm ERR!/,
  /FAIL\s/,
  /failure/i,
  /panic:/,
  /test failed/i,
  /tests? failing/i,
  /not ok\b/i
];

// Auto-fix suggestions for common errors
const FIX_SUGGESTIONS = {
  'lint': {
    pattern: /lint|eslint|flake8|pylint|ruff/i,
    fix: 'npm run lint -- --fix || ruff check --fix .'
  },
  'format': {
    pattern: /format|prettier|black|yapf/i,
    fix: 'npm run format || black . || prettier --write .'
  },
  'type': {
    pattern: /type|tsc|mypy|pyright/i,
    fix: 'Review type annotations in the indicated file'
  },
  'import': {
    pattern: /import|module not found|cannot find module/i,
    fix: 'npm install || pip install -r requirements.txt'
  },
  'syntax': {
    pattern: /syntax|unexpected token|parse error/i,
    fix: 'Check the indicated line for syntax errors'
  }
};

/**
 * Log CI auto-fix events
 */
function logEvent(eventType, data) {
  ensureDir(METRICS_DIR);
  const entry = {
    timestamp: new Date().toISOString(),
    event: eventType,
    ...data
  };
  fs.appendFileSync(CI_LOG, JSON.stringify(entry) + '\n');
}

/**
 * Load retry state from file
 */
function getRetryState() {
  ensureDir(STATE_DIR);
  try {
    if (fs.existsSync(RETRY_STATE_FILE)) {
      return JSON.parse(fs.readFileSync(RETRY_STATE_FILE, 'utf8'));
    }
  } catch (err) {
    // Ignore parse errors
  }
  return {};
}

/**
 * Save retry state to file
 */
function saveRetryState(state) {
  ensureDir(STATE_DIR);
  fs.writeFileSync(RETRY_STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Generate a unique key for the test command
 */
function getTestKey(command) {
  // Extract test file or pattern
  const match = command.match(/(?:pytest|test|jest|vitest|mocha)\s+([^\s|&;]+)/);
  if (match) {
    return `test:${match[1]}`;
  }
  // Hash the command for uniqueness
  let hash = 0;
  for (let i = 0; i < command.length; i++) {
    hash = ((hash << 5) - hash) + command.charCodeAt(i);
    hash = hash & hash; // Convert to 32bit integer
  }
  return `cmd:${Math.abs(hash) % 10000}`;
}

/**
 * Check if command is a CI/test command
 */
function isCiCommand(command) {
  return CI_COMMAND_PATTERNS.some(pattern => pattern.test(command));
}

/**
 * Check if output contains failure indicators
 */
function hasFailure(output) {
  if (!output) return false;
  return FAILURE_PATTERNS.some(pattern => pattern.test(output));
}

/**
 * Extract error context from output
 */
function extractErrorContext(output, command) {
  const context = {
    command: command,
    errorMessage: '',
    filePath: '',
    lineNumber: '',
    testName: '',
    stackTrace: '',
    suggestedFix: ''
  };

  // Extract first error message
  const errorMatch = output.match(/((?:Error|FAILED|AssertionError|FAIL)[^\n]+)/i);
  if (errorMatch) {
    context.errorMessage = errorMatch[1].trim();
  }

  // Extract file path from various test frameworks
  // Python pytest: tests/test_file.py:42
  // Node.js: at file.js:42:15
  // Jest: at Object.<anonymous> (file.js:42:15)
  const filePatterns = [
    /([^\s]+\.(py|js|ts|jsx|tsx)):(\d+)/,
    /at\s+.*?\(([^)]+):(\d+):\d+\)/,
    /([^\s]+\.(py|js|ts)):(\d+):\d+/
  ];

  for (const pattern of filePatterns) {
    const fileMatch = output.match(pattern);
    if (fileMatch) {
      context.filePath = fileMatch[1];
      context.lineNumber = fileMatch[3] || fileMatch[2];
      break;
    }
  }

  // Extract test name
  const testMatch = output.match(/(test_\w+|it\s*\(['"`][^'"`)]+|describe\s*\(['"`][^'"`)]+)/);
  if (testMatch) {
    context.testName = testMatch[1];
  }

  // Extract stack trace (last 20 lines before error)
  const lines = output.split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (/(?:Error|FAILED)/i.test(lines[i])) {
      const start = Math.max(0, i - 20);
      context.stackTrace = lines.slice(start, i + 5).join('\n').substring(0, 1000);
      break;
    }
  }

  // Suggest fix based on error type
  for (const [type, suggestion] of Object.entries(FIX_SUGGESTIONS)) {
    if (suggestion.pattern.test(output)) {
      context.suggestedFix = suggestion.fix;
      break;
    }
  }

  return context;
}

/**
 * Generate fix instruction for Claude
 */
function generateFixInstruction(errorContext) {
  let instruction = `
## CI FAILURE - Auto-Fix Required

**Error:** ${errorContext.errorMessage || 'Unknown error'}

**Location:** \`${errorContext.filePath || 'Unknown'}:${errorContext.lineNumber || '?'}\`

**Test:** \`${errorContext.testName || 'Unknown'}\`
`;

  if (errorContext.stackTrace) {
    instruction += `
**Stack Trace:**
\`\`\`
${errorContext.stackTrace.substring(0, 500)}
\`\`\`
`;
  }

  if (errorContext.suggestedFix) {
    instruction += `
**Suggested Fix:** \`${errorContext.suggestedFix}\`
`;
  }

  instruction += `
**Action Required:**
1. Read the failing file${errorContext.filePath ? ` at ${errorContext.filePath}` : ''}
2. Analyze the root cause from the error message
3. Fix the code
4. Re-run the test: \`${errorContext.command}\`
`;

  logEvent('fix_instruction_generated', { context: errorContext });
  return instruction;
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    const inputData = await readStdinJson();

    // Check if this is a Bash tool use
    const toolName = inputData.tool_name || '';
    if (toolName !== 'Bash') {
      process.exit(0);
    }

    // Get command and output
    const toolInput = inputData.tool_input || {};
    const command = toolInput.command || '';
    const toolResult = inputData.tool_result || inputData.tool_output || '';

    // Convert tool_result to string if it's an object
    const resultStr = typeof toolResult === 'object'
      ? (toolResult.stdout || '') + (toolResult.stderr || '')
      : String(toolResult);

    // Check if it's a CI command
    if (!isCiCommand(command)) {
      process.exit(0);
    }

    // Check if there's a failure
    if (!hasFailure(resultStr)) {
      // Success - clear retry state for this test
      const testKey = getTestKey(command);
      const state = getRetryState();
      if (state[testKey]) {
        delete state[testKey];
        saveRetryState(state);
      }
      process.exit(0);
    }

    // We have a failure
    const testKey = getTestKey(command);
    const state = getRetryState();

    // Get current retry count
    const retryInfo = state[testKey] || { count: 0, firstFailure: new Date().toISOString() };
    let retryCount = retryInfo.count;

    if (retryCount < MAX_RETRIES) {
      // Auto-retry with exponential backoff
      retryCount += 1;
      const delay = Math.pow(2, retryCount); // 2, 4, 8 seconds

      state[testKey] = {
        count: retryCount,
        firstFailure: retryInfo.firstFailure || new Date().toISOString(),
        lastRetry: new Date().toISOString()
      };
      saveRetryState(state);

      logEvent('retry_scheduled', { testKey, retryCount, delay });

      // Output message for Claude to see
      const msg = `CI failure detected (attempt ${retryCount}/${MAX_RETRIES}). Auto-retry in ${delay}s recommended.`;
      output({
        continue: true,
        systemMessage: `${msg}\nRun the command again: ${command}`
      });
    } else {
      // Retries exhausted - generate fix instruction
      const errorContext = extractErrorContext(resultStr, command);

      logEvent('retries_exhausted', {
        testKey,
        retryCount,
        error: errorContext.errorMessage
      });

      // Clear retry state
      if (state[testKey]) {
        delete state[testKey];
        saveRetryState(state);
      }

      // Generate fix instruction
      const fixInstruction = generateFixInstruction(errorContext);

      output({
        continue: true,
        systemMessage: fixInstruction
      });
    }
  } catch (err) {
    // Fail silently - don't block the user
    process.exit(0);
  }
}

main();
