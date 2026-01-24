#!/usr/bin/env node
/**
 * README Generator Hook for Claude Code
 *
 * Detects significant code changes and suggests README updates:
 * 1. Detect README-relevant file changes
 * 2. Check README.md consistency
 * 3. Suggest updates for outdated sections
 *
 * Hook Type: PostToolUse
 * Matcher: Write/Edit (when modifying package.json, exports, etc.)
 * Timeout: 10s
 *
 * Ported from: claude-hooks-shared/hooks/productivity/readme-generator.py
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output, readFile, getClaudeDir, ensureDir } = require('../../lib/utils');
const { isGitRepo, getRepoRoot, runGitCommand } = require('../../lib/git-utils');

// README file locations
const README_LOCATIONS = [
  'README.md',
  'docs/README.md'
];

// Files that should trigger README review
const README_TRIGGER_PATTERNS = [
  /^src\//,
  /^lib\//,
  /^api\//,
  /^app\//,
  /^scripts\//,
  /pyproject\.toml$/,
  /Cargo\.toml$/,
  /package\.json$/,
  /requirements\.txt$/,
  /setup\.py$/,
  /Dockerfile$/,
  /docker-compose/,
  /\.env\.example$/,
  /Makefile$/,
  /CLAUDE\.md$/,
  /ARCHITECTURE\.md$/
];

// Files to exclude
const EXCLUDE_PATTERNS = [
  /^\.claude\//,
  /^\.git\//,
  /__pycache__/,
  /\.pyc$/,
  /^tests?\//,
  /^test_/,
  /\.lock$/,
  /node_modules\//
];

// README sections to check
const README_SECTIONS = {
  installation: {
    triggers: ['package.json', 'requirements.txt', 'Cargo.toml', 'pyproject.toml', 'setup.py'],
    keywords: ['install', 'setup', 'getting started', 'prerequisites']
  },
  usage: {
    triggers: ['src/', 'lib/', 'bin/', 'cli'],
    keywords: ['usage', 'how to use', 'example', 'quick start']
  },
  configuration: {
    triggers: ['.env.example', 'config', 'settings'],
    keywords: ['configuration', 'config', 'environment', 'settings']
  },
  api: {
    triggers: ['api/', 'routes/', 'endpoints'],
    keywords: ['api', 'endpoints', 'routes', 'reference']
  },
  development: {
    triggers: ['Makefile', 'docker-compose', 'Dockerfile', '.devcontainer'],
    keywords: ['development', 'contributing', 'building', 'testing']
  }
};

// Minimum commits between README checks (to avoid over-triggering)
const MIN_COMMITS_BETWEEN_CHECKS = 5;

// State file for tracking
const STATE_DIR = path.join(getClaudeDir(), 'state');
const README_STATE_FILE = path.join(STATE_DIR, 'readme_check_state.json');

/**
 * Check if file is README-relevant
 */
function isReadmeRelevant(filePath) {
  if (!filePath) return false;

  // Check exclusions first
  for (const pattern of EXCLUDE_PATTERNS) {
    if (pattern.test(filePath)) {
      return false;
    }
  }

  // Check trigger patterns
  for (const pattern of README_TRIGGER_PATTERNS) {
    if (pattern.test(filePath)) {
      return true;
    }
  }

  return false;
}

/**
 * Find README.md in project
 */
function findReadmeFile(projectDir) {
  for (const loc of README_LOCATIONS) {
    const readmeFile = path.join(projectDir, loc);
    if (fs.existsSync(readmeFile)) {
      return readmeFile;
    }
  }
  return null;
}

/**
 * Get commits since README was last modified
 */
function getCommitsSinceReadmeChange() {
  try {
    const result = runGitCommand(['log', '--oneline', 'README.md']);
    if (result && result.success && result.stdout.trim()) {
      const readmeCommit = result.stdout.trim().split('\n')[0].split(' ')[0];
      const countResult = runGitCommand(['rev-list', '--count', `${readmeCommit}..HEAD`]);
      if (countResult && countResult.success) {
        return parseInt(countResult.stdout.trim(), 10);
      }
    }
  } catch (err) {
    // Ignore errors
  }
  return 0;
}

/**
 * Load and save README check state
 */
function loadState() {
  try {
    if (fs.existsSync(README_STATE_FILE)) {
      return JSON.parse(fs.readFileSync(README_STATE_FILE, 'utf8'));
    }
  } catch (err) {
    // Ignore errors
  }
  return { lastCheck: null, lastCommit: null };
}

