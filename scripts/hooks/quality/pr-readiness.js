#!/usr/bin/env node
/**
 * PR Readiness Check Hook for Claude Code
 *
 * Evaluates PR readiness using ensemble scoring from multiple criteria:
 * 1. Git Diff Size - Sufficient changes
 * 2. Phase Completion - Tasks in current phase completed
 * 3. Tests Passing - All tests green
 * 4. Coverage Level - Adequate test coverage
 * 5. No Uncommitted Changes - Clean working directory
 *
 * Hook Type: PreToolUse
 * Matcher: Bash (when command contains 'gh pr create')
 * Timeout: 15s
 *
 * Ported from: claude-hooks-shared/hooks/quality/pr-readiness-check.py
 */

const fs = require('fs');
const path = require('path');
const { readStdinJson, output, getClaudeDir, ensureDir, readFile } = require('../../lib/utils');
const { runGitCommand, getUncommittedChanges, getCurrentBranch } = require('../../lib/git-utils');

// Configuration
const WEIGHTS = {
  git_diff: 0.10,
  phase_complete: 0.25,
  tests_green: 0.30,
  coverage: 0.20,
  clean_working_dir: 0.15
};

// Thresholds
const MIN_DIFF_LINES = 10;
const MIN_COVERAGE = 70;
const READY_THRESHOLD = 80;
const WARNING_THRESHOLD = 60;

// Paths
const METRICS_DIR = path.join(getClaudeDir(), 'metrics');
const PR_CHECK_LOG = path.join(METRICS_DIR, 'pr_readiness.jsonl');

/**
 * Log PR readiness check results
 */
function logPrCheck(data) {
  ensureDir(METRICS_DIR);
  const entry = {
    timestamp: new Date().toISOString(),
    ...data
  };
  fs.appendFileSync(PR_CHECK_LOG, JSON.stringify(entry) + '\n');
}

/**
 * Get git diff statistics
 */
