---
name: speckit.autofix
description: Auto-fix issues found by /speckit.analyze to reach confidence threshold. Iterates until CRITICAL=0 and confidence >= threshold.
---

# /speckit.autofix - Automatic Issue Resolution

Automatically fixes issues found by `/speckit.analyze` until confidence threshold is reached.

## Usage

```bash
/speckit.autofix                    # Fix until confidence >= 85 (default)
/speckit.autofix --threshold 90     # Custom threshold
/speckit.autofix --max-iterations 5 # Max fix attempts
/speckit.autofix --dry-run          # Show what would be fixed
```

## What It Fixes

| Issue Type | Auto-Fix Strategy |
|------------|-------------------|
| **Coverage Gap** | Add missing tasks to tasks.md |
| **Duplication** | Merge duplicate requirements in spec.md |
| **Ambiguity** | Add measurable criteria to vague terms |
| **Inconsistency** | Align terminology across artifacts |
| **Missing Dependency** | Add dependency links in tasks.md |
| **Constitution Violation** | Flag for human (cannot auto-fix) |

## Execution Flow

```
┌─────────────────────────────────────────────┐
│  /speckit.autofix                           │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 1. Run /speckit.analyze                     │
│    Parse issues into fixable categories     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 2. Check for CRITICAL issues                │
│    CRITICAL = human review required         │
│    If only CRITICAL → exit 2                │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 3. Fix HIGH/MEDIUM/LOW issues               │
│    Coverage gaps → add tasks                │
│    Duplications → merge                     │
│    Ambiguities → add criteria               │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 4. Re-run /speckit.analyze                  │
│    Check new issue count                    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ 5. /confidence-gate --step autofix          │
│    confidence >= threshold? → done          │
│    else → iterate (max N times)             │
└─────────────────┬───────────────────────────┘
                  ↓
              RESULT
```

## Execution

When invoked:

### Step 1: Initial Analysis

```bash
echo "🔬 Running initial analysis..."
ANALYZE_OUTPUT=$(/speckit.analyze)

# Parse issues
CRITICAL_COUNT=$(echo "$ANALYZE_OUTPUT" | grep -c "CRITICAL" || echo 0)
HIGH_COUNT=$(echo "$ANALYZE_OUTPUT" | grep -c "HIGH" || echo 0)
MEDIUM_COUNT=$(echo "$ANALYZE_OUTPUT" | grep -c "MEDIUM" || echo 0)
LOW_COUNT=$(echo "$ANALYZE_OUTPUT" | grep -c "LOW" || echo 0)
TOTAL_ISSUES=$((CRITICAL_COUNT + HIGH_COUNT + MEDIUM_COUNT + LOW_COUNT))

echo "📊 Issues found: $CRITICAL_COUNT CRITICAL, $HIGH_COUNT HIGH, $MEDIUM_COUNT MEDIUM, $LOW_COUNT LOW"
```

### Step 2: Check CRITICAL

```bash
if [ "$CRITICAL_COUNT" -gt 0 ] && [ "$HIGH_COUNT" -eq 0 ] && [ "$MEDIUM_COUNT" -eq 0 ]; then
    echo "🚫 Only CRITICAL issues remain - cannot auto-fix"
    echo "   CRITICAL issues require human intervention:"
    echo "$ANALYZE_OUTPUT" | grep -A2 "CRITICAL"
    exit 2
fi
```

### Step 3: Fix Loop

```python
MAX_ITERATIONS = args.max_iterations or 3
THRESHOLD = args.threshold or 85

for iteration in range(MAX_ITERATIONS):
    print(f"\n🔧 Fix iteration {iteration + 1}/{MAX_ITERATIONS}")

    # Parse current issues
    issues = parse_analyze_output(analyze_output)

    # Fix by priority (HIGH first, then MEDIUM, then LOW)
    for issue in sorted(issues, key=lambda x: x.severity, reverse=True):
        if issue.severity == "CRITICAL":
            continue  # Skip - needs human

        if issue.category == "coverage_gap":
            fix_coverage_gap(issue)
        elif issue.category == "duplication":
            fix_duplication(issue)
        elif issue.category == "ambiguity":
            fix_ambiguity(issue)
        elif issue.category == "inconsistency":
            fix_inconsistency(issue)
        elif issue.category == "missing_dependency":
            fix_dependency(issue)

    # Re-analyze
    analyze_output = run_analyze()

    # Check confidence
    gate_result = run_confidence_gate(analyze_output, step="autofix")

    if gate_result.confidence >= THRESHOLD:
        print(f"✅ Confidence {gate_result.confidence}% >= {THRESHOLD}% threshold")
        break
    else:
        print(f"📈 Confidence {gate_result.confidence}% < {THRESHOLD}% - continuing...")
```

