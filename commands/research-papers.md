# /research-papers - Query Academic Papers Knowledge Base

Query processed academic papers from the Research Pipeline (SQLite via HTTP API).

## Usage

```
/research-papers "query"              # Search papers by title/abstract
/research-papers --list               # List all papers with stage info
/research-papers --detail ID          # Full paper detail with formulas, validations, codegen
/research-papers --formulas           # List all formulas
/research-papers --formulas ID        # Formulas for paper ID
```

## User Input

```text
$ARGUMENTS
```

## Execution

### Parse Flags

```python
args = "$ARGUMENTS"
if "--detail" in args:
    MODE = "detail"
    PAPER_ID = args.replace("--detail", "").strip()
elif "--list" in args:
    MODE = "list"
elif "--formulas" in args:
    MODE = "formulas"
    PAPER_ID = args.replace("--formulas", "").strip() or None
else:
    MODE = "search"
    QUERY = args.strip().strip('"').strip("'")
```

### Check Pipeline Availability

```bash
curl -sf http://localhost:8775/health >/dev/null 2>&1
```

**If pipeline is not available:**
```
⚠️ Research Pipeline non disponibile (localhost:8775).
Avvia con: cd /media/sam/1TB/research-pipeline && docker compose up -d
```

### List Papers (--list or default)

```bash
curl -sf http://localhost:8775/papers?limit=50
```

**Output:**

```markdown
## Research Papers in Pipeline

| ID | Title | Stage | Score | arXiv |
|----|-------|-------|-------|-------|
| 1 | [Title](arxiv_url) | codegen | 0.85 | 2401.00001 |
| 2 | [Title](arxiv_url) | analyzed | 0.72 | 2401.00002 |
```

### Paper Detail (--detail ID)

```bash
curl -sf "http://localhost:8775/papers?id=PAPER_ID"
```

Returns paper with nested formulas, validations, and generated code.

**Output:**

```markdown
## Paper Detail: [Title]

**Authors:** [Author list]
**arXiv:** [ID]
**Stage:** [stage]
**Score:** X/1.0
**DOI:** [doi]

### Formulas (N total)

**Formula 1:** [description]
```latex
f^* = \frac{p}{a} - \frac{q}{b}
```

**Validations:**
| Engine | Valid | Time |
|--------|-------|------|
| sympy | ✅ | 120ms |
| maxima | ✅ | 85ms |

**Generated Code:**
| Language | Stage |
|----------|-------|
| python | codegen |
```

### List Formulas (--formulas [ID])

```bash
# All formulas
curl -sf http://localhost:8775/formulas?limit=50

# Formulas for specific paper
curl -sf "http://localhost:8775/formulas?paper_id=PAPER_ID"
```

### Search Papers (default mode)

Search papers by matching query against titles in the results:

```bash
# Fetch all papers
curl -sf http://localhost:8775/papers?limit=100
```

Then filter client-side by checking if QUERY terms appear in title or abstract.

## Output Format

### Recent Academic Research

| Paper | Stage | Score | Formulas |
|-------|-------|-------|----------|
| [Title 1](arxiv_url) | codegen | 0.85 | 3 validated |
| [Title 2](arxiv_url) | discovered | - | - |

### Paper Details: [Title]

**Authors:** [Author list]
**arXiv:** [ID]
**Score:** X/1.0

#### Validated Formulas

**Formula 1:** Kelly Criterion
```latex
f* = \frac{p \cdot b - q}{b}
```

**Multi-CAS Validation:**
| CAS | Result | Time |
|-----|--------|------|
| SymPy | VALID | 120ms |
| Maxima | VALID | 85ms |

**Confidence:** HIGH (2/2 consensus)

#### Generated Code

**Python:**
```python
def kelly_fraction(win_prob: float, win_loss_ratio: float) -> float:
    q = 1 - win_prob
    return (win_prob * win_loss_ratio - q) / win_loss_ratio
```

## No Results?

If no results found:
1. Check if pipeline is running: `docker compose ps` in research-pipeline/
2. Pipeline may need a run: `curl -X POST http://localhost:8775/run -H 'Content-Type: application/json' -d '{"query": "your query", "stages": 5, "max_papers": 10}'`

Run `/research "your query"` to trigger new academic research via the pipeline.

## Related Commands

- `/research` - Trigger new research with CoAT (delegates to pipeline)
