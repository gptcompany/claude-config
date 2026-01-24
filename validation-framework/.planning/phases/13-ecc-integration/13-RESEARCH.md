# Phase 13: ECC Full Integration - Research

**Researched:** 2026-01-24
**Domain:** Agent orchestration, validation systems integration
**Confidence:** HIGH (direct source code audit)

<research_summary>
## Summary

Researched the ECC (everything-claude-code) repository to understand its agent architecture, skills, and verification patterns. ECC provides 9 specialized agents and 11 skills that complement our 14-dimension ValidationOrchestrator.

Key finding: ECC uses a **sequential 6-phase verification loop** (Build → Types → Lint → Tests → Security → Diff Review) while we use a **parallel 14-dimension tiered system** (Tier 1 Blockers → Tier 2 Warnings → Tier 3 Monitors). The integration approach is to port ECC agents as new validator implementations that plug into our existing `VALIDATOR_REGISTRY`.

**Primary recommendation:** Create adapter classes that wrap ECC agent prompts/logic as Python validators, maintaining our tiered execution model while gaining ECC's specialized domain knowledge (especially e2e-runner, security-reviewer, code-reviewer, tdd-guide).
</research_summary>

<standard_stack>
## Standard Stack

### ECC Components to Integrate

| Component | Type | LOC | Purpose | Integration Priority |
|-----------|------|-----|---------|---------------------|
| e2e-runner | Agent | 708 | Playwright E2E testing specialist | HIGH - fills visual/behavioral gap |
| security-reviewer | Agent | 545 | OWASP Top 10, secrets, injection detection | HIGH - enhances our SecurityValidator |
| code-reviewer | Agent | 104 | Quality/security checklist | MEDIUM - overlaps with code_quality |
| tdd-guide | Agent | 251 | TDD enforcement, test-first workflow | MEDIUM - new dimension |
| build-error-resolver | Agent | 366 | Build error diagnosis and fixes | LOW - reactive, not validation |
| verification-loop | Skill | 121 | 6-phase sequential verification | HIGH - workflow pattern |
| tdd-workflow | Skill | 409 | TDD lifecycle management | MEDIUM - methodology skill |
| coding-standards | Skill | 520 | TypeScript/React best practices | LOW - reference material |
| eval-harness | Skill | 221 | pass@k metrics, eval-driven development | HIGH - new dimension |

### Our Existing Validators (14 dimensions)

| Dimension | Tier | Status | ECC Enhancement |
|-----------|------|--------|-----------------|
| code_quality | 1 | ✅ Implemented | code-reviewer patterns |
| type_safety | 1 | ✅ Implemented | - |
| security | 1 | ✅ Implemented | security-reviewer OWASP depth |
| coverage | 1 | ✅ Implemented | tdd-workflow coverage patterns |
| design_principles | 2 | ✅ Real impl | - |
| architecture | 2 | ✅ Stub | - |
| documentation | 2 | ✅ Stub | - |
| oss_reuse | 2 | ✅ Real impl | - |
| performance | 3 | ✅ Stub | - |
| accessibility | 3 | ✅ Stub | - |
| mathematical | 3 | ✅ Real impl | - |
| api_contract | 3 | ✅ Real impl | - |
| visual | 3 | ⚪ Placeholder | e2e-runner screenshots |
| data_integrity | 3 | ⚪ Placeholder | - |

### New Dimensions from ECC

| New Dimension | Source | Tier | Purpose |
|---------------|--------|------|---------|
| e2e_validation | e2e-runner | 1/2 | Playwright E2E test execution |
| tdd_compliance | tdd-guide | 2 | TDD workflow enforcement |
| eval_metrics | eval-harness | 3 | pass@k reliability metrics |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Agent → Validator Adapter

ECC agents are markdown prompt files. We wrap their logic as Python validators.

