/**
 * Git Utilities for Claude Code Hooks
 *
 * Provides safe git operations with timeouts and graceful error handling.
 * All functions return null on failure (never throw).
 *
 * Functions:
 * - getCurrentCommit() - HEAD commit hash
 * - getCurrentBranch() - current branch name
 * - getRepoRoot() - git root directory
 * - getUncommittedChanges() - change statistics
 * - getSessionCommits(startCommit) - commits since a point
 * - categorizeFile(path) - classify file type
 * - runGitCommand(args, timeout) - safe git execution
 */

const { execSync } = require('child_process');
const path = require('path');

// Default timeout for git commands (5 seconds)
const DEFAULT_TIMEOUT = 5000;

/**
 * Run a git command safely with timeout
 * @param {string[]} args - Git command arguments
 * @param {number} [timeout=5000] - Timeout in milliseconds
 * @param {string} [cwd=process.cwd()] - Working directory
 * @returns {object|null} Result object with stdout/stderr or null on error
 */
function runGitCommand(args, timeout = DEFAULT_TIMEOUT, cwd = process.cwd()) {
  try {
    const command = `git ${args.join(' ')}`;
    const result = execSync(command, {
      encoding: 'utf8',
      timeout,
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      maxBuffer: 10 * 1024 * 1024 // 10MB buffer for large diffs
    });
    return { success: true, stdout: result.trim(), stderr: '' };
  } catch (err) {
    if (err.killed) {
      return { success: false, stdout: '', stderr: 'Command timed out', timedOut: true };
    }
    return {
      success: false,
      stdout: err.stdout ? err.stdout.toString().trim() : '',
      stderr: err.stderr ? err.stderr.toString().trim() : err.message
    };
  }
}

/**
 * Check if current directory is inside a git repository
 * @returns {boolean} True if in a git repo
 */
function isGitRepo() {
  const result = runGitCommand(['rev-parse', '--git-dir']);
  return result !== null && result.success;
}

/**
 * Get the current HEAD commit hash
 * @param {boolean} [short=false] - Return short (7 char) hash
 * @returns {string|null} Commit hash or null if not in a repo
 */
function getCurrentCommit(short = false) {
  const args = short
    ? ['rev-parse', '--short', 'HEAD']
    : ['rev-parse', 'HEAD'];
  const result = runGitCommand(args);
  return result && result.success ? result.stdout : null;
}

/**
 * Get the current branch name
 * @returns {string|null} Branch name or null if not in a repo/detached HEAD
 */
function getCurrentBranch() {
  // Try symbolic-ref first (works for attached HEAD)
  const result = runGitCommand(['symbolic-ref', '--short', 'HEAD']);
  if (result && result.success) {
    return result.stdout;
  }

  // Fall back to describe for detached HEAD
  const descResult = runGitCommand(['describe', '--tags', '--always']);
  if (descResult && descResult.success) {
    return `detached:${descResult.stdout}`;
  }

  return null;
}

/**
 * Get the git repository root directory
 * @returns {string|null} Absolute path to repo root or null
 */
function getRepoRoot() {
  const result = runGitCommand(['rev-parse', '--show-toplevel']);
  return result && result.success ? result.stdout : null;
}

/**
 * Get uncommitted changes statistics
 * @returns {object|null} Object with hasChanges, linesAdded, linesDeleted, files, or null on error
 */
