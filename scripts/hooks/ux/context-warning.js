#!/usr/bin/env node
/**
 * Context Warning Hook (UserPromptSubmit)
 *
 * Checks context usage flag and injects instruction for Claude
 * to use AskUserQuestion when context is high (>70%).
 *
 * Reads flag file written by context-monitor.js (statusline)
 */

const fs = require("fs");
const path = require("path");
const os = require("os");

const FLAG_FILE = path.join(os.homedir(), ".claude", "stats", "context-high-flag.json");
const PIPELINE_FLAG = path.join(os.homedir(), ".claude", "stats", "pipeline-active.flag");

async function main() {
  // Skip if pipeline is active (GSD, SpecKit, etc.)
  if (fs.existsSync(PIPELINE_FLAG)) {
    process.exit(0);
  }
  // Read stdin (hook input)
  let inputData = "";
  for await (const chunk of process.stdin) {
    inputData += chunk;
  }

  try {
    // Check if flag file exists
    if (!fs.existsSync(FLAG_FILE)) {
      process.exit(0);
    }

    const stats = fs.statSync(FLAG_FILE);
    const ageMs = Date.now() - stats.mtimeMs;

    // Only trigger if flag is fresh (< 5 minutes)
    if (ageMs > 300000) {
      fs.unlinkSync(FLAG_FILE);
      process.exit(0);
    }

    const flagData = JSON.parse(fs.readFileSync(FLAG_FILE, "utf8"));

    // Remove flag so it doesn't trigger again until next statusline update
    fs.unlinkSync(FLAG_FILE);

    // Inject system-reminder instructing Claude to use AskUserQuestion
    console.log(JSON.stringify({
      result: "continue",
      message: `⚠️ CONTEXT ALTO (${flagData.percent}%) - DEVI usare AskUserQuestion per chiedere all'utente quale azione eseguire tra: (1) Checkpoint + /compact, (2) Checkpoint + /clear, (3) Solo /compact, (4) Ignora. USA IL TOOL AskUserQuestion ORA.`
    }));

    process.exit(0);
  } catch (err) {
    // Silent fail
    process.exit(0);
  }
}

main();