function saveState(state) {
  ensureDir(STATE_DIR);
  fs.writeFileSync(README_STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Analyze README content for sections
 */
function analyzeReadme(content) {
  if (!content) return {};

  const sections = {};
  const lines = content.split('\n');
  let currentSection = null;

  for (const line of lines) {
    // Detect headers
    const headerMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headerMatch) {
      currentSection = headerMatch[1].toLowerCase();
    }

    // Track which sections exist
    for (const [sectionName, sectionDef] of Object.entries(README_SECTIONS)) {
      for (const keyword of sectionDef.keywords) {
        if (currentSection && currentSection.includes(keyword)) {
          sections[sectionName] = true;
        }
      }
    }
  }

  return sections;
}

/**
 * Determine which sections need attention based on file changes
 */
function detectNeededUpdates(filePath, readmeContent) {
  const updates = [];
  const existingSections = analyzeReadme(readmeContent);
  const fileName = path.basename(filePath).toLowerCase();
  const normalizedPath = filePath.toLowerCase();

  for (const [sectionName, sectionDef] of Object.entries(README_SECTIONS)) {
    // Check if this file triggers this section
    const triggers = sectionDef.triggers.some(trigger => {
      if (trigger.includes('/')) {
        return normalizedPath.includes(trigger);
      }
      return fileName.includes(trigger) || normalizedPath.includes(trigger);
    });

    if (triggers) {
      if (!existingSections[sectionName]) {
        updates.push({
          section: sectionName,
          action: 'missing',
          message: `Consider adding a ${sectionName} section to README.md`
        });
      } else {
        updates.push({
          section: sectionName,
          action: 'review',
          message: `Review ${sectionName} section - related file changed`
        });
      }
    }
  }

  return updates;
}

/**
 * Extract package info from package.json or pyproject.toml
 */
function extractPackageInfo(projectDir) {
  const info = {};

  // Try package.json
  const packageJson = readFile(path.join(projectDir, 'package.json'));
  if (packageJson) {
    try {
      const pkg = JSON.parse(packageJson);
      info.name = pkg.name;
      info.version = pkg.version;
      info.description = pkg.description;
      info.scripts = pkg.scripts ? Object.keys(pkg.scripts) : [];
    } catch (err) {
      // Ignore parse errors
    }
  }

  // Try pyproject.toml
  const pyproject = readFile(path.join(projectDir, 'pyproject.toml'));
  if (pyproject) {
    const nameMatch = pyproject.match(/name\s*=\s*["']([^"']+)["']/);
    const versionMatch = pyproject.match(/version\s*=\s*["']([^"']+)["']/);
    const descMatch = pyproject.match(/description\s*=\s*["']([^"']+)["']/);

    if (nameMatch) info.name = nameMatch[1];
    if (versionMatch) info.version = versionMatch[1];
    if (descMatch) info.description = descMatch[1];
  }

  return info;
}

/**
 * Generate README suggestion
 */
function generateSuggestion(filePath, updates, readmeFile, packageInfo) {
  if (updates.length === 0) {
    return null;
  }

  const lines = [
    '',
    '## README Update Suggested',
    '',
    `**File Changed:** \`${filePath}\``,
    ''
  ];

  if (packageInfo.name) {
    lines.push(`**Project:** ${packageInfo.name}${packageInfo.version ? ` v${packageInfo.version}` : ''}`);
    lines.push('');
  }

  const missing = updates.filter(u => u.action === 'missing');
  const review = updates.filter(u => u.action === 'review');

  if (missing.length > 0) {
    lines.push('**Missing sections:**');
    for (const update of missing) {
      lines.push(`  - ${update.message}`);
    }
    lines.push('');
  }

  if (review.length > 0) {
    lines.push('**Sections to review:**');
    for (const update of review) {
      lines.push(`  - ${update.message}`);
    }
    lines.push('');
  }

  if (readmeFile) {
    lines.push(`README location: \`${readmeFile}\``);
  } else {
    lines.push('Consider creating a README.md for this project.');
  }

  return lines.join('\n');
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    const inputData = await readStdinJson();

    // Check if this is a Write or Edit tool use
    const toolName = inputData.tool_name || '';
    if (toolName !== 'Write' && toolName !== 'Edit') {
      process.exit(0);
    }

    // Get file path
    const toolInput = inputData.tool_input || {};
    const filePath = toolInput.file_path || '';

    // Check if file is README-relevant
    if (!isReadmeRelevant(filePath)) {
      process.exit(0);
    }

    // Get project root
    let projectDir = process.cwd();
    if (isGitRepo()) {
      const root = getRepoRoot();
      if (root) projectDir = root;
    }

    // Check if we should skip (too frequent)
    const readmeFile = findReadmeFile(projectDir);
    if (readmeFile && isGitRepo()) {
      const commitsSince = getCommitsSinceReadmeChange();
      if (commitsSince < MIN_COMMITS_BETWEEN_CHECKS) {
        // README was recently updated, skip
        process.exit(0);
      }
    }

    // Load state to avoid duplicate suggestions in same session
    const state = loadState();
    const now = new Date().toISOString();

    // Don't suggest more than once per 5 minutes
    if (state.lastCheck) {
      const lastCheck = new Date(state.lastCheck);
      const minutesSince = (Date.now() - lastCheck.getTime()) / (1000 * 60);
      if (minutesSince < 5) {
        process.exit(0);
      }
    }

    // Read README content
    let readmeContent = null;
    if (readmeFile) {
      readmeContent = readFile(readmeFile);
    }

    // Detect needed updates
    const updates = detectNeededUpdates(filePath, readmeContent);

    if (updates.length > 0) {
      // Get package info for context
      const packageInfo = extractPackageInfo(projectDir);

      // Generate suggestion
      const suggestion = generateSuggestion(filePath, updates, readmeFile, packageInfo);

      if (suggestion) {
        // Update state
        saveState({ lastCheck: now, lastFile: filePath });

        output({
          systemMessage: suggestion
        });
      }
    }

    process.exit(0);

  } catch (err) {
    // Fail silently - don't block the user
    process.exit(0);
  }
}

main();
