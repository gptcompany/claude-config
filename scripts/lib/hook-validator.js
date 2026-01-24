/**
 * Hook Validator Library for Claude Code Hooks
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * Provides:
 * - Validate hooks.json structure
 * - Validate hook scripts exist and are executable
 * - Validate hook output against expected schema
 * - Test hook execution with sample inputs
 * - Compare expected vs actual results
 * - Generate validation reports
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_FILE = path.join(HOME_DIR, '.claude', 'hooks', 'hooks.json');
const SCRIPT_TIMEOUT = 5000; // 5 seconds

// Expected output schemas per hook event
const OUTPUT_SCHEMAS = {
  PreToolUse: {
    optional: ['decision', 'reason', 'message', 'approve'],
    decision: ['approve', 'block', 'skip'],
    types: {
      decision: 'string',
      reason: 'string',
      message: 'string',
      approve: 'boolean'
    }
  },
  PostToolUse: {
    optional: ['systemMessage', 'additionalContext'],
    types: {
      systemMessage: 'string',
      additionalContext: 'string'
    }
  },
  UserPromptSubmit: {
    optional: ['additionalContext', 'systemMessage', 'deny'],
    types: {
      additionalContext: 'string',
      systemMessage: 'string',
      deny: 'boolean'
    }
  },
  Stop: {
    optional: ['systemMessage'],
    types: {
      systemMessage: 'string'
    }
  },
  PreCompact: {
    optional: ['additionalContext'],
    types: {
      additionalContext: 'string'
    }
  },
  SessionStart: {
    optional: ['additionalContext'],
    types: {
      additionalContext: 'string'
    }
  },
  SessionEnd: {
    optional: [],
    types: {}
  }
};

/**
 * Validation result structure
 */
class ValidationResult {
  constructor() {
    this.valid = true;
    this.errors = [];
    this.warnings = [];
    this.info = [];
  }

  addError(message) {
    this.valid = false;
    this.errors.push(message);
  }

  addWarning(message) {
    this.warnings.push(message);
  }

  addInfo(message) {
    this.info.push(message);
  }

  merge(other) {
    if (!other.valid) this.valid = false;
    this.errors.push(...other.errors);
    this.warnings.push(...other.warnings);
    this.info.push(...other.info);
  }
}

/**
 * Validate hooks.json structure
 * @param {string|object} hooksJson - Path to hooks.json or parsed object
 * @returns {ValidationResult} Validation result
 */
function validateHookConfig(hooksJson) {
  const result = new ValidationResult();

  let config;
  try {
    if (typeof hooksJson === 'string') {
      const content = fs.readFileSync(hooksJson, 'utf8');
      config = JSON.parse(content);
    } else {
      config = hooksJson;
    }
  } catch (e) {
    result.addError(`Failed to parse hooks.json: ${e.message}`);
    return result;
  }

  // Check required structure
  if (!config.hooks || typeof config.hooks !== 'object') {
    result.addError('Missing or invalid "hooks" property');
    return result;
  }

  // Valid event types
  const validEvents = [
    'PreToolUse', 'PostToolUse', 'UserPromptSubmit', 'Stop',
    'PreCompact', 'PostCompact', 'SessionStart', 'SessionEnd'
  ];

  // Validate each event type
  for (const [eventType, hookDefs] of Object.entries(config.hooks)) {
    if (!validEvents.includes(eventType)) {
      result.addWarning(`Unknown event type: ${eventType}`);
    }

    if (!Array.isArray(hookDefs)) {
      result.addError(`Hooks for ${eventType} must be an array`);
      continue;
    }

    // Validate each hook definition
    for (let i = 0; i < hookDefs.length; i++) {
      const hookDef = hookDefs[i];
      const prefix = `${eventType}[${i}]`;

      // Check matcher
      if (!hookDef.matcher) {
        result.addError(`${prefix}: Missing "matcher" property`);
      } else if (typeof hookDef.matcher !== 'string') {
        result.addError(`${prefix}: "matcher" must be a string`);
      }

      // Check hooks array
      if (!hookDef.hooks || !Array.isArray(hookDef.hooks)) {
        result.addError(`${prefix}: Missing or invalid "hooks" array`);
        continue;
      }

      // Validate each hook in the array
      for (let j = 0; j < hookDef.hooks.length; j++) {
        const hook = hookDef.hooks[j];
        const hookPrefix = `${prefix}.hooks[${j}]`;

        if (!hook.type) {
          result.addError(`${hookPrefix}: Missing "type" property`);
        } else if (hook.type !== 'command') {
          result.addWarning(`${hookPrefix}: Unknown hook type "${hook.type}"`);
        }

        if (!hook.command) {
          result.addError(`${hookPrefix}: Missing "command" property`);
        }
      }

      // Check optional fields
      if (hookDef.description) {
        result.addInfo(`${prefix}: Has description`);
      }

      if (hookDef.enabled !== undefined && typeof hookDef.enabled !== 'boolean') {
        result.addWarning(`${prefix}: "enabled" should be boolean`);
      }
    }
  }

  return result;
}

