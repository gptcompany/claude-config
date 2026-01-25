#!/usr/bin/env node
/**
 * UI Components for Claude Code Status Line
 * Powerline-style visual elements inspired by ccstatusline
 *
 * Features:
 * - ANSI color support (16/256/truecolor)
 * - Powerline separators and caps
 * - Progress bars with proper Unicode
 * - Token/cost formatting
 */

// ANSI color codes
const COLORS = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  // Foreground
  black: "\x1b[30m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  white: "\x1b[37m",
  gray: "\x1b[90m",
  brightRed: "\x1b[91m",
  brightGreen: "\x1b[92m",
  brightYellow: "\x1b[93m",
  brightBlue: "\x1b[94m",
  brightMagenta: "\x1b[95m",
  brightCyan: "\x1b[96m",
  // Background
  bgBlack: "\x1b[40m",
  bgRed: "\x1b[41m",
  bgGreen: "\x1b[42m",
  bgYellow: "\x1b[43m",
  bgBlue: "\x1b[44m",
  bgMagenta: "\x1b[45m",
  bgCyan: "\x1b[46m",
  bgWhite: "\x1b[47m",
  bgGray: "\x1b[100m",
};

// Powerline symbols (Nerd Fonts compatible)
const SYMBOLS = {
  // Powerline arrows
  separator: "\uE0B0", //
  separatorThin: "\uE0B1", //
  separatorLeft: "\uE0B2", //
  separatorLeftThin: "\uE0B3", //
  // Icons
  branch: "\uE0A0", //  Git branch
  folder: "\uF07B", //  Folder
  tokens: "\uF49E", // 󰒞 Brain (context)
  cost: "\uF155", //  Dollar
  clock: "\uF017", //  Clock
  lines: "\uF15C", //  Document
  error: "\uF057", //  Error circle
  warning: "\uF071", //  Warning triangle
  success: "\uF058", //  Check circle
  fire: "\uF490", // 󰒐 Fire (hot context)
};

// Progress bar characters
const BAR_CHARS = {
  full: "█",
  seven: "▉",
  six: "▊",
  five: "▋",
  four: "▌",
  three: "▍",
  two: "▎",
  one: "▏",
  empty: "▁",
};

/**
 * Create a progress bar with smooth fill
 * @param {number} percent - 0-100
 * @param {number} width - Bar width in characters
 * @returns {string}
 */
function progressBar(percent, width = 8) {
  const clamped = Math.max(0, Math.min(100, percent));
  const fillFraction = (clamped / 100) * width;
  const filled = Math.floor(fillFraction);
  const partial = fillFraction - filled;
  const empty = width - filled - (partial > 0 ? 1 : 0);

  let bar = BAR_CHARS.full.repeat(filled);

  // Smooth partial fill
  if (partial > 0) {
    if (partial >= 0.875) bar += BAR_CHARS.seven;
    else if (partial >= 0.75) bar += BAR_CHARS.six;
    else if (partial >= 0.625) bar += BAR_CHARS.five;
    else if (partial >= 0.5) bar += BAR_CHARS.four;
    else if (partial >= 0.375) bar += BAR_CHARS.three;
    else if (partial >= 0.25) bar += BAR_CHARS.two;
    else if (partial > 0) bar += BAR_CHARS.one;
  }

  bar += BAR_CHARS.empty.repeat(empty);
  return bar;
}

/**
 * Get color based on percentage threshold
 * @param {number} percent
 * @param {Object} thresholds
 * @returns {string}
 */
function percentColor(
  percent,
  thresholds = { critical: 95, high: 90, medium: 75, low: 50 },
) {
  if (percent >= thresholds.critical) return COLORS.brightRed + COLORS.bold;
  if (percent >= thresholds.high) return COLORS.red;
  if (percent >= thresholds.medium) return COLORS.yellow;
  if (percent >= thresholds.low) return COLORS.green;
  return COLORS.cyan;
}

/**
 * Format token count (k/M notation)
 * @param {number} tokens
 * @returns {string}
 */
function formatTokens(tokens) {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 10_000) return `${Math.round(tokens / 1_000)}k`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}k`;
  return String(tokens);
}

/**
 * Format cost in USD
 * @param {number} costUsd
 * @returns {string}
 */
function formatCost(costUsd) {
  if (costUsd < 0.01) return `${Math.round(costUsd * 100)}¢`;
  if (costUsd < 0.1) return `$${costUsd.toFixed(3)}`;
  return `$${costUsd.toFixed(2)}`;
}

/**
 * Format duration
 * @param {number} ms - Milliseconds
 * @returns {string}
 */
function formatDuration(ms) {
  if (ms < 60000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3600000) return `${Math.round(ms / 60000)}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