function getUncommittedChanges() {
  try {
    // Get list of changed files
    const statusResult = runGitCommand(['status', '--porcelain']);
    if (!statusResult || !statusResult.success) {
      return null;
    }

    const statusLines = statusResult.stdout.split('\n').filter(Boolean);
    const files = statusLines.map(line => {
      const status = line.substring(0, 2).trim();
      const filePath = line.substring(3);
      return { status, path: filePath };
    });

    if (files.length === 0) {
      return {
        hasChanges: false,
        linesAdded: 0,
        linesDeleted: 0,
        files: [],
        staged: [],
        unstaged: [],
        untracked: []
      };
    }

    // Get diff stats for tracked files
    const diffResult = runGitCommand(['diff', '--numstat']);
    const stagedDiffResult = runGitCommand(['diff', '--cached', '--numstat']);

    let linesAdded = 0;
    let linesDeleted = 0;

    // Parse unstaged diff
    if (diffResult && diffResult.success && diffResult.stdout) {
      for (const line of diffResult.stdout.split('\n')) {
        const parts = line.split('\t');
        if (parts.length >= 2) {
          const added = parseInt(parts[0], 10);
          const deleted = parseInt(parts[1], 10);
          if (!isNaN(added)) linesAdded += added;
          if (!isNaN(deleted)) linesDeleted += deleted;
        }
      }
    }

    // Parse staged diff
    if (stagedDiffResult && stagedDiffResult.success && stagedDiffResult.stdout) {
      for (const line of stagedDiffResult.stdout.split('\n')) {
        const parts = line.split('\t');
        if (parts.length >= 2) {
          const added = parseInt(parts[0], 10);
          const deleted = parseInt(parts[1], 10);
          if (!isNaN(added)) linesAdded += added;
          if (!isNaN(deleted)) linesDeleted += deleted;
        }
      }
    }

    // Categorize files
    const staged = files.filter(f => f.status[0] !== ' ' && f.status[0] !== '?');
    const unstaged = files.filter(f => f.status[1] !== ' ' && f.status[0] !== '?');
    const untracked = files.filter(f => f.status === '??');

    return {
      hasChanges: true,
      linesAdded,
      linesDeleted,
      files: files.map(f => f.path),
      staged: staged.map(f => f.path),
      unstaged: unstaged.map(f => f.path),
      untracked: untracked.map(f => f.path)
    };
  } catch (err) {
    return null;
  }
}

/**
 * Get commits since a starting commit
 * @param {string} startCommit - Starting commit hash
 * @param {string} [format='%H|%s|%an|%ai'] - Git log format
 * @returns {object[]|null} Array of commit objects or null on error
 */
function getSessionCommits(startCommit, format = '%H|%s|%an|%ai') {
  try {
    // Verify startCommit exists
    const verifyResult = runGitCommand(['cat-file', '-t', startCommit]);
    if (!verifyResult || !verifyResult.success) {
      return null;
    }

    const result = runGitCommand([
      'log',
      `${startCommit}..HEAD`,
      `--format=${format}`,
      '--no-merges'
    ], 10000); // 10 second timeout for log

    if (!result || !result.success) {
      return [];
    }

    if (!result.stdout) {
      return [];
    }

    const commits = result.stdout.split('\n').filter(Boolean).map(line => {
      const parts = line.split('|');
      return {
        hash: parts[0] || '',
        subject: parts[1] || '',
        author: parts[2] || '',
        date: parts[3] || ''
      };
    });

    return commits;
  } catch (err) {
    return null;
  }
}

/**
 * Get the number of commits between two points
 * @param {string} startCommit - Starting commit
 * @param {string} [endCommit='HEAD'] - Ending commit
 * @returns {number|null} Number of commits or null on error
 */
function getCommitCount(startCommit, endCommit = 'HEAD') {
  const result = runGitCommand(['rev-list', '--count', `${startCommit}..${endCommit}`]);
  if (result && result.success) {
    const count = parseInt(result.stdout, 10);
    return isNaN(count) ? null : count;
  }
  return null;
}

/**
 * Categorize a file by its path/extension
 * @param {string} filePath - File path
 * @returns {string} Category: 'code', 'test', 'config', 'docs', 'other'
 */
