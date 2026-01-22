# Phase 9: Tier 2 Validators - Research

**Researched:** 2026-01-22 (updated with multi-language support)
**Domain:** Static analysis (Python primary, Rust/JS/TS future-ready)
**Confidence:** HIGH

<research_summary>
## Summary

Researched the Python static analysis ecosystem for implementing Tier 2 validators: design_principles (KISS/YAGNI/DRY via complexity metrics) and oss_reuse (package suggestion for reimplemented patterns). The standard approach uses Radon for complexity metrics with Xenon for CI enforcement, plus custom AST analysis for nesting depth and parameter count detection.

Key finding: Radon provides cyclomatic complexity (grades A-F with score 1-5 for A, 41+ for F) and maintainability index. Xenon wraps Radon for CI with exit codes on threshold violations. For oss_reuse, no existing tool does "detect reimplemented code → suggest package" - this is a novel validator that will use AST pattern detection plus PyPI JSON API validation.

**Primary recommendation:** Use radon + xenon for complexity metrics, extend post-commit-quality.py hook with radon integration, implement custom AST-based pattern detection for oss_reuse with PyPI API validation.
</research_summary>

<standard_stack>
## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| radon | 6.0.1 | Cyclomatic complexity, maintainability index | Industry standard for Python metrics |
| xenon | 0.9.3 | CI enforcement with thresholds | Wraps radon with exit codes for CI |
| ast (stdlib) | N/A | AST parsing for custom analysis | Python standard library, always available |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pypi-json | 0.4.0 | PyPI JSON API client | Validating suggested packages exist |
| astroid | 3.x | Enhanced AST (Pylint uses) | If need type inference in AST |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| radon | CytoScnPy | CytoScnPy is Rust-based, faster, but radon is pure Python and well-established |
| radon | pylint --reports | Pylint provides metrics but radon is specialized and lighter |
| xenon | flake8-radon | flake8-radon integrates with existing flake8 workflow, xenon is standalone |
| custom AST | Pylint plugin | Pylint plugins are heavier but integrate with existing lint workflows |

**Installation:**
```bash
pip install radon>=6.0.0 xenon>=0.9.0 pypi-json>=0.4.0
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
templates/validation/
├── validators/
│   ├── __init__.py
│   ├── design_principles.py   # Radon + AST analysis
│   └── oss_reuse.py           # Pattern detection + PyPI
├── orchestrator.py.j2          # Wire new validators
└── config.schema.json          # Already has dimension config

hooks-shared/hooks/quality/
└── post-commit-quality.py      # EXTEND with radon (SSOT)
```

### Pattern 1: Radon CI Integration
**What:** Use xenon in CI workflows to fail on complexity thresholds
**When to use:** PR checks, pre-merge validation
**Example:**
```bash
# Fail if any block exceeds grade C (complexity > 20)
xenon --max-absolute C --max-modules B --max-average B .
```

### Pattern 2: AST NodeVisitor for Custom Metrics
**What:** Subclass ast.NodeVisitor to collect nesting depth, parameter count
**When to use:** Metrics radon doesn't provide directly
**Example:**
```python
import ast

class NestingAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0

    def visit_FunctionDef(self, node):
        self.current_depth = 0
        self._check_nesting(node.body)
        self.generic_visit(node)

    def _check_nesting(self, stmts, depth=1):
        for stmt in stmts:
            if isinstance(stmt, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                self.max_depth = max(self.max_depth, depth)
                # Check nested body
                for attr in ('body', 'orelse', 'handlers', 'finalbody'):
                    if hasattr(stmt, attr):
                        self._check_nesting(getattr(stmt, attr), depth + 1)
```

### Pattern 3: PyPI API Package Validation
**What:** Verify suggested packages exist and are maintained before recommending
**When to use:** oss_reuse validator suggestions
**Example:**
```python
from pypi_json import PyPIJSON

def validate_package(name: str) -> bool:
    """Check if package exists on PyPI."""
    try:
        with PyPIJSON() as client:
            metadata = client.get_metadata(name)
            return metadata is not None
    except Exception:
        return False
```

### Anti-Patterns to Avoid
- **Running radon in loops per-file:** Use `radon cc -j .` once, parse JSON output
- **Hardcoding thresholds:** Read from config.json dimensions
- **Blocking on oss_reuse suggestions:** This is Tier 2 (WARNING), never block
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cyclomatic complexity | Custom control-flow counting | radon | McCabe's algorithm is non-trivial, radon is battle-tested |
| Maintainability Index | Custom formula | radon mi | MI formula involves Halstead metrics which radon handles |
| CI threshold enforcement | Custom exit code logic | xenon | Already wraps radon with proper exit codes |
| PyPI package existence | Raw HTTP requests | pypi-json | Handles API quirks, rate limiting, response parsing |
| AST traversal basics | Manual recursion | ast.NodeVisitor | Standard library pattern, handles all node types |

