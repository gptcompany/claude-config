#!/usr/bin/env node
/**
 * Architecture Validator Hook for Claude Code
 *
 * Detects new components in code and suggests ARCHITECTURE.md updates:
 * 1. Detect architecture-relevant file changes
 * 2. Compare with documented architecture
 * 3. Suggest updates when new patterns detected
 *
 * Hook Type: PostToolUse
 * Matcher: Write/Edit (when file is in src/, lib/, components/, etc.)
 * Timeout: 10s
 *
 * Ported from: claude-hooks-shared/hooks/productivity/architecture-validator.py
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output, readFile } = require('../../lib/utils');
const { isGitRepo, getRepoRoot, getCurrentBranch } = require('../../lib/git-utils');

// Architecture file locations to check
const ARCHITECTURE_LOCATIONS = [
  'docs/ARCHITECTURE.md',
  'ARCHITECTURE.md',
  'architecture/ARCHITECTURE.md',
  '.planning/ARCHITECTURE.md'
];

// Files that indicate architecture-relevant changes
const ARCHITECTURE_TRIGGER_PATTERNS = [
  /^src\//,
  /^lib\//,
  /^api\//,
  /^app\//,
  /^scripts\//,
  /^components\//,
  /^services\//,
  /^hooks\//,
  /^utils\//,
  /^core\//,
  /^modules\//,
  /\.py$/,
  /\.rs$/,
  /\.ts$/,
  /\.tsx$/,
  /\.js$/,
  /\.jsx$/,
  /Dockerfile/,
  /docker-compose/,
  /\.sql$/,
  /pyproject\.toml$/,
  /Cargo\.toml$/,
  /package\.json$/
];

// Files to exclude from triggering
const EXCLUDE_PATTERNS = [
  /\.md$/,
  /\.json$/,
  /\.txt$/,
  /^\.claude\//,
  /^\.git\//,
  /__pycache__/,
  /\.pyc$/,
  /\/tests?\//,      // /test/ or /tests/ anywhere in path
  /^tests?\//,       // tests/ at start
  /\/test_/,         // test_ prefix
  /^test_/,          // test_ at start
  /\.test\./,        // .test. in filename
  /\.spec\./,        // .spec. in filename
  /_test\./,         // _test. in filename
  /_spec\./,         // _spec. in filename
  /node_modules\//,
  /\.d\.ts$/
];

// Component patterns to detect
const COMPONENT_PATTERNS = {
  'class': /^(?:export\s+)?class\s+(\w+)/gm,
  'function': /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/gm,
  'const_function': /^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(/gm,
  'interface': /^(?:export\s+)?interface\s+(\w+)/gm,
  'type': /^(?:export\s+)?type\s+(\w+)/gm,
  'module': /^module\s+(\w+)/gm,
  'struct': /^(?:pub\s+)?struct\s+(\w+)/gm,
  'impl': /^impl\s+(?:\w+\s+for\s+)?(\w+)/gm,
  'python_class': /^class\s+(\w+)/gm,
  'python_def': /^def\s+(\w+)/gm
};

/**
 * Check if file is architecture-relevant
 */
function isArchitectureRelevant(filePath) {
  if (!filePath) return false;

  // Check exclusions first
  for (const pattern of EXCLUDE_PATTERNS) {
    if (pattern.test(filePath)) {
      return false;
    }
  }

  // Check trigger patterns
  for (const pattern of ARCHITECTURE_TRIGGER_PATTERNS) {
    if (pattern.test(filePath)) {
      return true;
    }
  }

  return false;
}

/**
 * Find ARCHITECTURE.md in project
 */
function findArchitectureFile(projectDir) {
  for (const loc of ARCHITECTURE_LOCATIONS) {
    const archFile = path.join(projectDir, loc);
    if (fs.existsSync(archFile)) {
      return archFile;
    }
  }
  return null;
}

/**
 * Extract components from file content
 */
