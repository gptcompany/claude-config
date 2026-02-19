#!/usr/bin/env node
/**
 * Confidence Gate Sync Hook
 *
 * Detects drift between confidence_gate.py script and its documentation:
 * - skills/confidence-gate/SKILL.md
 * - commands/pipeline.gsd.md
 * - commands/pipeline.speckit.md
 * - skills/auto-pipeline/SKILL.md
 *
 * Triggers on edits to any of these files and cross-checks consistency.
 *
 * Hook Type: PostToolUse
 * Matcher: Write|Edit|MultiEdit
 * Timeout: 5s
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output } = require('../../lib/utils');

const CLAUDE_DIR = path.join(require('os').homedir(), '.claude');

// Files to monitor for drift
const MONITORED_FILES = {
  script: path.join(CLAUDE_DIR, 'scripts', 'confidence_gate.py'),
  skill: path.join(CLAUDE_DIR, 'skills', 'confidence-gate', 'SKILL.md'),
  pipelineGsd: path.join(CLAUDE_DIR, 'commands', 'pipeline.gsd.md'),
  pipelineSpeckit: path.join(CLAUDE_DIR, 'commands', 'pipeline.speckit.md'),
  autoPipeline: path.join(CLAUDE_DIR, 'skills', 'auto-pipeline', 'SKILL.md'),
};

// Debounce: skip if ran recently
const DEBOUNCE_FILE = '/tmp/confidence-gate-sync-lastrun';
const DEBOUNCE_MS = 10000;

function shouldRun() {
  try {
    if (fs.existsSync(DEBOUNCE_FILE)) {
      const lastRun = parseInt(fs.readFileSync(DEBOUNCE_FILE, 'utf8'), 10);
      if (Date.now() - lastRun < DEBOUNCE_MS) return false;
    }
  } catch { /* ignore */ }
  return true;
}

function markRun() {
  try { fs.writeFileSync(DEBOUNCE_FILE, Date.now().toString()); } catch { /* ignore */ }
}

/**
 * Extract CLI flag names from confidence_gate.py argparse calls.
 * Returns Set of flag names like: --files, --step, --json, etc.
 */
function extractScriptFlags(content) {
  const flags = new Set();
  // Match all add_argument() calls, then extract ALL --flags from each
  const callRe = /parser\.add_argument\(([^)]+)\)/g;
  let call;
  while ((call = callRe.exec(content)) !== null) {
    const flagRe = /"(--[\w-]+)"/g;
    let m;
    while ((m = flagRe.exec(call[1])) !== null) {
      flags.add(m[1]);
    }
  }
  return flags;
}

/**
 * Extract documented flags from a markdown file.
 * Looks for patterns like: | `--flag` | or `--flag` in code blocks
 */
function extractDocFlags(content) {
  const flags = new Set();
  // Table format: | `--flag-name` | or | `--flag1`, `--flag2` |
  // Capture all backtick-enclosed --flags anywhere in table rows
  const tableRe = /`(--[\w-]+)`/g;
  let m;
  while ((m = tableRe.exec(content)) !== null) {
    flags.add(m[1]);
  }
  return flags;
}

/**
 * Extract GateDecision values from the script.
 */
function extractDecisions(content) {
  const decisions = new Set();
  const re = /class GateDecision[\s\S]*?(?=\nclass |\n[^\s])/;
  const match = content.match(re);
  if (match) {
    const enumRe = /(\w+)\s*=\s*"(\w+)"/g;
    let m;
    while ((m = enumRe.exec(match[0])) !== null) {
      decisions.add(m[1]); // e.g., AUTO_APPROVE
    }
  }
  return decisions;
}

/**
 * Check if a doc file references invalid decision names.
 */
function findInvalidDecisions(docContent, validDecisions) {
  const invalid = [];
  // Look for decision-like patterns: ITERATE, AUTO_REJECT, etc.
  const candidates = ['ITERATE', 'AUTO_REJECT', 'REJECT', 'APPROVE'];
  for (const c of candidates) {
    if (!validDecisions.has(c) && docContent.includes(c)) {
      // Verify it's used as a decision name (not just a verb)
      const re = new RegExp(`\\b${c}\\b(?!\\s*[a-z])`, 'g');
      const matches = docContent.match(re);
      if (matches && matches.length > 0) {
        invalid.push(c);
      }
    }
  }
  return invalid;
}

/**
 * Main: check if edited file is monitored, then validate consistency.
 */
async function main() {
  if (!shouldRun()) {
    process.exit(0);
  }

  let input;
  try {
    input = await readStdinJson();
  } catch {
    process.exit(0);
  }

  const toolInput = input?.tool_input || {};
  const filePath = toolInput.file_path || '';

  // Check if edited file is one we monitor
  const monitoredPaths = Object.values(MONITORED_FILES);
  const isMonitored = monitoredPaths.some(mp => filePath.includes(path.basename(mp)));

  if (!isMonitored) {
    process.exit(0);
  }

  markRun();

  // Read all files
  const files = {};
  for (const [key, fp] of Object.entries(MONITORED_FILES)) {
    try {
      files[key] = fs.readFileSync(fp, 'utf8');
    } catch {
      files[key] = null;
    }
  }

  if (!files.script) {
    process.exit(0); // Can't validate without the script
  }

  const drifts = [];

  // 1. Compare script flags vs SKILL.md flags
  const scriptFlags = extractScriptFlags(files.script);
  if (files.skill) {
    const skillFlags = extractDocFlags(files.skill);
    for (const flag of scriptFlags) {
      if (flag === '--output' || flag === '--confidence') continue; // Aliases, not primary
      if (!skillFlags.has(flag)) {
        drifts.push(`SKILL.md missing flag: ${flag}`);
      }
    }
    for (const flag of skillFlags) {
      if (!scriptFlags.has(flag)) {
        drifts.push(`SKILL.md documents non-existent flag: ${flag}`);
      }
    }
  }

  // 2. Check decision names in docs
  const validDecisions = extractDecisions(files.script);
  for (const [key, content] of Object.entries(files)) {
    if (key === 'script' || !content) continue;
    const invalid = findInvalidDecisions(content, validDecisions);
    if (invalid.length > 0) {
      const fileName = path.basename(MONITORED_FILES[key]);
      drifts.push(`${fileName} uses invalid decision(s): ${invalid.join(', ')}`);
    }
  }

  // 3. Report
  if (drifts.length > 0) {
    output({
      systemMessage: `[confidence-gate-sync] Drift detected (${drifts.length} issue${drifts.length > 1 ? 's' : ''}):\n${drifts.map(d => `  - ${d}`).join('\n')}\nConsider updating docs to match scripts/confidence_gate.py`
    });
  }

  process.exit(0);
}

main().catch(() => process.exit(0));
