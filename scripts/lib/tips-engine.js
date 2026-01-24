/**
 * Tips Engine for Claude Code Hooks
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/scripts/tips_engine.py
 *
 * Generates optimization tips based on:
 * - DORA metrics and thresholds
 * - Statistical anomaly detection (z-score)
 * - Session metrics analysis
 * - Pattern matching rules
 *
 * Storage: ~/.claude/tips/
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HOME_DIR = os.homedir();
const TIPS_DIR = path.join(HOME_DIR, '.claude', 'tips');
const NEXT_SESSION_TIPS_FILE = path.join(TIPS_DIR, 'next_session.json');
const TIP_HISTORY_FILE = path.join(TIPS_DIR, 'history.jsonl');

// Categories
const CATEGORIES = ['errors', 'config', 'uncommitted', 'long', 'rework', 'quality', 'planning', 'safety'];

// Industry defaults (DORA benchmarks)
const INDUSTRY_DEFAULTS = {
  avgErrorRate: 0.10,
  stddevErrorRate: 0.05,
  avgReworkRate: 0.15,
  stddevReworkRate: 0.08,
  avgTestPassRate: 0.85,
  eliteErrorThreshold: 0.15,
  dangerReworkThreshold: 0.30
};

// Command registry with success baselines
const COMMAND_REGISTRY = {
  safety: [
    { name: '/undo:checkpoint', risk: 'low', cost: 'low', baseline: 0.90 },
    { name: '/undo:rollback', risk: 'medium', cost: 'low', baseline: 0.85 }
  ],
  quality: [
    { name: '/tdd:cycle', risk: 'low', cost: 'medium', baseline: 0.70 },
    { name: '/tdd:red', risk: 'low', cost: 'low', baseline: 0.80 },
    { name: '/tdd:spec-to-test', risk: 'low', cost: 'low', baseline: 0.75 }
  ],
  planning: [
    { name: '/speckit.specify', risk: 'low', cost: 'medium', baseline: 0.70 },
    { name: '/speckit.plan', risk: 'low', cost: 'medium', baseline: 0.65 },
    { name: '/speckit.clarify', risk: 'low', cost: 'low', baseline: 0.80 },
    { name: '/speckit.tasks', risk: 'low', cost: 'low', baseline: 0.70 }
  ],
  diagnosis: [
    { name: '/health', risk: 'none', cost: 'low', baseline: 0.95 },
    { name: '/audit', risk: 'none', cost: 'medium', baseline: 0.90 }
  ],
  simplification: [
    { name: '/code-simplifier', risk: 'low', cost: 'high', baseline: 0.85 }
  ]
};

const RISK_SCORES = { none: 1.0, low: 0.9, medium: 0.6, high: 0.3 };
const COST_SCORES = { low: 1.0, medium: 0.7, high: 0.5 };

/**
 * Ensure tips directory exists
 */
