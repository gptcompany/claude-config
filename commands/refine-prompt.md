# /refine-prompt - Transform Vague Requests into Actionable Specifications

Transform vague or incomplete prompts into precise, actionable specifications optimized for implementation.

## Usage

```
/refine-prompt <your prompt>
/refine-prompt fix the bug
/refine-prompt add authentication
/refine-prompt improve performance
```

## When to Use

- Prompt feels vague or underspecified
- Multiple interpretations possible
- Complex feature requiring clarification
- Before starting significant implementation work
- When you want Claude to ask better questions

## Refinement Process

Analyze the user's prompt through these lenses:

### 1. Domain Detection

Identify which domain(s) the request touches based on the current project:

| Domain | Common Indicators | Clarifications Needed |
|--------|------------------|----------------------|
| **Backend** | API, database, server, auth | Endpoints? Data model? |
| **Frontend** | UI, component, page, form | Framework? Design system? |
| **Data** | pipeline, ETL, migration, schema | Source? Format? Volume? |
| **DevOps** | deploy, CI/CD, docker, infra | Environment? Scale? |
| **Testing** | test, coverage, e2e, unit | Scope? Frameworks? |
| **Security** | auth, permissions, encryption | Compliance? Attack vectors? |

### 2. Specificity Analysis

For the prompt "$ARGUMENTS", identify:

**Missing Elements:**
- [ ] Target file(s) or module(s)
- [ ] Specific function/class names
- [ ] Input/output specifications
- [ ] Success criteria
- [ ] Edge cases to handle
- [ ] Integration points
- [ ] Error handling requirements

**Ambiguous Terms:**
| Vague Term | Clarifying Questions |
|------------|---------------------|
| "fix" | What's broken? Error message? Expected vs actual? |
| "improve" | Performance? Readability? Accuracy? By what metric? |
| "add" | Where exactly? How should it integrate? |
| "update" | What specifically changes? Backwards compatibility? |
| "refactor" | What's the target architecture? Constraints? |
| "optimize" | Speed? Memory? Readability? Current bottleneck? |

### 3. Project Context

Apply project-specific knowledge by checking:

1. **CLAUDE.md** - Project conventions and constraints
2. **ARCHITECTURE.md** - System design and patterns
3. **README.md** - Project purpose and setup
4. **Existing code patterns** - How similar features are implemented

```python
# Common clarifications needed:
- Language/framework version constraints?
- Existing patterns to follow?
- External dependencies allowed?
- Test coverage requirements?
- Documentation requirements?
```

### 4. Technical Precision

For technical requests:

- Specify algorithms or approaches explicitly
- Define variable names, types, and units
- State assumptions
- Identify potential edge cases
- Consider error scenarios

## Output Format

Generate a refined prompt with this structure:

```markdown
## Refined Request

### Objective
[One clear sentence describing the goal]

### Scope
- Target: [specific files/modules]
- Changes: [what will be modified]
- Constraints: [what must NOT change]

### Technical Specification
[Precise description with:
- Input/output types
- Algorithm or logic
- Error handling
- Edge cases]

### Success Criteria
1. [Measurable criterion 1]
2. [Measurable criterion 2]
3. [Test coverage requirement]

### Questions for User (if any)
- [Clarifying question 1]
- [Clarifying question 2]
```

## Examples

### Example 1: Vague Bug Fix

**Original:** "fix the login bug"

**Refined:**
```markdown
## Refined Request

### Objective
Debug and fix the authentication issue in the login flow.

### Scope
- Target: `src/auth/` or `app/login/`
- Changes: Fix identified bugs while maintaining existing interface
- Constraints: No changes to session management or password storage

### Technical Specification
To diagnose, need to identify:
1. Error type: Runtime exception? Auth failure? Session issue?
2. Symptom: When does it fail? Specific user conditions?
3. Expected behavior: What should happen on successful login?

### Success Criteria
1. All existing auth tests pass
2. Login flow works for valid credentials
3. Proper error messages for invalid credentials

### Questions for User
- What error message or behavior are you seeing?
- Can you reproduce it consistently?
- Do you have logs or screenshots?
```

### Example 2: Vague Feature Request

**Original:** "add caching"

**Refined:**
```markdown
## Refined Request

### Objective
Implement caching for [specific operation] to improve performance.

### Scope
- Target: [API endpoints? Database queries? Computed values?]
- Changes: Add caching layer with appropriate invalidation
- Constraints: Maintain data consistency

### Technical Specification
```python
# Caching options to consider:
- In-memory (Redis, Memcached)
- Local cache (LRU)
- HTTP cache headers
- Database query cache

# Parameters needed:
- TTL (time to live)
- Cache key strategy
- Invalidation triggers
```

### Success Criteria
1. Response time reduced by X%
2. Cache hit rate > Y%
3. No stale data served beyond TTL

### Questions for User
- What specifically should be cached?
- What invalidation strategy?
- What's the acceptable staleness?
- Expected cache size/memory budget?
```

### Example 3: Vague Improvement Request

**Original:** "improve performance"

**Refined:**
```markdown
## Refined Request

### Objective
Optimize performance of [specific component/operation].

### Scope
- Target: [identified bottleneck]
- Changes: Performance optimization while maintaining functionality
- Constraints: No breaking API changes

### Technical Specification
Performance improvements could include:

| Aspect | Current | Potential Improvement |
|--------|---------|----------------------|
| Query optimization | N+1 queries | Eager loading, batching |
| Algorithm | O(n²) | O(n log n) or O(n) |
| Caching | None | Add caching layer |
| Concurrency | Sequential | Parallel processing |

### Success Criteria
1. Measurable improvement in [metric]
2. No regression in other areas
3. Load test passes with [X] concurrent users

### Questions for User
- What's currently slow? (specific operation/page/endpoint)
- Current performance metrics?
- Target performance?
- Performance budget (memory/CPU tradeoffs)?
```

## Integration

After refinement:
1. User reviews and approves refined prompt
2. Use refined prompt for implementation
3. Refined prompt serves as mini-specification

For complex features, consider using `/speckit.specify` instead for full specification workflow.

## Notes

- This command does NOT execute the task, only refines the prompt
- User must explicitly proceed with the refined version
- Output can feed into `/speckit.specify` for larger features
