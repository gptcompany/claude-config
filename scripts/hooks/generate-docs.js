#!/usr/bin/env node
/**
 * Hooks Documentation Generator
 *
 * Phase 14.6-04: Documentation & Validation
 *
 * Auto-generates documentation from hook files:
 * - Parses JSDoc comments
 * - Extracts configuration
 * - Generates markdown catalog
 * - Updates HOOKS-CATALOG.md
 *
 * Usage:
 *   node generate-docs.js              # Generate to stdout
 *   node generate-docs.js --update     # Update HOOKS-CATALOG.md
 *   node generate-docs.js --json       # Output as JSON
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HOME_DIR = os.homedir();
const HOOKS_DIR = path.join(HOME_DIR, '.claude', 'scripts', 'hooks');
const DOCS_DIR = path.join(HOME_DIR, '.claude', 'docs');
const CATALOG_FILE = path.join(DOCS_DIR, 'HOOKS-CATALOG.md');

// Hook categories
const CATEGORIES = {
  safety: 'Core & Safety Hooks',
  intelligence: 'Intelligence & Session Hooks',
  productivity: 'Quality & Productivity Hooks',
  quality: 'Quality & Productivity Hooks',
  metrics: 'Metrics & Monitoring Hooks',
  coordination: 'Coordination Hooks',
  control: 'Control Hooks',
  ux: 'UX Hooks',
  debug: 'Debug Hooks'
};

/**
 * Find all hook files recursively
 * @param {string} dir - Directory to search
 * @returns {string[]} Array of file paths
 */
function findHookFiles(dir) {
  const hooks = [];

  if (!fs.existsSync(dir)) {
    return hooks;
  }

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      // Skip lib, node_modules, test directories
      if (!['lib', 'node_modules', '__tests__', 'test'].includes(entry.name)) {
        hooks.push(...findHookFiles(fullPath));
      }
    } else if (entry.name.endsWith('.js') && !entry.name.includes('.test.')) {
      hooks.push(fullPath);
    }
  }

  return hooks;
}

/**
 * Parse JSDoc comment from file
 * @param {string} content - File content
 * @returns {object} Parsed documentation
 */
function parseJSDoc(content) {
  const doc = {
    description: '',
    event: '',
    purpose: '',
    inputExample: null,
    outputExample: null,
    configuration: [],
    exports: []
  };

  // Extract main JSDoc block
  const jsdocMatch = content.match(/\/\*\*\s*([\s\S]*?)\s*\*\//);
  if (jsdocMatch) {
    const jsdoc = jsdocMatch[1];

    // Extract description (first paragraph)
    const descMatch = jsdoc.match(/^\s*\*?\s*([^@\n][^\n]*(?:\n\s*\*?\s*[^@\n][^\n]*)*)/);
    if (descMatch) {
      doc.description = descMatch[1]
        .split('\n')
        .map(line => line.replace(/^\s*\*?\s*/, '').trim())
        .filter(Boolean)
        .join(' ');
    }

    // Extract @event
    const eventMatch = jsdoc.match(/@event\s+(\w+)/i) || jsdoc.match(/Event:\s*(\w+)/i);
    if (eventMatch) {
      doc.event = eventMatch[1];
    }

    // Extract @purpose
    const purposeMatch = jsdoc.match(/@purpose\s+(.+)/i) || jsdoc.match(/Purpose:\s*(.+)/i);
    if (purposeMatch) {
      doc.purpose = purposeMatch[1].trim();
    }
  }

  // Infer event from content if not found
  if (!doc.event) {
    if (content.includes('PreToolUse') || content.includes('tool_input')) {
      doc.event = 'PreToolUse';
    } else if (content.includes('PostToolUse') || content.includes('tool_output')) {
      doc.event = 'PostToolUse';
    } else if (content.includes('UserPromptSubmit') || content.includes('message')) {
      doc.event = 'UserPromptSubmit';
    } else if (content.includes('Stop') || content.includes('stop_reason')) {
      doc.event = 'Stop';
    }
  }

  // Extract configuration constants
  const configPatterns = [
    /const\s+(\w+)\s*=\s*(\d+)/g,
    /const\s+(\w+)\s*=\s*'([^']+)'/g,
    /const\s+(\w+)\s*=\s*"([^"]+)"/g,
    /const\s+(\w+)\s*=\s*(\[.+?\])/g
  ];

  for (const pattern of configPatterns) {
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const name = match[1];
      // Skip internal/private constants
      if (!name.startsWith('_') && name === name.toUpperCase()) {
        doc.configuration.push({
          name,
          value: match[2]
        });
      }
    }
  }

  // Extract module.exports
  const exportsMatch = content.match(/module\.exports\s*=\s*\{([^}]+)\}/);
  if (exportsMatch) {
    const exports = exportsMatch[1]
      .split(',')
      .map(e => e.trim().split(':')[0].trim())
      .filter(e => e && !e.startsWith('//'));
    doc.exports = exports;
  }

  return doc;
}

/**
 * Get category from file path
 * @param {string} filePath - Hook file path
 * @returns {string} Category key
 */
function getCategory(filePath) {
  const relative = path.relative(HOOKS_DIR, filePath);
  const parts = relative.split(path.sep);

  if (parts.length > 1) {
    return parts[0];
  }

  return 'other';
}