function ensureTipsDir() {
  try {
    if (!fs.existsSync(TIPS_DIR)) {
      fs.mkdirSync(TIPS_DIR, { recursive: true });
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load tips from a specific category file
 * @param {string} category - Tip category
 * @returns {object[]} Array of tips
 */
function loadTips(category) {
  try {
    const filePath = path.join(TIPS_DIR, `${category}.json`);
    if (!fs.existsSync(filePath)) {
      return [];
    }
    const content = fs.readFileSync(filePath, 'utf8');
    const data = JSON.parse(content);
    return data.tips || [];
  } catch (err) {
    return [];
  }
}

/**
 * Save tips to a category file
 * @param {string} category - Tip category
 * @param {object[]} tips - Array of tips
 * @returns {boolean} Success status
 */
function saveTips(category, tips) {
  ensureTipsDir();
  try {
    const filePath = path.join(TIPS_DIR, `${category}.json`);
    const data = {
      category,
      tips,
      savedAt: new Date().toISOString()
    };
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Calculate error rate from session data
 * @param {object} session - Session metrics
 * @returns {number} Error rate (0-1)
 */
function getErrorRate(session) {
  const toolCalls = session.toolCalls || 0;
  const errors = session.errors || 0;
  return toolCalls > 0 ? errors / toolCalls : 0;
}

/**
 * Calculate rework rate from session data
 * @param {object} session - Session metrics
 * @returns {number} Rework rate (0-1)
 */
function getReworkRate(session) {
  const fileEdits = session.fileEdits || 0;
  const reworks = session.reworks || 0;
  return fileEdits > 0 ? reworks / fileEdits : 0;
}

/**
 * Calculate test pass rate from session data
 * @param {object} session - Session metrics
 * @returns {number} Test pass rate (0-1)
 */
function getTestPassRate(session) {
  const testRuns = session.testRuns || 0;
  const testsPassed = session.testsPassed || 0;
  return testRuns > 0 ? testsPassed / testRuns : 0;
}

/**
 * Calculate z-score for a value
 * @param {number} value - Current value
 * @param {number} mean - Mean value
 * @param {number} stddev - Standard deviation
 * @returns {number} Z-score
 */
function zScore(value, mean, stddev) {
  if (stddev === 0) return 0;
  return (value - mean) / stddev;
}

/**
 * Select best command for a category based on historical success
 * @param {string} category - Command category
 * @param {object} historical - Historical stats with command success rates
 * @param {string[]} [failedCommands=[]] - Recently failed commands
 * @returns {object} { command, score, rationale }
 */
function selectBestCommand(category, historical = {}, failedCommands = []) {
  const commands = COMMAND_REGISTRY[category];
  if (!commands || commands.length === 0) {
    return { command: '', score: 0, rationale: 'No commands for category' };
  }

  const successRates = historical.commandSuccessRates || {};
  const candidates = [];

  for (const cmd of commands) {
    let successRate = successRates[cmd.name];
    const isBaseline = successRate === undefined;
    if (isBaseline) {
      successRate = cmd.baseline;
    }

    // Calculate composite score
    let score = successRate * 0.6 + RISK_SCORES[cmd.risk] * 0.25 + COST_SCORES[cmd.cost] * 0.15;

    // Penalty for recently failed commands
    if (failedCommands.includes(cmd.name)) {
      score *= 0.5;
    }

    candidates.push({
      command: cmd.name,
      score,
      successRate,
      isBaseline
    });
  }

  // Sort by score descending
  candidates.sort((a, b) => b.score - a.score);
  const best = candidates[0];

  const rationale = best.isBaseline
    ? `Baseline success: ${(best.successRate * 100).toFixed(0)}%`
    : `Historical success: ${(best.successRate * 100).toFixed(0)}%`;

  return { command: best.command, score: best.score, rationale };
}

/**
 * Calculate tip confidence based on various factors
 * @param {string} ruleName - Rule that triggered the tip
 * @param {object} session - Current session metrics
 * @param {object} historical - Historical statistics
 * @param {number} [providedZScore] - Pre-calculated z-score
 * @returns {number} Confidence (0-1)
 */
function calculateConfidence(ruleName, session, historical = {}, providedZScore = null) {
  const defaults = INDUSTRY_DEFAULTS;

  // 1. Z-score factor (how anomalous is current value?)
  let zs = providedZScore;
  if (zs === null) {
    const errorRate = getErrorRate(session);
    const reworkRate = getReworkRate(session);

    if (ruleName.includes('error')) {
      const stddev = historical.stddevErrorRate || defaults.stddevErrorRate;
      const mean = historical.avgErrorRate || defaults.avgErrorRate;
      zs = zScore(errorRate, mean, stddev);
    } else if (ruleName.includes('rework')) {
      const stddev = historical.stddevReworkRate || defaults.stddevReworkRate;
      const mean = historical.avgReworkRate || defaults.avgReworkRate;
      zs = zScore(reworkRate, mean, stddev);
    } else {
      zs = 2.0; // Default for non-statistical rules
    }
  }

  // z-score to probability (z=2 -> ~95%, z=3 -> ~99.7%)
  const statisticalConfidence = Math.min(0.99, 0.5 + Math.abs(zs) * 0.15);

  // 2. Sample size factor
  const sessionCount = historical.sessionCount || 0;
  const sampleFactor = Math.min(1.0, sessionCount / 20);

  // 3. Rule accuracy factor
  const ruleAccuracies = historical.ruleAccuracies || {};
  const ruleAccuracy = ruleAccuracies[ruleName] || 0.7;

  // 4. Confidence penalty for less reliable data
  const confidencePenalty = historical.confidencePenalty || 0;

  // Weighted combination
  let confidence =
    statisticalConfidence * 0.35 +
    sampleFactor * 0.15 +
    ruleAccuracy * 0.30 +
    0.7 * 0.20; // Default context match

  // Apply penalty
  confidence *= 1 - confidencePenalty;

  return Math.min(0.95, Math.max(0.10, confidence));
}

// Pattern rules for tip generation
const PATTERN_RULES = [
  {
    name: 'high_error_rate',
    category: 'safety',
    evidence: 'DORA Change Failure Rate threshold + statistical anomaly',
    condition: (session, hist) => {
      const errorRate = getErrorRate(session);
      const toolCalls = session.toolCalls || 0;
      const stddev = hist.stddevErrorRate || INDUSTRY_DEFAULTS.stddevErrorRate;
      const mean = hist.avgErrorRate || INDUSTRY_DEFAULTS.avgErrorRate;
      return (
        errorRate > INDUSTRY_DEFAULTS.eliteErrorThreshold &&
        toolCalls >= 10 &&
        (stddev === 0 || errorRate > mean + 2 * stddev)
      );
    },
    messageBuilder: (session, hist) => {
      const errorRate = getErrorRate(session);
      const stddev = hist.stddevErrorRate || INDUSTRY_DEFAULTS.stddevErrorRate;
      const mean = hist.avgErrorRate || INDUSTRY_DEFAULTS.avgErrorRate;
      if (stddev > 0) {
        const z = zScore(errorRate, mean, stddev);
        return `Error rate ${(errorRate * 100).toFixed(0)}% (z=${z.toFixed(1)}, elite <15%)`;
      }
      return `Error rate ${(errorRate * 100).toFixed(0)}% (elite <15%)`;
    },
    fallbackCommand: '/undo:checkpoint'
  },
  {
    name: 'stuck_in_loop',
    category: 'planning',
    evidence: 'Pattern analysis: >5 iterations = same approach failing',
    condition: (session) => (session.maxTaskIterations || 0) > 5,
    messageBuilder: (session) => `Stuck in loop: ${session.maxTaskIterations} iterations on same task`,
    fallbackCommand: '/speckit.plan'
  },
  {
    name: 'high_rework',
    category: 'quality',
    evidence: 'Microsoft Research: Code churn predicts defects with 89% accuracy',
    condition: (session) => {
      const reworkRate = getReworkRate(session);
      const fileEdits = session.fileEdits || 0;
      return reworkRate > INDUSTRY_DEFAULTS.dangerReworkThreshold && fileEdits >= 5;
    },
    messageBuilder: (session) => {
      const reworkRate = getReworkRate(session);
      return `High rework rate: ${(reworkRate * 100).toFixed(0)}% of edits are reworks`;
    },
    fallbackCommand: '/tdd:cycle'
  },
  {
    name: 'no_tests',
    category: 'quality',
    evidence: 'Test coverage correlates with 75-77% precision in defect prediction',
    condition: (session) => {
      const fileEdits = session.fileEdits || 0;
      const testRuns = session.testRuns || 0;
      return fileEdits > 5 && testRuns === 0;
    },
    messageBuilder: (session) => `${session.fileEdits} file edits without running tests`,
    fallbackCommand: '/tdd:red'
  },
  {
    name: 'large_change_size',
    category: 'quality',
    evidence: 'Cisco study: 40% fewer defects when changes <200 lines',
    condition: (session) => (session.linesChanged || 0) > 400,
    messageBuilder: (session) => `Large change: ${session.linesChanged} lines modified`,
    fallbackCommand: '/speckit.clarify'
  },
  {
    name: 'too_many_files',
    category: 'planning',
    evidence: 'PR size studies: fewer files = easier review, fewer bugs',
    condition: (session) => (session.filesModified || 0) > 10,
    messageBuilder: (session) => `Many files touched: ${session.filesModified} files modified`,
    fallbackCommand: '/speckit.tasks'
  },
  {
    name: 'high_churn_single_file',
    category: 'safety',
    evidence: 'Microsoft Research: file churn predicts defects',
    condition: (session) => {
      const maxEdits = session.maxFileEdits || 0;
      const maxReworks = session.maxFileReworks || 0;
      return maxEdits > 5 && maxReworks > 2;
    },
    messageBuilder: (session) => `File ${session.mostChurnedFile || 'unknown'} edited ${session.maxFileEdits}x`,
    fallbackCommand: '/undo:checkpoint'
  },
  {
    name: 'low_test_pass_rate',
    category: 'quality',
    evidence: 'Focus on one test at a time for better debugging',
    condition: (session) => {
      const testRuns = session.testRuns || 0;
      const passRate = getTestPassRate(session);
      return testRuns >= 3 && passRate < 0.60;
    },
    messageBuilder: (session) => {
      const passRate = getTestPassRate(session);
      return `Low test pass rate: ${(passRate * 100).toFixed(0)}%`;
    },
    fallbackCommand: '/tdd:red'
  },
  {
    name: 'long_session',
    category: 'diagnosis',
    evidence: 'Long sessions often indicate scope creep or complexity',
    condition: (session) => (session.durationSeconds || 0) > 3600,
    messageBuilder: (session) => {
      const mins = Math.floor((session.durationSeconds || 0) / 60);
      return `Long session: ${mins} minutes`;
    },
    fallbackCommand: '/health'
  }
];

/**
 * Generate tips from session data
 * @param {object} sessionData - Current session metrics
 * @param {object} [historical={}] - Historical statistics
 * @returns {object[]} Array of tip objects
 */
function generateTips(sessionData, historical = {}) {
  const tips = [];
  const failedCommands = sessionData.recentlyFailedCommands || [];

  for (const rule of PATTERN_RULES) {
    try {
      if (rule.condition(sessionData, historical)) {
        // Select best command for this category
        const { command, score, rationale } = selectBestCommand(
          rule.category,
          historical,
          failedCommands
        );

        // Calculate confidence
        const confidence = calculateConfidence(rule.name, sessionData, historical);

        tips.push({
          ruleName: rule.name,
          message: rule.messageBuilder(sessionData, historical),
          command: command || rule.fallbackCommand,
          confidence,
          evidence: rule.evidence,
          category: rule.category,
          rationale
        });
      }
    } catch (err) {
      // Skip rules that error
    }
  }

  // Sort by confidence descending
  tips.sort((a, b) => b.confidence - a.confidence);

  // Deduplicate by command (keep highest confidence)
  const seenCommands = new Set();
  const deduped = [];
  for (const tip of tips) {
    if (!seenCommands.has(tip.command)) {
      seenCommands.add(tip.command);
      deduped.push(tip);
    }
  }

  // Limit to 5 tips
  return deduped.slice(0, 5);
}

/**
 * Score a single tip based on context
 * @param {object} tip - Tip object
 * @param {object} context - Current context (session data)
 * @returns {number} Relevance score (0-1)
 */
function scoreTip(tip, context) {
  let score = tip.confidence || 0.5;

  // Boost for matching patterns
  if (tip.category === 'errors' && getErrorRate(context) > 0.15) {
    score *= 1.2;
  }
  if (tip.category === 'rework' && getReworkRate(context) > 0.25) {
    score *= 1.2;
  }

  // Penalty for failed commands
  const failed = context.recentlyFailedCommands || [];
  if (failed.includes(tip.command)) {
    score *= 0.5;
  }

  return Math.min(1.0, Math.max(0, score));
}

/**
 * Format tips for terminal display
 * @param {object[]} tips - Array of tips
 * @param {number} [maxCount=5] - Maximum tips to display
 * @param {boolean} [coldStart=false] - Whether this is cold start mode
 * @returns {string} Formatted output
 */
function formatTips(tips, maxCount = 5, coldStart = false) {
  if (!tips || tips.length === 0) {
    return '';
  }

  const displayTips = tips.slice(0, maxCount);
  const lines = [];

  lines.push('');
  lines.push('='.repeat(66));
  if (coldStart) {
    lines.push('  DYNAMIC OPTIMIZATION TIPS (Cold Start Mode)');
  } else {
    lines.push(`  DYNAMIC OPTIMIZATION TIPS (${displayTips.length} triggered)`);
  }
  lines.push('='.repeat(66));
  lines.push('');

  for (let i = 0; i < displayTips.length; i++) {
    const tip = displayTips[i];
    const confPct = Math.round((tip.confidence || 0) * 100);

    lines.push(`  ${i + 1}. [Conf: ${confPct}%] ${tip.message}`);
    lines.push(`     -> ${tip.command}`);
    lines.push(`     Evidence: ${tip.evidence}`);
    if (tip.rationale) {
      lines.push(`     (${tip.rationale})`);
    }
    lines.push('');
  }

  lines.push('-'.repeat(66));
  lines.push(`  ${displayTips.length} rules triggered`);
  if (coldStart) {
    lines.push('  Note: Building your project baseline. After 5+ sessions,');
    lines.push('  tips will be personalized to YOUR patterns.');
  }
  lines.push('');
  lines.push('  -> Next session: /tips to inject these recommendations');
  lines.push('='.repeat(66));
  lines.push('');

  return lines.join('\n');
}

/**
 * Save tips for next session injection
 * @param {object[]} tips - Tips to save
 * @param {string} [sessionId=''] - Current session ID
 * @param {string} [project=''] - Project name
 * @returns {boolean} Success status
 */
function saveTipsForNextSession(tips, sessionId = '', project = '') {
  ensureTipsDir();
  try {
    const data = {
      tips,
      sessionId,
      project,
      generatedAt: new Date().toISOString()
    };
    fs.writeFileSync(NEXT_SESSION_TIPS_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load tips saved for this session
 * @returns {object|null} Saved tips data or null
 */
function loadNextSessionTips() {
  try {
    if (!fs.existsSync(NEXT_SESSION_TIPS_FILE)) {
      return null;
    }
    const content = fs.readFileSync(NEXT_SESSION_TIPS_FILE, 'utf8');
    return JSON.parse(content);
  } catch (err) {
    return null;
  }
}

/**
 * Clear next session tips after injection
 * @returns {boolean} Success status
 */
function clearNextSessionTips() {
  try {
    if (fs.existsSync(NEXT_SESSION_TIPS_FILE)) {
      fs.unlinkSync(NEXT_SESSION_TIPS_FILE);
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Record tip to history
 * @param {object} tip - Tip object
 * @param {string} outcome - 'helpful', 'not_helpful', 'ignored'
 * @returns {boolean} Success status
 */
function recordTipHistory(tip, outcome) {
  ensureTipsDir();
  try {
    const entry = {
      ...tip,
      outcome,
      recordedAt: new Date().toISOString()
    };
    fs.appendFileSync(TIP_HISTORY_FILE, JSON.stringify(entry) + '\n');
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Convert tips to JSON-serializable format
 * @param {object[]} tips - Array of tips
 * @param {string} sessionId - Session ID
 * @param {string} project - Project name
 * @param {object} historical - Historical stats
 * @returns {object} Serializable object
 */
function tipsToDict(tips, sessionId, project, historical = {}) {
  return {
    sessionId,
    project,
    analysis: {
      sessionsAnalyzed: historical.sessionCount || 0,
      dataSource: historical.dataSource || 'defaults',
      statisticalMethod: 'z-score anomaly detection'
    },
    tips: tips.map(tip => ({
      confidence: tip.confidence,
      message: tip.message,
      command: tip.command,
      evidence: tip.evidence,
      category: tip.category,
      rationale: tip.rationale,
      ruleName: tip.ruleName
    }))
  };
}

module.exports = {
  // Core functions
  loadTips,
  saveTips,
  generateTips,
  scoreTip,
  formatTips,

  // Session tip persistence
  saveTipsForNextSession,
  loadNextSessionTips,
  clearNextSessionTips,

  // History
  recordTipHistory,

  // Utilities
  tipsToDict,
  selectBestCommand,
  calculateConfidence,
  getErrorRate,
  getReworkRate,
  getTestPassRate,
  zScore,

  // Constants
  TIPS_DIR,
  CATEGORIES,
  INDUSTRY_DEFAULTS,
  COMMAND_REGISTRY,
  PATTERN_RULES
};