function getGitDiffStats() {
  try {
    // Try common base branches
    for (const base of ['main', 'master', 'develop']) {
      const result = runGitCommand(['diff', '--stat', `${base}...HEAD`]);
      if (result && result.success && result.stdout.trim()) {
        const output = result.stdout;

        // Parse stats line: "X files changed, Y insertions(+), Z deletions(-)"
        const statsMatch = output.match(
          /(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?/
        );

        if (statsMatch) {
          const files = parseInt(statsMatch[1] || '0', 10);
          const added = parseInt(statsMatch[2] || '0', 10);
          const removed = parseInt(statsMatch[3] || '0', 10);
          const total = added + removed;

          // Score: 100 if >= MIN_DIFF_LINES, proportional otherwise
          const score = MIN_DIFF_LINES > 0
            ? Math.min(100, (total / MIN_DIFF_LINES) * 100)
            : 100;

          return {
            linesAdded: added,
            linesRemoved: removed,
            filesChanged: files,
            totalLines: total,
            score: Math.round(score),
            message: `${total} lines changed in ${files} file(s)`
          };
        }
        break;
      }
    }

    // Fallback to uncommitted changes
    const changes = getUncommittedChanges();
    if (changes && changes.hasChanges) {
      const total = changes.linesAdded + changes.linesDeleted;
      const score = MIN_DIFF_LINES > 0
        ? Math.min(100, (total / MIN_DIFF_LINES) * 100)
        : 100;
      return {
        linesAdded: changes.linesAdded,
        linesRemoved: changes.linesDeleted,
        filesChanged: changes.files.length,
        totalLines: total,
        score: Math.round(score),
        message: `${total} uncommitted lines`
      };
    }
  } catch (err) {
    // Ignore errors
  }

  return { linesAdded: 0, linesRemoved: 0, filesChanged: 0, totalLines: 0, score: 0, message: 'No changes detected' };
}

/**
 * Check if current phase tasks are completed
 */
function checkPhaseCompletion() {
  const tasksPaths = [
    path.join(process.cwd(), 'tasks.md'),
    path.join(process.cwd(), 'specs', 'tasks.md'),
    path.join(process.cwd(), '.speckit', 'tasks.md'),
    path.join(process.cwd(), '.planning', 'tasks.md')
  ];

  for (const tasksPath of tasksPaths) {
    const content = readFile(tasksPath);
    if (!content) continue;

    // Count tasks by status
    const completed = (content.match(/- \[x\]/gi) || []).length;
    const pending = (content.match(/- \[ \]/g) || []).length;
    const inProgress = (content.match(/- \[~\]/g) || []).length;

    const total = completed + pending + inProgress;
    if (total === 0) {
      return { status: 'no_tasks', score: 50, message: 'No tasks found' };
    }

    // Find current phase section
    const phaseMatch = content.match(
      /##\s*(Phase\s*\d+|Current Phase)[^\n]*\n([\s\S]*?)(?=##|\Z)/i
    );

    if (phaseMatch) {
      const phaseContent = phaseMatch[2];
      const phaseCompleted = (phaseContent.match(/- \[x\]/gi) || []).length;
      const phasePending = (phaseContent.match(/- \[ \]/g) || []).length;
      const phaseInProgress = (phaseContent.match(/- \[~\]/g) || []).length;
      const phaseTotal = phaseCompleted + phasePending + phaseInProgress;

      if (phaseTotal > 0) {
        const score = (phaseCompleted / phaseTotal) * 100;
        return {
          status: 'phase_found',
          phaseCompleted,
          phaseTotal,
          score: Math.round(score),
          message: `Phase: ${phaseCompleted}/${phaseTotal} tasks done`
        };
      }
    }

    // Fallback to overall completion
    const score = (completed / total) * 100;
    return {
      status: 'overall',
      completed,
      total,
      score: Math.round(score),
      message: `Overall: ${completed}/${total} tasks done`
    };
  }

  return { status: 'no_tasks_file', score: 50, message: 'No tasks.md found' };
}

/**
 * Check if tests are passing
 */
function checkTestsPassing() {
  // Check for recent pytest results
  const testResultPaths = [
    path.join(getClaudeDir(), 'metrics', 'test_results.json'),
    path.join(process.cwd(), '.pytest_cache', 'v', 'cache', 'lastfailed'),
    path.join(process.cwd(), 'test-results.json')
  ];

  for (const resultPath of testResultPaths) {
    const content = readFile(resultPath);
    if (!content) continue;

    try {
      if (resultPath.includes('lastfailed')) {
        // pytest lastfailed cache - empty means all passed
        const trimmed = content.trim();
        if (trimmed === '{}' || !trimmed) {
          return { status: 'green', score: 100, message: 'All tests passing' };
        } else {
          const failedCount = (trimmed.match(/"/g) || []).length / 2;
          return { status: 'red', score: 0, message: `${failedCount} test(s) failing`, failed: failedCount };
        }
      } else {
        const data = JSON.parse(content);
        const passed = data.passed || 0;
        const failed = data.failed || 0;
        const total = passed + failed;
        if (total > 0) {
          const score = (passed / total) * 100;
          const status = failed === 0 ? 'green' : 'red';
          return {
            status,
            passed,
            failed,
            score: Math.round(score),
            message: `${passed}/${total} tests passing`
          };
        }
      }
    } catch (err) {
      // Ignore parse errors
    }
  }

  return { status: 'unknown', score: 50, message: 'Test status unknown - run tests first' };
}

/**
 * Check code coverage level
 */
function checkCoverage() {
  const coveragePaths = [
    path.join(process.cwd(), 'coverage.json'),
    path.join(process.cwd(), '.coverage.json'),
    path.join(process.cwd(), 'htmlcov', 'status.json'),
    path.join(process.cwd(), 'coverage', 'coverage-final.json'),
    path.join(getClaudeDir(), 'metrics', 'coverage.json')
  ];

  for (const coveragePath of coveragePaths) {
    const content = readFile(coveragePath);
    if (!content) continue;

    try {
      const data = JSON.parse(content);
      let coveragePct = 0;

      // Handle different coverage output formats
      if (data.totals && data.totals.percent_covered !== undefined) {
        coveragePct = data.totals.percent_covered;
      } else if (data.meta && data.totals) {
        coveragePct = data.totals.percent_covered || 0;
      } else if (data.coverage !== undefined) {
        coveragePct = data.coverage;
      } else if (data.percent !== undefined) {
        coveragePct = data.percent;
      }

      const score = Math.min(100, (coveragePct / MIN_COVERAGE) * 100);
      const status = coveragePct >= MIN_COVERAGE ? 'good' : 'low';

      return {
        status,
        coveragePct: Math.round(coveragePct * 10) / 10,
        score: Math.round(score),
        message: `Coverage: ${coveragePct.toFixed(1)}%`
      };
    } catch (err) {
      // Ignore parse errors
    }
  }

  return { status: 'unknown', score: 50, message: 'Coverage unknown - run with --cov' };
}

/**
 * Check for clean working directory
 */
function checkCleanWorkingDir() {
  const changes = getUncommittedChanges();

  if (!changes) {
    return { status: 'unknown', score: 50, message: 'Could not check git status' };
  }

  if (!changes.hasChanges) {
    return { status: 'clean', score: 100, message: 'Working directory clean' };
  }

  // Staged changes are OK for PR
  if (changes.staged.length > 0 && changes.unstaged.length === 0 && changes.untracked.length === 0) {
    return { status: 'staged', score: 90, message: `${changes.staged.length} file(s) staged` };
  }

  // Unstaged or untracked changes are a problem
  const score = Math.max(0, 100 - (changes.unstaged.length + changes.untracked.length) * 10);
  return {
    status: 'dirty',
    score: Math.round(score),
    unstaged: changes.unstaged.length,
    untracked: changes.untracked.length,
    message: `${changes.unstaged.length} unstaged, ${changes.untracked.length} untracked`
  };
}

/**
 * Calculate weighted ensemble score
 */
function calculateEnsembleScore(criteria) {
  let totalScore = 0;
  const breakdown = {};

  for (const [criterion, data] of Object.entries(criteria)) {
    const weight = WEIGHTS[criterion] || 0;
    const score = data.score || 0;
    const weightedScore = score * weight;
    totalScore += weightedScore;
    breakdown[criterion] = {
      rawScore: score,
      weight,
      weighted: Math.round(weightedScore * 10) / 10
    };
  }

  return {
    totalScore: Math.round(totalScore),
    breakdown
  };
}

/**
 * Format output for display
 */
function formatOutput(criteria, ensemble) {
  const total = ensemble.totalScore;

  // Determine status
  let statusText, statusIcon;
  if (total >= READY_THRESHOLD) {
    statusIcon = '[READY]';
    statusText = 'PR Ready';
  } else if (total >= WARNING_THRESHOLD) {
    statusIcon = '[CAUTION]';
    statusText = 'Review Recommended';
  } else {
    statusIcon = '[NOT READY]';
    statusText = 'Not Ready for PR';
  }

  const lines = [
    '',
    `${statusIcon} PR READINESS: ${statusText} (Score: ${total}/100)`,
    '=' .repeat(50),
    '',
    'CRITERIA BREAKDOWN:',
    ''
  ];

  const criterionNames = {
    git_diff: 'Git Diff Size',
    phase_complete: 'Phase Complete',
    tests_green: 'Tests Passing',
    coverage: 'Code Coverage',
    clean_working_dir: 'Working Dir'
  };

  for (const [criterion, data] of Object.entries(criteria)) {
    const name = criterionNames[criterion] || criterion;
    const score = data.score || 0;
    const message = data.message || '';
    const weight = WEIGHTS[criterion] || 0;
    const weighted = score * weight;

    // Score bar
    const barFilled = Math.floor(score / 10);
    const bar = '#'.repeat(barFilled) + '.'.repeat(10 - barFilled);

    lines.push(`  ${name.padEnd(18)} [${bar}] ${String(score).padStart(3)}% x ${Math.round(weight * 100)}% = ${weighted.toFixed(1)}`);
    if (message) {
      lines.push(`                      ${message}`);
    }
    lines.push('');
  }

  lines.push('='.repeat(50));
  lines.push(`ENSEMBLE SCORE: ${total}/100`);
  lines.push('');

  // Add recommendations
  if (total < READY_THRESHOLD) {
    lines.push('RECOMMENDATIONS:');
    if (criteria.tests_green && criteria.tests_green.status === 'red') {
      lines.push('  * Fix failing tests before creating PR');
    }
    if (criteria.tests_green && criteria.tests_green.status === 'unknown') {
      lines.push('  * Run tests: npm test / pytest tests/ -v');
    }
    if (criteria.coverage && criteria.coverage.score < 90) {
      lines.push('  * Improve coverage: pytest --cov --cov-report=json');
    }
    if (criteria.phase_complete && criteria.phase_complete.score < 100) {
      lines.push('  * Complete remaining tasks in current phase');
    }
    if (criteria.clean_working_dir && criteria.clean_working_dir.status === 'dirty') {
      lines.push('  * Commit or stash uncommitted changes');
    }
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Main hook entry point
 */
async function main() {
  try {
    const inputData = await readStdinJson();

    // Check if this is a Bash tool use
    const toolName = inputData.tool_name || '';
    if (toolName !== 'Bash') {
      process.exit(0);
    }

    // Get command
    const toolInput = inputData.tool_input || {};
    const command = toolInput.command || '';

    // Only trigger on gh pr create commands
    if (!command.includes('gh') || !command.includes('pr') || !command.includes('create')) {
      process.exit(0);
    }

    // Gather all criteria
    const criteria = {
      git_diff: getGitDiffStats(),
      phase_complete: checkPhaseCompletion(),
      tests_green: checkTestsPassing(),
      coverage: checkCoverage(),
      clean_working_dir: checkCleanWorkingDir()
    };

    // Calculate ensemble score
    const ensemble = calculateEnsembleScore(criteria);
    const totalScore = ensemble.totalScore;

    // Log results
    logPrCheck({
      criteria,
      ensemble,
      cwd: process.cwd(),
      branch: getCurrentBranch()
    });

    // Format output
    const outputMessage = formatOutput(criteria, ensemble);

    // Determine if we should block
    let shouldBlock = false;
    const blockReasons = [];

    // Block if tests are failing
    if (criteria.tests_green && criteria.tests_green.status === 'red') {
      shouldBlock = true;
      blockReasons.push('Tests are failing');
    }

    // Block if score is very low
    if (totalScore < 40) {
      shouldBlock = true;
      blockReasons.push(`Readiness score too low (${totalScore}/100)`);
    }

    if (shouldBlock) {
      output({
        decision: 'block',
        reason: outputMessage + '\n\n[BLOCKED] ' + blockReasons.join(', ')
      });
      process.exit(1);
    }

    // Show as informational message
    output({
      systemMessage: outputMessage
    });
    process.exit(0);

  } catch (err) {
    // Fail open - don't block the user
    process.exit(0);
  }
}

main();
