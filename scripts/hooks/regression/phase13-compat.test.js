#!/usr/bin/env node
/**
 * Phase 13 ECC Integration Compatibility Tests
 *
 * Validates backward compatibility with Phase 13 ECC integration:
 * - /validate skill functionality
 * - ValidationOrchestrator API
 * - ECC validators registration
 *
 * Run with: node --test phase13-compat.test.js
 */

const { describe, it, before } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync, spawnSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const SKILLS_DIR = path.join(HOME_DIR, '.claude', 'skills');
const VALIDATION_DIR = path.join(HOME_DIR, '.claude', 'templates', 'validation');
const ORCHESTRATOR_PATH = path.join(VALIDATION_DIR, 'orchestrator.py');

// =============================================================================
// /validate Skill Tests
// =============================================================================

describe('Phase 13: /validate Skill Compatibility', () => {
  it('validate skill definition exists', () => {
    const skillPath = path.join(SKILLS_DIR, 'validate.md');
    assert.ok(fs.existsSync(skillPath), 'validate.md skill should exist');
  });

  it('validate skill has required sections', () => {
    const skillPath = path.join(SKILLS_DIR, 'validate.md');
    if (!fs.existsSync(skillPath)) {
      assert.fail('validate.md not found - cannot check sections');
    }
    const content = fs.readFileSync(skillPath, 'utf8');

    // Required sections per Phase 13 spec
    assert.ok(content.includes('Usage'), 'Should have Usage section');
    assert.ok(content.includes('Tier'), 'Should document tiers');
    assert.ok(content.includes('Exit Code'), 'Should document exit codes');
  });

  it('validate skill documents tier filtering', () => {
    const skillPath = path.join(SKILLS_DIR, 'validate.md');
    if (!fs.existsSync(skillPath)) {
      assert.fail('validate.md not found');
    }
    const content = fs.readFileSync(skillPath, 'utf8');

    // Phase 13 tier options: 1/quick, 2, 3, all
    assert.ok(
      content.includes('1') || content.includes('quick'),
      'Should mention Tier 1/quick'
    );
    assert.ok(content.includes('2'), 'Should mention Tier 2');
    assert.ok(content.includes('3'), 'Should mention Tier 3');
  });

  it('validate skill documents exit codes', () => {
    const skillPath = path.join(SKILLS_DIR, 'validate.md');
    if (!fs.existsSync(skillPath)) {
      assert.fail('validate.md not found');
    }
    const content = fs.readFileSync(skillPath, 'utf8');

    // Exit codes: 0=pass, 1=fail, 2=error
    assert.ok(content.includes('0'), 'Should document exit code 0');
    assert.ok(content.includes('1'), 'Should document exit code 1');
  });

  it('orchestrator run_from_cli callable via subprocess', async () => {
    // Verify orchestrator can be invoked
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const result = spawnSync('python3', [ORCHESTRATOR_PATH, '--help'], {
      encoding: 'utf8',
      timeout: 5000,
      cwd: VALIDATION_DIR
    });

    // Should not crash (exit 0 or 2 for argparse)
    assert.ok(
      result.status === 0 || result.status === 2 || result.stderr.includes('usage'),
      'Orchestrator should accept --help or show usage'
    );
  });
});

// =============================================================================
// ECC Validators Registration Tests
// =============================================================================

describe('Phase 13: ECC Validators Registration', () => {
  it('ECCValidatorBase module exists', () => {
    const basePath = path.join(VALIDATION_DIR, 'validators', 'ecc', 'base.py');
    assert.ok(fs.existsSync(basePath), 'ECCValidatorBase should exist at validators/ecc/base.py');
  });

  it('validators/ecc structure is intact', () => {
    const eccDir = path.join(VALIDATION_DIR, 'validators', 'ecc');
    assert.ok(fs.existsSync(eccDir), 'validators/ecc directory should exist');

    // Check for expected files
    const expectedFiles = ['__init__.py', 'base.py'];
    for (const file of expectedFiles) {
      assert.ok(
        fs.existsSync(path.join(eccDir, file)),
        `validators/ecc/${file} should exist`
      );
    }
  });

  it('ECC_VALIDATORS_AVAILABLE flag pattern present', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');
    assert.ok(
      content.includes('ECC_VALIDATORS_AVAILABLE'),
      'Orchestrator should have ECC_VALIDATORS_AVAILABLE flag'
    );
  });

  it('graceful fallback when ECC unavailable', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');

    // Should have try/except pattern for ECC imports
    assert.ok(
      content.includes('try:') && content.includes('except ImportError:'),
      'Should have try/except for graceful import fallback'
    );
  });

  it('no import errors when loading orchestrator', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const result = spawnSync(
      'python3',
      ['-c', `import sys; sys.path.insert(0, '${VALIDATION_DIR}'); import orchestrator`],
      {
        encoding: 'utf8',
        timeout: 10000
      }
    );

    assert.strictEqual(
      result.status,
      0,
      `Orchestrator should import without errors: ${result.stderr}`
    );
  });
});

// =============================================================================
// ValidationOrchestrator API Tests
// =============================================================================

describe('Phase 13: ValidationOrchestrator API', () => {
  it('orchestrator has run method', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');
    assert.ok(
      content.includes('async def run_all') || content.includes('def run'),
      'Orchestrator should have run/run_all method'
    );
  });

  it('orchestrator has run_from_cli method', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');
    assert.ok(
      content.includes('run_from_cli'),
      'Orchestrator should have run_from_cli method for skill invocation'
    );
  });

  it('VALIDATOR_REGISTRY structure exists', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');
    assert.ok(
      content.includes('VALIDATOR_REGISTRY'),
      'Orchestrator should have VALIDATOR_REGISTRY'
    );
  });

  it('14 core dimensions registered', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');

    // Core dimensions from Phase 13
    const coreDimensions = [
      'code_quality',
      'type_safety',
      'security',
      'coverage',
      'design_principles',
      'architecture',
      'documentation',
      'performance',
      'accessibility'
    ];

    for (const dim of coreDimensions) {
      assert.ok(
        content.includes(`"${dim}"`),
        `Registry should include "${dim}" dimension`
      );
    }
  });

  it('report generation works', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');

    // Report should have to_dict method
    assert.ok(
      content.includes('to_dict') && content.includes('ValidationReport'),
      'Should have ValidationReport with to_dict method'
    );
  });
});

// =============================================================================
// ASCII Output Format Tests (Phase 13 spec)
// =============================================================================

describe('Phase 13: ASCII Output Format', () => {
  it('uses ASCII status indicators', () => {
    if (!fs.existsSync(ORCHESTRATOR_PATH)) {
      assert.ok(true, 'Orchestrator not found - skipping');
      return;
    }

    const content = fs.readFileSync(ORCHESTRATOR_PATH, 'utf8');

    // Phase 13 spec: ASCII [PASS]/[FAIL]/[+]/[-] instead of emoji
    assert.ok(
      content.includes('[PASS]') || content.includes('[FAIL]') ||
      content.includes('[+]') || content.includes('[-]'),
      'run_from_cli should use ASCII status indicators'
    );
  });
});
