/**
 * Unit tests for package-manager.js
 * Uses Node.js built-in test runner (node --test)
 */

const { describe, it, before, after } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const pm = require('./package-manager.js');

describe('PACKAGE_MANAGERS', () => {
  it('contains npm, pnpm, yarn, bun', () => {
    assert.ok(pm.PACKAGE_MANAGERS.npm);
    assert.ok(pm.PACKAGE_MANAGERS.pnpm);
    assert.ok(pm.PACKAGE_MANAGERS.yarn);
    assert.ok(pm.PACKAGE_MANAGERS.bun);
  });

  it('each PM has required properties', () => {
    for (const pmName of Object.keys(pm.PACKAGE_MANAGERS)) {
      const config = pm.PACKAGE_MANAGERS[pmName];
      assert.ok(config.name, `${pmName} should have name`);
      assert.ok(config.lockFile, `${pmName} should have lockFile`);
      assert.ok(config.installCmd, `${pmName} should have installCmd`);
      assert.ok(config.runCmd, `${pmName} should have runCmd`);
      assert.ok(config.execCmd, `${pmName} should have execCmd`);
      assert.ok(config.testCmd, `${pmName} should have testCmd`);
      assert.ok(config.buildCmd, `${pmName} should have buildCmd`);
      assert.ok(config.devCmd, `${pmName} should have devCmd`);
    }
  });
});

describe('DETECTION_PRIORITY', () => {
  it('contains all package managers', () => {
    assert.ok(pm.DETECTION_PRIORITY.includes('npm'));
    assert.ok(pm.DETECTION_PRIORITY.includes('pnpm'));
    assert.ok(pm.DETECTION_PRIORITY.includes('yarn'));
    assert.ok(pm.DETECTION_PRIORITY.includes('bun'));
  });
});

describe('getPackageManager', () => {
  it('returns object with name, config, source', () => {
    const result = pm.getPackageManager();
    assert.ok(typeof result.name === 'string');
    assert.ok(typeof result.config === 'object');
    assert.ok(typeof result.source === 'string');
  });

  it('config contains required commands', () => {
    const result = pm.getPackageManager();
    assert.ok(result.config.installCmd);
    assert.ok(result.config.runCmd);
    assert.ok(result.config.testCmd);
  });

  it('source is one of valid values', () => {
    const result = pm.getPackageManager();
    const validSources = ['environment', 'project-config', 'package.json', 'lock-file', 'global-config', 'fallback', 'default'];
    assert.ok(validSources.includes(result.source));
  });
});

describe('getAvailablePackageManagers', () => {
  it('returns array', () => {
    const available = pm.getAvailablePackageManagers();
    assert.ok(Array.isArray(available));
  });

  it('npm should be available (comes with Node.js)', () => {
    const available = pm.getAvailablePackageManagers();
    assert.ok(available.includes('npm'));
  });
});

describe('detectFromLockFile', () => {
  let tempDir;

  before(() => {
    tempDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'pm-test-'));
  });

  after(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('returns null for empty directory', () => {
    const result = pm.detectFromLockFile(tempDir);
    assert.strictEqual(result, null);
  });

  it('detects npm from package-lock.json', () => {
    fs.writeFileSync(path.join(tempDir, 'package-lock.json'), '{}');
    const result = pm.detectFromLockFile(tempDir);
    assert.strictEqual(result, 'npm');
    fs.unlinkSync(path.join(tempDir, 'package-lock.json'));
  });

  it('detects pnpm from pnpm-lock.yaml', () => {
    fs.writeFileSync(path.join(tempDir, 'pnpm-lock.yaml'), 'lockfileVersion: 5');
    const result = pm.detectFromLockFile(tempDir);
    assert.strictEqual(result, 'pnpm');
    fs.unlinkSync(path.join(tempDir, 'pnpm-lock.yaml'));
  });
});

describe('detectFromPackageJson', () => {
  let tempDir;

  before(() => {
    tempDir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'pm-test-'));
  });

  after(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('returns null for missing package.json', () => {
    const result = pm.detectFromPackageJson(tempDir);
    assert.strictEqual(result, null);
  });

  it('detects pnpm from packageManager field', () => {
    fs.writeFileSync(path.join(tempDir, 'package.json'), JSON.stringify({
      name: 'test',
      packageManager: 'pnpm@8.6.0'
    }));
    const result = pm.detectFromPackageJson(tempDir);
    assert.strictEqual(result, 'pnpm');
    fs.unlinkSync(path.join(tempDir, 'package.json'));
  });
});

describe('getRunCommand', () => {
  it('returns install command for "install"', () => {
    const cmd = pm.getRunCommand('install');
    assert.ok(cmd.includes('install'));
  });

  it('returns test command for "test"', () => {
    const cmd = pm.getRunCommand('test');
    assert.ok(cmd.includes('test'));
  });

  it('returns build command for "build"', () => {
    const cmd = pm.getRunCommand('build');
    assert.ok(cmd.includes('build'));
  });

  it('returns dev command for "dev"', () => {
    const cmd = pm.getRunCommand('dev');
    assert.ok(cmd.includes('dev'));
  });

  it('returns run command for custom script', () => {
    const cmd = pm.getRunCommand('custom-script');
    assert.ok(cmd.includes('custom-script'));
  });
});

describe('getExecCommand', () => {
  it('returns command for binary', () => {
    const cmd = pm.getExecCommand('prettier');
    assert.ok(cmd.includes('prettier'));
  });

  it('includes arguments when provided', () => {
    const cmd = pm.getExecCommand('prettier', '--write .');
    assert.ok(cmd.includes('--write .'));
  });
});

describe('getSelectionPrompt', () => {
  it('returns string with available PMs', () => {
    const prompt = pm.getSelectionPrompt();
    assert.ok(typeof prompt === 'string');
    assert.ok(prompt.includes('npm'));
  });

  it('includes instructions', () => {
    const prompt = pm.getSelectionPrompt();
    assert.ok(prompt.includes('CLAUDE_PACKAGE_MANAGER'));
  });
});

describe('getCommandPattern', () => {
  it('returns valid regex pattern for dev', () => {
    const pattern = pm.getCommandPattern('dev');
    const regex = new RegExp(pattern);
    assert.ok(regex.test('npm run dev'));
    assert.ok(regex.test('pnpm dev'));
    assert.ok(regex.test('yarn dev'));
    assert.ok(regex.test('bun run dev'));
  });

  it('returns valid regex pattern for install', () => {
    const pattern = pm.getCommandPattern('install');
    const regex = new RegExp(pattern);
    assert.ok(regex.test('npm install'));
    assert.ok(regex.test('pnpm install'));
    assert.ok(regex.test('yarn'));
    assert.ok(regex.test('bun install'));
  });

  it('returns valid regex pattern for test', () => {
    const pattern = pm.getCommandPattern('test');
    const regex = new RegExp(pattern);
    assert.ok(regex.test('npm test'));
    assert.ok(regex.test('pnpm test'));
  });

  it('returns valid regex pattern for custom action', () => {
    const pattern = pm.getCommandPattern('lint');
    const regex = new RegExp(pattern);
    assert.ok(regex.test('npm run lint'));
    assert.ok(regex.test('yarn lint'));
  });
});
