# Phase 10: Tier 3 Validators - Research

**Researched:** 2026-01-22
**Domain:** CAS formula validation + OpenAPI contract diffing
**Confidence:** HIGH

<research_summary>
## Summary

Researched the ecosystem for mathematical formula validation via CAS and API contract breaking change detection.

**Key findings:**

1. **CAS Microservice already exists** at `localhost:8769` with Maxima, SageMath, MATLAB engines. Protocol is simple POST to `/validate` with `{"latex": "...", "cas": "maxima|sagemath|matlab"}`. MCP Wolfram available as fallback.

2. **OpenAPI diffing tools are Go/Java-based**, not native Python. Best options: **oasdiff** (Go CLI, 250+ checks, JSON/YAML output) or **Schemathesis** (Python, validates response against spec, not spec-vs-spec diff).

3. **Formula extraction from code**: Use Python AST for docstrings, regex for inline comments with `:math:` RST directives. SymPy's `parse_latex()` converts LaTeX to symbolic expressions.

**Primary recommendation:** Use existing CAS microservice via HTTP client, use oasdiff CLI via subprocess for breaking change detection, use Schemathesis for live API drift validation against spec.
</research_summary>

<standard_stack>
## Standard Stack

### Core - CAS Integration
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27+ | HTTP client for CAS microservice | Async-capable, timeout handling |
| sympy | 1.13+ | LaTeX parsing & symbolic math | `parse_latex()` for expression parsing |
| mcp_wolfram | MCP | Fallback CAS validation | Cloud-based, always available |

### Core - OpenAPI Contract
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| oasdiff | 1.10+ | Breaking change detection CLI | 250+ checks, ERR/WARN/INFO levels |
| schemathesis | 4.9+ | Live API drift validation | Python-native, pytest integration |
| openapi-spec-validator | 0.7+ | Spec schema validation | Validates spec before diffing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pylatexenc | 3.0+ | LaTeX to unicode/parsing | Extracting math from docstrings |
| pyyaml | 6.0+ | YAML spec parsing | Reading OpenAPI specs |
| watchdog | 4.0+ | File change monitoring | Trigger on spec/route changes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| oasdiff CLI | openapi-diff (Java) | Java-based, heavier runtime |
| Schemathesis | Dredd | Node.js-based, less Python integration |
| CAS microservice | Pure SymPy | Limited to SymPy capabilities, no Maxima/SageMath |

**Installation:**
```bash
pip install httpx sympy schemathesis openapi-spec-validator pylatexenc pyyaml watchdog
# oasdiff via binary or Go install
go install github.com/oasdiff/oasdiff@latest
# Or use Docker: docker pull oasdiff/oasdiff
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Validator Structure
```
validators/
├── mathematical/
│   ├── __init__.py
│   ├── validator.py          # MathematicalValidator class
│   ├── cas_client.py         # CAS microservice client
│   ├── formula_extractor.py  # Extract math from code/docs
│   └── wolfram_fallback.py   # MCP Wolfram fallback
├── api_contract/
│   ├── __init__.py
│   ├── validator.py          # APIContractValidator class
│   ├── spec_discovery.py     # Find OpenAPI specs
│   ├── oasdiff_runner.py     # oasdiff CLI wrapper
│   └── drift_checker.py      # Schemathesis-based live check
```

### Pattern 1: CAS Client with Fallback
**What:** HTTP client to local CAS, automatic fallback to Wolfram MCP
**When to use:** All formula validation calls
**Example:**
```python
import httpx
from typing import Optional

