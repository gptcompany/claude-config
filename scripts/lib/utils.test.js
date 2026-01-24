/**
 * Unit tests for utils.js
 * Uses Node.js built-in test runner (node --test)
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const utils = require('./utils.js');

describe('Platform detection', () => {
  it('exactly one platform should be true', () => {
    const platforms = [utils.isWindows, utils.isMacOS, utils.isLinux];
    const trueCount = platforms.filter(Boolean).length;
    assert.strictEqual(trueCount, 1, 'Exactly one platform should be true');
  });

  it('isLinux should be true on Linux', () => {
    if (process.platform === 'linux') {
      assert.strictEqual(utils.isLinux, true);
    }
  });
});

describe('Directory functions', () => {
  it('getHomeDir returns non-empty string', () => {
    const home = utils.getHomeDir();
    assert.ok(typeof home === 'string' && home.length > 0);
  });

  it('getClaudeDir returns path ending in .claude', () => {
    const claudeDir = utils.getClaudeDir();
    assert.ok(claudeDir.endsWith('.claude'));
  });

  it('getSessionsDir returns path containing sessions', () => {
    const sessionsDir = utils.getSessionsDir();
    assert.ok(sessionsDir.includes('sessions'));
  });

  it('getLearnedSkillsDir returns path containing skills/learned', () => {
    const skillsDir = utils.getLearnedSkillsDir();
    assert.ok(skillsDir.includes('skills'));
    assert.ok(skillsDir.includes('learned'));
  });

  it('getTempDir returns non-empty string', () => {
    const tempDir = utils.getTempDir();
    assert.ok(typeof tempDir === 'string' && tempDir.length > 0);
  });

  it('ensureDir creates directory', () => {
    const testDir = path.join(utils.getTempDir(), `utils-test-${Date.now()}`);
    try {
      assert.ok(!fs.existsSync(testDir));
      utils.ensureDir(testDir);
      assert.ok(fs.existsSync(testDir));
    } finally {
      if (fs.existsSync(testDir)) {
        fs.rmdirSync(testDir);
      }
    }
  });
});

describe('Date/Time functions', () => {
  it('getDateString returns YYYY-MM-DD format', () => {
    const date = utils.getDateString();
    assert.match(date, /^\d{4}-\d{2}-\d{2}$/);
  });

  it('getTimeString returns HH:MM format', () => {
    const time = utils.getTimeString();
    assert.match(time, /^\d{2}:\d{2}$/);
  });

  it('getDateTimeString returns YYYY-MM-DD HH:MM:SS format', () => {
    const datetime = utils.getDateTimeString();
    assert.match(datetime, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
  });
});

describe('File operations', () => {
  let testFile;

  before(() => {
    testFile = path.join(utils.getTempDir(), `utils-test-${Date.now()}.txt`);
  });

  after(() => {
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile);
    }
  });

  it('writeFile and readFile roundtrip', () => {
    const content = 'Hello, World!';
    utils.writeFile(testFile, content);
    const read = utils.readFile(testFile);
    assert.strictEqual(read, content);
  });

  it('appendFile adds content', () => {
    utils.writeFile(testFile, 'Line 1\n');
    utils.appendFile(testFile, 'Line 2\n');
    const content = utils.readFile(testFile);
    assert.ok(content.includes('Line 1'));
    assert.ok(content.includes('Line 2'));
  });

  it('readFile returns null for non-existent file', () => {
    const result = utils.readFile('/non/existent/file.txt');
    assert.strictEqual(result, null);
  });

  it('findFiles finds matching files', () => {
    const tempDir = utils.getTempDir();
    // Create a test file
    const testFileName = `findtest-${Date.now()}.txt`;
    const testFilePath = path.join(tempDir, testFileName);
    fs.writeFileSync(testFilePath, 'test');

    try {
      const files = utils.findFiles(tempDir, '*.txt');
      const found = files.some(f => f.path.includes('findtest-'));
      assert.ok(found, 'Should find test file');
    } finally {
      fs.unlinkSync(testFilePath);
    }
  });

  it('countInFile counts occurrences', () => {
    utils.writeFile(testFile, 'foo bar foo baz foo');
    const count = utils.countInFile(testFile, /foo/g);
    assert.strictEqual(count, 3);
  });

  it('grepFile finds matching lines', () => {
    utils.writeFile(testFile, 'line 1 foo\nline 2 bar\nline 3 foo');
    const results = utils.grepFile(testFile, /foo/);
    assert.strictEqual(results.length, 2);
    assert.strictEqual(results[0].lineNumber, 1);
    assert.strictEqual(results[1].lineNumber, 3);
  });

  it('replaceInFile replaces content', () => {
    utils.writeFile(testFile, 'hello world');
    utils.replaceInFile(testFile, 'world', 'universe');
    const content = utils.readFile(testFile);
    assert.strictEqual(content, 'hello universe');
  });
});

describe('Hook I/O', () => {
  it('log writes to stderr', () => {
    // Just verify it doesn't throw
    assert.doesNotThrow(() => utils.log('test message'));
  });

  it('output writes to stdout', () => {
    // Just verify it doesn't throw
    assert.doesNotThrow(() => utils.output('test'));
    assert.doesNotThrow(() => utils.output({ key: 'value' }));
  });

  it('readStdinJson is async function', () => {
    assert.ok(utils.readStdinJson.constructor.name === 'AsyncFunction');
  });
});

describe('System functions', () => {
  it('commandExists returns true for node', () => {
    assert.strictEqual(utils.commandExists('node'), true);
  });

  it('commandExists returns false for nonexistent command', () => {
    assert.strictEqual(utils.commandExists('nonexistent_command_xyz123'), false);
  });

  it('runCommand returns success for valid command', () => {
    const result = utils.runCommand('echo hello');
    assert.strictEqual(result.success, true);
    assert.strictEqual(result.output, 'hello');
  });

  it('runCommand returns failure for invalid command', () => {
    const result = utils.runCommand('nonexistent_command_xyz123');
    assert.strictEqual(result.success, false);
  });

  it('isGitRepo returns boolean', () => {
    const result = utils.isGitRepo();
    assert.ok(typeof result === 'boolean');
  });

  it('getGitModifiedFiles returns array', () => {
    const files = utils.getGitModifiedFiles();
    assert.ok(Array.isArray(files));
  });
});
