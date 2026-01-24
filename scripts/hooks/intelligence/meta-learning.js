#!/usr/bin/env node
/**
 * Meta Learning - Stop Hook
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/intelligence/meta_learning.py
 *
 * Functionality:
 * - Extract patterns from session:
 *   - high_rework: >3 edits on same file
 *   - high_error: >25% error rate
 *   - quality_drop: declining quality trend
 * - Calculate confidence scores
 * - Store patterns via mcp-client for SONA learning
 *
 * Hook: Stop
 * Output: {} (no output, just stores patterns)
 */

const path = require('path');
const fs = require('fs');
const {
  readFile,
  ensureDir,
  readStdinJson,
  output
} = require('../../lib/utils');
const {
  memoryRetrieve,
  patternStore,
  getProjectName,
  getTimestamp
} = require('../../lib/mcp-client');
const { METRICS_DIR } = require('../../lib/metrics');

// Configuration
const SESSION_ANALYSIS_FILE = path.join(METRICS_DIR, 'session_analysis.json');
const FILE_EDIT_COUNTS_FILE = path.join(METRICS_DIR, 'file_edit_counts.json');

// Thresholds
const THRESHOLD_REWORK_EDITS = 3;
const THRESHOLD_ERROR_RATE = 0.25;
const THRESHOLD_QUALITY_DROP = 0.15;
const MIN_QUALITY_SAMPLES = 3;

/**
 * Load trajectory data from memory
 * @param {string} project - Project name
 * @returns {object[]} Trajectory index
 */
function loadTrajectoryData(project) {
  try {
    const data = memoryRetrieve(`trajectory:${project}:index`);
    return Array.isArray(data) ? data : [];
  } catch (err) {
    return [];
  }
}

/**
 * Load session analyzer output from file
 * @returns {object} Session analysis data
 */
function loadSessionAnalysis() {
  try {
    const content = readFile(SESSION_ANALYSIS_FILE);
    if (!content) return {};
    return JSON.parse(content);
  } catch (err) {
    return {};
  }
}

/**
 * Load file edit counts from session metrics
 * @returns {object} File edit counts { filepath: count }
 */
function loadFileEditCounts() {
  try {
    const content = readFile(FILE_EDIT_COUNTS_FILE);
    if (!content) return {};
    return JSON.parse(content);
  } catch (err) {
    return {};
  }
}

/**
 * Load quality scores from trajectory steps
 * @returns {number[]} Array of quality scores
 */
function loadQualityScores() {
  const project = getProjectName();
  const trajectoryIndex = loadTrajectoryData(project);

  if (!trajectoryIndex || trajectoryIndex.length === 0) {
    return [];
  }

  const scores = [];
  const recentTrajectories = trajectoryIndex.slice(-10);

  for (const traj of recentTrajectories) {
    if (typeof traj.success_rate === 'number') {
      scores.push(traj.success_rate);
    } else if (typeof traj.successRate === 'number') {
      scores.push(traj.successRate);
    } else if (typeof traj.success === 'boolean') {
      scores.push(traj.success ? 1.0 : 0.5);
    }
  }

  return scores;
}

/**
 * Calculate confidence score for a pattern based on signal strength
 * Base confidence is 0.5, with up to 0.5 additional based on severity
 * @param {string} patternType - Type of pattern
 * @param {object} data - Pattern-specific data
 * @returns {number} Confidence score (0-1)
 */
function calculateConfidence(patternType, data) {
  const base = 0.5;
  let bonus = 0.0;

  switch (patternType) {
    case 'high_rework': {
      const excess = (data.editCount || 0) - (data.threshold || THRESHOLD_REWORK_EDITS);
      bonus = Math.min(0.5, excess * 0.15);
      break;
    }
    case 'high_error': {
      const excess = (data.errorRate || 0) - THRESHOLD_ERROR_RATE;
      bonus = Math.min(0.5, excess * 1.5);
      break;
    }
    case 'quality_drop': {
      const excess = (data.totalDrop || 0) - (data.threshold || THRESHOLD_QUALITY_DROP);
      bonus = Math.min(0.5, excess * 2);
      break;
    }
    default:
      bonus = 0;
  }

  return Math.min(1.0, Math.max(0.0, base + bonus));
}

/**
 * Extract high rework pattern from file edit counts
 * @param {object} fileEditCounts - File edit counts
 * @returns {object|null} Pattern or null
 */
function extractReworkPattern(fileEditCounts) {
  if (!fileEditCounts || Object.keys(fileEditCounts).length === 0) {
    return null;
  }

  const highReworkFiles = Object.entries(fileEditCounts)
    .filter(([, count]) => count > THRESHOLD_REWORK_EDITS)
    .map(([filepath]) => filepath);

  if (highReworkFiles.length === 0) {
    return null;
  }

  const maxEdits = Math.max(...highReworkFiles.map(f => fileEditCounts[f]));

  return {
    type: 'high_rework',
    files: highReworkFiles,
    maxEdits,
    confidence: calculateConfidence('high_rework', {
      editCount: maxEdits,
      threshold: THRESHOLD_REWORK_EDITS
    })
  };
}

