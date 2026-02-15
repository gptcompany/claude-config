# /research - CoAT Iterative Research v2

Deep research using Chain-of-Associated-Thoughts with multi-source triangulation for >95% confidence.

**Architecture:** ClaudeFlow primary orchestrator with automatic Native Task fallback via circuit breaker.

## Usage

```
/research "query"
```

**Zero flags needed.** Claude auto-detects everything:

| Context | Auto-Behavior |
|---------|---------------|
| Inside spec directory | Saves to `research/research.md` |
| Query contains academic keywords | Enables Academic APIs + PMW |
| Incomplete checkpoint exists | Prompts to resume |
| Same query within 1 hour | Uses cache |

**Academic keywords (auto-trigger):**
`paper`, `study`, `research`, `journal`, `academic`, `peer-reviewed`, `citation`, `arxiv`, `literature`, `scholarly`, `empirical`, `methodology`

**Override only if needed:**
```
/research fresh "query"     # Skip cache, fresh results
```

## User Input

```text
$ARGUMENTS
```

## Smart Detection (executed automatically)

```python
QUERY = "$ARGUMENTS".strip()

# 1. Remove optional "fresh" prefix
USE_CACHE = True
if QUERY.lower().startswith("fresh "):
    USE_CACHE = False
    QUERY = QUERY[6:].strip()

# 2. Auto-detect academic intent from keywords
ACADEMIC_KEYWORDS = [
    "paper", "study", "research", "journal", "academic",
    "peer-reviewed", "citation", "arxiv", "literature",
    "scholarly", "empirical", "methodology", "thesis",
    "publication", "review", "meta-analysis"
]
query_lower = QUERY.lower()
USE_ACADEMIC = any(kw in query_lower for kw in ACADEMIC_KEYWORDS)
RUN_PMW = USE_ACADEMIC  # PMW always with academic

# 3. Auto-detect spec context
import subprocess
spec_check = subprocess.run(
    ["bash", "-c", "find . -maxdepth 3 -name 'spec.md' -type f 2>/dev/null | head -1"],
    capture_output=True, text=True
)
IN_SPEC_CONTEXT = bool(spec_check.stdout.strip())
AUTO_SAVE = IN_SPEC_CONTEXT

# 4. Check for incomplete checkpoint
from research_checkpoint import ResearchCheckpoint
incomplete = [c for c in ResearchCheckpoint.list_all()
              if c['state'] not in ['completed', 'failed']
              and c['query'].lower() == QUERY.lower()]
if incomplete:
    # Claude will ask: "Found incomplete research for this query. Resume?"
    RESUME_ID = incomplete[0]['run_id']
else:
    RESUME_ID = None

# Defaults
SAVE_MODE = "merge"
MAX_TOKENS = 200000
```

## Pre-Execution: Guards Initialization

Before starting research, initialize guards:

```python
# 1. Token Budget Guard (200K default, 5 iterations max)
from research_budget import BudgetGuard
budget = BudgetGuard(
    query=QUERY,
    max_tokens=MAX_TOKENS or 200000,
    max_iterations=5,
    max_time_minutes=30
)

# 2. Research Cache (1-hour TTL)
from research_cache import ResearchCache
cache = ResearchCache(ttl_hours=1)

# 3. Checkpoint Manager
from research_checkpoint import ResearchCheckpoint, ResearchState
if RESUME_ID:
    checkpoint = ResearchCheckpoint.load(RESUME_ID)
else:
    checkpoint = ResearchCheckpoint(query=QUERY)
```

## Spec Context Detection (Auto)

Automatically detects if running inside a spec directory:

```bash
# Find nearest spec.md
SPEC_FILE=$(find . -maxdepth 3 -name "spec.md" -type f 2>/dev/null | head -1)
SPEC_DIR=$(dirname "$SPEC_FILE" 2>/dev/null)
```

**If spec context found:**
- `AUTO_SAVE=true` (automatic)
- Creates `$SPEC_DIR/research/research.md`
- Uses smart merge with existing research

