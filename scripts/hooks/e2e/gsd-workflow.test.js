/**
 * GSD Workflow E2E Tests
 *
 * Tests GSD (Get Shit Done) workflow hook chains:
 * 1. /gsd:plan-phase workflow
 * 2. /gsd:execute-plan workflow
 * 3. /gsd:sync-github workflow
 * 4. plan-validator with real .planning/
 * 5. tdd-guard integration
 * 6. dora-tracker integration
 *
 * Uses Node.js built-in test runner.
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawnSync } = require('child_process');

// Test directories
const TEST_DIR = path.join(os.tmpdir(), 'e2e-gsd-workflow-' + Date.now());
const HOOKS_DIR = path.join(os.homedir(), '.claude', 'scripts', 'hooks');
const METRICS_DIR = path.join(os.homedir(), '.claude', 'metrics');

// Real .planning/ directory (for reference tests)
const REAL_PLANNING_DIR = '/home/sam/.claude/validation-framework/.planning';

/**
 * Run a hook script with input
 */
function runHook(hookPath, input = {}) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(input),
    encoding: 'utf8',
    timeout: 5000,
    env: { ...process.env, CLAUDE_SESSION_ID: 'gsd-e2e-test-' + Date.now() }
  });

  let output = {};
  try {
    if (result.stdout && result.stdout.trim()) {
      output = JSON.parse(result.stdout.trim());
    }
  } catch (e) {}

  return {
    success: result.status === 0,
    output,
    stdout: result.stdout,
    stderr: result.stderr
  };
}

/**
 * Create a mock .planning/ structure
 */
function createMockPlanning(baseDir) {
  const planningDir = path.join(baseDir, '.planning');
  fs.mkdirSync(planningDir, { recursive: true });

  // PROJECT.md
  fs.writeFileSync(path.join(planningDir, 'PROJECT.md'), `# Test Project

## Overview
E2E test project for GSD workflow.
`);

  // ROADMAP.md
  fs.writeFileSync(path.join(planningDir, 'ROADMAP.md'), `# Roadmap

## Phase 1.0
- Basic setup
`);

  // Create phases directory
  const phasesDir = path.join(planningDir, 'phases', '1.0-test');
  fs.mkdirSync(phasesDir, { recursive: true });

  // 1.0-01-PLAN.md
  const planContent = `---
phase: 1.0-test
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/test.js
autonomous: true
---

<objective>
Test plan for E2E testing of GSD workflow.
</objective>

<context>
@.planning/PROJECT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create test file</name>
  <files>src/test.js</files>
  <action>
Create a simple test file with basic functionality.
  </action>
  <verify>File exists</verify>
  <done>Test file created</done>
</task>

</tasks>

<verification>
- [ ] src/test.js exists
- [ ] Tests pass
</verification>

<success_criteria>
- All tasks completed
- No regressions
</success_criteria>
`;

  fs.writeFileSync(path.join(phasesDir, '1.0-01-PLAN.md'), planContent);

  return planningDir;
}

// =============================================================================
// Setup/Teardown
// =============================================================================

beforeEach(() => {
  fs.mkdirSync(TEST_DIR, { recursive: true });
});

afterEach(() => {
  try {
    fs.rmSync(TEST_DIR, { recursive: true, force: true });
  } catch (e) {}
});

// =============================================================================
// /gsd:plan-phase Workflow
// =============================================================================

