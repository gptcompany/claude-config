# ECC Integration Architecture

**Document:** ECC Agent Integration Guide
**Version:** 1.0
**Date:** 2026-01-24

## Overview

This document describes how ECC (everything-claude-code) agents are integrated into our 14-dimension ValidationOrchestrator. ECC provides specialized agents for verification tasks that complement our existing validators.

**Why integrate ECC agents:**
- Specialized domain knowledge (E2E testing, TDD enforcement, security review)
- Battle-tested patterns from real-world Claude Code usage
- CLI tool orchestration expertise

**Integration approach:**
- ECC agents (markdown prompts) become Python validators
- Validators invoke the same CLI tools ECC agents would use
- Results flow through our tiered validation system

## Tier Mapping

ECC's 6-phase verification loop maps to our 3-tier system:

| ECC Phase | Our Tier | Our Dimension | Notes |
|-----------|----------|---------------|-------|
| Build Check | Tier 1 | `code_quality` | Build portion (compilation, syntax) |
| Type Check | Tier 1 | `type_safety` | Direct mapping |
| Lint Check | Tier 1 | `code_quality` | Lint portion (style, complexity) |
| Test Suite | Tier 1 | `coverage` + `e2e_validation` | Split: unit → coverage, E2E → new dimension |
| Security | Tier 1 | `security` | Enhanced with OWASP checks |
| Diff Review | Tier 2 | `design_principles` + `architecture` | Code review patterns |

**Key difference:** ECC runs phases sequentially (stop on first failure). We run tiers in parallel within each tier level, then gate on tier completion.

## New Dimensions

ECC integration adds 3 new validation dimensions:

### e2e_validation (Tier 1/2)

**Source:** `e2e-runner` agent
**Purpose:** Playwright E2E test execution
**Tier:** BLOCKER for critical flows, WARNING for non-critical

Validates:
- E2E test suite passes
- No flaky tests (or quarantined appropriately)
- Screenshot/trace artifacts captured on failure

### tdd_compliance (Tier 2)

**Source:** `tdd-guide` agent
**Purpose:** TDD workflow enforcement
**Tier:** WARNING

Validates:
- Test-first development pattern followed
- Test coverage for new code
- RED-GREEN-REFACTOR cycle adherence

### eval_metrics (Tier 3)

**Source:** `eval-harness` skill
**Purpose:** pass@k reliability metrics
**Tier:** MONITOR

Tracks:
- pass@1, pass@5, pass@10 metrics
- Eval suite execution results
- Reliability trends over time

## Adapter Pattern

ECC agents are markdown prompt files designed for Claude sessions. We adapt them as Python validators:

```
ECC Agent (markdown)          →  Python Validator
─────────────────────────────────────────────────
Natural language prompts      →  Class with validate() method
"Run npx playwright test"     →  subprocess.run(["npx", "playwright", "test"])
Parse output manually         →  _parse_json_output() helper
Decision logic in prompt      →  Python conditionals
```

### Example Adapter

```python
from validators.ecc import ECCValidatorBase

class E2EValidator(ECCValidatorBase):
    """Wraps e2e-runner agent patterns."""

    dimension = "e2e_validation"
    tier = ValidationTier.BLOCKER
    agent = "e2e-runner"

    async def validate(self) -> ValidationResult:
        # 1. Check preconditions (same as agent would)
        if not Path("playwright.config.ts").exists():
            return self._skip_result("No Playwright config")

        # 2. Run CLI tool (same command agent uses)
        result = await self._run_tool(
            ["npx", "playwright", "test", "--reporter=json"]
        )

        # 3. Parse output (same parsing logic)
        data = self._parse_json_output(result.stdout)

        # 4. Return structured result
        return ValidationResult(...)
```

## Integration Points

### VALIDATOR_REGISTRY

ECC validators register in the orchestrator's `VALIDATOR_REGISTRY`:

```python
VALIDATOR_REGISTRY: dict[str, type[BaseValidator]] = {
    # Existing validators...
    "e2e_validation": E2EValidator,
    "tdd_compliance": TDDValidator,
    "eval_metrics": EvalValidator,
}
```

### Config-Driven Enablement

New dimensions are enabled via project config:

```json
{
  "dimensions": {
    "e2e_validation": { "enabled": true, "tier": 1 },
    "tdd_compliance": { "enabled": true, "tier": 2 },
    "eval_metrics": { "enabled": false, "tier": 3 }
  }
}
```

### Agent Spawning Suggestions

When validation fails, results include the source agent for fix guidance:

```python
ValidationResult(
    passed=False,
    message="E2E tests failed: 3 failures",
    agent="e2e-runner",  # Suggests spawning this agent
)
```

## Source Reference

Original ECC agent files:

| Agent | Path | LOC |
|-------|------|-----|
| e2e-runner | `/media/sam/1TB/everything-claude-code/agents/e2e-runner.md` | 708 |
| security-reviewer | `/media/sam/1TB/everything-claude-code/agents/security-reviewer.md` | 545 |
| code-reviewer | `/media/sam/1TB/everything-claude-code/agents/code-reviewer.md` | 104 |
| tdd-guide | `/media/sam/1TB/everything-claude-code/agents/tdd-guide.md` | 251 |
| eval-harness | `/media/sam/1TB/everything-claude-code/skills/eval-harness/` | 221 |

## Anti-Patterns

Avoid these common mistakes:

1. **Porting prompts as code**: Extract CLI commands, don't translate natural language
2. **Breaking tier parallelism**: Keep dimensions running in parallel within tiers
3. **Duplicating validators**: Enhance existing validators, don't create duplicates
4. **Over-engineering skills**: `/validate` is a thin wrapper, not an orchestration layer

---

*Phase: 13-ecc-integration*
*Plan: 01*
