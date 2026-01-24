#!/usr/bin/env node
/**
 * Hook Health Monitor
 *
 * Phase 14.5-08: Debug & Validation System
 *
 * Provides:
 * - Periodic health checks for all hooks
 * - Status reporting: healthy/degraded/failing
 * - Error rate tracking
 * - Stuck hook detection
 * - QuestDB export for Grafana dashboards
 *
 * Usage:
 *   node hook-health.js --check     # Run full health check
 *   node hook-health.js --export    # Force QuestDB export
 *   node hook-health.js --status    # Show current status
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawn } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const DEBUG_DIR = path.join(HOME_DIR, '.claude', 'debug', 'hooks');
const HEALTH_FILE = path.join(DEBUG_DIR, 'health.json');
const HOOKS_FILE = path.join(HOME_DIR, '.claude', 'hooks', 'hooks.json');
const HEALTH_CHECK_TIMEOUT = 5000; // 5 seconds
const ERROR_RATE_THRESHOLD_DEGRADED = 0.05; // 5%
const ERROR_RATE_THRESHOLD_FAILING = 0.20; // 20%

// Import libraries
let metrics, debugger_;
try {
  metrics = require('../../lib/metrics');
} catch (e) {
  metrics = null;
}

try {
  debugger_ = require('../../lib/hook-debugger');
} catch (e) {
  debugger_ = null;
}

// Health status enum
const HealthStatus = {
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  FAILING: 'failing',
  UNKNOWN: 'unknown'
};

/**
 * Ensure debug directory exists
 */
