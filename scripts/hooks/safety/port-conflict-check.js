#!/usr/bin/env node
/**
 * Port Conflict Prevention Hook
 *
 * Intercepts Bash commands that try to bind to ports and checks if:
 * 1. Port is already in use
 * 2. Port is reserved for a known service
 *
 * Prevents orphan processes and port conflicts.
 *
 * Returns: { decision: "block", reason: "..." } or { decision: "warn", message: "..." } or {}
 */

const path = require('path');
const { readStdinJson, output, runCommand } = require(path.join(__dirname, '..', '..', 'lib', 'utils.js'));

// Reserved ports for known services (port -> service name)
const RESERVED_PORTS = {
  3000: 'grafana',
  3100: 'loki',
  5432: 'postgres',
  5433: 'postgres-n8n',
  5678: 'n8n',
  6379: 'redis',
  7007: 'backstage',
  8000: 'utxoracle-api',
  8001: 'utxoracle-ws',
  8080: 'mempool-web',
  8086: 'influxdb',
  8332: 'bitcoind-rpc',
  8812: 'questdb-pg',
  8999: 'mempool-api',
  9000: 'questdb-http',
  9009: 'questdb-ilp',
  9090: 'prometheus',
  9093: 'alertmanager',
  9100: 'node-exporter',
  11434: 'ollama'
};

// Default ports for common dev servers
const DEFAULT_SERVER_PORTS = {
  'npm run dev': 3000,
  'npm start': 3000,
  'yarn dev': 3000,
  'yarn start': 3000,
  'vite': 5173,
  'next dev': 3000,
  'react-scripts start': 3000,
  'flask run': 5000,
  'uvicorn': 8000,
  'gunicorn': 8000,
  'http.server': 8000,
  'php -S': 8000
};

// Server command indicators
const SERVER_INDICATORS = [
  'http.server',
  '--port',
  '-p ',
  'uvicorn',
  'gunicorn',
  'flask run',
  'npm start',
  'npm run dev',
  'yarn start',
  'yarn dev',
  'node ',
  '--bind',
  'listen',
  'vite',
  'next dev'
];

/**
 * Check if port is in use using ss command
 */
function isPortInUse(port) {
  // Try ss first (Linux)
  let result = runCommand(`ss -tlnp sport = :${port} 2>/dev/null`);
  if (result.success && result.output.includes('LISTEN')) {
    // Extract process name
    const match = result.output.match(/users:\(\("([^"]+)"/);
    const processName = match ? match[1] : 'unknown';
    return { inUse: true, process: processName };
  }

  // Fallback to lsof
  result = runCommand(`lsof -i :${port} -t 2>/dev/null`);
  if (result.success && result.output.trim()) {
    // Get process name from PID
    const pid = result.output.trim().split('\n')[0];
    const psResult = runCommand(`ps -p ${pid} -o comm= 2>/dev/null`);
    const processName = psResult.success ? psResult.output.trim() : 'unknown';
    return { inUse: true, process: processName };
  }

  return { inUse: false, process: null };
}

/**
 * Extract port number from command using various patterns
 */
function extractPortFromCommand(command) {
  const patterns = [
    // Explicit port flags
    /--port[=\s]+(\d+)/,           // --port=3000 or --port 3000
    /-p[=\s]+(\d+)/,               // -p=3000 or -p 3000
    /-p(\d+)/,                      // -p3000 (no space)

    // Python http.server
    /-m\s+http\.server\s+(\d+)/,

    // URL-style bindings
    /localhost:(\d+)/,
    /127\.0\.0\.1:(\d+)/,
    /0\.0\.0\.0:(\d+)/,
    /:(\d{4,5})(?:\s|$|\/)/,       // :PORT at end or before path

    // Framework-specific
    /uvicorn.*--port[=\s]+(\d+)/,
    /gunicorn.*-b[=\s]+[^:]+:(\d+)/,
    /flask.*--port[=\s]+(\d+)/,
    /PORT=(\d+)/                    // Environment variable
  ];

  for (const pattern of patterns) {
    const match = command.match(pattern);
    if (match) {
      const port = parseInt(match[1], 10);
      if (port >= 1 && port <= 65535) {
        return port;
      }
    }
  }

  return null;
}

/**
 * Get default port for a command if known
 */
function getDefaultPort(command) {
  for (const [indicator, port] of Object.entries(DEFAULT_SERVER_PORTS)) {
    if (command.includes(indicator)) {
      return port;
    }
  }
  return null;
}

/**
 * Check if command appears to start a server
 */
function isServerCommand(command) {
  return SERVER_INDICATORS.some(indicator => command.includes(indicator));
}

async function main() {
  try {
    const input = await readStdinJson();

    const toolName = input.tool_name || '';
    const toolInput = input.tool_input || {};
    const command = toolInput.command || '';

    // Only check Bash commands
    if (toolName !== 'Bash' || !command) {
      output({});
      process.exit(0);
    }

    // Skip if not a server/bind command
    if (!isServerCommand(command)) {
      output({});
      process.exit(0);
    }

    // Try to extract explicit port from command
    let port = extractPortFromCommand(command);

    // If no explicit port, check for default
    if (!port) {
      port = getDefaultPort(command);
    }

    // If still no port, we can't check - allow
    if (!port) {
      output({});
      process.exit(0);
    }

    // Check if port is reserved for a known service
    if (RESERVED_PORTS[port]) {
      const service = RESERVED_PORTS[port];
      const portCheck = isPortInUse(port);

      if (portCheck.inUse) {
        output({
          decision: 'block',
          reason: `Port ${port} is reserved for '${service}' and currently in use by '${portCheck.process}'.\n` +
            `Use a different port or stop the existing service first:\n` +
            `  kill $(lsof -t -i:${port})`
        });
        process.exit(0);
      }

      // Reserved but not in use - warn
      output({
        decision: 'warn',
        message: `Port ${port} is typically reserved for '${service}'.\n` +
          `If this conflicts, consider using a different port.`
      });
      process.exit(0);
    }

    // Check if port is in use by anything
    const portCheck = isPortInUse(port);
    if (portCheck.inUse) {
      output({
        decision: 'block',
        reason: `Port ${port} is already in use by '${portCheck.process}'.\n` +
          `Use a different port or stop the existing process:\n` +
          `  kill $(lsof -t -i:${port})`
      });
      process.exit(0);
    }

    // Port is free, allow
    output({});
    process.exit(0);

  } catch (err) {
    // On error, fail open (allow operation)
    console.error(`Port conflict check error: ${err.message}`);
    output({});
    process.exit(0);
  }
}

main();