**Structure:**
```python
# validators/ecc/e2e_validator.py
from orchestrator import BaseValidator, ValidationResult, ValidationTier

class E2EValidator(BaseValidator):
    """
    Wraps ECC e2e-runner agent patterns.

    Runs Playwright tests, captures artifacts, manages flaky tests.
    Based on: /media/sam/1TB/everything-claude-code/agents/e2e-runner.md
    """
    dimension = "e2e_validation"
    tier = ValidationTier.BLOCKER  # Critical user flows
    agent = "e2e-runner"

    async def validate(self) -> ValidationResult:
        # 1. Check for playwright.config.ts
        # 2. Run: npx playwright test
        # 3. Parse results (pass/fail/flaky counts)
        # 4. Capture artifacts (screenshots, traces)
        # 5. Return ValidationResult with details
        ...
```

### Pattern 2: Verification Loop → Tier Mapping

ECC's 6-phase loop maps to our 3-tier system:

```
ECC Phase          Our Tier    Our Dimension
─────────────────────────────────────────────
1. Build Check  →  Tier 1   →  code_quality (build portion)
2. Type Check   →  Tier 1   →  type_safety
3. Lint Check   →  Tier 1   →  code_quality (lint portion)
4. Test Suite   →  Tier 1   →  coverage + e2e_validation
5. Security     →  Tier 1   →  security
6. Diff Review  →  Tier 2   →  design_principles + architecture
```

### Pattern 3: Skill → Command Skill

ECC skills become our `/` commands (already in our skill system):

```
ECC Skill             Our Integration
────────────────────────────────────────
verification-loop  →  /validate (unified skill)
tdd-workflow       →  /tdd:* commands (already have)
eval-harness       →  /eval:* commands (new)
coding-standards   →  Reference material only
```

### Recommended Project Structure

```
~/.claude/templates/validation/
├── orchestrator.py              # Existing 14-dim orchestrator
├── validators/
│   ├── __init__.py
│   ├── code_quality/           # Existing
│   ├── security/               # Existing
│   ├── design_principles/      # Existing (real impl)
│   ├── oss_reuse/              # Existing (real impl)
│   ├── mathematical/           # Existing (real impl)
│   ├── api_contract/           # Existing (real impl)
│   ├── multimodal/             # Existing (visual/behavioral)
│   └── ecc/                    # NEW: ECC agent adapters
│       ├── __init__.py
│       ├── e2e_validator.py     # Wraps e2e-runner
│       ├── security_enhanced.py # Enhances security with ECC patterns
│       ├── tdd_validator.py     # Wraps tdd-guide
│       └── eval_validator.py    # Wraps eval-harness
└── skills/
    └── validate.py              # Unified /validate skill
```

### Anti-Patterns to Avoid

- **Direct prompting during validation:** ECC agents are prompts for Claude sessions; validators run as Python code with subprocess calls. Don't try to invoke Claude during validation.
- **Duplicating ECC logic:** Port patterns, not prompts. Use subprocess to run tools (Playwright, ruff, bandit) that ECC agents would invoke.
- **Sequential execution for all:** Keep our parallel tier execution. Only ECC's verification-loop is sequential (and mapped to multiple dimensions).
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| E2E test execution | Custom browser automation | Playwright CLI (`npx playwright test`) | ECC e2e-runner shows the patterns; Playwright handles all the complexity |
| Security scanning | Pattern matching for secrets | gitleaks, bandit, Trivy | ECC security-reviewer just orchestrates these tools |
| Test coverage analysis | Custom AST parsing | pytest-cov, coverage.py | Standard tools with JSON output |
| Flaky test detection | Manual tracking | Playwright's `--repeat-each` + quarantine patterns from ECC | ECC documents the exact patterns |
| OWASP checks | Custom vulnerability patterns | Semgrep, ESLint security plugin | ECC security-reviewer lists the tools |

**Key insight:** ECC agents don't implement validation logic — they orchestrate existing tools and document best practices. Our validators should do the same: invoke tools via subprocess, parse their output, return structured ValidationResult.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Trying to Port Agent Prompts as Code
**What goes wrong:** Attempting to convert the natural language in agent .md files into equivalent Python logic
**Why it happens:** ECC agents look like specifications, but they're actually prompts for Claude sessions
**How to avoid:** Extract the *tool commands* from agents (e.g., `npx playwright test`, `bandit -r .`), port those as subprocess calls
**Warning signs:** Writing complex conditional logic that mirrors agent decision trees

