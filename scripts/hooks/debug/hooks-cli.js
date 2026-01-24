#!/usr/bin/env node
/**
 * Hooks CLI - Diagnostic Commands for Claude Code Hooks
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * Commands:
 *   status       Show all hooks and their status
 *   test <hook>  Test a specific hook
 *   log <hook>   Show recent invocations for a hook
 *   validate     Run full validation suite
 *   stats        Show hook statistics
 *   debug        Enable/disable debug mode for a hook
 *   health       Show health status
 *   export       Force export stats to QuestDB
 *
 * Usage:
 *   node hooks-cli.js status
 *   node hooks-cli.js test git-safety-check
 *   node hooks-cli.js log git-safety-check --last 10
 *   node hooks-cli.js validate
 *   node hooks-cli.js stats
 *   node hooks-cli.js debug git-safety-check --enable
 *   node hooks-cli.js health
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_FILE = path.join(HOME_DIR, '.claude', 'hooks', 'hooks.json');
const LIB_DIR = path.join(HOME_DIR, '.claude', 'scripts', 'lib');
const DEBUG_DIR = path.join(HOME_DIR, '.claude', 'debug', 'hooks');

// ANSI colors
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

// Check if output should be JSON
const jsonMode = process.argv.includes('--json');

/**
 * Format output with optional color
 * @param {string} text - Text to format
 * @param {string} color - Color name
 * @returns {string} Formatted text
 */
function fmt(text, color) {
  if (jsonMode || !process.stdout.isTTY) {
    return text;
  }
  return `${colors[color] || ''}${text}${colors.reset}`;
}

/**
 * Load libraries
 */
let debugger_, validator, health;
try {
  debugger_ = require(path.join(LIB_DIR, 'hook-debugger'));
} catch (e) {
  debugger_ = null;
}

try {
  validator = require(path.join(LIB_DIR, 'hook-validator'));
} catch (e) {
  validator = null;
}

try {
  health = require(path.join(HOME_DIR, '.claude/scripts/hooks/debug/hook-health'));
} catch (e) {
  health = null;
}

/**
 * Load hooks from hooks.json
 * @returns {object[]} Array of hook definitions
 */
function loadHooks() {
  try {
    const config = JSON.parse(fs.readFileSync(HOOKS_FILE, 'utf8'));
    const hooks = [];

    for (const [eventType, hookDefs] of Object.entries(config.hooks || {})) {
      for (const hookDef of hookDefs) {
        for (const hook of hookDef.hooks || []) {
          let name = 'unknown';
          const match = hook.command?.match(/([a-zA-Z0-9_-]+)\.js/);
          if (match) name = match[1];

          hooks.push({
            name,
            eventType,
            matcher: hookDef.matcher,
            command: hook.command,
            description: hookDef.description,
            enabled: hookDef.enabled !== false
          });
        }
      }
    }

    return hooks;
  } catch (e) {
    return [];
  }
}

/**
 * Command: status - Show all hooks and their status
 */
function cmdStatus() {
  const hooks = loadHooks();
  const uniqueHooks = new Map();

  for (const hook of hooks) {
    if (!uniqueHooks.has(hook.name)) {
      uniqueHooks.set(hook.name, hook);
    }
  }

  if (jsonMode) {
    const result = [];
    for (const [name, hook] of uniqueHooks) {
      const stats = debugger_?.getHookStats(name) || {};
      result.push({
        name,
        eventType: hook.eventType,
        enabled: hook.enabled,
        calls: stats.calls || 0,
        errorRate: stats.errorRate || 0,
        lastCall: stats.lastCall || null
      });
    }
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log(fmt('Hook Status', 'bright'));
  console.log('===========\n');

  const eventTypes = new Set(hooks.map(h => h.eventType));

  for (const eventType of eventTypes) {
    console.log(fmt(`[${eventType}]`, 'cyan'));

    for (const [name, hook] of uniqueHooks) {
      if (hook.eventType === eventType) {
        const status = hook.enabled ? fmt('[ON]', 'green') : fmt('[OFF]', 'dim');
        const stats = debugger_?.getHookStats(name) || {};
        const callInfo = stats.calls > 0 ? fmt(` (${stats.calls} calls)`, 'dim') : '';

        console.log(`  ${status} ${name}${callInfo}`);
      }
    }
    console.log();
  }

  console.log(`Total: ${uniqueHooks.size} unique hooks`);
}

/**
 * Command: test - Test a specific hook
 * @param {string} hookName - Hook name to test
 */
async function cmdTest(hookName) {
  const hooks = loadHooks();
  const hook = hooks.find(h => h.name === hookName);

  if (!hook) {
    console.error(fmt(`Error: Hook "${hookName}" not found`, 'red'));
    process.exit(1);
  }

  if (jsonMode) {
    console.log(JSON.stringify({ testing: hookName, command: hook.command }));
  } else {
    console.log(fmt(`Testing hook: ${hookName}`, 'bright'));
    console.log(`Event: ${hook.eventType}`);
    console.log(`Command: ${hook.command.slice(0, 80)}...`);
    console.log();
  }

  // Get sample input
  const sampleInput = validator?.getSampleInput(hook.eventType) || {};

  if (!jsonMode) {
    console.log('Sample input:', JSON.stringify(sampleInput, null, 2));
    console.log();
  }

  // Run hook
  const result = await runHook(hook.command, sampleInput);

  if (jsonMode) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    if (result.code === 0) {
      console.log(fmt('Result: PASS', 'green'));
    } else {
      console.log(fmt('Result: FAIL', 'red'));
    }
    console.log(`Exit code: ${result.code}`);
    console.log(`Duration: ${result.duration}ms`);

    if (result.stdout) {
      console.log('\nStdout:');
      console.log(result.stdout.slice(0, 500));
    }
    if (result.stderr) {
      console.log('\nStderr:');
      console.log(result.stderr.slice(0, 500));
    }
  }
}