/**
 * Extract high error rate pattern from session analysis
 * @param {object} sessionAnalysis - Session analysis data
 * @returns {object|null} Pattern or null
 */
function extractErrorPattern(sessionAnalysis) {
  const session = sessionAnalysis.session || {};

  if (!session || Object.keys(session).length === 0) {
    return null;
  }

  let errorRate = session.error_rate || session.errorRate;

  if (errorRate === undefined) {
    const toolCalls = session.tool_calls || session.toolCalls || 0;
    if (toolCalls > 0) {
      errorRate = (session.errors || 0) / toolCalls;
    } else {
      return null;
    }
  }

  if (errorRate <= THRESHOLD_ERROR_RATE) {
    return null;
  }

  return {
    type: 'high_error',
    errorRate,
    totalErrors: session.errors || 0,
    confidence: calculateConfidence('high_error', { errorRate })
  };
}

/**
 * Extract quality drop pattern from quality score trend
 * @param {number[]} qualityScores - Array of quality scores
 * @returns {object|null} Pattern or null
 */
function extractQualityDropPattern(qualityScores) {
  if (!qualityScores || qualityScores.length < MIN_QUALITY_SAMPLES) {
    return null;
  }

  const n = qualityScores.length;
  const xMean = (n - 1) / 2;
  const yMean = qualityScores.reduce((a, b) => a + b, 0) / n;

  // Calculate slope using linear regression
  let numerator = 0;
  let denominator = 0;

  for (let i = 0; i < n; i++) {
    numerator += (i - xMean) * (qualityScores[i] - yMean);
    denominator += (i - xMean) ** 2;
  }

  if (denominator === 0) {
    return null;
  }

  const slope = numerator / denominator;
  const startQuality = qualityScores[0];
  const endQuality = qualityScores[n - 1];
  const totalChange = startQuality - endQuality;

  // Only flag if there's actual decline
  if (totalChange <= THRESHOLD_QUALITY_DROP || slope >= 0) {
    return null;
  }

  return {
    type: 'quality_drop',
    trend: 'declining',
    startQuality,
    endQuality,
    totalDrop: totalChange,
    slope,
    confidence: calculateConfidence('quality_drop', {
      totalDrop: totalChange,
      threshold: THRESHOLD_QUALITY_DROP
    })
  };
}

/**
 * Extract all patterns from session data
 * @param {object} sessionAnalysis - Session analysis data
 * @param {object} fileEditCounts - File edit counts
 * @param {number[]} qualityScores - Quality scores
 * @returns {object[]} Array of patterns
 */
function extractPatterns(sessionAnalysis, fileEditCounts, qualityScores) {
  const patterns = [];

  const reworkPattern = extractReworkPattern(fileEditCounts);
  if (reworkPattern) patterns.push(reworkPattern);

  const errorPattern = extractErrorPattern(sessionAnalysis);
  if (errorPattern) patterns.push(errorPattern);

  const qualityPattern = extractQualityDropPattern(qualityScores);
  if (qualityPattern) patterns.push(qualityPattern);

  return patterns;
}

/**
 * Store extracted patterns via mcp_client
 * @param {object[]} patterns - Patterns to store
 */
function storePatterns(patterns) {
  const project = getProjectName();
  const timestamp = getTimestamp();

  for (const pattern of patterns) {
    const patternType = pattern.type || 'unknown';
    const confidence = pattern.confidence || 0.5;

    // Build metadata (exclude type and confidence)
    const metadata = {
      project,
      timestamp,
      ...Object.fromEntries(
        Object.entries(pattern).filter(([k]) => !['type', 'confidence'].includes(k))
      )
    };

    try {
      patternStore(patternType, patternType, confidence, metadata);
    } catch (err) {
      // Ignore errors, continue with other patterns
    }
  }
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    // Read stdin (required by hook protocol, but not used by this hook)
    await readStdinJson().catch(() => {});

    const project = getProjectName();
    const trajectoryIndex = loadTrajectoryData(project);
    const sessionAnalysis = loadSessionAnalysis();
    const fileEditCounts = loadFileEditCounts();
    const qualityScores = loadQualityScores();

    const patterns = extractPatterns(
      sessionAnalysis,
      fileEditCounts,
      qualityScores
    );

    if (patterns.length > 0) {
      storePatterns(patterns);
    }

    // This hook doesn't output anything
    output({});
    process.exit(0);
  } catch (err) {
    // Graceful failure
    output({});
    process.exit(0);
  }
}

// Export for testing
module.exports = {
  loadTrajectoryData,
  loadSessionAnalysis,
  loadFileEditCounts,
  loadQualityScores,
  calculateConfidence,
  extractReworkPattern,
  extractErrorPattern,
  extractQualityDropPattern,
  extractPatterns,
  storePatterns,
  THRESHOLD_REWORK_EDITS,
  THRESHOLD_ERROR_RATE,
  THRESHOLD_QUALITY_DROP,
  MIN_QUALITY_SAMPLES
};

// Run if executed directly
if (require.main === module) {
  main();
}
