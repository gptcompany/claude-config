# Validation Framework - SSOT

**Single Source of Truth** for the 14-Dimension ValidationOrchestrator.

**Last Updated:** 2026-01-26
**Version:** v4.0

---

## Overview

The validation framework provides automated code quality validation through 14 dimensions organized in 3 tiers:

| Tier | Purpose | Behavior | Dimensions |
|------|---------|----------|------------|
| **1** | Blockers | MUST pass - blocks CI/merge | code_quality, type_safety, security, coverage |
| **2** | Warnings | SHOULD fix - auto-suggest | design_principles, oss_reuse, accessibility, performance |
| **3** | Monitors | Track metrics - Grafana | mathematical, api_contract, visual, behavioral |

---

## Components

### Code Location

| Component | Path | LOC |
|-----------|------|-----|
| **Orchestrator** | `~/.claude/templates/validation/orchestrator.py` | ~1,100 |
| **Validators** | `~/.claude/templates/validation/validators/` | 12 dirs |
| **Config loader** | `~/.claude/templates/validation/config_loader.py` | ~500 |
| **Skill** | `~/.claude/skills/validate/SKILL.md` | - |
| **Hook** | `~/.claude/scripts/hooks/quality/validation-orchestrator.js` | ~150 |
| **Tests** | `~/.claude/validation-framework/tests/` | 358 tests |

### Validators (12)

| Validator | Tier | Purpose |
|-----------|------|---------|
| `code_quality` | 1 | Ruff linting |
| `type_safety` | 1 | mypy/pyright type checking |
| `security` | 1 | Trivy + dependency scanning |
| `coverage` | 1 | pytest-cov thresholds |
| `design_principles` | 2 | KISS/YAGNI/DRY detection |
| `oss_reuse` | 2 | Package suggestions |
| `accessibility` | 2 | axe-core a11y |
| `performance` | 2 | Lighthouse/Core Web Vitals |
| `mathematical` | 3 | CAS formula validation |
| `api_contract` | 3 | OpenAPI diff |
| `visual` | 3 | ODiff + SSIM screenshot comparison |
| `behavioral` | 3 | DOM tree comparison |

---

## Usage

### Manual: `/validate` Skill

```bash
/validate              # Full 14-dimension validation
/validate quick        # Tier 1 blockers only (fast)
/validate 1            # Tier 1 only
/validate 2            # Tier 2 only
/validate 3            # Tier 3 only
```

### Automatic: PostToolUse Hook

The `validation-orchestrator.js` hook triggers automatically on `Write|Edit|MultiEdit`:

- **Async execution** (non-blocking)
- **Tier 1 only** (fast feedback)
- **5s debounce** (avoids spam)
- **Conditional** (only if `.claude/validation/config.json` exists)

### CLI Direct

```bash
python3 ~/.claude/templates/validation/orchestrator.py [tier]
# tier: 1, 2, 3, quick, all (default)
```

---

## Project Setup

### Scaffold New Project

```bash
~/.claude/templates/validation/scaffold.sh /path/to/project [domain]
```

**Domains:** `trading`, `workflow`, `data`, `general` (default)

### Manual Setup

Create `.claude/validation/config.json`:

```json
{
  "project_name": "my_project",
  "domain": "general",
  "smoke_tests": {
    "critical_imports": ["mymodule.core"],
    "config_files": ["config.yaml"],
    "external_services": []
  },
  "dimensions": {
    "code_quality": { "tier": 1, "enabled": true },
    "type_safety": { "tier": 1, "enabled": true },
    "security": { "tier": 1, "enabled": true },
    "coverage": { "tier": 1, "enabled": true, "threshold": 80 }
  }
}
```

---

## Integration Points

### GSD Integration

`/gsd:verify-work` can invoke validation:

```python
# In verify-work.md
python3 ~/.claude/templates/validation/orchestrator.py quick
```

### CI Integration

```yaml
# .github/workflows/validate.yml
- name: Run validation
  run: python3 ~/.claude/templates/validation/orchestrator.py 1
```

### Grafana/Prometheus

Metrics emitted to:
- **Prometheus:** `validation_*` metrics
- **QuestDB:** `claude_validation_results` table

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VALIDATION_ENABLED` | `true` | Master switch - set to `false` to disable all validation |
| `VALIDATION_AGENT_SPAWN` | `true` | Enable automatic agent spawning for fixes |
| `VALIDATION_SWARM` | `true` | Enable parallel execution for Tier 3 |

**Disable validation example:**

```bash
VALIDATION_ENABLED=false /gsd:execute-plan
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All validations passed |
| 1 | Tier 1 blocker(s) failed |
| 2 | Orchestrator error (config missing, etc.) |

---

## Troubleshooting

### Validation not running automatically

1. Check hook is registered: `grep validation-orchestrator ~/.claude/settings.json`
2. Check config exists: `ls .claude/validation/config.json`
3. Check logs: `tail ~/.claude/logs/validation-hook.log`

### Slow validation

Use `/validate quick` for Tier 1 only (~5s vs ~30s full).

### Missing validators

Some validators require external tools:
- `visual`: requires `odiff` npm package
- `security`: requires `trivy`
- `accessibility`: requires `axe-core`

---

## Related Documentation

- [HOOKS-CATALOG.md](HOOKS-CATALOG.md) - All hooks reference
- [templates/validation/README.md](../templates/validation/README.md) - Detailed validator docs
- [templates/validation/docs/ECC_INTEGRATION.md](../templates/validation/docs/ECC_INTEGRATION.md) - ECC hybrid workflow

---

*SSOT maintained in `~/.claude/docs/VALIDATION.md`*
