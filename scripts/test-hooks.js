#!/usr/bin/env node
/**
 * Integration test for all hooks
 *
 * Validates:
 * 1. hooks.json is valid JSON
 * 2. All referenced scripts exist
 * 3. All hooks run without crashing
 * 4. All hooks exit 0 (graceful degradation)
 */

const fs = require('fs');
const path = require('path');
const { execSync, spawnSync } = require('child_process');

const HOOKS_JSON_PATH = path.join(process.env.HOME, '.claude', 'hooks', 'hooks.json');
const SCRIPTS_DIR = path.join(process.env.HOME, '.claude', 'scripts', 'hooks');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    passed++;
  } catch (err) {
    console.error(`✗ ${name}`);
    console.error(`  Error: ${err.message}`);
    failed++;
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// Test 1: hooks.json exists and is valid JSON
test('hooks.json exists', () => {
  assert(fs.existsSync(HOOKS_JSON_PATH), 'hooks.json not found');
});

let hooksConfig;
test('hooks.json is valid JSON', () => {
  const content = fs.readFileSync(HOOKS_JSON_PATH, 'utf8');
  hooksConfig = JSON.parse(content);
  assert(typeof hooksConfig === 'object', 'hooks.json should be an object');
});

test('hooks.json has $schema', () => {
  assert(hooksConfig.$schema, 'hooks.json should have $schema for IDE support');
});

test('hooks.json has hooks object', () => {
  assert(hooksConfig.hooks, 'hooks.json should have hooks object');
  assert(typeof hooksConfig.hooks === 'object', 'hooks should be an object');
});

// Test 2: All hook events are present
const expectedEvents = ['PreToolUse', 'PostToolUse', 'PreCompact', 'SessionStart', 'SessionEnd', 'Stop'];
for (const event of expectedEvents) {
  test(`hooks.json has ${event} event`, () => {
    assert(Array.isArray(hooksConfig.hooks[event]), `${event} should be an array`);
  });
}

// Test 3: Hook counts match expectations
test('PreToolUse has 5 hooks', () => {
  assert(hooksConfig.hooks.PreToolUse.length === 5, `Expected 5, got ${hooksConfig.hooks.PreToolUse.length}`);
});

test('PostToolUse has 4 hooks', () => {
  assert(hooksConfig.hooks.PostToolUse.length === 4, `Expected 4, got ${hooksConfig.hooks.PostToolUse.length}`);
});

test('SessionEnd has 2 hooks', () => {
  assert(hooksConfig.hooks.SessionEnd.length === 2, `Expected 2, got ${hooksConfig.hooks.SessionEnd.length}`);
});

// Test 4: External script hooks exist
const externalHooks = [
  'session-start.js',
  'session-end.js',
  'pre-compact.js',
  'suggest-compact.js',
  'evaluate-session.js'
];

for (const hookFile of externalHooks) {
  test(`Hook script exists: ${hookFile}`, () => {
    const scriptPath = path.join(SCRIPTS_DIR, hookFile);
    assert(fs.existsSync(scriptPath), `Script not found: ${scriptPath}`);
  });
}

// Test 5: Hook scripts run without error
function runHook(scriptPath, input = '{}') {
  const result = spawnSync('node', [scriptPath], {
    input,
    encoding: 'utf8',
    timeout: 5000,
    env: { ...process.env, HOME: process.env.HOME }
  });
  return result;
}

test('session-start.js runs and exits 0', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'session-start.js'));
  assert(result.status === 0, `Exit code: ${result.status}, stderr: ${result.stderr}`);
});

test('session-end.js runs and exits 0', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'session-end.js'), '{"session_id":"test"}');
  assert(result.status === 0, `Exit code: ${result.status}, stderr: ${result.stderr}`);
});

test('pre-compact.js runs and exits 0', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'pre-compact.js'));
  assert(result.status === 0, `Exit code: ${result.status}, stderr: ${result.stderr}`);
});

test('suggest-compact.js runs and exits 0', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'suggest-compact.js'), '{"tool_name":"Edit"}');
  assert(result.status === 0, `Exit code: ${result.status}, stderr: ${result.stderr}`);
});

test('evaluate-session.js runs and exits 0', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'evaluate-session.js'));
  assert(result.status === 0, `Exit code: ${result.status}, stderr: ${result.stderr}`);
});

// Test 6: Hooks handle invalid input gracefully
test('session-end.js handles invalid JSON gracefully', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'session-end.js'), 'invalid json');
  // Should still exit 0 (graceful degradation)
  assert(result.status === 0, `Should exit 0 on invalid input, got ${result.status}`);
});

test('suggest-compact.js handles empty input gracefully', () => {
  const result = runHook(path.join(SCRIPTS_DIR, 'suggest-compact.js'), '');
  assert(result.status === 0, `Should exit 0 on empty input, got ${result.status}`);
});

// Test 7: Library dependencies work
test('utils.js can be required', () => {
  const utilsPath = path.join(process.env.HOME, '.claude', 'scripts', 'lib', 'utils.js');
  require(utilsPath);
});

test('package-manager.js can be required', () => {
  const pmPath = path.join(process.env.HOME, '.claude', 'scripts', 'lib', 'package-manager.js');
  require(pmPath);
});

// Summary
console.log('\n-------------------');
console.log(`Tests: ${passed + failed} total`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log('-------------------');

process.exit(failed > 0 ? 1 : 0);