/**
 * Validate a hook script exists and is executable
 * @param {string} scriptPath - Path to script (may include arguments)
 * @returns {ValidationResult} Validation result
 */
function validateHookScript(scriptPath) {
  const result = new ValidationResult();

  // Extract just the script path (first part before arguments)
  const parts = scriptPath.trim().split(/\s+/);
  let executablePath = parts[0];

  // Handle 'node' prefix
  if (executablePath === 'node') {
    if (parts.length < 2) {
      result.addError('Node command missing script path');
      return result;
    }
    executablePath = parts[1];
  }

  // Expand environment variables
  executablePath = executablePath.replace(/\$HOME|\$\{HOME\}/g, HOME_DIR);
  executablePath = executablePath.replace(/~/g, HOME_DIR);

  // Remove quotes if present
  executablePath = executablePath.replace(/^["']|["']$/g, '');

  // Check if file exists
  if (!fs.existsSync(executablePath)) {
    result.addError(`Script not found: ${executablePath}`);
    return result;
  }

  // Check if file is readable
  try {
    fs.accessSync(executablePath, fs.constants.R_OK);
    result.addInfo(`Script is readable: ${executablePath}`);
  } catch (e) {
    result.addError(`Script not readable: ${executablePath}`);
  }

  // Check file type (should be .js or have shebang)
  const content = fs.readFileSync(executablePath, 'utf8');
  if (!executablePath.endsWith('.js') && !content.startsWith('#!')) {
    result.addWarning(`Script may not be executable: ${executablePath}`);
  }

  // Check for syntax errors in JS files
  if (executablePath.endsWith('.js')) {
    try {
      new Function(content);
      result.addInfo('JavaScript syntax is valid');
    } catch (e) {
      result.addError(`JavaScript syntax error: ${e.message}`);
    }
  }

  return result;
}

/**
 * Validate hook output against expected schema
 * @param {object|string} output - Hook output
 * @param {string} eventType - Event type (PreToolUse, PostToolUse, etc.)
 * @returns {ValidationResult} Validation result
 */
function validateHookOutput(output, eventType) {
  const result = new ValidationResult();

  // Parse if string
  let parsed;
  try {
    parsed = typeof output === 'string' ? JSON.parse(output) : output;
  } catch (e) {
    result.addError(`Output is not valid JSON: ${e.message}`);
    return result;
  }

  // Get schema for event type
  const schema = OUTPUT_SCHEMAS[eventType];
  if (!schema) {
    result.addWarning(`No schema defined for event type: ${eventType}`);
    return result;
  }

  // Check for unexpected fields
  for (const key of Object.keys(parsed)) {
    if (!schema.optional.includes(key) && !schema.types[key]) {
      result.addWarning(`Unexpected field in output: ${key}`);
    }
  }

  // Validate field types
  for (const [key, value] of Object.entries(parsed)) {
    const expectedType = schema.types[key];
    if (expectedType) {
      const actualType = typeof value;
      if (actualType !== expectedType) {
        result.addError(`Field "${key}" should be ${expectedType}, got ${actualType}`);
      }
    }

    // Validate decision values
    if (key === 'decision' && schema.decision) {
      if (!schema.decision.includes(value)) {
        result.addError(`Invalid decision value: ${value}. Expected: ${schema.decision.join(', ')}`);
      }
    }
  }

  result.addInfo(`Output validation passed for ${eventType}`);
  return result;
}

/**
 * Test hook execution with sample input
 * @param {string} command - Hook command
 * @param {object} testInput - Test input data
 * @param {number} [timeout=5000] - Timeout in ms
 * @returns {Promise<object>} Execution result
 */
async function testHookExecution(command, testInput, timeout = SCRIPT_TIMEOUT) {
  return new Promise((resolve) => {
    const result = {
      success: false,
      output: null,
      stderr: '',
      exitCode: null,
      durationMs: 0,
      error: null
    };

    const startTime = Date.now();

    // Expand environment variables in command
    let expandedCmd = command
      .replace(/\$HOME|\$\{HOME\}/g, HOME_DIR)
      .replace(/~/g, HOME_DIR);

    // Split command into parts
    const parts = expandedCmd.split(/\s+/);
    const cmd = parts[0];
    const args = parts.slice(1);

    try {
      const child = spawn(cmd, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        timeout,
        env: { ...process.env, HOOK_TEST: '1' }
      });

      let stdout = '';
      let stderr = '';

      child.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      child.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      // Send input
      child.stdin.write(JSON.stringify(testInput));
      child.stdin.end();

      const timer = setTimeout(() => {
        child.kill('SIGTERM');
        result.error = 'Timeout';
        result.durationMs = Date.now() - startTime;
        resolve(result);
      }, timeout);

      child.on('close', (code) => {
        clearTimeout(timer);
        result.durationMs = Date.now() - startTime;
        result.exitCode = code;
        result.success = code === 0;
        result.stderr = stderr.trim();

        // Try to parse stdout as JSON
        try {
          result.output = JSON.parse(stdout.trim());
        } catch (e) {
          result.output = stdout.trim();
        }

        resolve(result);
      });

      child.on('error', (err) => {
        clearTimeout(timer);
        result.error = err.message;
        result.durationMs = Date.now() - startTime;
        resolve(result);
      });
    } catch (err) {
      result.error = err.message;
      result.durationMs = Date.now() - startTime;
      resolve(result);
    }
  });
}

/**
 * Compare expected vs actual results
 * @param {object} expected - Expected output
 * @param {object} actual - Actual output
 * @returns {object} Comparison result
 */
function compareExpectedActual(expected, actual) {
  const result = {
    match: true,
    differences: []
  };

  // Compare all keys
  const allKeys = new Set([...Object.keys(expected), ...Object.keys(actual)]);

  for (const key of allKeys) {
    const expVal = expected[key];
    const actVal = actual[key];

    if (expVal === undefined && actVal !== undefined) {
      result.differences.push({
        key,
        type: 'extra',
        actual: actVal
      });
    } else if (expVal !== undefined && actVal === undefined) {
      result.match = false;
      result.differences.push({
        key,
        type: 'missing',
        expected: expVal
      });
    } else if (JSON.stringify(expVal) !== JSON.stringify(actVal)) {
      result.match = false;
      result.differences.push({
        key,
        type: 'mismatch',
        expected: expVal,
        actual: actVal
      });
    }
  }

  return result;
}

/**
 * Generate a validation report
 * @param {object[]} results - Array of validation results
 * @returns {object} Report object
 */
function generateValidationReport(results) {
  const report = {
    timestamp: new Date().toISOString(),
    total: results.length,
    passed: 0,
    failed: 0,
    warnings: 0,
    details: []
  };

  for (const item of results) {
    const valid = item.result?.valid !== false;

    if (valid) {
      report.passed++;
    } else {
      report.failed++;
    }

    if (item.result?.warnings?.length > 0) {
      report.warnings++;
    }

    report.details.push({
      name: item.name,
      valid,
      errors: item.result?.errors || [],
      warnings: item.result?.warnings || [],
      info: item.result?.info || []
    });
  }

  report.passRate = report.total > 0 ? Math.round((report.passed / report.total) * 100) : 0;

  return report;
}

/**
 * Validate all hooks from hooks.json
 * @param {string} [hooksPath] - Path to hooks.json
 * @returns {Promise<object>} Validation report
 */
async function validateAllHooks(hooksPath = HOOKS_FILE) {
  const results = [];

  // Validate config structure
  const configResult = validateHookConfig(hooksPath);
  results.push({
    name: 'hooks.json structure',
    result: configResult
  });

  if (!configResult.valid) {
    return generateValidationReport(results);
  }

  // Load config
  const config = JSON.parse(fs.readFileSync(hooksPath, 'utf8'));

  // Validate each hook script
  for (const [eventType, hookDefs] of Object.entries(config.hooks)) {
    for (let i = 0; i < hookDefs.length; i++) {
      const hookDef = hookDefs[i];

      for (let j = 0; j < hookDef.hooks.length; j++) {
        const hook = hookDef.hooks[j];
        const name = `${eventType}[${i}].hooks[${j}]`;

        // Validate script exists
        const scriptResult = validateHookScript(hook.command);
        results.push({
          name: `${name} (script)`,
          result: scriptResult
        });
      }
    }
  }

  return generateValidationReport(results);
}

/**
 * Get sample test input for an event type
 * @param {string} eventType - Event type
 * @returns {object} Sample input
 */
function getSampleInput(eventType) {
  switch (eventType) {
    case 'PreToolUse':
      return {
        tool_name: 'Bash',
        tool_input: { command: 'echo test' }
      };
    case 'PostToolUse':
      return {
        tool_name: 'Bash',
        tool_input: { command: 'echo test' },
        tool_output: { output: 'test' }
      };
    case 'UserPromptSubmit':
      return {
        message: 'Hello, Claude!'
      };
    case 'Stop':
      return {
        stop_reason: 'end_turn'
      };
    case 'PreCompact':
    case 'PostCompact':
      return {
        compact_reason: 'context_full'
      };
    case 'SessionStart':
    case 'SessionEnd':
      return {
        session_id: 'test-session'
      };
    default:
      return {};
  }
}

/**
 * Format validation report for display
 * @param {object} report - Validation report
 * @returns {string} Formatted report
 */
function formatReport(report) {
  const lines = [
    'Hook Validation Report',
    '======================',
    '',
    `Total: ${report.total} checks`,
    `Passed: ${report.passed} (${report.passRate}%)`,
    `Failed: ${report.failed}`,
    `Warnings: ${report.warnings}`,
    ''
  ];

  if (report.failed > 0) {
    lines.push('FAILED:');
    for (const detail of report.details) {
      if (!detail.valid) {
        lines.push(`- ${detail.name}`);
        for (const error of detail.errors) {
          lines.push(`  ERROR: ${error}`);
        }
      }
    }
    lines.push('');
  }

  if (report.warnings > 0) {
    lines.push('WARNINGS:');
    for (const detail of report.details) {
      if (detail.warnings.length > 0) {
        lines.push(`- ${detail.name}`);
        for (const warning of detail.warnings) {
          lines.push(`  WARNING: ${warning}`);
        }
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}

module.exports = {
  // Validation functions
  validateHookConfig,
  validateHookScript,
  validateHookOutput,
  testHookExecution,
  compareExpectedActual,
  generateValidationReport,
  validateAllHooks,

  // Helpers
  getSampleInput,
  formatReport,

  // Classes
  ValidationResult,

  // Constants
  OUTPUT_SCHEMAS,
  HOOKS_FILE,
  SCRIPT_TIMEOUT
};