### Fix Strategies

**Coverage Gap:**
```python
def fix_coverage_gap(issue):
    """Add missing task for uncovered requirement."""
    requirement = issue.requirement_key

    # Generate task from requirement
    task = {
        "id": generate_task_id(),
        "description": f"Implement: {requirement}",
        "phase": infer_phase(requirement),
        "files": infer_files(requirement),
    }

    append_to_tasks_md(task)
    print(f"  ✅ Added task for: {requirement}")
```

**Duplication:**
```python
def fix_duplication(issue):
    """Merge duplicate requirements, keep better phrasing."""
    req1, req2 = issue.duplicates
    better = req1 if len(req1) > len(req2) else req2  # Keep more detailed

    remove_from_spec(req2 if better == req1 else req1)
    print(f"  ✅ Merged duplicate: kept '{better[:50]}...'")
```

**Ambiguity:**
```python
def fix_ambiguity(issue):
    """Add measurable criteria to vague terms."""
    VAGUE_TO_CONCRETE = {
        "fast": "< 200ms response time",
        "scalable": "supports 10,000 concurrent users",
        "secure": "OWASP Top 10 compliant",
        "intuitive": "< 3 clicks to complete core action",
        "robust": "99.9% uptime SLA",
    }

    vague_term = issue.vague_term
    if vague_term.lower() in VAGUE_TO_CONCRETE:
        concrete = VAGUE_TO_CONCRETE[vague_term.lower()]
        replace_in_spec(vague_term, f"{vague_term} ({concrete})")
        print(f"  ✅ Clarified '{vague_term}' → '{concrete}'")
```

**Inconsistency:**
```python
def fix_inconsistency(issue):
    """Align terminology across artifacts."""
    canonical = issue.terms[0]  # First occurrence is canonical

    for variant in issue.terms[1:]:
        replace_in_all_artifacts(variant, canonical)

    print(f"  ✅ Aligned terminology: '{canonical}'")
```

## Output

```
═══════════════════════════════════════════════════════════
  SPECKIT AUTOFIX
═══════════════════════════════════════════════════════════

🔬 Initial analysis: 2 HIGH, 5 MEDIUM, 3 LOW issues

🔧 Fix iteration 1/3
  ✅ Added task for: user-can-reset-password
  ✅ Merged duplicate requirement
  ✅ Clarified 'fast' → '< 200ms response time'
  ✅ Aligned terminology: 'user' (was: 'User', 'USER')

📊 Re-analysis: 0 HIGH, 2 MEDIUM, 1 LOW issues

🔧 Fix iteration 2/3
  ✅ Added task for: api-rate-limiting
  ✅ Clarified 'secure' → 'OWASP Top 10 compliant'

📊 Re-analysis: 0 HIGH, 0 MEDIUM, 1 LOW issues

🔒 Confidence gate: 88% >= 85% threshold

═══════════════════════════════════════════════════════════
  RESULT: ✅ All fixable issues resolved
  - Fixed: 7 issues
  - Remaining: 1 LOW (acceptable)
  - Confidence: 88%
═══════════════════════════════════════════════════════════
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Confidence threshold reached |
| 1 | Max iterations reached, some issues remain |
| 2 | Only CRITICAL issues remain (needs human) |
| 3 | Error |

## Integration with Pipeline

In `/pipeline:speckit`, autofix runs automatically if analyze finds issues:

```bash
# Step 6: Analyze
ANALYZE_OUTPUT=$(/speckit.analyze)

# Step 6b: Autofix if needed
if echo "$ANALYZE_OUTPUT" | grep -qE "HIGH|MEDIUM"; then
    echo "🔧 Auto-fixing issues..."
    /speckit.autofix --threshold $THRESHOLD
fi

# Step 7: Confidence Gate
/confidence-gate --step analyze
```
