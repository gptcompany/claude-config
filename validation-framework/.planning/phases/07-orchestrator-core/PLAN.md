# Phase 7: Orchestrator Core - PLAN

## Overview

Create `ValidationOrchestrator` class that integrates existing validation infrastructure into a unified 14-dimension system with tiered execution.

**Key Design Decision**: ~80% components exist. Focus on **integration**, not creation.

---

## Plan 07-01: Create ValidationOrchestrator Template

### Objective

Create a Jinja2 template for the orchestrator that:
1. Imports existing validators (from templates)
2. Runs validators in 3 tiers (Blockers → Warnings → Monitors)
3. Integrates with Ralph loop backpressure
4. Emits metrics to QuestDB/Grafana

### Tasks

#### Task 1: Create Orchestrator Base Class
**File**: `~/.claude/templates/validation/orchestrator.py.j2`

```python
"""
ValidationOrchestrator - 14-Dimension Tiered Validation

Tier 1 (Blockers): MUST pass before merge
Tier 2 (Warnings): Auto-suggest fixes, don't block
Tier 3 (Monitors): Metrics only, inform dashboards
"""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any
import json
import logging

class ValidationTier(Enum):
    BLOCKER = 1   # Must pass
    WARNING = 2   # Warn + suggest fix
    MONITOR = 3   # Metrics only

@dataclass
class ValidationResult:
    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None

@dataclass  
class TierResult:
    tier: ValidationTier
    results: list[ValidationResult]
    
    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)
    
    @property
    def has_warnings(self) -> bool:
        return any(not r.passed for r in self.results)

class ValidationOrchestrator:
    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.validators: dict[str, Callable] = {}
        self._register_validators()
    
    def _load_config(self, path: Path) -> dict:
        return json.loads(path.read_text())
    
    def _register_validators(self):
        """Register validators based on config dimensions."""
        dimensions = self.config.get("dimensions", {})
        for name, dim_config in dimensions.items():
            if dim_config.get("enabled", True):
                self.validators[name] = self._get_validator(name)
    
    def _get_validator(self, name: str) -> Callable:
        """Get validator function by dimension name."""
        # Import from existing templates/hooks
        validators = {
            # Tier 1 - Blockers
            "code_quality": self._validate_code_quality,
            "type_safety": self._validate_types,
            "security": self._validate_security,
            "coverage": self._validate_coverage,
            # Tier 2 - Warnings
            "design_principles": self._validate_design,
            "oss_reuse": self._validate_oss_reuse,
            "architecture": self._validate_architecture,
            "documentation": self._validate_docs,
            # Tier 3 - Monitors
            "performance": self._validate_performance,
            "accessibility": self._validate_a11y,
            "visual": self._validate_visual,
            "mathematical": self._validate_math,
            "data_integrity": self._validate_data,
            "api_contract": self._validate_api,
        }
        return validators.get(name, lambda: ValidationResult(
            dimension=name, tier=ValidationTier.MONITOR, 
            passed=True, message="No validator"
        ))
    
    async def run_tier(self, tier: ValidationTier) -> TierResult:
        """Run all validators for a specific tier."""
        tier_validators = [
            (name, v) for name, v in self.validators.items()
            if self._get_tier(name) == tier
        ]
        results = await asyncio.gather(*[
            self._run_validator(name, v) 
            for name, v in tier_validators
        ])
        return TierResult(tier=tier, results=list(results))
    
    async def run_all(self) -> dict:
        """Run all tiers in sequence."""
        report = {"tiers": [], "blocked": False, "overall_passed": True}
        
        # Tier 1: Blockers (must all pass)
        t1 = await self.run_tier(ValidationTier.BLOCKER)
        report["tiers"].append(t1)
        if not t1.passed:
            report["blocked"] = True
            report["overall_passed"] = False
            return report
        
        # Tier 2: Warnings (suggest fixes)
        t2 = await self.run_tier(ValidationTier.WARNING)
        report["tiers"].append(t2)
        if t2.has_warnings:
            await self._suggest_fixes(t2)
        
        # Tier 3: Monitors (emit metrics)
        t3 = await self.run_tier(ValidationTier.MONITOR)
        report["tiers"].append(t3)
        await self._emit_metrics(t3)
        
        return report
```

**Acceptance**: Template renders without syntax errors

