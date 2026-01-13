# /research - CoAT Iterative Research

Deep research using Chain-of-Associated-Thoughts with optional academic enrichment.

## Usage

```
/research "query"                    # CoAT only (fast, ~2-3 min)
/research --save "query"             # CoAT + auto-save to spec (no academic)
/research -s "query"                 # Short form for --save
/research --academic "query"         # CoAT + PMW + N8N + auto-save (smart merge)
/research -a "query"                 # Short form (includes PMW)
/research --academic --no-save "q"   # Skip auto-save to spec
/research --append "query"           # Append new findings to existing research
/research --fresh "query"            # Overwrite existing research completely
/research --version "query"          # Create new version, keep old as backup
```

**Note**: `--academic` automatically includes PMW (Prove Me Wrong) analysis and saves to spec context if detected.

## User Input

```text
$ARGUMENTS
```

**Parse flags first:**
- If `--save` or `-s` present: Set `AUTO_SAVE=true`, `TRIGGER_N8N=false`, `RUN_PMW=false`, `SAVE_MODE=merge`
- If `--academic` or `-a` present: Set `TRIGGER_N8N=true`, `RUN_PMW=true`, `AUTO_SAVE=true`, `SAVE_MODE=merge`
- If `--append` present: Set `SAVE_MODE=append`
- If `--fresh` present: Set `SAVE_MODE=fresh`
- If `--version` present: Set `SAVE_MODE=version`
- If `--no-save` present: Set `AUTO_SAVE=false`
- Default `SAVE_MODE=merge` (smart merge with existing)

You **MUST** process the user's research query using the CoAT methodology below.

## Spec Context Detection

When `AUTO_SAVE=true`, detect spec context to save research:

```bash
# Check for active spec via check-prerequisites.sh
SPEC_DIR=$(.specify/scripts/bash/check-prerequisites.sh --paths-only 2>/dev/null | grep FEATURE_DIR | cut -d= -f2)

# Fallback: Find most recent spec with spec.md
if [ -z "$SPEC_DIR" ]; then
  SPEC_DIR=$(find specs -name "spec.md" -printf '%T@ %h\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2)
fi
```

**If spec context found:**
- Create research directory if needed: `mkdir -p $SPEC_DIR/research`
- Set `SPEC_RESEARCH_PATH=$SPEC_DIR/research/research.md`
- After research complete, save full output to `research/research.md`

**If no spec context:**
- Skip auto-save, output to screen only
- Inform user: "No spec context detected. Use --no-save or run from spec directory."

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

## N8N Academic Trigger (Smart Suggestion)

### Step 1: Check explicit flag
If user passed `--academic` or `-a` → Set `TRIGGER_N8N=true`

### Step 2: Semantic evaluation (if no flag)
After completing CoAT research, evaluate if academic papers would add value.

**Criteria to consider:**
- **Complexity**: Is this a nuanced topic requiring peer-reviewed depth?
- **Novelty**: Are there recent academic advances the user should know?
- **Rigor**: Would mathematical proofs/formulas benefit the answer?
- **Importance**: Is accuracy critical (finance, medical, legal)?
- **Gap**: Did web search leave significant knowledge gaps?

**Decision matrix:**

| Complexity | Importance | Web Coverage | Suggest Academic? |
|------------|------------|--------------|-------------------|
| High | High | Poor | Yes |
| High | Medium | Poor | Yes |
| Medium | High | Poor | Yes |
| Low | Any | Good | No |
| Any | Any | Excellent | No |

### Step 3: Suggest (don't auto-trigger)

If evaluation suggests academic enrichment would help, ASK the user:

```
The research is complete, but this topic could benefit from academic papers:
- [Reason 1: e.g., "Complex mathematical foundations"]
- [Reason 2: e.g., "Recent advances in 2024-2025 not fully covered"]

Would you like me to trigger the academic pipeline? (~15-30 min async)
Reply 'yes' or run: /research --academic "query"
```

**Only trigger after user confirms.**

### Step 4: Trigger (if confirmed or flag present)

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

### Step 5: PMW Validation (if `RUN_PMW=true`)

> **"Cerca attivamente disconferme, non conferme"** - Actively seek disconfirmation, not confirmation.

When `--academic` flag is present, ALWAYS run PMW after CoAT research:

#### 5.1 Counter-Evidence Search

Search for contradicting evidence using inverted queries:

```
Original: "{topic} benefits optimal"
Counter:  "{topic} failure", "{topic} limitations", "{topic} criticism", "{topic} poor performance"
```

Execute WebSearch with counter-queries IN PARALLEL.

