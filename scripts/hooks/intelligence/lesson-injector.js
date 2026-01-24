#!/usr/bin/env node
/**
 * Lesson Injector - UserPromptSubmit Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/intelligence/lesson_injector.py
 *
 * Functionality:
 * - Load learned lessons from pattern storage
 * - Match lessons to current context (file types, commands)
 * - Inject relevant lessons into context
 * - Maximum 3 lessons per injection to avoid context bloat
 *
 * Confidence thresholds:
 * - HIGH (>0.8): Auto-inject with "[Lessons]" prefix
 * - MEDIUM (0.5-0.8): Suggest with "Consider:" prefix
 * - LOW (<0.5): Skip
 *
 * Hook: UserPromptSubmit
 * Output: { additionalContext: string }
 */

const path = require('path');
const fs = require('fs');
const {
  readFile,
  ensureDir,
  getClaudeDir,
  readStdinJson,
  output
} = require('../../lib/utils');
const {
  patternSearch,
  getProjectName
} = require('../../lib/mcp-client');

// Configuration
const LESSONS_DIR = path.join(getClaudeDir(), 'lessons');

// Confidence thresholds
const CONFIDENCE_HIGH = 0.8;
const CONFIDENCE_MEDIUM = 0.5;
const MAX_LESSONS = 3;

/**
 * Extract context from hook input
 * @param {object} hookInput - Hook input data
 * @returns {object} { prompt, project }
 */
function extractContext(hookInput) {
  const prompt = hookInput.prompt || '';
  const cwd = hookInput.cwd || '';

  // Get project name
  let project = getProjectName();
  if (!project && cwd) {
    project = path.basename(cwd);
  }

  return { prompt, project };
}

/**
 * Load lessons from local filesystem
 * @returns {object[]} Array of lessons
 */
function loadLocalLessons() {
  try {
    ensureDir(LESSONS_DIR);

    const lessons = [];
    const files = fs.readdirSync(LESSONS_DIR);

    for (const file of files) {
      if (!file.endsWith('.json')) continue;

      const filePath = path.join(LESSONS_DIR, file);
      const content = readFile(filePath);

      if (!content) continue;

      try {
        const lesson = JSON.parse(content);
        if (lesson.pattern && lesson.confidence !== undefined) {
          lessons.push(lesson);
        }
      } catch (err) {
        // Skip invalid files
      }
    }

    return lessons;
  } catch (err) {
    return [];
  }
}

/**
 * Format a pattern as a lesson string based on confidence
 * @param {object} pattern - Pattern object
 * @returns {string|null} Formatted lesson or null if should be skipped
 */
function formatLesson(pattern) {
  const confidence = pattern.confidence || 0;
  const lessonText = pattern.pattern || '';

  if (!lessonText) {
    return null;
  }

  if (confidence < CONFIDENCE_MEDIUM) {
    // LOW: Skip
    return null;
  } else if (confidence < CONFIDENCE_HIGH) {
    // MEDIUM: Suggest with "Consider:" prefix
    return `- Consider: ${lessonText}`;
  } else {
    // HIGH: Auto-inject
    return `- ${lessonText}`;
  }
}

/**
 * Match lessons to context based on prompt content
 * @param {object[]} lessons - Array of lessons
 * @param {string} prompt - User prompt
 * @returns {object[]} Matched and sorted lessons
 */
function matchLessonsToContext(lessons, prompt) {
  if (!lessons || lessons.length === 0) {
    return [];
  }

  const promptLower = prompt.toLowerCase();
  const matched = [];

  for (const lesson of lessons) {
    let relevanceScore = lesson.confidence || 0.5;

    // Boost relevance if lesson keywords match prompt
    const pattern = (lesson.pattern || '').toLowerCase();
    const metadata = lesson.metadata || {};

    // Check for keyword matches in pattern
    const words = pattern.split(/\s+/).filter(w => w.length > 3);
    for (const word of words) {
      if (promptLower.includes(word)) {
        relevanceScore *= 1.1;
      }
    }

    // Check for file type matches
    if (metadata.files) {
      const files = Array.isArray(metadata.files) ? metadata.files : [metadata.files];
      for (const file of files) {
        const ext = path.extname(file);
        if (promptLower.includes(ext)) {
          relevanceScore *= 1.15;
        }
      }
    }

    // Check for type-specific boosts
    const type = lesson.type || '';
    if (type === 'high_error' && promptLower.includes('error')) {
      relevanceScore *= 1.2;
    }
    if (type === 'high_rework' && (promptLower.includes('edit') || promptLower.includes('fix'))) {
      relevanceScore *= 1.2;
    }

    matched.push({
      ...lesson,
      relevanceScore: Math.min(1.0, relevanceScore)
    });
  }

  // Sort by relevance score descending
  matched.sort((a, b) => b.relevanceScore - a.relevanceScore);

  return matched;
}

/**
 * Process the hook input and return additionalContext
 * @param {object} hookInput - Hook input data
 * @returns {object} { additionalContext } or {}
 */
function processHook(hookInput) {
  try {
    const { prompt, project } = extractContext(hookInput);

    if (!prompt) {
      return {};
    }

    // Build search query from prompt context
    const searchQuery = prompt.length > 100 ? prompt.substring(0, 100) : prompt;

    // Search for relevant patterns from pattern storage
    let patterns = patternSearch(
      searchQuery,
      '', // no type filter
      CONFIDENCE_MEDIUM, // minimum confidence
      5 // get a few more to filter
    );

    // Also load local lessons
    const localLessons = loadLocalLessons();

    // Combine and deduplicate
    const allLessons = [...patterns, ...localLessons];
    const seen = new Set();
    const uniqueLessons = [];

    for (const lesson of allLessons) {
      const key = lesson.pattern || lesson.id || JSON.stringify(lesson);
      if (!seen.has(key)) {
        seen.add(key);
        uniqueLessons.push(lesson);
      }
    }

    if (uniqueLessons.length === 0) {
      return {};
    }

    // Match lessons to context
    const matchedLessons = matchLessonsToContext(uniqueLessons, prompt);

    // Format lessons
    const formattedLessons = [];
    for (const lesson of matchedLessons) {
      // Skip raw output format
      if (lesson.raw) continue;

      const formatted = formatLesson(lesson);
      if (formatted) {
        formattedLessons.push(formatted);
      }
    }

    if (formattedLessons.length === 0) {
      return {};
    }

    // Limit to MAX_LESSONS
    const limitedLessons = formattedLessons.slice(0, MAX_LESSONS);

    // Build output
    const contextLines = ['[Lessons from past sessions]', ...limitedLessons];
    const additionalContext = contextLines.join('\n');

    return { additionalContext };
  } catch (err) {
    return {};
  }
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    const inputData = await readStdinJson();
    const result = processHook(inputData);
    output(result);
    process.exit(0);
  } catch (err) {
    // Graceful failure
    output({});
    process.exit(0);
  }
}

// Export for testing
module.exports = {
  extractContext,
  loadLocalLessons,
  formatLesson,
  matchLessonsToContext,
  processHook,
  CONFIDENCE_HIGH,
  CONFIDENCE_MEDIUM,
  MAX_LESSONS,
  LESSONS_DIR
};

// Run if executed directly
if (require.main === module) {
  main();
}