/**
 * Run a hook command
 */
async function runHook(command, input) {
  return new Promise((resolve) => {
    const start = Date.now();
    const inputJson = JSON.stringify(input);

    const child = spawn('sh', ['-c', `echo '${inputJson.replace(/'/g, "'\\''")}' | ${command}`], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, HOOK_TEST: '1', HOME: HOME_DIR }
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', data => { stdout += data.toString(); });
    child.stderr.on('data', data => { stderr += data.toString(); });

    const timer = setTimeout(() => {
      child.kill('SIGTERM');
      resolve({ code: -1, stdout, stderr, duration: 10000, timeout: true });
    }, 10000);

    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code, stdout: stdout.trim(), stderr: stderr.trim(), duration: Date.now() - start });
    });
  });
}

/**
 * Command: log - Show recent invocations
 * @param {string} hookName - Hook name
 * @param {number} last - Number of entries
 */
function cmdLog(hookName, last = 10) {
  if (!debugger_) {
    console.error(fmt('Error: hook-debugger not available', 'red'));
    process.exit(1);
  }

  const logs = debugger_.getInvocationLog(hookName, last);

  if (jsonMode) {
    console.log(JSON.stringify(logs, null, 2));
    return;
  }

  console.log(fmt(`Recent invocations for: ${hookName}`, 'bright'));
  console.log('='.repeat(40));

  if (logs.length === 0) {
    console.log(fmt('No invocations logged', 'dim'));
    return;
  }

  for (const log of logs) {
    const event = log.event === 'error' ? fmt(log.event, 'red') :
                  log.event === 'output' ? fmt(log.event, 'green') :
                  fmt(log.event, 'blue');

    console.log(`\n${log.ts} [${event}]`);

    if (log.data) {
      if (log.data.durationMs) {
        console.log(`  Duration: ${log.data.durationMs}ms`);
      }
      if (log.data.success !== undefined) {
        console.log(`  Success: ${log.data.success}`);
      }
      if (log.data.error) {
        console.log(`  Error: ${log.data.error}`);
      }
    }
  }
}

/**
 * Command: validate - Run full validation
 */
async function cmdValidate() {
  if (!validator) {
    console.error(fmt('Error: hook-validator not available', 'red'));
    process.exit(1);
  }

  if (!jsonMode) {
    console.log(fmt('Running full hook validation...', 'bright'));
    console.log();
  }

  const report = await validator.validateAllHooks(HOOKS_FILE);

  if (jsonMode) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log(validator.formatReport(report));
  }

  process.exit(report.passRate >= 95 ? 0 : 1);
}

/**
 * Command: stats - Show hook statistics
 */
function cmdStats() {
  if (!debugger_) {
    console.error(fmt('Error: hook-debugger not available', 'red'));
    process.exit(1);
  }

  const allStats = debugger_.getAllHookStats();

  if (jsonMode) {
    console.log(JSON.stringify(allStats, null, 2));
    return;
  }

  console.log(fmt('Hook Statistics', 'bright'));
  console.log('===============\n');

  if (allStats.length === 0) {
    console.log(fmt('No statistics available', 'dim'));
    return;
  }

  // Table header
  console.log(fmt('Hook'.padEnd(25) + 'Calls'.padStart(8) + 'Errors'.padStart(8) + 'Err%'.padStart(8) + 'AvgMs'.padStart(8), 'bright'));
  console.log('-'.repeat(57));

  for (const stats of allStats) {
    const errRate = (stats.errorRate * 100).toFixed(1) + '%';
    const errColor = stats.errorRate > 0.1 ? 'red' : stats.errorRate > 0.05 ? 'yellow' : 'green';

    console.log(
      stats.hook.padEnd(25) +
      String(stats.calls).padStart(8) +
      String(stats.errors).padStart(8) +
      fmt(errRate.padStart(8), errColor) +
      String(stats.avgDuration).padStart(8)
    );
  }

  console.log();
  console.log(`Total hooks tracked: ${allStats.length}`);
  console.log(`Total calls: ${allStats.reduce((s, h) => s + h.calls, 0)}`);
}

