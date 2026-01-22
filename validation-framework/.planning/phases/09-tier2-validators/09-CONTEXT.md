# Phase 9: Tier 2 Validators - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<vision>
## How This Should Work

The Tier 2 validators (design_principles + oss_reuse) work as both:
1. **CI-first static analysis** - Runs in CI, produces warnings without blocking
2. **Agent-driven fixes** - When issues found, code-simplifier agent suggests improvements

The design_principles validator detects KISS/YAGNI/DRY violations using:
- Radon for cyclomatic complexity and maintainability index
- AST analysis for nesting depth and parameter count
- Config-driven thresholds from `dimensions.design_principles`

The oss_reuse validator suggests OSS packages to replace reimplemented code:
- Pattern-based detection for common reimplementations (date parsing, HTTP, etc.)
- PyPI/npm API validation to ensure suggested packages exist and are maintained
- Confidence scoring based on pattern match strength

Both integrate seamlessly with the existing infrastructure:
- **Extend `post-commit-quality.py`** hook (already triggers code-simplifier)
- **Add CI workflow** `design-principles.yml.j2` for PR checks
- **Update orchestrator** stub with real implementation

</vision>

<essential>
## What Must Be Nailed

1. **Radon integration** - Cyclomatic complexity (threshold 10), maintainability index
2. **Config thresholds respected** - All limits from config.json dimensions
3. **SSOT with hooks-shared** - Extend existing `post-commit-quality.py`, don't duplicate
4. **OSS pattern matching** - At least 10 common patterns (dateutil, requests, jsonschema, etc.)
5. **PyPI API validation** - Verify suggested packages exist before recommending

</essential>

<specifics>
## Specific Ideas

### Existing Infrastructure to Leverage

| Component | Location | Action |
|-----------|----------|--------|
| `post-commit-quality.py` | hooks-shared/hooks/quality/ | EXTEND with radon |
| `code-simplifier` agent | plugins/code-simplifier/ | Already integrated |
| Orchestrator stub | templates/validation/orchestrator.py.j2 | UPDATE implementation |
| Config schema | templates/validation/config.schema.json | Already complete |

### Radon Metrics Mapping

| Config Parameter | Radon Command | Grade |
|------------------|---------------|-------|
| `max_complexity` (default 10) | `radon cc --min C` | C+ needs refactor |
| Maintainability | `radon mi --min B` | B+ is acceptable |

### CI Enforcement

Use `xenon` for hard failures:
```bash
xenon --max-absolute C --max-modules B .
```

### OSS Patterns to Implement

```python
OSS_PATTERNS = {
    "date parsing": {"patterns": ["strptime", "parse.*date"], "suggestion": "python-dateutil"},
    "HTTP client": {"patterns": ["urllib.request", "http.client"], "suggestion": "requests/httpx"},
    "JSON schema": {"patterns": ["validate.*schema"], "suggestion": "jsonschema"},
    "YAML parsing": {"patterns": ["yaml.load"], "suggestion": "pyyaml (safe_load)"},
    "CLI args": {"patterns": ["sys.argv\["], "suggestion": "click/typer"},
    "Path handling": {"patterns": ["os.path.join"], "suggestion": "pathlib (already stdlib)"},
    "Retry logic": {"patterns": ["while.*retry", "for.*attempt"], "suggestion": "tenacity"},
    "Caching": {"patterns": ["cache\s*=\s*\{\}"], "suggestion": "cachetools"},
    "Rate limiting": {"patterns": ["sleep.*loop", "time.sleep"], "suggestion": "ratelimit"},
    "Logging config": {"patterns": ["logging.basicConfig"], "suggestion": "structlog"},
}
```

### Dependencies to Add

```
radon>=6.0.0
xenon>=0.9.0
pypi-json>=0.4.0  # For registry validation
```

</specifics>

<notes>
## Additional Context

### Research Findings

- Radon threshold of 10 is industry standard for cyclomatic complexity
- PyPI JSON API at `https://pypi.org/pypi/{name}/json` provides package metadata
- No existing tool does "detect reimplemented code → suggest package" - this is novel

### Gaps Identified

1. `post-commit-quality.py` doesn't use radon (only line/function counts)
2. No OSS suggestion validator exists anywhere
3. No CI workflow for design principles
4. Orchestrator has stub only for both validators

### Integration Points

- Hook triggers post-commit → already invokes code-simplifier
- Orchestrator runs during Ralph loop → needs real implementation
- CI workflow runs on PR → new addition

</notes>

---

*Phase: 09-tier2-validators*
*Context gathered: 2026-01-22*
