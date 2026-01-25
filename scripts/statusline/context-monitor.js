#!/usr/bin/env node
/**
 * Claude Code Context Monitor (Node.js Port)
 *
 * HYBRID APPROACH: Best of ccstatusline UI + our persistence layer
 *
 * DUAL PURPOSE:
 * 1. Data persistence (analysis, metrics) - PRIMARY GOAL
 *    - JSONL logging with contextual metadata
 *    - QuestDB export for real-time dashboards
 *    - Cost attribution (infers task type)
 * 2. StatusLine display (real-time, eye-candy) - SECONDARY GOAL
 *    - Powerline-style UI (inspired by ccstatusline)
 *    - Smooth progress bars, Nerd Fonts icons
 *    - Context-aware coloring
 *
 * Ported from: /media/sam/1TB/claude-hooks-shared/scripts/context-monitor.py
 * UI inspired by: github.com/sirmalloc/ccstatusline
 *
 * CHANGELOG:
 * - v3: Python version with QuestDB export
 * - v4: Node.js port with powerline UI
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execSync } = require("child_process");
const net = require("net");

const {
  COLORS,
  SYMBOLS,
  modelBadge,
  gitBranch,
  directory,
  contextUsage,
  sessionMetrics,
  formatTokens,
} = require("./ui-components");

// Configuration
const STATS_DIR = path.join(os.homedir(), ".claude", "stats");
const METRICS_FILE = path.join(STATS_DIR, "session_metrics.jsonl");
const CONTEXT_WINDOW = 200000; // Assume 200k for Claude

// QuestDB settings
const QUESTDB_HOST = process.env.QUESTDB_HOST || "localhost";
const QUESTDB_ILP_PORT = parseInt(process.env.QUESTDB_ILP_PORT || "9009");

// ============= Context Parsing =============

function parseContextFromTranscript(transcriptPath) {
  if (!transcriptPath || !fs.existsSync(transcriptPath)) return null;

  try {
    const content = fs.readFileSync(transcriptPath, "utf8");
    const lines = content.split("\n").filter((l) => l.trim());
    const recentLines = lines.slice(-15);

    for (const line of recentLines.reverse()) {
      try {
        const data = JSON.parse(line);

        // Method 1: Parse usage tokens from assistant messages
        if (data.type === "assistant") {
          const usage = data.message?.usage;
          if (usage) {
            const inputTokens = usage.input_tokens || 0;
            const cacheRead = usage.cache_read_input_tokens || 0;
            const cacheCreation = usage.cache_creation_input_tokens || 0;
            const outputTokens = usage.output_tokens || 0;
            const totalTokens = inputTokens + cacheRead + cacheCreation;

            if (totalTokens > 0) {
              const percentUsed = Math.min(
                100,
                (totalTokens / CONTEXT_WINDOW) * 100,
              );
              return {
                percent: percentUsed,
                tokens: totalTokens,
                inputTokens,
                outputTokens,
                cacheCreation,
                cacheRead,
                method: "usage",
              };
            }
          }
        }

        // Method 2: Parse system context warnings
        if (data.type === "system_message") {
          const content = data.content || "";

          let match = content.match(/Context left until auto-compact: (\d+)%/);
          if (match) {
            const percentLeft = parseInt(match[1]);
            return {
              percent: 100 - percentLeft,
              warning: "auto-compact",
              method: "system",
            };
          }

          match = content.match(/Context low \((\d+)% remaining\)/);
          if (match) {
            const percentLeft = parseInt(match[1]);
            return {
              percent: 100 - percentLeft,
              warning: "low",
              method: "system",
            };
          }
        }
      } catch {
        continue;
      }
    }
    return null;
  } catch {
    return null;
  }
}

// ============= Context Detection =============

function getGitBranchName() {
  try {
    return (
      execSync("git branch --show-current", {
        encoding: "utf8",
        timeout: 2000,
        stdio: ["pipe", "pipe", "pipe"],
      }).trim() || null
    );
  } catch {
    return null;
  }
}

function getProjectName() {
  try {
    const root = execSync("git rev-parse --show-toplevel", {
      encoding: "utf8",
      timeout: 2000,
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
    return path.basename(root);
  } catch {
    return path.basename(process.cwd());
  }
}

function getTaskContext() {
  // Priority: env var > file > last commit
  if (process.env.CLAUDE_TASK_DESC) return process.env.CLAUDE_TASK_DESC;

  const descFile = path.join(process.cwd(), ".claude", ".session_description");
  if (fs.existsSync(descFile)) {
    try {
      return fs.readFileSync(descFile, "utf8").trim();
    } catch {
      // ignore
    }
  }

  try {
    const msg = execSync("git log -1 --pretty=%s", {
      encoding: "utf8",
      timeout: 2000,
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
    return `Commit: ${msg.slice(0, 80)}`;
  } catch {
    // ignore
  }

  return null;
}

function getAgentName(workspaceData) {
  if (process.env.CLAUDE_AGENT_NAME) return process.env.CLAUDE_AGENT_NAME;

  if (workspaceData?.project_dir) {
    if (
      workspaceData.project_dir.includes(".claude/agents/") ||
      workspaceData.project_dir.includes("/agents/")
    ) {
      return path.basename(workspaceData.project_dir);
    }
  }
  return null;
}

function getDirectoryDisplay(workspaceData) {
  const currentDir = workspaceData?.current_dir || "";
  const projectDir = workspaceData?.project_dir || "";

  if (currentDir && projectDir && currentDir.startsWith(projectDir)) {
    const relPath = currentDir.slice(projectDir.length).replace(/^\//, "");
    return relPath || path.basename(projectDir);
  }
  return path.basename(currentDir || projectDir || process.cwd());
}

// ============= Task Type Inference (Cost Attribution) =============

function inferTaskType(taskDescription) {
  if (!taskDescription) return null;
  const desc = taskDescription.toLowerCase();

  if (["fix", "bug", "error", "issue"].some((w) => desc.includes(w))) {
    return "bugfix";
  }
  if (["refactor", "clean", "optimize"].some((w) => desc.includes(w))) {
    return "refactor";
  }
  if (["test", "coverage", "spec"].some((w) => desc.includes(w))) {
    return "testing";
  }
  if (["doc", "readme", "comment"].some((w) => desc.includes(w))) {
    return "docs";
  }
  if (["add", "implement", "feature", "new"].some((w) => desc.includes(w))) {
    return "feature";
  }
  return null;
}

// ============= Persistence =============

function ensureStatsDir() {
  if (!fs.existsSync(STATS_DIR)) {
    fs.mkdirSync(STATS_DIR, { recursive: true });
  }
}

async function exportToQuestDB(metrics) {
  return new Promise((resolve) => {
    try {
      const socket = new net.Socket();
      socket.setTimeout(3000);

      socket.connect(QUESTDB_ILP_PORT, QUESTDB_HOST, () => {
        // ILP format: table,tag=value field=value timestamp
        const project = (metrics.project || "unknown").replace(/[,= ]/g, "_");
        const branch = (metrics.branch || "none").replace(/[,= ]/g, "_");
        const taskType = (metrics.taskType || "unknown").replace(/[,= ]/g, "_");

        const line =
          `claude_sessions,project=${project},branch=${branch},task_type=${taskType} ` +
          `input_tokens=${metrics.inputTokens || 0}i,` +
          `output_tokens=${metrics.outputTokens || 0}i,` +
          `cache_read=${metrics.cacheRead || 0}i,` +
          `cache_creation=${metrics.cacheCreation || 0}i,` +
          `context_percent=${metrics.contextPercent || 0},` +
          `cost_usd=${metrics.costUsd || 0},` +
          `lines_added=${metrics.linesAdded || 0}i,` +
          `lines_removed=${metrics.linesRemoved || 0}i ` +
          `${Date.now() * 1000000}\n`;

        socket.write(line);
        socket.end();
        resolve(true);
      });

      socket.on("error", () => resolve(false));
      socket.on("timeout", () => {
        socket.destroy();
        resolve(false);
      });
    } catch {
      resolve(false);
    }
  });
}

function calculateCost(contextInfo, costData) {
  if (costData?.total_cost_usd) return costData.total_cost_usd;

  // Manual calculation (Claude 4.5 Sonnet pricing)
  const inputTokens = contextInfo?.inputTokens || 0;
  const outputTokens = contextInfo?.outputTokens || 0;
  const cacheCreation = contextInfo?.cacheCreation || 0;
  const cacheRead = contextInfo?.cacheRead || 0;

  const costInput = (inputTokens / 1_000_000) * 3.0;
  const costOutput = (outputTokens / 1_000_000) * 15.0;
  const costCacheCreation = (cacheCreation / 1_000_000) * 3.75;
  const costCacheRead = (cacheRead / 1_000_000) * 0.3;

  return costInput + costOutput + costCacheCreation + costCacheRead;
}

function persistMetrics(
  sessionId,
  contextInfo,
  costData,
  modelName,
  workspaceData,
) {
  try {
    ensureStatsDir();

    const branch = getGitBranchName();
    const taskDesc = getTaskContext();
    const agentName = getAgentName(workspaceData);
    const project = getProjectName();
    const taskType = inferTaskType(taskDesc);
    const cost = calculateCost(contextInfo, costData);

    const metrics = {
      session_id: sessionId,
      timestamp: new Date().toISOString(),
      model: modelName,
      tokens: {
        input: contextInfo?.inputTokens || 0,
        output: contextInfo?.outputTokens || 0,
        cache_creation: contextInfo?.cacheCreation || 0,
        cache_read: contextInfo?.cacheRead || 0,
        total: contextInfo?.tokens || 0,
      },
      context_percent: Math.round((contextInfo?.percent || 0) * 10) / 10,
      cost_usd: Math.round(cost * 10000) / 10000,
      duration_minutes: costData?.total_duration_ms
        ? Math.round((costData.total_duration_ms / 60000) * 100) / 100
        : 0,
      lines_changed: {
        added: costData?.total_lines_added || 0,
        removed: costData?.total_lines_removed || 0,
      },
      context: {
        git_branch: branch,
        task_description: taskDesc,
        task_type: taskType,
        agent_name: agentName,
        working_dir: path.basename(process.cwd()),
        project,
      },
    };

    // Append to JSONL (primary storage)
    fs.appendFileSync(METRICS_FILE, JSON.stringify(metrics) + "\n");

    // Async export to QuestDB (best-effort)
    exportToQuestDB({
      project,
      branch,
      taskType,
      inputTokens: contextInfo?.inputTokens,
      outputTokens: contextInfo?.outputTokens,
      cacheRead: contextInfo?.cacheRead,
      cacheCreation: contextInfo?.cacheCreation,
      contextPercent: contextInfo?.percent,
      costUsd: cost,
      linesAdded: costData?.total_lines_added || 0,
      linesRemoved: costData?.total_lines_removed || 0,
    }).catch(() => {});

    return true;
  } catch {
    return false;
  }
}

// ============= Status Line Display =============

function buildStatusLine(modelName, workspace, contextInfo, costData) {
  const parts = [];

  // Model badge with context-aware color
  parts.push(modelBadge(modelName, contextInfo?.percent || 0));

  // Git branch (if in repo)
  const branch = getGitBranchName();
  if (branch) {
    parts.push(gitBranch(branch));
  }

  // Directory
  parts.push(directory(getDirectoryDisplay(workspace)));

  // Context usage with visual bar
  if (contextInfo) {
    parts.push(`🧠 ${contextUsage(contextInfo.percent, contextInfo.tokens)}`);
  } else {
    parts.push(`🧠 ${COLORS.blue}???${COLORS.reset}`);
  }

  // Session metrics (cost, duration, lines)
  if (costData || contextInfo) {
    const metricsStr = sessionMetrics({
      tokens: contextInfo?.tokens || 0,
      contextPercent: contextInfo?.percent || 0,
      cost: calculateCost(contextInfo, costData),
      duration: costData?.total_duration_ms || 0,
      linesAdded: costData?.total_lines_added || 0,
      linesRemoved: costData?.total_lines_removed || 0,
    });
    if (metricsStr) parts.push(metricsStr);
  }

  return parts.join(" ");
}

// ============= Main =============

async function main() {
  try {
    // Read JSON input from Claude Code
    let inputData = "";
    for await (const chunk of process.stdin) {
      inputData += chunk;
    }
    const data = JSON.parse(inputData);

    // Extract information
    const modelName = data.model?.display_name || "Claude";
    const workspace = data.workspace || {};
    const transcriptPath = data.transcript_path || "";
    const costData = data.cost || {};
    const sessionId = data.session_id || "unknown";

    // Parse context usage
    const contextInfo = parseContextFromTranscript(transcriptPath);

    // PRIMARY GOAL: Persist metrics with contextual metadata
    if (contextInfo) {
      persistMetrics(sessionId, contextInfo, costData, modelName, workspace);
    }

    // SECONDARY GOAL: Build and output status line
    const statusLine = buildStatusLine(
      modelName,
      workspace,
      contextInfo,
      costData,
    );

    // Add reset at the beginning to override Claude Code's dim setting (like ccstatusline)
    console.log("\x1b[0m" + statusLine);
  } catch (err) {
    // Fallback display on any error
    const cwd = path.basename(process.cwd());
    console.log(
      `${COLORS.blue}[Claude]${COLORS.reset} ${COLORS.brightYellow}📁 ${cwd}${COLORS.reset} 🧠 ${COLORS.red}[Error]${COLORS.reset}`,
    );
  }
}

main();