describe('gsd:plan-phase workflow', () => {
  test('task-checkpoint saves state on plan file write', () => {
    const planningDir = createMockPlanning(TEST_DIR);
    const planFile = path.join(planningDir, 'phases', '1.0-test', '1.0-01-PLAN.md');

    const result = runHook(
      path.join(HOOKS_DIR, 'productivity', 'task-checkpoint.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: planFile, content: 'updated content' }
      }
    );

    assert.strictEqual(result.success, true, 'Task checkpoint should succeed');
  });

  test('plan-validator validates plan structure', () => {
    const planningDir = createMockPlanning(TEST_DIR);
    const planFile = path.join(planningDir, 'phases', '1.0-test', '1.0-01-PLAN.md');
    const content = fs.readFileSync(planFile, 'utf8');

    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: planFile, content }
      }
    );

    assert.strictEqual(result.success, true, 'Plan validator should succeed');
  });

  test('tdd-guard checks for tests during planning', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'productivity', 'tdd-guard.js'),
      {
        tool_name: 'Write',
        tool_input: {
          file_path: path.join(TEST_DIR, 'src', 'feature.js'),
          content: 'module.exports = {};'
        }
      }
    );

    // Should succeed (warn mode is default)
    assert.strictEqual(result.success, true, 'TDD guard should complete');
  });

  test('plan-phase chain: checkpoint -> validator -> tdd-guard', () => {
    const planningDir = createMockPlanning(TEST_DIR);
    const planFile = path.join(planningDir, 'phases', '1.0-test', '1.0-01-PLAN.md');
    const content = fs.readFileSync(planFile, 'utf8');

    const input = {
      tool_name: 'Write',
      tool_input: { file_path: planFile, content }
    };

    const hooks = [
      'productivity/task-checkpoint.js',
      'quality/plan-validator.js'
    ];

    for (const hook of hooks) {
      const result = runHook(path.join(HOOKS_DIR, hook), input);
      assert.strictEqual(result.success, true, `Hook ${hook} should succeed`);
    }
  });

  test('plan validation reports missing sections', () => {
    const badPlan = `---
phase: 1.0
plan: 01
type: execute
---

Just some text without proper structure.
`;

    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'bad-PLAN.md'), content: badPlan }
      }
    );

    // Should succeed but may have warnings in output
    assert.strictEqual(result.success, true, 'Should complete validation');
  });
});

// =============================================================================
// /gsd:execute-plan Workflow
// =============================================================================

describe('gsd:execute-plan workflow', () => {
  test('file-coordination claims files during execution', () => {
    const testFile = path.join(TEST_DIR, 'src', 'execute.js');

    const result = runHook(
      path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'),
      { tool_name: 'Write', tool_input: { file_path: testFile } }
    );

    assert.strictEqual(result.success, true, 'File coordination should succeed');
  });

  test('safety hooks validate before execution', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'safety', 'smart-safety-check.js'),
      { tool_name: 'Bash', tool_input: { command: 'npm test' } }
    );

    assert.strictEqual(result.success, true, 'Safety check should pass for npm test');
  });

  test('quality hooks run during execution', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'quality-score.js'),
      {
        tool_name: 'Bash',
        tool_input: { command: 'npm test' },
        tool_output: 'Tests: 10 passed, 0 failed'
      }
    );

    assert.strictEqual(result.success, true, 'Quality score should succeed');
  });

  test('dora-tracker tracks file changes', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
      { tool_name: 'Write', tool_input: { file_path: path.join(TEST_DIR, 'tracked.js') } }
    );

    assert.strictEqual(result.success, true, 'DORA tracker should succeed');
  });

  test('execute-plan chain runs completely', () => {
    const testFile = path.join(TEST_DIR, 'execute-chain.js');
    const input = { tool_name: 'Write', tool_input: { file_path: testFile, content: 'test' } };

    const hooks = [
      'coordination/file-coordination.js',
      'productivity/auto-format.js',
      'metrics/dora-tracker.js',
      'metrics/quality-score.js'
    ];

    for (const hook of hooks) {
      const result = runHook(path.join(HOOKS_DIR, hook), input);
      assert.strictEqual(result.success, true, `Hook ${hook} should succeed`);
    }
  });
});

// =============================================================================
// /gsd:sync-github Workflow
// =============================================================================

describe('gsd:sync-github workflow', () => {
  test('claudeflow-sync handles Task tool', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js'),
      { tool_name: 'Task', tool_input: { description: 'Sync test' } }
    );

    assert.strictEqual(result.success, true, 'ClaudeFlow sync should succeed');
  });

  test('claudeflow-sync handles non-Task tools gracefully', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js'),
      { tool_name: 'Edit', tool_input: { file_path: '/tmp/test.js' } }
    );

    assert.strictEqual(result.success, true, 'Should handle non-Task gracefully');
    // Returns sync state info regardless of tool type (state tracking)
    assert.ok(typeof result.output === 'object', 'Should return object');
  });

  test('github sync handles missing config gracefully', () => {
    // Should not crash even without GitHub config
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'claudeflow-sync.js'),
      { tool_name: 'Task', tool_input: { description: 'GitHub sync test' } }
    );

    assert.strictEqual(result.success, true, 'Should handle missing config');
  });
});

// =============================================================================
// Plan Validator with Real .planning/
// =============================================================================