**If no spec context:**
- Output to screen only
- No save prompt needed

## CoAT Process (Chain-of-Associated-Thoughts)

Execute this iterative research loop (max 5 iterations, enforced by BudgetGuard):

### Phase 1: Associate (checkpoint: QUERYING)

```python
checkpoint.transition(ResearchState.QUERYING)
```

Generate 3-5 related concepts/queries from the user's question:
- Think laterally - what adjacent topics might be relevant?
- Consider synonyms, related fields, prerequisite concepts
- Identify potential sources: web, codebase, documentation, academic

**Output format:**
```
Associated Queries:
1. [query 1] - [why relevant]
2. [query 2] - [why relevant]
3. [query 3] - [why relevant]
```

### Phase 2: Search (checkpoint: SEARCHING)

```python
checkpoint.transition(ResearchState.SEARCHING)
budget.record(iteration=True, step_name="search")
```

**Check cache first (if USE_CACHE=true):**
```python
cached_result = cache.get(query)
if cached_result:
    print("Cache HIT")
    # Use cached results, skip API calls
else:
    # Execute searches
```

Execute searches IN PARALLEL using multiple sources:

1. **WebSearch** - For current information, articles, documentation
2. **Grep/Read** - Search codebase for implementations, patterns, examples
3. **Research Pipeline** (if `USE_ACADEMIC=true` and `PIPELINE_AVAILABLE`):
   ```python
   # Delegated to pipeline microservices (Discovery + Analyzer)
   # Triggered via POST /run, results read via GET /papers
   # See "Academic Search Integration" section below
   ```
4. **GitHub Search** (always, for implementations):
   ```
   WebSearch "{topic} site:github.com implementation"
   ```

**Cache results (if USE_CACHE=true):**
```python
if not cached_result:
    cache.set(query, results, source="search", ttl_hours=1)
```

For each source, extract:
- Key findings
- Source URL/path
- Confidence in relevance (1-10)

### Phase 3: Triangulation (checkpoint: TRIANGULATING)

```python
checkpoint.transition(ResearchState.TRIANGULATING)
```

**Multi-source triangulation for >95% confidence:**

| Source Type | Weight | Quality Indicators |
|-------------|--------|-------------------|
| Academic Papers | 40% | Peer-reviewed, citations, methodology |
| Official Docs | 30% | First-party, version-matched |
| Web Articles | 20% | Author expertise, recency, citations |
| Codebase | 10% | Working implementation, tests |

Score each finding:
```
Triangulation Score =
  (source_agreement × 0.40) +    # Multiple sources confirm
  (source_quality × 0.30) +       # High-quality sources
  (coverage_depth × 0.20) +       # Comprehensive coverage
  (counter_evidence × 0.10)       # Addressed contradictions
```

**Decision logic:**
- If triangulation score < 60%: **BACKTRACK** - generate new queries
- If any critical gap identified: **BACKTRACK** with focused query
- If score >= 80%: proceed to synthesis
- If score 60-80%: proceed but note uncertainty

### Phase 4: Hypothesize

Synthesize findings into a coherent answer:
1. Identify common themes across sources (triangulated findings)
2. Resolve contradictions (prefer authoritative sources)
3. Note remaining gaps or uncertainties
4. Form preliminary hypothesis/answer

### Phase 5: Refine (Loop Decision)

**Check budget before continuing:**
```python
if not budget.can_continue():
    print("Budget exceeded - stopping gracefully")
    checkpoint.transition(ResearchState.SYNTHESIZING)
    # Skip to final synthesis
```

Calculate overall confidence:
```
Confidence =
  (triangulation_score × 0.50) +
  (source_diversity × 0.25) +
  (gap_coverage × 0.25)
```

**If confidence < 80% AND budget.can_continue():**
- Identify weakest area
- Generate refined queries targeting gaps
- Return to Phase 1

**If confidence >= 80% OR budget exhausted:**
- Finalize answer
- Proceed to PMW (if RUN_PMW=true)
- Output final response