### Pitfall 2: Breaking Tier Parallelism
**What goes wrong:** Converting ECC's sequential 6-phase loop to sequential execution in our system
**Why it happens:** ECC's verification-loop runs Build → Types → Lint → Tests → Security → Diff in order
**How to avoid:** Keep our tier-parallel model. Each phase becomes a dimension running in parallel within its tier.
**Warning signs:** Adding `if tier_1_passed:` gates that serialize execution

### Pitfall 3: Duplicating Existing Validators
**What goes wrong:** Creating e.g., `ECCSecurityValidator` that duplicates our existing `SecurityValidator`
**Why it happens:** ECC security-reviewer is comprehensive, tempting to port wholesale
**How to avoid:** Enhance existing validators with ECC patterns. Add checks, don't replace validators.
**Warning signs:** Two validators covering the same dimension (security vs ecc_security)

### Pitfall 4: Over-Engineering the /validate Skill
**What goes wrong:** Building a complex orchestration layer on top of ValidationOrchestrator
**Why it happens:** ECC verification-loop has 6 distinct phases with rich output
**How to avoid:** /validate is just a thin wrapper calling `orchestrator.run_all()` with nice terminal output
**Warning signs:** Skill file growing beyond ~100 lines
</common_pitfalls>

<code_examples>
## Code Examples

### E2E Validator (wrapping e2e-runner patterns)
```python
# Source: ECC e2e-runner.md patterns
import subprocess
import json
from pathlib import Path

class E2EValidator(BaseValidator):
    dimension = "e2e_validation"
    tier = ValidationTier.BLOCKER
    agent = "e2e-runner"

    async def validate(self) -> ValidationResult:
        start = datetime.now()

        # Check if Playwright is configured
        if not Path("playwright.config.ts").exists():
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No Playwright config (skipped)",
            )

        try:
            result = subprocess.run(
                ["npx", "playwright", "test", "--reporter=json"],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min max
            )

            # Parse Playwright JSON output
            report = json.loads(result.stdout)
            total = report.get("stats", {}).get("total", 0)
            passed = report.get("stats", {}).get("passed", 0)
            failed = report.get("stats", {}).get("failed", 0)
            flaky = report.get("stats", {}).get("flaky", 0)

            # Fail if any critical tests failed (allow flaky)
            is_passed = failed == 0

            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=is_passed,
                message=f"E2E: {passed}/{total} passed, {failed} failed, {flaky} flaky",
                details={
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "flaky": flaky,
                },
                fix_suggestion="Run: npx playwright test --debug" if not is_passed else None,
                agent=self.agent if not is_passed else None,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )
        except FileNotFoundError:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="Playwright not installed (skipped)",
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=False,
                message="E2E tests timed out (5 min)",
            )
```

### Security Validator Enhancement (from security-reviewer)
```python
# Source: ECC security-reviewer.md OWASP patterns
async def _check_owasp_top_10(self) -> list[str]:
    """Additional OWASP checks from ECC security-reviewer."""
    issues = []

    # A01: Broken Access Control
    # Check for authorization decorators
    result = subprocess.run(
        ["grep", "-r", "@requires_auth\\|@login_required", "src/"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        issues.append("A01: No authorization decorators found")

    # A03: Injection
    # Check for parameterized queries
    result = subprocess.run(
        ["grep", "-rE", "f['\"].*\\{.*\\}.*SELECT|f['\"].*\\{.*\\}.*INSERT", "src/"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        issues.append("A03: Possible SQL injection (f-string queries)")

    # A07: XSS - Check for innerHTML usage
    result = subprocess.run(
        ["grep", "-r", "innerHTML\\s*=", "src/"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        issues.append("A07: innerHTML usage detected (XSS risk)")

    return issues
```