function extractComponents(content, filePath) {
  const components = [];
  const ext = path.extname(filePath).toLowerCase();

  // Select relevant patterns based on file extension
  let patterns = {};
  if (['.js', '.jsx', '.ts', '.tsx', '.mjs'].includes(ext)) {
    patterns = {
      'class': COMPONENT_PATTERNS['class'],
      'function': COMPONENT_PATTERNS['function'],
      'const_function': COMPONENT_PATTERNS['const_function'],
      'interface': COMPONENT_PATTERNS['interface'],
      'type': COMPONENT_PATTERNS['type']
    };
  } else if (['.py'].includes(ext)) {
    patterns = {
      'class': COMPONENT_PATTERNS['python_class'],
      'function': COMPONENT_PATTERNS['python_def']
    };
  } else if (['.rs'].includes(ext)) {
    patterns = {
      'struct': COMPONENT_PATTERNS['struct'],
      'impl': COMPONENT_PATTERNS['impl']
    };
  }

  for (const [type, pattern] of Object.entries(patterns)) {
    // Reset regex state
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const name = match[1];
      // Filter out common non-component names
      if (!['test', 'describe', 'it', 'expect', 'beforeEach', 'afterEach', '__init__'].includes(name.toLowerCase())) {
        components.push({ type, name, file: filePath });
      }
    }
  }

  return components;
}

/**
 * Check if component is documented in ARCHITECTURE.md
 */
function isComponentDocumented(component, architectureContent) {
  if (!architectureContent) return false;

  // Check for component name in architecture file
  const patterns = [
    new RegExp(`\\b${component.name}\\b`, 'i'),
    new RegExp(`\`${component.name}\``, 'i'),
    new RegExp(`\\*\\*${component.name}\\*\\*`, 'i')
  ];

  return patterns.some(p => p.test(architectureContent));
}

/**
 * Categorize file into architecture section
 */
function categorizeFile(filePath) {
  const normalized = filePath.toLowerCase();

  if (/^(src\/)?api\//.test(normalized) || /routes?/.test(normalized)) {
    return 'API';
  }
  if (/^(src\/)?components?\//.test(normalized)) {
    return 'UI Components';
  }
  if (/^(src\/)?services?\//.test(normalized)) {
    return 'Services';
  }
  if (/^(src\/)?hooks?\//.test(normalized)) {
    return 'Hooks';
  }
  if (/^(src\/)?utils?\//.test(normalized) || /^(src\/)?lib\//.test(normalized)) {
    return 'Utilities';
  }
  if (/^(src\/)?models?\//.test(normalized) || /^(src\/)?entities?\//.test(normalized)) {
    return 'Data Models';
  }
  if (/^(src\/)?core\//.test(normalized)) {
    return 'Core';
  }
  if (/database|migrations?|schema/.test(normalized)) {
    return 'Database';
  }
  if (/docker|container/.test(normalized)) {
    return 'Infrastructure';
  }

  return 'Other';
}

/**
 * Generate suggestion for architecture update
 */
function generateSuggestion(components, filePath, architectureFile) {
  const section = categorizeFile(filePath);
  const newComponents = components.filter(c => c.isNew);

  if (newComponents.length === 0) {
    return null;
  }

  const lines = [
    '',
    '## Architecture Update Suggested',
    '',
    `**File:** \`${filePath}\``,
    `**Section:** ${section}`,
    '',
    '**New components detected:**'
  ];

  for (const comp of newComponents) {
    lines.push(`  - \`${comp.name}\` (${comp.type})`);
  }

  lines.push('');

  if (architectureFile) {
    lines.push(`Consider updating \`${architectureFile}\` to document these components.`);
  } else {
    lines.push('Consider creating an ARCHITECTURE.md to document your codebase structure.');
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

    // Check if file is architecture-relevant
    if (!isArchitectureRelevant(filePath)) {
      process.exit(0);
    }

    // Get project root
    let projectDir = process.cwd();
    if (isGitRepo()) {
      const root = getRepoRoot();
      if (root) projectDir = root;
    }

    // Find architecture file
    const architectureFile = findArchitectureFile(projectDir);
    let architectureContent = null;
    if (architectureFile) {
      architectureContent = readFile(architectureFile);
    }

    // Get file content
    let content = toolInput.content || '';
    if (!content && toolInput.new_string) {
      // For Edit tool, we only have the edited portion
      content = toolInput.new_string;
    }

    // If no content provided, try to read the file
    if (!content && fs.existsSync(filePath)) {
      try {
        content = fs.readFileSync(filePath, 'utf8');
      } catch (err) {
        // Ignore read errors
      }
    }

    if (!content) {
      process.exit(0);
    }

    // Extract components
    const components = extractComponents(content, filePath);

    if (components.length === 0) {
      process.exit(0);
    }

    // Check which components are new (not documented)
    for (const comp of components) {
      comp.isNew = !isComponentDocumented(comp, architectureContent);
    }

    const newComponents = components.filter(c => c.isNew);

    // Only suggest if there are new components
    if (newComponents.length > 0) {
      const suggestion = generateSuggestion(components, filePath, architectureFile);

      if (suggestion) {
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
