# /research-papers - Query Academic Papers Knowledge Base

Query processed academic papers using RAG (semantic search + knowledge graph).

## Usage

```
/research-papers "query"              # Semantic search (hybrid mode)
/research-papers --local "query"      # Local context search
/research-papers --global "query"     # Global summary search
/research-papers --db                 # Show DB records (PostgreSQL)
/research-papers --list               # List indexed papers
```

## User Input

```text
$ARGUMENTS
```

## Execution

### Parse Flags

```python
args = "$ARGUMENTS"
if "--db" in args:
    MODE = "database"
elif "--list" in args:
    MODE = "list"
elif "--local" in args:
    MODE = "local"
    QUERY = args.replace("--local", "").strip()
elif "--global" in args:
    MODE = "global"
    QUERY = args.replace("--global", "").strip()
else:
    MODE = "hybrid"
    QUERY = args.strip().strip('"').strip("'")
```

### RAG Query (Default)

For MODE in ["hybrid", "local", "global"]:

```bash
curl -s -X POST http://localhost:8767/query \
  -H "Content-Type: application/json" \
  -d '{"query": "QUERY", "mode": "MODE"}'
```

**Output:**

```markdown
## Research Papers Query

**Query**: {query}
**Mode**: {mode}

### Answer

{answer from RAG knowledge graph}

---
*Processed via RAGAnything v3.0*
```

### Database Query (--db)

If `MODE == "database"`, query PostgreSQL for paper records:

```sql
-- Connection: postgres://user:pass@localhost:5432/n8n_dev
-- Schema: finance_papers

-- Recent completed papers
SELECT
    p.id,
    p.title,
    p.authors,
    p.relevance_score,
    p.status,
    p.created_at
FROM finance_papers.papers p
WHERE p.status = 'completed'
ORDER BY p.created_at DESC
LIMIT 10;

-- Validated formulas for a paper
SELECT
    f.id,
    f.latex,
    f.context,
    v.consensus_result,
    v.confidence
FROM finance_papers.formulas f
JOIN finance_papers.validations v ON f.id = v.formula_id
WHERE f.paper_id = $PAPER_ID
AND v.confidence IN ('HIGH', 'VERY_HIGH');

-- Generated code
SELECT
    gc.language,
    gc.code,
    gc.is_executable,
    gc.test_results
FROM finance_papers.generated_code gc
WHERE gc.formula_id = $FORMULA_ID;
```

## Output Format

### Recent Academic Research

| Paper | Relevance | Status | Formulas |
|-------|-----------|--------|----------|
| [Title 1](arxiv_url) | 85/100 | Completed | 3 validated |
| [Title 2](arxiv_url) | 72/100 | Processing | - |

### Paper Details: [Title]

**Authors:** [Author list]
**arXiv:** [ID]
**Relevance Score:** X/100

#### Validated Formulas

**Formula 1:** Kelly Criterion
```latex
f* = \frac{p \cdot b - q}{b}
```

**Multi-CAS Validation:**
| CAS | Result | Notes |
|-----|--------|-------|
| SymPy | VALID | Algebraic check passed |
| Wolfram | VALID | Symbolic verification |
| SageMath | VALID | Numerical consistency |

**Confidence:** HIGH (3/3 consensus)

#### Generated Code

**Python (SymPy):**
```python
def kelly_fraction(win_prob: float, win_loss_ratio: float) -> float:
    """
    Calculate optimal Kelly fraction for position sizing.

    Args:
        win_prob: Probability of winning (0-1)
        win_loss_ratio: Ratio of average win to average loss

    Returns:
        Optimal fraction of capital to risk
    """
    q = 1 - win_prob
    return (win_prob * win_loss_ratio - q) / win_loss_ratio
```

**Test Status:** PASSED (3/3 tests)

### Pending Research

If there are pending research requests:

| Query | Triggered | ETA |
|-------|-----------|-----|
| "optimal execution" | 10 min ago | ~5 min |
| "volatility models" | 25 min ago | Processing |

## No Results?

If no results found:
1. Check if N8N pipeline is running: `docker ps | grep n8n`
2. Verify research was triggered: Check Discord for trigger notification
3. Pipeline may still be processing (typical: 15-30 min)

Run `/research "your query"` to trigger new academic research.

## Database Connection

```bash
# Direct PostgreSQL access (if needed)
psql -h localhost -p 5432 -U postgres -d n8n_dev -c "SELECT * FROM finance_papers.papers LIMIT 5;"
```

## Related Commands

- `/research` - Trigger new research with CoAT
- `/audit metrics` - Check pipeline health