### /validate Skill Entry Point
```python
# skills/validate.py - unified validation command
"""
Unified validation command wrapping ValidationOrchestrator.

Usage: /validate [tier]
  - /validate        Run all tiers
  - /validate 1      Run Tier 1 blockers only
  - /validate quick  Run Tier 1 only (alias)
"""

async def run_validate(args: str = "") -> str:
    from orchestrator import ValidationOrchestrator, ValidationTier

    orchestrator = ValidationOrchestrator()

    if args in ("1", "quick"):
        result = await orchestrator.run_tier(ValidationTier.BLOCKER)
        return format_tier_result(result)
    elif args == "2":
        result = await orchestrator.run_tier(ValidationTier.WARNING)
        return format_tier_result(result)
    elif args == "3":
        result = await orchestrator.run_tier(ValidationTier.MONITOR)
        return format_tier_result(result)
    else:
        report = await orchestrator.run_all()
        return format_full_report(report)
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Aspect | ECC Approach | Our Current Approach | Recommended |
|--------|--------------|---------------------|-------------|
| Execution model | Sequential 6-phase | Parallel 3-tier | Keep parallel tiers |
| Agent spawning | Markdown prompts | Python validators | Validators invoke tools |
| E2E testing | Playwright via agent | Not implemented | Add E2EValidator |
| Security depth | OWASP Top 10 checklist | bandit + gitleaks | Enhance with OWASP checks |
| TDD enforcement | tdd-workflow skill | tdd:* skills (partial) | Port full workflow |
| Eval metrics | pass@k tracking | None | Add EvalValidator |

**New patterns worth adopting:**
- **Flaky test quarantine:** ECC e2e-runner's pattern for marking `test.fixme()` and tracking quarantined tests
- **Verification report format:** ECC's structured `VERIFICATION REPORT` output format
- **OWASP-specific checks:** A01-A10 vulnerability patterns from security-reviewer

**Patterns to avoid:**
- ECC's sequential execution model (we have better parallelism)
- Markdown-based agent definitions (we use Python validators)
- Skill-per-check pattern (we use dimensions/tiers)
</sota_updates>

<open_questions>
## Open Questions

1. **Playwright CI Integration**
   - What we know: E2EValidator needs browser; Playwright handles this in CI with `npx playwright install`
   - What's unclear: How to handle projects without E2E tests (skip cleanly vs warn)
   - Recommendation: Skip if no `playwright.config.ts`, pass with info message

2. **Agent Spawning from Validators**
   - What we know: ECC agents suggest spawning specialized agents for fixes (e.g., `spawn security-reviewer`)
   - What's unclear: How to implement agent spawning in our validator results
   - Recommendation: Validators set `agent` field in result; orchestrator logs suggestion but doesn't spawn (human decides)

3. **Eval Metrics Storage**
   - What we know: ECC eval-harness tracks pass@k metrics in `.claude/evals/`
   - What's unclear: Whether to integrate with our QuestDB metrics or separate storage
   - Recommendation: Push to QuestDB via existing `_emit_metrics()` pattern
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `/media/sam/1TB/everything-claude-code/agents/` - Direct audit of 9 agent files
- `/media/sam/1TB/everything-claude-code/skills/` - Direct audit of 11 skill directories
- `/media/sam/1TB/everything-claude-code/commands/verify.md` - Verification command spec
- `~/.claude/templates/validation/orchestrator.py` - Our existing orchestrator (1,093 LOC)

### Secondary (HIGH confidence - internal reference)
- `~/.claude/templates/validation/validators/` - Our existing validator implementations
- `.planning/phases/13-ecc-integration/13-CONTEXT.md` - User vision for integration

### Research Method
- Direct source code audit (no WebSearch needed - all sources local)
- Line counts verified with `wc -l`
- Pattern extraction from markdown agent definitions
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Python validation framework + ECC markdown agents
- Ecosystem: Playwright, ruff, bandit, gitleaks, Trivy
- Patterns: Agent → Validator adapter, tier mapping, skill integration
- Pitfalls: Prompt-as-code confusion, breaking parallelism, duplication

**Confidence breakdown:**
- Standard stack: HIGH - direct source audit
- Architecture: HIGH - existing orchestrator well understood
- Pitfalls: HIGH - based on integration experience
- Code examples: HIGH - adapted from real implementations

**Research date:** 2026-01-24
**Valid until:** 2026-03-24 (60 days - stable internal codebase)
</metadata>

---

*Phase: 13-ecc-integration*
*Research completed: 2026-01-24*
*Ready for planning: yes*