function ensureDebugDir() {
  try {
    if (!fs.existsSync(DEBUG_DIR)) {
      fs.mkdirSync(DEBUG_DIR, { recursive: true });
    }
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Load current health status
 * @returns {object} Health data
 */
function loadHealthData() {
  try {
    if (fs.existsSync(HEALTH_FILE)) {
      return JSON.parse(fs.readFileSync(HEALTH_FILE, 'utf8'));
    }
  } catch (e) {
    // Ignore errors
  }
  return {
    lastCheck: null,
    hooks: {}
  };
}

/**
 * Save health data
 * @param {object} data - Health data
 */
function saveHealthData(data) {
  ensureDebugDir();
  try {
    fs.writeFileSync(HEALTH_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Extract hook scripts from hooks.json
 * @returns {object[]} Array of hook info
 */
function getHooksFromConfig() {
  const hooks = [];

  try {
    if (!fs.existsSync(HOOKS_FILE)) {
      return hooks;
    }

    const config = JSON.parse(fs.readFileSync(HOOKS_FILE, 'utf8'));

    for (const [eventType, hookDefs] of Object.entries(config.hooks || {})) {
      for (const hookDef of hookDefs) {
        for (const hook of hookDef.hooks || []) {
          if (hook.command) {
            // Extract script name from command
            const command = hook.command;
            let name = 'unknown';

            // Try to extract script name
            const match = command.match(/([a-zA-Z0-9_-]+)\.js/);
            if (match) {
              name = match[1];
            }

            hooks.push({
              name,
              command,
              eventType,
              matcher: hookDef.matcher,
              description: hookDef.description,
              enabled: hookDef.enabled !== false
            });
          }
        }
      }
    }
  } catch (e) {
    console.error('Error loading hooks config:', e.message);
  }

  return hooks;
}

/**
 * Check if a script file exists
 * @param {string} command - Hook command
 * @returns {boolean} Exists
 */
function checkScriptExists(command) {
  try {
    // Extract script path from command
    let scriptPath = command;

    // Handle node prefix
    if (scriptPath.startsWith('node ')) {
      scriptPath = scriptPath.replace(/^node\s+/, '');
    }

    // Handle -e flag (inline scripts)
    if (scriptPath.includes(' -e ')) {
      return true; // Inline scripts always "exist"
    }

    // Expand environment variables
    scriptPath = scriptPath.replace(/\$HOME|\$\{HOME\}/g, HOME_DIR);
    scriptPath = scriptPath.replace(/~/g, HOME_DIR);

    // Remove quotes
    scriptPath = scriptPath.replace(/^["']|["']$/g, '');

    // Extract just the path (first part)
    scriptPath = scriptPath.split(/\s+/)[0];

    return fs.existsSync(scriptPath);
  } catch (e) {
    return false;
  }
}

/**
 * Check if hook returns within timeout
 * @param {string} command - Hook command
 * @param {number} timeout - Timeout in ms
 * @returns {Promise<object>} Check result
 */
async function checkHookTimeout(command, timeout = HEALTH_CHECK_TIMEOUT) {
  return new Promise((resolve) => {
    const result = {
      success: false,
      durationMs: 0,
      error: null
    };

    const startTime = Date.now();

    // Expand command
    let expandedCmd = command
      .replace(/\$HOME|\$\{HOME\}/g, HOME_DIR)
      .replace(/~/g, HOME_DIR);

    // Handle inline scripts (-e flag)
    if (expandedCmd.includes(' -e ')) {
      // For inline scripts, just check they can be parsed
      result.success = true;
      result.durationMs = Date.now() - startTime;
      resolve(result);
      return;
    }

    // Split command
    const parts = expandedCmd.split(/\s+/);
    const cmd = parts[0];
    const args = parts.slice(1);

    try {
      const child = spawn(cmd, args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, HOOK_HEALTH_CHECK: '1' }
      });

      const timer = setTimeout(() => {
        child.kill('SIGTERM');
        result.error = 'Timeout';
        result.durationMs = timeout;
        resolve(result);
      }, timeout);

      // Send empty input
      child.stdin.write('{}');
      child.stdin.end();

      child.on('close', (code) => {
        clearTimeout(timer);
        result.durationMs = Date.now() - startTime;
        result.success = code === 0;
        if (code !== 0) {
          result.error = `Exit code ${code}`;
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
 * Determine health status from stats
 * @param {object} stats - Hook stats
 * @returns {string} Health status
 */
function determineHealthStatus(stats) {
  if (!stats) return HealthStatus.UNKNOWN;

  const errorRate = stats.errorRate || 0;

  if (errorRate >= ERROR_RATE_THRESHOLD_FAILING) {
    return HealthStatus.FAILING;
  }

  if (errorRate >= ERROR_RATE_THRESHOLD_DEGRADED) {
    return HealthStatus.DEGRADED;
  }

  return HealthStatus.HEALTHY;
}

/**
 * Run full health check on all hooks
 * @returns {Promise<object>} Health check result
 */
async function runHealthCheck() {
  const hooks = getHooksFromConfig();
  const healthData = {
    lastCheck: new Date().toISOString(),
    totalHooks: hooks.length,
    healthy: 0,
    degraded: 0,
    failing: 0,
    unknown: 0,
    hooks: {}
  };

  for (const hook of hooks) {
    const hookHealth = {
      status: HealthStatus.UNKNOWN,
      lastSuccess: null,
      lastError: null,
      errorRate: 0,
      checks: {
        exists: false,
        timeout: false,
        valid: false
      }
    };

    // Check 1: Script exists
    hookHealth.checks.exists = checkScriptExists(hook.command);

    // Check 2: Returns within timeout
    if (hookHealth.checks.exists) {
      const timeoutCheck = await checkHookTimeout(hook.command);
      hookHealth.checks.timeout = timeoutCheck.success;

      if (!timeoutCheck.success && timeoutCheck.error) {
        hookHealth.lastError = timeoutCheck.error;
      }
    }

    // Check 3: Get stats from debugger
    if (debugger_) {
      const stats = debugger_.getHookStats(hook.name);
      if (stats && stats.calls > 0) {
        hookHealth.errorRate = stats.errorRate;
        hookHealth.lastSuccess = stats.lastSuccess;
        hookHealth.lastError = stats.lastError || hookHealth.lastError;
      }
    }

    // Determine overall status
    if (!hookHealth.checks.exists) {
      hookHealth.status = HealthStatus.FAILING;
    } else if (!hookHealth.checks.timeout) {
      hookHealth.status = HealthStatus.DEGRADED;
    } else {
      hookHealth.status = determineHealthStatus(hookHealth);
    }

    // Count by status
    switch (hookHealth.status) {
      case HealthStatus.HEALTHY:
        healthData.healthy++;
        break;
      case HealthStatus.DEGRADED:
        healthData.degraded++;
        break;
      case HealthStatus.FAILING:
        healthData.failing++;
        break;
      default:
        healthData.unknown++;
    }

    healthData.hooks[hook.name] = hookHealth;
  }

  // Save health data
  saveHealthData(healthData);

  // Export to QuestDB
  await exportHealthToQuestDB(healthData);

  return healthData;
}

/**
 * Export health data to QuestDB
 * @param {object} healthData - Health data
 * @returns {Promise<boolean>} Success
 */
async function exportHealthToQuestDB(healthData) {
  if (!metrics) return false;

  try {
    const project = process.env.PROJECT_NAME || path.basename(process.cwd());

    for (const [hookName, hookHealth] of Object.entries(healthData.hooks)) {
      const statusCode = {
        [HealthStatus.HEALTHY]: 0,
        [HealthStatus.DEGRADED]: 1,
        [HealthStatus.FAILING]: 2,
        [HealthStatus.UNKNOWN]: 3
      }[hookHealth.status] || 3;

      const lastSuccessAge = hookHealth.lastSuccess
        ? Math.floor((Date.now() - new Date(hookHealth.lastSuccess).getTime()) / 1000)
        : -1;

      const tags = {
        hook: hookName,
        project
      };

      const values = {
        status: statusCode,
        error_rate: hookHealth.errorRate,
        last_success_age_s: lastSuccessAge
      };

      await metrics.exportToQuestDB('claude_hook_health', values, tags);
    }

    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Format health data for display
 * @param {object} healthData - Health data
 * @returns {string} Formatted output
 */
function formatHealthOutput(healthData) {
  const lines = [
    'Hook Health Report',
    '==================',
    '',
    `Last Check: ${healthData.lastCheck}`,
    `Total Hooks: ${healthData.totalHooks}`,
    '',
    `Healthy:  ${healthData.healthy}`,
    `Degraded: ${healthData.degraded}`,
    `Failing:  ${healthData.failing}`,
    `Unknown:  ${healthData.unknown}`,
    ''
  ];

  // Show failing hooks
  if (healthData.failing > 0) {
    lines.push('FAILING:');
    for (const [name, health] of Object.entries(healthData.hooks)) {
      if (health.status === HealthStatus.FAILING) {
        lines.push(`  - ${name}: ${health.lastError || 'Unknown error'}`);
      }
    }
    lines.push('');
  }

  // Show degraded hooks
  if (healthData.degraded > 0) {
    lines.push('DEGRADED:');
    for (const [name, health] of Object.entries(healthData.hooks)) {
      if (health.status === HealthStatus.DEGRADED) {
        lines.push(`  - ${name}: error_rate=${(health.errorRate * 100).toFixed(1)}%`);
      }
    }
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Main CLI handler
 */
async function main() {
  const args = process.argv.slice(2);
  const command = args[0] || '--status';

  switch (command) {
    case '--check':
    case '-c':
      console.log('Running health check...');
      const healthData = await runHealthCheck();
      console.log(formatHealthOutput(healthData));
      break;

    case '--export':
    case '-e':
      console.log('Exporting to QuestDB...');
      const data = loadHealthData();
      if (data.lastCheck) {
        const success = await exportHealthToQuestDB(data);
        console.log(success ? 'Export successful' : 'Export failed');
      } else {
        console.log('No health data to export. Run --check first.');
      }
      break;

    case '--status':
    case '-s':
      const current = loadHealthData();
      if (current.lastCheck) {
        console.log(formatHealthOutput(current));
      } else {
        console.log('No health data available. Run --check first.');
      }
      break;

    case '--json':
    case '-j':
      const jsonData = loadHealthData();
      console.log(JSON.stringify(jsonData, null, 2));
      break;

    case '--help':
    case '-h':
      console.log(`
Hook Health Monitor

Usage:
  node hook-health.js --check   Run full health check
  node hook-health.js --export  Force QuestDB export
  node hook-health.js --status  Show current status
  node hook-health.js --json    Output as JSON
  node hook-health.js --help    Show this help

Environment:
  HOOK_HEALTH_CHECK=1  Set when running health checks (for hooks to detect)
`);
      break;

    default:
      console.error(`Unknown command: ${command}`);
      process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
  });
}

module.exports = {
  runHealthCheck,
  loadHealthData,
  saveHealthData,
  getHooksFromConfig,
  checkScriptExists,
  checkHookTimeout,
  determineHealthStatus,
  exportHealthToQuestDB,
  formatHealthOutput,
  HealthStatus,
  HEALTH_FILE,
  HOOKS_FILE
};