#### Task 2: Integrate Existing Validators

Wire existing implementations into orchestrator:

| Dimension | Source | Integration |
|-----------|--------|-------------|
| code_quality | `post-commit-quality.py` | Import complexity check |
| type_safety | `post-commit-quality.py` | Import pyright runner |
| security | `ci/security.yml.j2` | Shell out to Trivy/Bandit |
| coverage | pytest-cov | Parse coverage.xml |
| architecture | `architecture-validator.py` | Import validator |
| documentation | `readme-generator.py` | Import checker |
| performance | `ci/performance.yml.j2` | Lighthouse CI |
| accessibility | `ci/accessibility.yml.j2` | axe-core |
| visual | `extensions/visual/` | Playwright |

**Acceptance**: 9/14 dimensions have working validators

#### Task 3: Create Tier Classification Config

**File**: `~/.claude/templates/validation/tier-config.yaml.j2`

```yaml
dimensions:
  # Tier 1 - BLOCKERS (must pass)
  code_quality:
    tier: 1
    enabled: true
    threshold:
      max_complexity: 10
      max_lines_per_file: 500
  type_safety:
    tier: 1
    enabled: true
    strict: false
  security:
    tier: 1
    enabled: true
    fail_on: ["HIGH", "CRITICAL"]
  coverage:
    tier: 1
    enabled: true
    min_percent: 70

  # Tier 2 - WARNINGS (auto-suggest)
  design_principles:
    tier: 2
    enabled: true
    agent: "code-simplifier"
  oss_reuse:
    tier: 2
    enabled: false  # Phase 9
  architecture:
    tier: 2
    enabled: true
    agent: "architecture-validator"
  documentation:
    tier: 2
    enabled: true
    agent: "readme-generator"

  # Tier 3 - MONITORS (metrics)
  performance:
    tier: 3
    enabled: true
    budgets_file: "budgets.json"
  accessibility:
    tier: 3
    enabled: true
    standard: "WCAG21AA"
  visual:
    tier: 3
    enabled: false  # Phase 12
  mathematical:
    tier: 3
    enabled: false  # Phase 10
  data_integrity:
    tier: 3
    enabled: false  # Phase 10
  api_contract:
    tier: 3
    enabled: false  # Phase 10
```

**Acceptance**: Config loads and validates

#### Task 4: Wire Into Ralph Loop

Modify `ralph-loop.py` to call orchestrator instead of inline CI checks.

**Edit**: `/media/sam/1TB/claude-hooks-shared/hooks/control/ralph-loop.py`

```python
# In run_ci_validation(), replace inline checks with:
async def run_ci_validation() -> tuple[bool, str, dict]:
    """Run tiered validation between iterations."""
    config_path = find_validation_config()
    if config_path:
        orchestrator = ValidationOrchestrator(config_path)
        report = await orchestrator.run_all()
        
        if report["blocked"]:
            return False, "Tier 1 blockers failed", report
        
        return True, "Validation passed", report
    
    # Fallback to legacy inline checks
    return legacy_ci_validation()
```

**Acceptance**: Ralph loop uses orchestrator when config exists

---

## Estimated Effort

| Task | LOC | Risk |
|------|-----|------|
| Task 1: Orchestrator base | ~150 | Low |
| Task 2: Wire validators | ~100 | Medium |
| Task 3: Tier config | ~60 | Low |
| Task 4: Ralph integration | ~30 | Low |
| **Total** | ~340 | Medium |

---

## Dependencies

- Phase 1-6 templates (complete)
- `ralph-loop.py` (exists)
- `post-commit-quality.py` (exists)
- CI templates (exists)

---

## Verification

1. **Unit test**: Orchestrator runs with mock validators
2. **Integration test**: Run on LiquidationHeatmap project
3. **Ralph test**: Execute Ralph loop, verify orchestrator fires
4. **Metrics test**: Check QuestDB for validation metrics

---

## Notes

### Patterns from Ralph Research (2026-01-22)

Integrate these patterns:
1. **PRD tracking** (snarktank/ralph): `passes: true/false` per dimension
2. **Dual-condition exit** (frankbria): Tier 1 pass + explicit signal
3. **Multi-phase chaining**: Tier 1 → Tier 2 → Tier 3 sequence
4. **Fresh context**: Each validation run is independent
