#!/usr/bin/env node
/**
 * Plan Validator Hook for Claude Code
 *
 * Validates GSD plan structure and PMW (Plan Mode Warnings):
 * 1. Validates frontmatter (phase, plan, type, wave)
 * 2. Validates task structure
 * 3. Checks for complexity issues (PMW)
 * 4. Reports issues without blocking
 *
 * Hook Type: PostToolUse
 * Matcher: Write (when file = *-PLAN.md or /plans/*.md)
 * Timeout: 5s
 *
 * Ported from: claude-hooks-shared/hooks/quality/plan_validator.py
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output, getClaudeDir } = require('../../lib/utils');

// Required frontmatter fields for GSD plans
const REQUIRED_FRONTMATTER = ['phase', 'plan', 'type'];

// Optional but recommended fields
const RECOMMENDED_FRONTMATTER = ['wave', 'depends_on', 'files_modified'];

// Task structure requirements
const TASK_REQUIREMENTS = {
  name: /name/i,
  files: /files/i,
  action: /action/i
};

/**
 * Parse YAML-like frontmatter from markdown content
 */
function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) {
    return null;
  }

  const frontmatter = {};
  const lines = match[1].split('\n');

  for (const line of lines) {
    const colonIndex = line.indexOf(':');
    if (colonIndex > 0) {
      const key = line.substring(0, colonIndex).trim();
      const value = line.substring(colonIndex + 1).trim();
      frontmatter[key] = value;
    }
  }

  return frontmatter;
}

/**
 * Extract tasks from plan content
 */
function extractTasks(content) {
  const tasks = [];
  // Match <task> blocks
  const taskMatches = content.matchAll(/<task[^>]*>([\s\S]*?)<\/task>/g);

  for (const match of taskMatches) {
    const taskContent = match[1];
    const task = {
      content: taskContent,
      hasName: /<name>/i.test(taskContent),
      hasFiles: /<files>/i.test(taskContent),
      hasAction: /<action>/i.test(taskContent),
      hasVerify: /<verify>/i.test(taskContent),
      hasDone: /<done>/i.test(taskContent)
    };
    tasks.push(task);
  }

  return tasks;
}

/**
 * Validate plan structure and return issues
 */
function validatePlan(content) {
  const issues = [];

  // Check for frontmatter
  const frontmatter = parseFrontmatter(content);
  if (!frontmatter) {
    issues.push('STRUCTURE: Missing YAML frontmatter (---...---)');
  } else {
    // Check required fields
    for (const field of REQUIRED_FRONTMATTER) {
      if (!frontmatter[field]) {
        issues.push(`FRONTMATTER: Missing required field '${field}'`);
      }
    }

    // Check recommended fields (warning only)
    for (const field of RECOMMENDED_FRONTMATTER) {
      if (!frontmatter[field]) {
        issues.push(`INFO: Consider adding '${field}' field`);
      }
    }

    // Validate type value
    if (frontmatter.type && !['execute', 'research', 'design', 'review'].includes(frontmatter.type)) {
      issues.push(`FRONTMATTER: Invalid type '${frontmatter.type}' - expected: execute, research, design, or review`);
    }
  }

  // Check for objective
  if (!/<objective>/i.test(content)) {
    issues.push('STRUCTURE: Missing <objective> section');
  }

  // Check for tasks
  if (!/<tasks>/i.test(content)) {
    issues.push('STRUCTURE: Missing <tasks> section');
  }

  // Extract and validate tasks
  const tasks = extractTasks(content);
  if (tasks.length === 0) {
    issues.push('TASKS: No <task> blocks found');
  } else {
    // Validate each task
    tasks.forEach((task, index) => {
      if (!task.hasName) {
        issues.push(`TASK ${index + 1}: Missing <name> element`);
      }
      if (!task.hasAction) {
        issues.push(`TASK ${index + 1}: Missing <action> element`);
      }
    });
  }

  // Check for verification section
  if (!/<verification>/i.test(content)) {
    issues.push('STRUCTURE: Missing <verification> section');
  }

  // PMW Checks (Plan Mode Warnings)

  // PMW 1: Too many classes/complexity in code blocks
  const classCount = (content.match(/^class \w+/gm) || []).length;
  if (classCount > 3) {
    issues.push(`COMPLEXITY: ${classCount} classes in code blocks - consider simplifying`);
  }

  // PMW 2: Subprocess calls without cache mention
  if (/subprocess\.run|execSync|spawnSync/.test(content) && !/cache/i.test(content)) {
    issues.push('PERF: Subprocess calls without caching strategy');
  }

  // PMW 3: Assumes data files that might not exist
  const assumedFiles = content.match(/Path.*?\/\s*["']([^"']+\.json)["']/g) || [];
  if (assumedFiles.length > 0) {
    issues.push(`DATA: Plan assumes ${assumedFiles.length} JSON file(s) exist - verify availability`);
  }

  // PMW 4: Lines of code estimate
  const codeBlocks = content.match(/```(?:python|javascript|typescript|js|ts)\n([\s\S]*?)```/g) || [];
  let totalLines = 0;
  for (const block of codeBlocks) {
    totalLines += block.split('\n').length;
  }
  if (totalLines > 200) {
    issues.push(`SIZE: ~${totalLines} lines of code in plan - KISS violation risk`);
  }

  // PMW 5: Too many files modified
  const filesModifiedMatch = content.match(/files_modified:\s*\n((?:\s+-[^\n]+\n?)+)/);
  if (filesModifiedMatch) {
    const fileCount = (filesModifiedMatch[1].match(/-/g) || []).length;
    if (fileCount > 10) {
      issues.push(`SCOPE: ${fileCount} files to modify - consider splitting plan`);
    }
  }

  // PMW 6: Missing context references
  if (!/<context>/i.test(content)) {
    issues.push('INFO: Consider adding <context> section with @file references');
  }

  return issues;
}

/**
 * Check if file path is a plan file
 */
function isPlanFile(filePath) {
  if (!filePath) return false;
  const normalized = filePath.toLowerCase();
  return normalized.endsWith('-plan.md') ||
         normalized.includes('/plans/') ||
         normalized.includes('.planning/');
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    const inputData = await readStdinJson();

    // Check if this is a Write tool use
    const toolName = inputData.tool_name || '';
    if (toolName !== 'Write') {
      process.exit(0);
    }

    // Get file path and content
    const toolInput = inputData.tool_input || {};
    const filePath = toolInput.file_path || '';
    const content = toolInput.content || '';

    // Only validate plan files
    if (!isPlanFile(filePath)) {
      process.exit(0);
    }

    // Validate the plan
    const issues = validatePlan(content);

    if (issues.length > 0) {
      // Categorize issues
      const errors = issues.filter(i => !i.startsWith('INFO:'));
      const infos = issues.filter(i => i.startsWith('INFO:'));

      let message = `Plan validation for ${path.basename(filePath)}:\n`;

      if (errors.length > 0) {
        message += '\nIssues found:\n';
        for (const issue of errors) {
          message += `  - ${issue}\n`;
        }
      }

      if (infos.length > 0) {
        message += '\nSuggestions:\n';
        for (const info of infos) {
          message += `  - ${info.replace('INFO: ', '')}\n`;
        }
      }

      output({
        systemMessage: message
      });
    }

    // Always allow the write to continue
    process.exit(0);

  } catch (err) {
    // Fail silently - don't block the user
    process.exit(0);
  }
}

main();
