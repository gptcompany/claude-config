# /research - CoAT Iterative Research

Deep research using Chain-of-Associated-Thoughts with optional academic enrichment.

## Usage

```
/research "query"                    # CoAT only (fast, ~2-3 min)
/research --academic "query"         # CoAT + N8N academic pipeline
/research -a "query"                 # Short form
```

## User Input

```text
$ARGUMENTS
```

**Parse flags first:**
- If `--academic` or `-a` present: Set `TRIGGER_N8N=true`, remove flag from query
- Otherwise: `TRIGGER_N8N=false`

You **MUST** process the user's research query using the CoAT methodology below.

## CoAT Process (Chain-of-Associated-Thoughts)

Execute this iterative research loop (max 5 iterations):

### Phase 1: Associate

Generate 3-5 related concepts/queries from the user's question:
- Think laterally - what adjacent topics might be relevant?
- Consider synonyms, related fields, prerequisite concepts
- Identify potential sources: web, codebase, documentation

**Output format:**
```
Associated Queries:
1. [query 1] - [why relevant]
2. [query 2] - [why relevant]
3. [query 3] - [why relevant]
```

### Phase 2: Search

Execute searches IN PARALLEL using multiple sources:

1. **WebSearch** - For current information, articles, documentation
2. **Grep** - Search codebase for implementations, patterns, examples
3. **Read** - Local documentation, README files, specs

For each source, extract:
- Key findings
- Source URL/path
- Confidence in relevance (1-10)

### Phase 3: Evaluate Branches

Score each search branch:

| Branch | Relevance | Confidence | Completeness |
|--------|-----------|------------|--------------|
| Web 1  | X/10      | X/10       | X/10         |
| Web 2  | X/10      | X/10       | X/10         |
| Code 1 | X/10      | X/10       | X/10         |

**Decision logic:**
- If average score < 5: **BACKTRACK** - generate new queries
- If any critical gap identified: **BACKTRACK** with focused query
- Otherwise: proceed to Hypothesize

### Phase 4: Hypothesize

Synthesize findings into a coherent answer:
1. Identify common themes across sources
2. Resolve contradictions (prefer authoritative sources)
3. Note remaining gaps or uncertainties
4. Form preliminary hypothesis/answer

### Phase 5: Refine (Loop Decision)

Calculate overall confidence:
```
Confidence = (avg_relevance + avg_source_quality + coverage) / 3
```

**If confidence < 80% AND iterations < 5:**
- Identify weakest area
- Generate refined queries targeting gaps
- Return to Phase 1

**If confidence >= 80% OR iterations >= 5:**
- Finalize answer
- Check if N8N academic trigger needed
- Output final response

## N8N Academic Trigger (Manual Flag Required)

**Only trigger if user passed `--academic` or `-a` flag.**

If `TRIGGER_N8N=true`:

```bash
~/.claude/scripts/trigger-n8n-research.sh "QUERY_WITHOUT_FLAGS"
```

**Inform user:**
```
Academic research triggered for: "QUERY"
- Discord notification when papers ready (~15-30 min)
- Use `/research-papers` to view results
```

**If `TRIGGER_N8N=false`:** Do NOT mention academic pipeline at all.

## Output Format

### Research Summary

[Synthesized answer addressing the user's query]

### Key Findings

1. **[Finding 1]** - [Source]
2. **[Finding 2]** - [Source]
3. **[Finding 3]** - [Source]

### Sources

**Web:**
- [Title](URL) - [brief relevance note]

**Codebase:**
- `path/to/file.py:line` - [what it shows]

**Documentation:**
- [Doc name] - [relevant section]

### Confidence

**Overall: X/100**

| Dimension | Score |
|-----------|-------|
| Source Quality | X/10 |
| Coverage | X/10 |
| Consistency | X/10 |

### Iterations Performed

X iterations, backtracked Y times

### Academic Enrichment

[Triggered / Not applicable]

If triggered: "Check `/research-papers` in ~15-30 min for academic papers and validated formulas."

## Configuration

- **Max iterations:** 5
- **Confidence threshold:** 80%
- **Sources:** WebSearch, Grep, Read
- **N8N webhook:** http://localhost:5678/webhook/research-trigger
- **Discord notifications:** Enabled via DISCORD_WEBHOOK_URL

## Examples

**General query (CoAT only):**
```
/research "Best practices for Python async error handling"
```
→ WebSearch + codebase, fast (~2-3 min)

**With academic enrichment:**
```
/research --academic "Kelly Criterion optimal bet sizing"
/research -a "volatility modeling GARCH"
```
→ CoAT results immediate + N8N pipeline async (~15-30 min)

**Codebase-focused:**
```
/research "How does NautilusTrader handle order matching?"
```
→ Heavy Grep/Read, targeted WebSearch