**Key insight:** Radon is the de-facto standard for Python complexity metrics. Xenon is designed specifically for CI integration. Don't reimplement these - focus implementation effort on the novel oss_reuse pattern detection which has no existing solution.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Radon JSON Output Parsing
**What goes wrong:** Expecting list, getting dict keyed by filename
**Why it happens:** radon cc -j outputs `{"file.py": [{"name": "func", "complexity": 5}]}`
**How to avoid:** Parse with `json.loads()` then iterate `.items()`
**Warning signs:** KeyError when accessing results

### Pitfall 2: Maintainability Index Interpretation
**What goes wrong:** Thinking 100 MI is bad (it's the best)
**Why it happens:** MI scale is inverted vs complexity (higher = better)
**How to avoid:** Check radon docs: A=100-20, B=19-10, C=9-0
**Warning signs:** Flagging well-maintained code as problematic

### Pitfall 3: AST Nesting Depth Off-by-One
**What goes wrong:** Counting module-level or function-level as nesting
**Why it happens:** Starting depth counter at wrong point
**How to avoid:** Start depth=1 inside function body, not at FunctionDef
**Warning signs:** All functions showing nesting=1 even with deep if/for

### Pitfall 4: False Positives in OSS Pattern Detection
**What goes wrong:** Suggesting dateutil for legitimate strptime usage
**Why it happens:** Pattern too broad, not checking context
**How to avoid:** Require multiple pattern matches or check if already using suggested package
**Warning signs:** Suggestions for code already following best practices

### Pitfall 5: PyPI Rate Limiting
**What goes wrong:** 429 errors during batch validation
**Why it happens:** Checking too many packages too fast
**How to avoid:** Cache results, batch requests, add small delays
**Warning signs:** Intermittent failures in CI
</common_pitfalls>

<code_examples>
## Code Examples

### Radon CLI Usage
```bash
# Source: radon.readthedocs.io

# Cyclomatic complexity (JSON output, min grade C)
radon cc --json --min C src/

# Maintainability index (show grade)
radon mi -s src/

# Raw metrics (SLOC, comments, etc.)
radon raw src/
```

### Radon Programmatic API
```python
# Source: radon documentation
from radon.complexity import cc_visit
from radon.metrics import mi_visit

code = '''
def example(x, y, z):
    if x > 0:
        if y > 0:
            return x + y
        return x
    return z
'''

# Get cyclomatic complexity
results = cc_visit(code)
for block in results:
    print(f"{block.name}: complexity={block.complexity}, rank={block.letter}")

# Get maintainability index
mi_score = mi_visit(code, multi=True)
print(f"MI: {mi_score}")
```

### Xenon CI Integration
```bash
# Source: xenon PyPI docs

# Fail if any block > C, any module > B, average > B
xenon --max-absolute C --max-modules B --max-average B src/

# Exit codes:
# 0 = all thresholds passed
# 1 = some thresholds exceeded
```

### Flake8-Radon Plugin (Alternative to Xenon)
```bash
# Source: radon.readthedocs.io/en/latest/flake8.html

# Install
pip install flake8 radon

# Run with complexity threshold (default 10)
flake8 --radon-max-cc 10 src/

# Options:
# --radon-max-cc <int>     Set complexity threshold (default: 10)
# --radon-no-assert        Don't count assert in complexity
# --radon-show-closures    Show nested functions/classes
```

### AST Function Parameter Count
```python
# Source: Python ast documentation
import ast

def count_parameters(code: str) -> dict[str, int]:
    """Count parameters for each function."""
    tree = ast.parse(code)
    counts = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            total = (
                len(args.posonlyargs) +
                len(args.args) +
                len(args.kwonlyargs) +
                (1 if args.vararg else 0) +
                (1 if args.kwarg else 0)
            )
            counts[node.name] = total

    return counts
```

### PyPI JSON API Direct Access
```python
# Source: docs.pypi.org/api/json/
import requests

def get_package_info(name: str) -> dict | None:
    """Get package metadata from PyPI."""
    url = f"https://pypi.org/pypi/{name}/json"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        return response.json()
    return None

# Response contains:
# - info: author, description, version, license, etc.
# - releases: all versions with file info
# - vulnerabilities: known CVEs
```
</code_examples>

<halstead_metrics>
## Halstead Metrics (Deep Dive)

Radon computes Halstead metrics which feed into the Maintainability Index.

### Base Measurements
| Symbol | Name | Description |
|--------|------|-------------|
| η₁ | Distinct operators | Number of unique operators (+, -, if, for, etc.) |
| η₂ | Distinct operands | Number of unique operands (variables, literals) |
| N₁ | Total operators | Total count of all operators |
| N₂ | Total operands | Total count of all operands |

### Derived Metrics
| Metric | Formula | Interpretation |
|--------|---------|----------------|
| Vocabulary (η) | η₁ + η₂ | Size of the "alphabet" used |
| Length (N) | N₁ + N₂ | Total tokens in program |
| Volume (V) | N × log₂(η) | Information content in bits |
| Difficulty (D) | (η₁/2) × (N₂/η₂) | Error-proneness |
| Effort (E) | D × V | Mental effort to understand |
| Time (T) | E / 18 seconds | Estimated coding time |
| Bugs (B) | V / 3000 | Estimated bug count |

### Maintainability Index Formula
```
MI = max[0, 100 × (171 - 5.2×ln(V) - 0.23×G - 16.2×ln(L) + 50×sin(√(2.4×C))) / 171]
```

Where:
- V = Halstead Volume
- G = Cyclomatic Complexity
- L = Source Lines of Code
- C = Percentage of comment lines

**Note:** Radon handles all this automatically via `radon mi` command.
</halstead_metrics>

<multi_language_support>
## Multi-Language Support (Future-Ready)

### Rust Complexity Analysis

#### rust-code-analysis (Mozilla)
**Source:** [github.com/mozilla/rust-code-analysis](https://github.com/mozilla/rust-code-analysis)

| Feature | Details |
|---------|---------|
| Version | 0.0.25 (Jan 2023) |
| Metrics | CC, Cognitive, Halstead, MI, SLOC, and 6 more |
| Languages | Rust, Python, JavaScript, TypeScript, Mozjs, TSX |
| Output | JSON, CSV, and other formats |

```bash
# Install
cargo install rust-code-analysis-cli

# Analyze Rust project
rust-code-analysis-cli --metrics --output json src/

# Metrics include:
# - CC (Cyclomatic Complexity)
# - COGNITIVE (Cognitive Complexity)
# - HALSTEAD (full suite)
# - MI (Maintainability Index)
# - NARGS (function parameters)
# - NEXITS (return points)
```

#### complexity crate (Cognitive Complexity)
**Source:** [crates.io/crates/complexity](https://crates.io/crates/complexity)

```rust
use complexity::Complexity;
use syn::{ItemFn, parse_quote};

let func: ItemFn = parse_quote! {
    fn example(x: i32) -> i32 {
        if x > 0 {
            for i in 0..x {
                if i % 2 == 0 { return i; }
            }
        }
        0
    }
};

// Returns cognitive complexity score
let score = func.complexity();
```

### JavaScript/TypeScript Complexity Analysis

#### ESLint Complexity Rule (Built-in)
**Source:** [eslint.org/docs/latest/rules/complexity](https://eslint.org/docs/latest/rules/complexity)

```javascript
// .eslintrc.js
module.exports = {
  rules: {
    // Warn when complexity > 10
    'complexity': ['warn', { max: 10 }]
  }
};
```

#### ESLintCC (Grades like Radon)
**Source:** [eslintcc.github.io](https://eslintcc.github.io/)

```bash
# Install
npm install -g eslintcc

# Analyze with grades (A-F like radon)
eslintcc src/

# Output includes:
# - Complexity grade per function
# - Aggregated project score
```

#### escomplex (Halstead + CC)
**Source:** [github.com/escomplex/escomplex](https://github.com/escomplex/escomplex)

```javascript
const escomplex = require('escomplex');

const result = escomplex.analyse(sourceCode);
// result.aggregate.cyclomatic - Cyclomatic complexity
// result.aggregate.halstead.volume - Halstead volume
// result.aggregate.maintainability - MI score
```

### npm Registry API (for oss_reuse JS packages)

**Endpoint:** `https://registry.npmjs.org/{package}`

```javascript
// Check if npm package exists
async function validateNpmPackage(name) {
  const response = await fetch(`https://registry.npmjs.org/${name}`);
  return response.ok;
}

// Get abbreviated metadata (faster)
async function getPackageInfo(name) {
  const response = await fetch(`https://registry.npmjs.org/${name}`, {
    headers: {
      'Accept': 'application/vnd.npm.install-v1+json'
    }
  });
  return response.json();
}
```

**Rate Limits:** Not officially documented. Handle HTTP 429 responses with exponential backoff. Authenticated requests get higher limits.
</multi_language_support>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pylint --reports for metrics | radon + xenon | 2020+ | Lighter, specialized tools preferred |
| Manual AST walking | ast.NodeVisitor pattern | Always | Standard library pattern |
| urllib for PyPI | pypi-json or requests | 2023+ | Better error handling |

**New tools/patterns to consider:**
- **CytoScnPy:** Rust-powered, faster than radon, includes nesting depth natively - but less established
- **ruff:** Extremely fast linter, may add complexity metrics in future

**Deprecated/outdated:**
- **pylint complexity checker:** Works but radon is more focused
- **mccabe standalone:** Use radon instead (includes McCabe algorithm)
</sota_updates>

<open_questions>
## Open Questions

Things that couldn't be fully resolved:

1. **npm registry rate limits** (PARTIALLY RESOLVED)
   - What we know: API exists, authenticated > unauthenticated limits, handle 429 with backoff
   - What's unclear: Exact numeric limits (npm doesn't document publicly, last blog post was 2017)
   - Recommendation: Implement caching, exponential backoff on 429, consider npm token for higher limits

2. **Optimal OSS pattern set**
   - What we know: Context from discuss-phase has 10 initial patterns (dateutil, requests, etc.)
   - What's unclear: Which patterns have highest value vs false positive rate
   - Recommendation: Start with high-confidence patterns (urllib→requests, sys.argv→click), iterate based on feedback

3. **Rust crate registry API**
   - What we know: crates.io has API at `https://crates.io/api/v1/crates/{name}`
   - What's unclear: Rate limits, authentication requirements for oss_reuse Rust suggestions
   - Recommendation: Research when extending to Rust (Phase 9 is Python-focused)
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [radon PyPI](https://pypi.org/project/radon/) - version 6.0.1, Python support
- [radon documentation](https://radon.readthedocs.io/en/latest/commandline.html) - grades, thresholds, CLI
- [radon flake8 plugin](https://radon.readthedocs.io/en/latest/flake8.html) - integration options
- [radon intro (Halstead)](https://radon.readthedocs.io/en/latest/intro.html) - Halstead metrics formulas
- [xenon PyPI](https://pypi.org/project/xenon/) - version 0.9.3, CI integration
- [Python ast documentation](https://docs.python.org/3/library/ast.html) - NodeVisitor, node types
- [PyPI JSON API](https://docs.pypi.org/api/json/) - endpoints, response structure
- [ESLint complexity rule](https://eslint.org/docs/latest/rules/complexity) - JS/TS built-in

### Secondary (MEDIUM confidence)
- [pypi-json documentation](https://pypi-json.readthedocs.io/) - client library usage
- [Pylint plugin guide](https://pylint.pycqa.org/en/latest/development_guide/how_tos/plugins.html) - custom checker patterns
- [rust-code-analysis](https://github.com/mozilla/rust-code-analysis) - Mozilla, multi-language metrics
- [complexity crate](https://docs.rs/complexity/latest/complexity/) - Rust cognitive complexity
- [escomplex](https://github.com/escomplex/escomplex) - JS/TS Halstead + CC
- [npm Registry API](https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md) - package metadata

### Tertiary (LOW confidence - needs validation)
- [CytoScnPy GitHub](https://github.com/djinn09/CytoScnPy) - nesting depth implementation reference
- [npm rate limiting blog (2017)](https://blog.npmjs.org/post/164799520460/api-rate-limiting-rolling-out.html) - outdated but only official source
- [ESLintCC](https://eslintcc.github.io/) - grades for JS/TS
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: radon, xenon, Python AST
- Multi-language: rust-code-analysis, ESLint, escomplex
- Ecosystem: pypi-json, npm registry, crates.io (future)
- Patterns: CI enforcement, AST visitors, API validation
- Pitfalls: JSON parsing, MI interpretation, rate limits

**Confidence breakdown:**
- Python stack: HIGH - radon/xenon are established tools with clear docs
- Halstead metrics: HIGH - verified formulas from official docs
- Architecture: HIGH - patterns from official documentation
- Multi-language: MEDIUM - tools verified but not deeply tested
- Pitfalls: HIGH - documented in community, verified with docs
- Code examples: HIGH - from official sources and verified

**Research date:** 2026-01-22 (expanded)
**Valid until:** 2026-02-22 (30 days - ecosystem stable)
</metadata>

---

## Radon Complexity Grades (Quick Reference)

### Cyclomatic Complexity

| Score | Grade | Risk Level |
|-------|-------|-----------|
| 1-5 | A | low - simple block |
| 6-10 | B | low - well structured |
| 11-20 | C | moderate - slightly complex |
| 21-30 | D | more than moderate |
| 31-40 | E | high - alarming |
| 41+ | F | very high - error-prone |

### Maintainability Index

| Score | Grade | Assessment |
|-------|-------|-----------|
| 100-20 | A | Very high maintainability |
| 19-10 | B | Medium maintainability |
| 9-0 | C | Extremely low maintainability |

---

*Phase: 09-tier2-validators*
*Research completed: 2026-01-22*
*Ready for planning: yes*