## Academic Search Integration (Auto with Academic Keywords)

Academic search is **delegated to the Research Pipeline** (microservices on ports 8770-8775).
The pipeline handles arXiv, Semantic Scholar, CrossRef with built-in rate limiting, dedup, and enrichment.

```python
import urllib.request, json

# 1. Check pipeline availability
try:
    urllib.request.urlopen("http://localhost:8775/health", timeout=3)
    PIPELINE_AVAILABLE = True
except Exception:
    PIPELINE_AVAILABLE = False
```

**If pipeline available** — trigger a pipeline run and read results:
```python
if PIPELINE_AVAILABLE:
    # Build arXiv query from user's natural language query
    # CoAT generates the arXiv-syntax query from the topic
    arx_query = f'abs:"{QUERY}"'  # Claude refines this based on context

    # Trigger pipeline: discovery + analysis (stages=2)
    payload = json.dumps({
        "query": arx_query, "stages": 2, "max_papers": 10
    }).encode()
    req = urllib.request.Request(
        "http://localhost:8775/run", data=payload,
        headers={"Content-Type": "application/json"}
    )
    run_result = json.loads(urllib.request.urlopen(req, timeout=300).read())

    # Read enriched results via GET endpoint
    papers = json.loads(urllib.request.urlopen(
        "http://localhost:8775/papers?limit=10", timeout=10
    ).read())

    # For each paper, get detail with formulas if needed
    for paper in papers[:5]:
        detail = json.loads(urllib.request.urlopen(
            f"http://localhost:8775/papers?id={paper['id']}", timeout=10
        ).read())
```

**If pipeline NOT available** — inform the user clearly:
```
⚠️ Research Pipeline non disponibile (localhost:8775).
Avvia con: cd /media/sam/1TB/research-pipeline && docker compose up -d
Solo la ricerca web sarà utilizzata per questa sessione.
```

**No fallback API dirette** — le query accademiche vivono SOLO nel pipeline (single source of truth).

## GitHub Implementation Search (Phase 2)