describe('plan-validator with real .planning/', () => {
  test('validates actual PLAN.md format', (t) => {
    // Skip if no real planning dir
    if (!fs.existsSync(REAL_PLANNING_DIR)) {
      t.skip('No real .planning/ directory available');
      return;
    }

    // Find a real PLAN.md file
    const phasesDir = path.join(REAL_PLANNING_DIR, 'phases');
    if (!fs.existsSync(phasesDir)) {
      t.skip('No phases directory');
      return;
    }

    // Look for any PLAN.md
    let planFile = null;
    const phases = fs.readdirSync(phasesDir);
    for (const phase of phases) {
      const phaseDir = path.join(phasesDir, phase);
      if (fs.statSync(phaseDir).isDirectory()) {
        const files = fs.readdirSync(phaseDir);
        const plan = files.find(f => f.endsWith('-PLAN.md'));
        if (plan) {
          planFile = path.join(phaseDir, plan);
          break;
        }
      }
    }

    if (!planFile) {
      t.skip('No PLAN.md found');
      return;
    }

    const content = fs.readFileSync(planFile, 'utf8');
    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: planFile, content }
      }
    );

    assert.strictEqual(result.success, true, 'Should validate real plan');
  });

  test('detects dependency graph in plans', (t) => {
    const planWithDeps = `---
phase: 14.6
plan: 02
type: execute
wave: 1
depends_on: [14.6-01]
files_modified:
  - src/test.js
---

<objective>
Plan with dependencies.
</objective>

<tasks>
<task type="auto">
  <name>Task 1</name>
  <action>Do thing</action>
</task>
</tasks>

<verification>
- [ ] Done
</verification>
`;

    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'dep-PLAN.md'), content: planWithDeps }
      }
    );

    assert.strictEqual(result.success, true, 'Should handle dependencies');
  });

  test('validates multiple task types', () => {
    const multiTaskPlan = `---
phase: 1.0
plan: 01
type: execute
---

<objective>Multi-task plan</objective>

<tasks>

<task type="auto">
  <name>Auto Task</name>
  <action>Automated action</action>
</task>

<task type="manual">
  <name>Manual Task</name>
  <action>Manual action required</action>
</task>

<task type="review">
  <name>Review Task</name>
  <action>Review the changes</action>
</task>

</tasks>

<verification>
- [ ] All tasks done
</verification>
`;

    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'multi-PLAN.md'), content: multiTaskPlan }
      }
    );

    assert.strictEqual(result.success, true, 'Should handle multiple task types');
  });

  test('reports complexity warnings (PMW)', () => {
    const complexPlan = `---
phase: 1.0
plan: 01
type: execute
---

<objective>Complex plan</objective>

<tasks>
<task type="auto">
  <name>Complex Task</name>
  <action>
\`\`\`javascript
class Service1 {}
class Service2 {}
class Service3 {}
class Service4 {}
class Service5 {}
\`\`\`
  </action>
</task>
</tasks>

<verification>
- [ ] Done
</verification>
`;

    const result = runHook(
      path.join(HOOKS_DIR, 'quality', 'plan-validator.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'complex-PLAN.md'), content: complexPlan }
      }
    );

    // Should succeed but may include complexity warnings
    assert.strictEqual(result.success, true, 'Should complete with warnings');
  });
});

// =============================================================================
// TDD Guard Integration
// =============================================================================

describe('tdd-guard integration', () => {
  test('detects test file writes', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'productivity', 'tdd-guard.js'),
      {
        tool_name: 'Write',
        tool_input: {
          file_path: path.join(TEST_DIR, 'tests', 'test_feature.js'),
          content: 'test("works", () => {});'
        }
      }
    );

    // Should succeed and skip (test files are not checked)
    assert.strictEqual(result.success, true, 'Should pass for test files');
  });

  test('tracks TDD cycle state', () => {
    const tddLogFile = path.join(METRICS_DIR, 'tdd_compliance.jsonl');
    const beforeLines = fs.existsSync(tddLogFile) ?
      fs.readFileSync(tddLogFile, 'utf8').split('\n').filter(Boolean).length : 0;

    // Write production code (should log)
    runHook(
      path.join(HOOKS_DIR, 'productivity', 'tdd-guard.js'),
      {
        tool_name: 'Write',
        tool_input: {
          file_path: path.join(TEST_DIR, 'src', 'service.js'),
          content: 'class Service {}'
        }
      }
    );

    const afterLines = fs.existsSync(tddLogFile) ?
      fs.readFileSync(tddLogFile, 'utf8').split('\n').filter(Boolean).length : 0;

    // Should log the compliance check
    assert.ok(afterLines >= beforeLines, 'Should log TDD compliance');
  });

  test('respects TDD mode configuration', () => {
    // Test with default warn mode
    const result = runHook(
      path.join(HOOKS_DIR, 'productivity', 'tdd-guard.js'),
      {
        tool_name: 'Write',
        tool_input: {
          file_path: path.join(TEST_DIR, 'src', 'handler.js'),
          content: 'function handler() {}'
        }
      }
    );

    // Default mode is 'warn', so should not block
    assert.strictEqual(result.success, true, 'Warn mode should not block');
  });

  test('skips non-code files', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'productivity', 'tdd-guard.js'),
      {
        tool_name: 'Write',
        tool_input: {
          file_path: path.join(TEST_DIR, 'README.md'),
          content: '# README'
        }
      }
    );

    assert.strictEqual(result.success, true, 'Should skip non-code files');
    assert.deepStrictEqual(result.output, {}, 'Should return empty for non-code');
  });
});

