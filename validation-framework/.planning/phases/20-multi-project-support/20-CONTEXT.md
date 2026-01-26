# Phase 20: Multi-Project Support - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<vision>
## How This Should Work

The validation framework works seamlessly across multiple projects with minimal configuration:

1. **Global defaults** at `~/.claude/validation/global-config.json` provide baseline validation for all projects
2. **Project configs** at `.claude/validation/config.json` override/extend global settings
3. **Monorepo packages** are auto-discovered by scanning for per-package configs
4. **Shared validators** can be installed via pip or referenced as local paths
5. **Metrics** flow to QuestDB with `project_id` for cross-project comparison

The user should be able to:
- Run validation on any project with zero config (uses global defaults)
- Customize per-project while inheriting global settings
- See aggregated metrics across all their projects in Grafana

</vision>

<essential>
## What Must Be Nailed

- **Config merge logic** - Global → Project inheritance with clean override semantics
- **Backward compatibility** - Existing projects with configs must continue working
- **Monorepo discovery** - Auto-detect packages without explicit manifest

</essential>

<specifics>
## SWOT-Validated Decisions

### 1. Config Inheritance: Merge with Override
- Global config: `~/.claude/validation/global-config.json` (already exists)
- Project config: `.claude/validation/config.json`
- Merge strategy: JSON merge patch (RFC 7396)
- Project values override global values at same path

### 2. Monorepo Structure: Directory Convention
- Scan subdirectories for `.claude/validation/config.json`
- No explicit manifest required
- Respect `.gitignore` / `node_modules` / `__pycache__` exclusions
- Each discovered config = separate validation target

### 3. Plugin Distribution: uv + Local Paths

**Cos'è:** Come condividere validatori custom tra progetti (non il package manager del progetto).

I validatori sono Python (orchestrator.py), quindi usiamo **uv** (il pip moderno già in uso):

```json
{
  "plugins": [
    "security-headers-validator",           // uv pip install <name>
    "/home/sam/validators/custom-lint",     // path locale (sviluppo)
    "git+ssh://github.com/org/private.git"  // repo privato
  ]
}
```

**Strategia:**
- `uv pip install` per validatori pubblicati su PyPI
- Path locali per sviluppo/testing
- Git URLs per validatori privati non pubblicati
- **NON serve npm/bun** - i validatori sono Python, non JS

### 4. Cross-Project Metrics: Single Table + Views
- Existing `push_validation_metrics(data, project_name)` already tracks project
- Add materialized views for aggregations:
  - `validation_by_project_daily` - Daily summaries per project
  - `validation_quality_scores` - Rolling quality score per project
  - `validation_cross_project` - Comparison across projects

</specifics>

<notes>
## Additional Context

**Existing Infrastructure:**
- Global config already exists with tier-1-only default
- `project_name` already passed to QuestDB metrics
- Grafana dashboards exist (Phase 17) - just need cross-project panels

**Implementation Priority:**
1. 20-01: Config inheritance (foundation)
2. 20-02: Monorepo discovery (extends 20-01)
3. 20-03: Plugin system (independent)
4. 20-04: Metrics aggregation (depends on data from 20-01/02)

**Test Counts from ROADMAP:**
- 20-01: 8 tests
- 20-02: 10 tests
- 20-03: 12 tests
- 20-04: 8 tests
- Total: 38 tests

</notes>

---

*Phase: 20-multi-project-support*
*Context gathered: 2026-01-26*