/**
 * Create a powerline segment
 * @param {string} text
 * @param {string} fg - Foreground color
 * @param {string} bg - Background color
 * @returns {string}
 */
function segment(text, fg = COLORS.white, bg = COLORS.bgBlack) {
  return `${bg}${fg} ${text} ${COLORS.reset}`;
}

/**
 * Create a segment with powerline separator
 * @param {string} text
 * @param {string} fgColor
 * @param {string} bgColor
 * @param {string|null} nextBg - Next segment's background for separator
 * @returns {string}
 */
function segmentWithSep(text, fgColor, bgColor, nextBg = null) {
  let result = `${bgColor}${fgColor} ${text} ${COLORS.reset}`;
  if (nextBg) {
    // Separator: fg = current bg color, bg = next bg color
    const sepFg = bgColor.replace("4", "3"); // Convert bg to fg
    result += `${sepFg}${nextBg}${SYMBOLS.separator}${COLORS.reset}`;
  }
  return result;
}

/**
 * Model badge with context-aware color
 * @param {string} modelName
 * @param {number} contextPercent
 * @returns {string}
 */
function modelBadge(modelName, contextPercent = 0) {
  const color = percentColor(contextPercent);
  return `${color}[${modelName}]${COLORS.reset}`;
}

/**
 * Git branch display
 * @param {string} branch
 * @returns {string}
 */
function gitBranch(branch) {
  if (!branch) return "";
  return `${COLORS.magenta}${SYMBOLS.branch} ${branch}${COLORS.reset}`;
}

/**
 * Directory display
 * @param {string} dir
 * @returns {string}
 */
function directory(dir) {
  return `${COLORS.brightYellow}${SYMBOLS.folder} ${dir}${COLORS.reset}`;
}

/**
 * Context usage display with visual bar
 * @param {number} percent
 * @param {number|null} tokens
 * @returns {string}
 */
function contextUsage(percent, tokens = null) {
  const color = percentColor(percent);
  const bar = progressBar(percent);
  const tokenStr = tokens ? ` ${formatTokens(tokens)}` : "";

  // Icon based on severity
  let icon = "🟢";
  if (percent >= 95) icon = "🚨";
  else if (percent >= 90) icon = "🔴";
  else if (percent >= 75) icon = "🟠";
  else if (percent >= 50) icon = "🟡";

  return `${icon}${color}${bar}${COLORS.reset} ${percent.toFixed(0)}%${tokenStr}`;
}

/**
 * Session metrics display (cost, duration, lines)
 * @param {Object} data
 * @returns {string}
 */
function sessionMetrics(data) {
  const parts = [];

  // Token count
  if (data.tokens > 0) {
    const tokenColor = data.contextPercent >= 75 ? COLORS.yellow : COLORS.cyan;
    parts.push(`${tokenColor}📊 ${formatTokens(data.tokens)}${COLORS.reset}`);
  }

  // Cost
  if (data.cost > 0) {
    const costColor =
      data.cost >= 0.1
        ? COLORS.red
        : data.cost >= 0.05
          ? COLORS.yellow
          : COLORS.green;
    parts.push(
      `${costColor}${SYMBOLS.cost} ${formatCost(data.cost)}${COLORS.reset}`,
    );
  }

  // Duration
  if (data.duration > 0) {
    const durColor = data.duration >= 1800000 ? COLORS.yellow : COLORS.green;
    parts.push(
      `${durColor}${SYMBOLS.clock} ${formatDuration(data.duration)}${COLORS.reset}`,
    );
  }

  // Lines changed
  if (data.linesAdded > 0 || data.linesRemoved > 0) {
    const net = data.linesAdded - data.linesRemoved;
    const linesColor =
      net > 0 ? COLORS.green : net < 0 ? COLORS.red : COLORS.yellow;
    const sign = net >= 0 ? "+" : "";
    parts.push(`${linesColor}${SYMBOLS.lines} ${sign}${net}${COLORS.reset}`);
  }

  return parts.length
    ? `${COLORS.gray}|${COLORS.reset} ${parts.join(" ")}`
    : "";
}

/**
 * Strip ANSI codes from string
 * @param {string} str
 * @returns {string}
 */
function stripAnsi(str) {
  return str.replace(/\x1b\[[0-9;]*m/g, "");
}

/**
 * Get visible length of string (without ANSI codes)
 * @param {string} str
 * @returns {number}
 */
function visibleLength(str) {
  return stripAnsi(str).length;
}

module.exports = {
  COLORS,
  SYMBOLS,
  BAR_CHARS,
  progressBar,
  percentColor,
  formatTokens,
  formatCost,
  formatDuration,
  segment,
  segmentWithSep,
  modelBadge,
  gitBranch,
  directory,
  contextUsage,
  sessionMetrics,
  stripAnsi,
  visibleLength,
};