#### 5.2 SWOT Assessment

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

#### 5.3 Mitigations Check

For each Threat/Weakness:
- Does existing research address it?
- Is mitigation documented?
- Flag unaddressed risks

#### 5.4 Verdict

Based on PMW analysis, provide verdict:

| Verdict | Meaning | Action |
|---------|---------|--------|
| **GO** | Solid foundation, risks addressed | Proceed with confidence |
| **WAIT** | Issues found but fixable | Address before implementation |
| **STOP** | Fundamental flaws discovered | Rethink approach entirely |

**Include verdict in final output.**

### Examples

**No suggestion needed:**
- "How to use Python asyncio" → Web coverage excellent, low complexity
- "Git rebase vs merge" → Well-documented, no academic depth needed

**Suggest academic:**
- "Optimal execution algorithms for large orders" → High complexity, finance importance
- "Kelly criterion with correlated assets" → Mathematical rigor needed
- "Volatility surface arbitrage" → Recent academic advances, critical accuracy

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

### PMW Analysis (if --academic)

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

## Step 6: Auto-Save to Spec (if `AUTO_SAVE=true`)

When saving is enabled and spec context is detected:

### 6.1 Check for Existing Research

```bash
RESEARCH_FILE="$SPEC_DIR/research/research.md"
if [ -f "$RESEARCH_FILE" ]; then
  EXISTING=true
  # Read existing content for comparison
else
  EXISTING=false
fi
```

### 6.2 Apply Save Mode

**SAVE_MODE=merge (default - Smart Merge):**
1. If no existing file → create new
2. If existing file:
   - Create backup: `research.md.bak`
   - Compare new findings with existing
   - Add only NEW findings (avoid duplicates)
   - Update PMW if new threats found
   - Merge sources (existing + new, deduplicated)
   - Update date and confidence scores
   - Preserve existing validated content

**SAVE_MODE=append:**
1. If no existing file → create new
2. If existing file:
   - Keep all existing content
   - Add separator: `---\n## Research Update (YYYY-MM-DD)\n`
   - Append all new findings below

**SAVE_MODE=fresh:**
1. Create backup: `research.md.bak`
2. Overwrite completely with new research

**SAVE_MODE=version:**
1. If existing file:
   - Rename to: `research_YYYY-MM-DD_HH-MM.md`
2. Create new `research.md` with fresh content

### 6.3 Generate research.md Content

Use the template as base structure:

**Template SSOT:** `~/.claude/templates/research-template.md`

Create a complete markdown document with:
- Header (feature name, date, method, status)
- Research query
- All key findings with sources
- PMW analysis (SWOT + verdict)
- Sources (academic, web, codebase)
- Confidence scores
- Academic pipeline status
- Spec validation table

**Template structure:**
```markdown
# Research: [Feature Name]

**Feature**: [spec-id]
**Research Date**: [date]
**Method**: CoAT + PMW + Academic Pipeline
**Status**: Complete

---

## Research Query
[query]

## Key Findings
[findings with sources]

## PMW: Prove Me Wrong Analysis
[SWOT + Verdict]

## Sources
[academic, web, codebase]

## Confidence
[scores]

## Academic Pipeline
[status]

## Spec Validation
[requirements vs academic support]
```

### 6.4 Report Save Status

After saving, inform user:
```
Research saved to: specs/XXX/research/research.md
- Save mode: [merge|append|fresh|version]
- Existing file: [yes/no]
- Backup created: [yes/no]
- Key findings: N (M new, K existing)
- PMW verdict: GO/WAIT/STOP
- Academic pipeline: Triggered/Not triggered
```

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

**With academic enrichment + PMW + auto-save:**
```
/research --academic "Kelly Criterion optimal bet sizing"
/research -a "volatility modeling GARCH"
```
→ CoAT + PMW + N8N pipeline + smart merge to `specs/XXX/research/research.md`

**Skip auto-save:**
```
/research --academic --no-save "general topic not tied to spec"
```
→ CoAT + PMW + N8N pipeline, output to screen only

**Append to existing research:**
```
/research --academic --append "Kelly criterion multi-asset correlation"
```
→ Keeps existing findings, appends new section with date separator

**Fresh overwrite (with backup):**
```
/research --academic --fresh "complete new research direction"
```
→ Creates backup, then overwrites with fresh research

**Create versioned file:**
```
/research --academic --version "updated findings after paper review"
```
→ Renames existing to `research_2026-01-13_14-30.md`, creates fresh `research.md`

**Codebase-focused:**
```
/research "How does NautilusTrader handle order matching?"
```
→ Heavy Grep/Read, targeted WebSearch