function categorizeFile(filePath) {
  const normalized = filePath.toLowerCase();
  const ext = path.extname(normalized);
  const basename = path.basename(normalized);
  const dirname = path.dirname(normalized);

  // Test files
  if (
    basename.includes('.test.') ||
    basename.includes('.spec.') ||
    basename.includes('_test.') ||
    basename.includes('_spec.') ||
    basename.startsWith('test_') ||
    dirname.includes('/test/') ||
    dirname.includes('/tests/') ||
    dirname.includes('/__tests__/') ||
    dirname.includes('/spec/') ||
    dirname.startsWith('test/') ||
    dirname.startsWith('tests/')
  ) {
    return 'test';
  }

  // Config files
  const configFiles = [
    '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.env', '.config', '.lock', '.properties'
  ];
  const configNames = [
    'package.json', 'tsconfig.json', 'jest.config', 'eslint', 'prettier',
    '.gitignore', '.npmrc', '.nvmrc', 'dockerfile', 'docker-compose',
    'makefile', 'cmakelists', 'cargo.toml', 'go.mod', 'requirements.txt',
    'pyproject.toml', 'setup.py', 'setup.cfg', 'tox.ini', '.babelrc',
    'webpack.config', 'vite.config', 'rollup.config', 'esbuild'
  ];

  if (configFiles.includes(ext)) {
    return 'config';
  }

  for (const name of configNames) {
    if (basename.includes(name)) {
      return 'config';
    }
  }

  // Documentation
  const docExts = ['.md', '.rst', '.txt', '.adoc', '.mdx'];
  const docDirs = ['docs/', 'doc/', 'documentation/', 'wiki/'];

  if (docExts.includes(ext)) {
    return 'docs';
  }

  for (const dir of docDirs) {
    if (normalized.includes(dir)) {
      return 'docs';
    }
  }

  if (basename === 'readme' || basename === 'changelog' || basename === 'license') {
    return 'docs';
  }

  // Code files
  const codeExts = [
    '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs',
    '.py', '.pyw', '.pyi',
    '.go',
    '.rs',
    '.java', '.kt', '.scala',
    '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp',
    '.cs',
    '.rb', '.erb',
    '.php',
    '.swift',
    '.vue', '.svelte',
    '.sql',
    '.sh', '.bash', '.zsh', '.fish',
    '.lua',
    '.r', '.R',
    '.pl', '.pm',
    '.ex', '.exs',
    '.hs',
    '.ml', '.mli',
    '.clj', '.cljs',
    '.elm',
    '.nim',
    '.zig',
    '.v',
    '.dart'
  ];

  if (codeExts.includes(ext)) {
    return 'code';
  }

  return 'other';
}

/**
 * Get files changed in a commit
 * @param {string} commit - Commit hash
 * @returns {string[]|null} Array of file paths or null on error
 */
function getCommitFiles(commit) {
  const result = runGitCommand(['diff-tree', '--no-commit-id', '--name-only', '-r', commit]);
  if (result && result.success) {
    return result.stdout.split('\n').filter(Boolean);
  }
  return null;
}

/**
 * Get the diff for a specific file
 * @param {string} filePath - File path
 * @param {boolean} [staged=false] - Get staged diff
 * @returns {string|null} Diff output or null on error
 */
function getFileDiff(filePath, staged = false) {
  const args = staged
    ? ['diff', '--cached', '--', filePath]
    : ['diff', '--', filePath];
  const result = runGitCommand(args, 10000);
  return result && result.success ? result.stdout : null;
}

/**
 * Get blame info for a file
 * @param {string} filePath - File path
 * @param {number} [line] - Specific line number
 * @returns {object[]|null} Array of blame entries or null
 */
function getBlame(filePath, line = null) {
  const args = ['blame', '--porcelain'];
  if (line) {
    args.push(`-L${line},${line}`);
  }
  args.push(filePath);

  const result = runGitCommand(args, 15000);
  if (!result || !result.success) {
    return null;
  }

  // Parse porcelain format
  const entries = [];
  const lines = result.stdout.split('\n');
  let current = null;

  for (const line of lines) {
    if (line.match(/^[0-9a-f]{40}/)) {
      const parts = line.split(' ');
      current = {
        commit: parts[0],
        originalLine: parseInt(parts[1], 10),
        finalLine: parseInt(parts[2], 10)
      };
    } else if (line.startsWith('author ') && current) {
      current.author = line.substring(7);
    } else if (line.startsWith('author-time ') && current) {
      current.timestamp = parseInt(line.substring(12), 10);
    } else if (line.startsWith('\t') && current) {
      current.content = line.substring(1);
      entries.push(current);
      current = null;
    }
  }

  return entries;
}

/**
 * Get remote URL
 * @param {string} [remote='origin'] - Remote name
 * @returns {string|null} Remote URL or null
 */
function getRemoteUrl(remote = 'origin') {
  const result = runGitCommand(['remote', 'get-url', remote]);
  return result && result.success ? result.stdout : null;
}

/**
 * Get all local branches
 * @returns {string[]|null} Array of branch names or null
 */
function getBranches() {
  const result = runGitCommand(['branch', '--format=%(refname:short)']);
  if (result && result.success) {
    return result.stdout.split('\n').filter(Boolean);
  }
  return null;
}

module.exports = {
  // Core operations
  runGitCommand,
  isGitRepo,
  getCurrentCommit,
  getCurrentBranch,
  getRepoRoot,

  // Change analysis
  getUncommittedChanges,
  getSessionCommits,
  getCommitCount,
  getCommitFiles,
  getFileDiff,

  // File categorization
  categorizeFile,

  // Additional utilities
  getBlame,
  getRemoteUrl,
  getBranches,

  // Constants
  DEFAULT_TIMEOUT
};