/**
 * Command: debug - Enable/disable debug for a hook
 * @param {string} hookName - Hook name
 * @param {boolean} enable - Enable or disable
 */
function cmdDebug(hookName, enable) {
  if (!debugger_) {
    console.error(fmt('Error: hook-debugger not available', 'red'));
    process.exit(1);
  }

  if (enable) {
    debugger_.enableDebug(hookName);
    console.log(fmt(`Debug enabled for: ${hookName}`, 'green'));
  } else {
    debugger_.disableDebug(hookName);
    console.log(fmt(`Debug disabled for: ${hookName}`, 'yellow'));
  }
}

/**
 * Command: health - Show health status
 */
async function cmdHealth() {
  if (!health) {
    console.error(fmt('Error: hook-health not available', 'red'));
    process.exit(1);
  }

  if (!jsonMode) {
    console.log(fmt('Running health check...', 'bright'));
  }

  const healthData = await health.runHealthCheck();

  if (jsonMode) {
    console.log(JSON.stringify(healthData, null, 2));
  } else {
    console.log(health.formatHealthOutput(healthData));
  }
}

/**
 * Command: export - Force export to QuestDB
 */
async function cmdExport() {
  if (!debugger_) {
    console.error(fmt('Error: hook-debugger not available', 'red'));
    process.exit(1);
  }

  console.log('Exporting stats to QuestDB...');
  const count = await debugger_.forceExportAllStats();
  console.log(fmt(`Exported ${count} hook stats`, 'green'));
}

/**
 * Show help
 */
function showHelp() {
  console.log(`
${fmt('Hooks CLI - Diagnostic Commands', 'bright')}

${fmt('Usage:', 'cyan')}
  node hooks-cli.js <command> [options]

${fmt('Commands:', 'cyan')}
  status              Show all hooks and their status
  test <hook>         Test a specific hook with sample input
  log <hook>          Show recent invocations for a hook
    --last <n>        Number of entries to show (default: 10)
  validate            Run full validation suite
  stats               Show hook statistics
  debug <hook>        Toggle debug mode for a hook
    --enable          Enable debug
    --disable         Disable debug
  health              Show health status
  export              Force export stats to QuestDB

${fmt('Options:', 'cyan')}
  --json              Output as JSON
  --help, -h          Show this help

${fmt('Examples:', 'cyan')}
  node hooks-cli.js status
  node hooks-cli.js test git-safety-check
  node hooks-cli.js log git-safety-check --last 20
  node hooks-cli.js debug git-safety-check --enable
  node hooks-cli.js validate --json
`);
}

/**
 * Main CLI handler
 */
async function main() {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--') || a === '--enable' || a === '--disable');
  const command = args[0];

  // Check for help
  if (!command || process.argv.includes('--help') || process.argv.includes('-h')) {
    showHelp();
    return;
  }

  switch (command) {
    case 'status':
      cmdStatus();
      break;

    case 'test':
      if (!args[1]) {
        console.error(fmt('Error: Hook name required', 'red'));
        console.error('Usage: node hooks-cli.js test <hook-name>');
        process.exit(1);
      }
      await cmdTest(args[1]);
      break;

    case 'log':
      if (!args[1]) {
        console.error(fmt('Error: Hook name required', 'red'));
        console.error('Usage: node hooks-cli.js log <hook-name>');
        process.exit(1);
      }
      const lastIndex = process.argv.indexOf('--last');
      const last = lastIndex > -1 ? parseInt(process.argv[lastIndex + 1], 10) : 10;
      cmdLog(args[1], last);
      break;

    case 'validate':
      await cmdValidate();
      break;

    case 'stats':
      cmdStats();
      break;

    case 'debug':
      if (!args[1]) {
        console.error(fmt('Error: Hook name required', 'red'));
        console.error('Usage: node hooks-cli.js debug <hook-name> --enable|--disable');
        process.exit(1);
      }
      const enable = process.argv.includes('--enable');
      const disable = process.argv.includes('--disable');
      if (!enable && !disable) {
        // Toggle: check current state
        const isEnabled = debugger_?.isDebugEnabled(args[1]);
        cmdDebug(args[1], !isEnabled);
      } else {
        cmdDebug(args[1], enable);
      }
      break;

    case 'health':
      await cmdHealth();
      break;

    case 'export':
      await cmdExport();
      break;

    default:
      console.error(fmt(`Unknown command: ${command}`, 'red'));
      console.error('Run with --help for usage');
      process.exit(1);
  }
}

// Run
main().catch(err => {
  console.error(fmt(`Error: ${err.message}`, 'red'));
  process.exit(1);
});