class CASClient:
    def __init__(self, base_url: str = "http://localhost:8769"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def validate(self, latex: str, cas: str = "maxima") -> dict:
        try:
            response = self.client.post(
                f"{self.base_url}/validate",
                json={"latex": latex, "cas": cas}
            )
            return response.json()
        except httpx.ConnectError:
            # Fallback to Wolfram MCP
            return self._wolfram_fallback(latex)

    def _wolfram_fallback(self, latex: str) -> dict:
        # Use mcp__wolframalpha__ask_llm
        # Implementation depends on MCP client availability
        return {"success": False, "error": "CAS unavailable, Wolfram fallback pending"}
```

### Pattern 2: oasdiff CLI Wrapper
**What:** Python wrapper for oasdiff binary, parses JSON output
**When to use:** Breaking change detection between specs
**Example:**
```python
import subprocess
import json
from pathlib import Path

class OasdiffRunner:
    def __init__(self, binary: str = "oasdiff"):
        self.binary = binary

    def breaking_changes(self, base_spec: Path, revision_spec: Path) -> dict:
        """Detect breaking changes between two OpenAPI specs."""
        result = subprocess.run(
            [self.binary, "breaking", str(base_spec), str(revision_spec), "-f", "json"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return {"breaking": False, "changes": []}
        # Parse JSON output for breaking changes
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"breaking": True, "raw_output": result.stdout}

    def diff(self, base_spec: Path, revision_spec: Path) -> dict:
        """Full diff between two specs."""
        result = subprocess.run(
            [self.binary, "diff", str(base_spec), str(revision_spec), "-f", "json"],
            capture_output=True,
            text=True
        )
        return json.loads(result.stdout) if result.stdout else {}
```

### Pattern 3: OpenAPI Spec Auto-Discovery
**What:** Find OpenAPI specs in project automatically
**When to use:** Initial setup, file change triggers
**Example:**
```python
from pathlib import Path
from typing import Optional, List

class SpecDiscovery:
    STANDARD_PATHS = [
        "openapi.yaml", "openapi.json",
        "api/openapi.yaml", "api/openapi.json",
        "docs/openapi.yaml", "docs/openapi.json",
        "swagger.yaml", "swagger.json"
    ]

    def __init__(self, project_root: Path):
        self.root = project_root

    def find_specs(self) -> List[Path]:
        """Find all OpenAPI specs in project."""
        specs = []
        for pattern in self.STANDARD_PATHS:
            spec_path = self.root / pattern
            if spec_path.exists():
                specs.append(spec_path)
        # Also check glob patterns
        for pattern in ["**/openapi*.yaml", "**/openapi*.json"]:
            specs.extend(self.root.glob(pattern))
        return list(set(specs))

    def fastapi_endpoint(self, base_url: str) -> Optional[str]:
        """Check for FastAPI auto-generated spec."""
        import httpx
        try:
            resp = httpx.get(f"{base_url}/openapi.json", timeout=5)
            if resp.status_code == 200:
                return f"{base_url}/openapi.json"
        except:
            pass
        return None
```

### Anti-Patterns to Avoid
- **Custom breaking change rules:** Use oasdiff's 250+ battle-tested checks
- **Blocking on Schemathesis in CI:** It generates thousands of tests, use sparingly
- **Ignoring CAS timeout:** Always set timeouts, formulas can be compute-intensive
- **Parsing OpenAPI manually:** Use established parsers like openapi-spec-validator
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Breaking change detection | Custom diff logic | oasdiff | 250+ edge cases handled, maintained |
| LaTeX parsing | Regex-based parser | SymPy parse_latex | Grammar-based, handles nested structures |
| OpenAPI validation | Schema checking code | openapi-spec-validator | Keeps up with spec versions |
| Formula simplification | Custom math logic | CAS microservice (Maxima/SageMath) | Production CAS engines |
| API drift detection | Manual response checking | Schemathesis | Property-based testing, finds edge cases |
| File watching | Custom inotify | watchdog | Cross-platform, handles edge cases |

**Key insight:** Both formula validation and API contract checking are solved problems with mature tooling. The CAS microservice already exists with 3 engines. oasdiff has 250+ breaking change checks. Hand-rolling would miss edge cases.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: CAS Timeout on Complex Formulas
**What goes wrong:** Validator hangs on recursive/complex expressions
**Why it happens:** CAS engines have no default timeout for computation
**How to avoid:** Always set httpx timeout (30s default), kill subprocess if needed
**Warning signs:** Single formula taking >5s, CPU spike

### Pitfall 2: OpenAPI Spec Version Mismatch
**What goes wrong:** oasdiff fails silently or gives wrong results
**Why it happens:** Comparing OpenAPI 2.0 (Swagger) to 3.0, or 3.0 to 3.1
**How to avoid:** Validate both specs with openapi-spec-validator first, check versions match
**Warning signs:** Empty diff output, "invalid spec" errors

### Pitfall 3: Breaking Change False Positives
**What goes wrong:** Non-breaking changes flagged as breaking
**Why it happens:** Enum extensions, optional field additions treated as breaks
**How to avoid:** Use oasdiff's `x-extensible-enum` support, configure ignore rules
**Warning signs:** Many WARN-level "breaking" changes on minor updates

### Pitfall 4: LaTeX Parsing Edge Cases
**What goes wrong:** parse_latex fails on valid LaTeX
**Why it happens:** Complex macros, custom commands, malformed input
**How to avoid:** Use `backend='antlr'` for partial parsing, catch exceptions
**Warning signs:** Exception on formulas that render correctly in LaTeX

### Pitfall 5: Schemathesis Test Explosion
**What goes wrong:** Thousands of test cases generated, slow CI
**Why it happens:** Property-based testing explores parameter space
**How to avoid:** Use `--hypothesis-max-examples=100`, run as separate validation (not blocking)
**Warning signs:** Test suite taking >10 minutes, flaky failures
</common_pitfalls>

<code_examples>
## Code Examples

### CAS Microservice Protocol
```python
# Source: /media/sam/1TB/N8N_dev/scripts/cas_microservice.py
import httpx

# Health check
resp = httpx.get("http://localhost:8769/health")
# {"status": "healthy", "cas_available": ["maxima", "sagemath", "matlab"]}

# Validate formula
resp = httpx.post("http://localhost:8769/validate", json={
    "latex": "x^2 + 2*x + 1",
    "cas": "maxima"
})
# {
#   "cas": "maxima",
#   "engine": "macsyma-lisp",
#   "success": true,
#   "input": "x^2 + 2*x + 1",
#   "simplified": "x^2 + 2*x + 1",
#   "factored": "(x + 1)^2",
#   "time_ms": 373
# }

# Validate equation (identity check)
resp = httpx.post("http://localhost:8769/validate", json={
    "latex": "(x+1)^2 = x^2 + 2x + 1",
    "cas": "maxima"
})
# {"is_identity": true, "success": true, ...}
```

### SymPy LaTeX Parsing
```python
# Source: SymPy documentation
from sympy.parsing.latex import parse_latex

# Basic parsing
expr = parse_latex(r"x^2 + \frac{a}{b}")
print(expr)  # x**2 + a/b

# With ANTLR backend (tolerant of malformed input)
expr = parse_latex(r"\sin(x) + \cos(y)", backend='antlr')
print(expr)  # sin(x) + cos(y)
```

### oasdiff Breaking Changes Detection
```bash
# Source: oasdiff documentation
# Detect breaking changes
oasdiff breaking base.yaml revision.yaml -f json

# Output format:
# {
#   "messages": [
#     {"level": "ERR", "code": "PATH_ITEM_DELETED", "path": "/users/{id}"}
#   ]
# }

# List all available checks
oasdiff checks
```

### Schemathesis API Validation
```python
# Source: Schemathesis documentation
import schemathesis

# Load schema
schema = schemathesis.openapi.from_url("http://api.example.com/openapi.json")

# Validate specific endpoint
operation = schema["/users"]["GET"]
case = operation.make_case(query={"limit": 10})
response = case.call()
case.validate_response(response)  # Raises if invalid
```

### Formula Extraction from Docstrings
```python
# Source: Python AST documentation + pylatexenc
import ast
import re
from pathlib import Path

def extract_math_from_docstrings(source_file: Path) -> list[str]:
    """Extract :math:`...` formulas from Python docstrings."""
    tree = ast.parse(source_file.read_text())
    formulas = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
            docstring = ast.get_docstring(node)
            if docstring:
                # Find RST math directives
                matches = re.findall(r':math:`([^`]+)`', docstring)
                formulas.extend(matches)

    return formulas
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| swagger-diff | oasdiff | 2023+ | Go-based, faster, more checks |
| Manual API testing | Schemathesis | 2022+ | Property-based, finds edge cases |
| SymPy only | CAS microservice | Project-specific | Multi-engine (Maxima, SageMath, MATLAB) |
| LaTeX regex parsing | parse_latex (Lark) | SymPy 1.12+ | Grammar-based, better error handling |

**New tools/patterns to consider:**
- **oasdiff-action:** GitHub Action for CI integration
- **Schemathesis stateful testing:** Multi-step API workflows
- **Wolfram MCP:** Cloud fallback when local CAS unavailable

**Deprecated/outdated:**
- **swagger-diff:** Replaced by oasdiff for modern OpenAPI
- **ANTLR LaTeX parser:** Being replaced by Lark in SymPy
</sota_updates>

<open_questions>
## Open Questions

1. **Wolfram MCP fallback implementation**
   - What we know: MCP tool `mcp__wolframalpha__ask_llm` exists
   - What's unclear: How to call MCP from validator code (not from Claude directly)
   - Recommendation: For now, return "CAS unavailable" error; investigate MCP client library

2. **OpenAPI git baseline tracking**
   - What we know: oasdiff compares two specs
   - What's unclear: How to track "last known good" spec version for drift detection
   - Recommendation: Store baseline spec hash in validation state, or use git diff
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- CAS microservice source: `/media/sam/1TB/N8N_dev/scripts/cas_microservice.py` - verified working
- Context7 `/oasdiff/oasdiff` - breaking change detection patterns
- Context7 `/schemathesis/schemathesis` - API validation patterns
- Context7 `/sympy/sympy` - parse_latex documentation

### Secondary (MEDIUM confidence)
- [oasdiff GitHub](https://github.com/oasdiff/oasdiff) - CLI usage, 250+ checks
- [Schemathesis PyPI](https://pypi.org/project/schemathesis/) - version 4.9.4
- [pylatexenc docs](https://pylatexenc.readthedocs.io/) - LaTeX parsing

### Tertiary (LOW confidence - needs validation)
- None - all findings verified with authoritative sources
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: CAS microservice, oasdiff, Schemathesis
- Ecosystem: SymPy, httpx, openapi-spec-validator, watchdog
- Patterns: HTTP client with fallback, CLI wrapper, spec discovery
- Pitfalls: Timeouts, version mismatch, false positives

**Confidence breakdown:**
- Standard stack: HIGH - verified with Context7, existing infrastructure
- Architecture: HIGH - patterns from official docs
- Pitfalls: MEDIUM - some from docs, some from domain knowledge
- Code examples: HIGH - CAS microservice tested, others from official sources

**Research date:** 2026-01-22
**Valid until:** 2026-02-22 (30 days - stable tools)
</metadata>

---

*Phase: 10-tier3-validators*
*Research completed: 2026-01-22*
*Ready for planning: yes*
