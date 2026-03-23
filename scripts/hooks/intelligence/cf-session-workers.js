#!/usr/bin/env node
// Hook: Session-start worker trigger (lightweight, background, with cooldown)
// Triggers map worker in background from the repo CWD on session start.
// Cooldown: 1 hour per-repo.

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CWD = process.cwd();
const COOLDOWN_MS = 3600000; // 1 hour
const MARKER_DIR = path.join(CWD, '.claude-flow', 'metrics');
const MARKER_FILE = path.join(MARKER_DIR, '.session-worker-last');

// Skip if we're in ~/.claude (daemon dir, not a project)
if (CWD === path.join(process.env.HOME, '.claude')) {
    process.exit(0);
}

// Skip if no .git (not a repo)
if (!fs.existsSync(path.join(CWD, '.git'))) {
    process.exit(0);
}

// Cooldown check
try {
    if (fs.existsSync(MARKER_FILE)) {
        const lastRun = parseInt(fs.readFileSync(MARKER_FILE, 'utf-8').trim(), 10);
        if (Date.now() - lastRun < COOLDOWN_MS) {
            process.exit(0);
        }
    }
} catch {
    // Continue if marker can't be read
}

// Trigger map worker in background (non-blocking)
try {
    fs.mkdirSync(MARKER_DIR, { recursive: true });
    fs.writeFileSync(MARKER_FILE, String(Date.now()));
    // Fire and forget - the worker runs in its own process
    execSync('claude-flow daemon trigger --worker map >/dev/null 2>&1 &', {
        cwd: CWD,
        timeout: 3000,
        stdio: 'ignore',
        shell: true,
    });
} catch {
    // Silent fail - don't block the session
}