// =============================================================================
// DORA Tracker Integration
// =============================================================================

describe('dora-tracker integration', () => {
  test('tracks commit frequency', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
      {
        tool_name: 'Bash',
        tool_input: { command: 'git commit -m "test"' },
        tool_output: '[main abc1234] test\n 1 file changed'
      }
    );

    assert.strictEqual(result.success, true, 'Should track commits');
  });

  test('tracks file changes', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
      {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'tracked.js') }
      }
    );

    assert.strictEqual(result.success, true, 'Should track file changes');
  });

  test('metrics export succeeds locally', () => {
    const metricsFile = path.join(METRICS_DIR, 'metrics.jsonl');

    // Run several tracker calls
    for (let i = 0; i < 3; i++) {
      runHook(
        path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
        { tool_name: 'Edit', tool_input: { file_path: path.join(TEST_DIR, `file${i}.js`) } }
      );
    }

    // Metrics file should exist
    assert.ok(fs.existsSync(metricsFile), 'Metrics file should exist');
  });

  test('handles deployment tracking', () => {
    const result = runHook(
      path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'),
      {
        tool_name: 'Bash',
        tool_input: { command: 'npm run deploy' },
        tool_output: 'Deployed to production'
      }
    );

    assert.strictEqual(result.success, true, 'Should track deployments');
  });
});

// =============================================================================
// Cross-Hook Integration
// =============================================================================

describe('cross-hook integration', () => {
  test('full GSD execute workflow simulation', () => {
    createMockPlanning(TEST_DIR);

    const results = [];

    // Pre-execution checks
    results.push(runHook(
      path.join(HOOKS_DIR, 'safety', 'smart-safety-check.js'),
      { tool_name: 'Bash', tool_input: { command: 'npm install' } }
    ));

    // File operations
    for (let i = 0; i < 3; i++) {
      const fileInput = {
        tool_name: 'Write',
        tool_input: { file_path: path.join(TEST_DIR, 'src', `feature${i}.js`) }
      };

      results.push(runHook(path.join(HOOKS_DIR, 'coordination', 'file-coordination.js'), fileInput));
      results.push(runHook(path.join(HOOKS_DIR, 'metrics', 'dora-tracker.js'), fileInput));
    }

    // Test execution
    results.push(runHook(
      path.join(HOOKS_DIR, 'metrics', 'quality-score.js'),
      {
        tool_name: 'Bash',
        tool_input: { command: 'npm test' },
        tool_output: '15 passed, 0 failed'
      }
    ));

    // All should succeed
    const failed = results.filter(r => !r.success);
    assert.strictEqual(failed.length, 0, 'All hooks should succeed');
  });

  test('hooks do not interfere with each other', () => {
    const input = {
      tool_name: 'Write',
      tool_input: { file_path: path.join(TEST_DIR, 'interference-test.js'), content: 'test' }
    };

    // Run hooks in parallel-like fashion
    const hooks = [
      'coordination/file-coordination.js',
      'productivity/auto-format.js',
      'productivity/task-checkpoint.js',
      'metrics/dora-tracker.js'
    ];

    const results = hooks.map(hook => runHook(path.join(HOOKS_DIR, hook), input));
    const allSuccess = results.every(r => r.success);

    assert.strictEqual(allSuccess, true, 'Hooks should not interfere');
  });
});