/**
 * Generate hook documentation
 * @param {string} filePath - Hook file path
 * @returns {object} Hook documentation
 */
function generateHookDoc(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const doc = parseJSDoc(content);

  const name = path.basename(filePath, '.js');
  const category = getCategory(filePath);
  const relativePath = path.relative(HOME_DIR, filePath);

  return {
    name,
    path: '~/' + relativePath,
    category,
    categoryTitle: CATEGORIES[category] || 'Other Hooks',
    event: doc.event || 'Unknown',
    description: doc.description || `Hook: ${name}`,
    purpose: doc.purpose || doc.description?.split('.')[0] || '',
    configuration: doc.configuration,
    exports: doc.exports
  };
}

/**
 * Generate markdown for a single hook
 * @param {object} hook - Hook documentation
 * @returns {string} Markdown content
 */
function generateHookMarkdown(hook) {
  const lines = [
    `### ${hook.name}.js`,
    '',
    `**Event:** ${hook.event}`,
    `**Path:** \`${hook.path}\``,
    `**Purpose:** ${hook.purpose || hook.description}`,
    ''
  ];

  if (hook.configuration.length > 0) {
    lines.push('**Configuration:**');
    for (const config of hook.configuration.slice(0, 5)) { // Limit to 5
      lines.push(`- \`${config.name}\`: ${config.value}`);
    }
    lines.push('');
  }

  lines.push('---');
  lines.push('');

  return lines.join('\n');
}

/**
 * Generate full catalog markdown
 * @param {object[]} hooks - Array of hook documentation
 * @returns {string} Full markdown content
 */
function generateCatalogMarkdown(hooks) {
  const lines = [
    '# Claude Code Hooks Catalog (Auto-Generated)',
    '',
    `**Generated:** ${new Date().toISOString().split('T')[0]}`,
    `**Total Hooks:** ${hooks.length}`,
    '',
    '---',
    ''
  ];

  // Group by category
  const byCategory = {};
  for (const hook of hooks) {
    const cat = hook.categoryTitle;
    if (!byCategory[cat]) {
      byCategory[cat] = [];
    }
    byCategory[cat].push(hook);
  }

  // Generate table of contents
  lines.push('## Table of Contents');
  lines.push('');
  let tocIndex = 1;
  for (const category of Object.keys(byCategory).sort()) {
    const anchor = category.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    lines.push(`${tocIndex}. [${category}](#${anchor})`);
    tocIndex++;
  }
  lines.push('');
  lines.push('---');
  lines.push('');

  // Generate sections
  for (const category of Object.keys(byCategory).sort()) {
    lines.push(`## ${category}`);
    lines.push('');

    for (const hook of byCategory[category].sort((a, b) => a.name.localeCompare(b.name))) {
      lines.push(generateHookMarkdown(hook));
    }
  }

  return lines.join('\n');
}

/**
 * Generate summary statistics
 * @param {object[]} hooks - Array of hook documentation
 * @returns {object} Statistics
 */
function generateStats(hooks) {
  const stats = {
    total: hooks.length,
    byCategory: {},
    byEvent: {}
  };

  for (const hook of hooks) {
    // By category
    const cat = hook.category;
    stats.byCategory[cat] = (stats.byCategory[cat] || 0) + 1;

    // By event
    const event = hook.event;
    stats.byEvent[event] = (stats.byEvent[event] || 0) + 1;
  }

  return stats;
}

/**
 * Main function
 */
function main() {
  const args = process.argv.slice(2);
  const outputJson = args.includes('--json');
  const updateFile = args.includes('--update');

  // Find all hooks
  const hookFiles = findHookFiles(HOOKS_DIR);

  if (hookFiles.length === 0) {
    console.error('No hook files found in', HOOKS_DIR);
    process.exit(1);
  }

  // Generate documentation
  const hooks = hookFiles.map(generateHookDoc);
  const stats = generateStats(hooks);

  if (outputJson) {
    // Output as JSON
    console.log(JSON.stringify({ stats, hooks }, null, 2));
  } else {
    // Generate markdown
    const markdown = generateCatalogMarkdown(hooks);

    if (updateFile) {
      // Ensure docs directory exists
      if (!fs.existsSync(DOCS_DIR)) {
        fs.mkdirSync(DOCS_DIR, { recursive: true });
      }

      // Write to file
      const autoGenFile = path.join(DOCS_DIR, 'HOOKS-CATALOG-AUTO.md');
      fs.writeFileSync(autoGenFile, markdown);
      console.log(`Documentation written to ${autoGenFile}`);
      console.log(`Total hooks documented: ${stats.total}`);
    } else {
      // Output to stdout
      console.log(markdown);
    }
  }

  // Print summary
  if (!outputJson) {
    console.error('\n--- Summary ---');
    console.error(`Total hooks: ${stats.total}`);
    console.error('By category:', stats.byCategory);
    console.error('By event:', stats.byEvent);
  }
}

// Export for testing
module.exports = {
  findHookFiles,
  parseJSDoc,
  getCategory,
  generateHookDoc,
  generateHookMarkdown,
  generateCatalogMarkdown,
  generateStats,
  HOOKS_DIR,
  DOCS_DIR
};

// Run if executed directly
if (require.main === module) {
  main();
}