After academic search, search for **existing implementations** on GitHub (not redundant — the pipeline doesn't search GitHub):

```
WebSearch "{topic} site:github.com implementation"
WebSearch "{topic} github repository python"
```

GitHub results go in the Sources section as "Implementations" with repo URL, stars, language.

## PMW Validation (Auto with Academic Keywords)

```python
checkpoint.transition(ResearchState.PMW_ANALYSIS)
```

> **"Cerca attivamente disconferme, non conferme"** - Actively seek disconfirmation, not confirmation.

### PMW.1 Counter-Evidence Search

Search for contradicting evidence using inverted queries:

```
Original: "{topic} benefits optimal"
Counter:  "{topic} failure", "{topic} limitations", "{topic} criticism", "{topic} poor performance"
```

Execute WebSearch with counter-queries IN PARALLEL.

### PMW.2 SWOT Assessment

Based on ALL findings (CoAT + Counter-Evidence), produce:

```markdown
## PMW: Prove Me Wrong Analysis

### Strengths
- [What the research strongly supports]

### Weaknesses
- [Identified limitations, edge cases, assumptions]

### Opportunities
- [Potential improvements, extensions, alternatives]

### Threats
- [What could make this approach fail]
```

### PMW.3 Mitigations Check

For each Threat/Weakness:
- Does existing research address it?
- Is mitigation documented?
- Flag unaddressed risks

### PMW.4 Verdict

Based on PMW analysis, provide verdict:

| Verdict | Meaning | Action |
|---------|---------|--------|
| **GO** | Solid foundation, risks addressed | Proceed with confidence |
| **WAIT** | Issues found but fixable | Address before implementation |
| **STOP** | Fundamental flaws discovered | Rethink approach entirely |

**Include verdict in final output.**

## Output Format

```python
checkpoint.transition(ResearchState.SYNTHESIZING)
```

### Research Summary

[Synthesized answer addressing the user's query]

### Key Findings

1. **[Finding 1]** - [Source] (Triangulated: X sources)
2. **[Finding 2]** - [Source] (Triangulated: X sources)
3. **[Finding 3]** - [Source] (Triangulated: X sources)

### Sources

**Academic (if used):**
- [Paper Title] ([Year]) - [DOI/URL] - Citations: N
- [Paper Title] ([Year]) - [DOI/URL] - Citations: N

**Web:**
- [Title](URL) - [brief relevance note]

**Codebase:**
- `path/to/file.py:line` - [what it shows]

**Documentation:**
- [Doc name] - [relevant section]

### Confidence

**Overall: X/100** (Target: >95%)

| Dimension | Score | Weight |
|-----------|-------|--------|
| Source Agreement | X/10 | 40% |
| Source Quality | X/10 | 30% |
| Coverage Depth | X/10 | 20% |
| Counter-Evidence | X/10 | 10% |

### Research Metrics

```
Run ID: [checkpoint.run_id]
Iterations: X (max 5)
Tokens used: X / 200,000
Sources searched: X
Cache: HIT/MISS
```

### PMW Analysis (if academic keywords detected)

```markdown
## PMW: Prove Me Wrong

### Strengths
- [findings]

### Weaknesses
- [findings]

### Opportunities
- [findings]

### Threats
- [findings]

### Mitigations
- [addressed/unaddressed risks]

### Verdict: [GO/WAIT/STOP]
[Justification]
```

## Auto-Save to Spec (Auto in Spec Context)

```python
checkpoint.transition(ResearchState.SAVING)
```

When in spec context, saves automatically using **smart merge**:

1. If no existing file → create new
2. If existing file:
   - Create backup: `research.md.bak`
   - Add only NEW findings (avoid duplicates)
   - Update PMW if new threats found
   - Merge sources (deduplicated)
   - Update date and confidence scores
   - Preserve existing validated content

**Template SSOT:** `~/.claude/templates/research-template.md`

### Report Save Status

```python
checkpoint.transition(ResearchState.COMPLETED)
checkpoint.update_metrics(confidence=final_confidence)
budget.complete()
```

After saving, inform user:
```
Research saved to: specs/XXX/research/research.md
- Backup: research.md.bak
- Findings: N total (M new)
- PMW verdict: GO/WAIT/STOP (if academic)
- Confidence: X%
```

## Configuration

- **Max iterations:** 5
- **Max tokens:** 200,000
- **Confidence threshold:** 95%
- **Cache TTL:** 1 hour
- **Sources:** WebSearch, Grep, Read, Academic APIs

## Error Recovery

If research fails at any point:
1. Checkpoint saves current state automatically
2. Next `/research` with same query auto-detects incomplete checkpoint
3. Claude prompts: "Found incomplete research. Resume?"
4. Research continues from last successful phase

## Examples

**General query:**
```
/research "Best practices for Python async error handling"
```
→ WebSearch + codebase, auto-saves if in spec directory

**Academic query (auto-detected from keywords):**
```
/research "Kelly Criterion academic paper analysis"
/research "GARCH volatility study methodology"
```
→ Keywords trigger: Academic APIs + PMW + auto-save

**Force fresh results (skip cache):**
```
/research fresh "latest Python 3.12 features"
```
→ Bypasses 1-hour cache

**Resume (auto-prompted):**
```
/research "same query as before"
```
→ If incomplete checkpoint exists, Claude asks: "Resume previous research?"

## ⚠️ Academic Papers: Pipeline Processing

Le fonti in `research.md` includono metadata (titolo, abstract, DOI) e punteggi di analisi dal pipeline.

**Per esplorare papers processati dal pipeline:**
- `/research-papers` per lista papers con stage e formule
- `/research-papers --detail 1` per dettaglio completo paper #1

**Pipeline stages:** Discovery → Analyzer → Extractor → Validator → Codegen
**Validazione CAS:** SymPy, Maxima (integrata nel pipeline, stage Validator)
