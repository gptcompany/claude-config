---
name: github-workflow
description: GitHub workflow automation for development. Generate standardized PR descriptions, issue templates, and commit messages. Reduces token usage by 70% on repetitive GitHub operations.
---

# GitHub Workflow Automation

Automate common GitHub operations with standardized templates to reduce token consumption.

## Token Consumption Analysis

### **Without Skill** (Direct GitHub Tools)

| Operation | Avg Tokens | Notes |
|-----------|-----------|-------|
| Create PR | ~2,500 | Tool metadata + body generation |
| Create Issue | ~1,800 | Template + label reasoning |
| Add PR Comment | ~1,200 | Review comment context |
| Commit Message | ~1,500 | Context gathering |

**Estimated Total**: ~7,000 tokens for typical PR workflow

### **With Skill** (Template-Driven)

| Operation | Tokens | Savings |
|-----------|--------|---------|
| Create PR | ~600 | **76%** |
| Create Issue | ~500 | **72%** |
| Add PR Comment | ~300 | **75%** |
| Commit Message | ~200 | **87%** |

**Estimated Total**: ~1,600 tokens (77% reduction)

---

## Quick Start

### Create Pull Request
```
User: "Create PR for user authentication feature"

Skill: github-workflow
--> Generates PR with template:
   Title: "[Feature] User Authentication: JWT-based login"
   Body: Auto-generated from template
   Labels: enhancement, auth
   Draft: true (if incomplete)
```

**Token Cost**: ~600 (vs ~2,500 without skill)

---

## Templates

### 1. Pull Request Template

```yaml
Title Pattern: "[{Type}] {Module}: Brief Description"

Types: Feature, Fix, Refactor, Docs, Test, Chore

Body:
## Summary
{description}

## Changes
- **Module**: `{file_path}`
- **Tests**: `{test_file}` ({test_count} tests)
- **Coverage**: {coverage}%

## Test Plan
- [ ] Unit tests passing
- [ ] Integration tests passing (if applicable)
- [ ] Coverage >{threshold}%

## Checklist
- [ ] Code follows project conventions
- [ ] Type hints complete
- [ ] Docstrings for public APIs
- [ ] No breaking changes (or documented)

## Related
- Closes #{issue_number}

Generated with [Claude Code](https://claude.ai/code)
```

**Usage**:
```
skill.create_pr(
    type="Feature",
    module="UserAuth",
    description="JWT-based authentication with refresh tokens",
    file_path="src/auth/jwt_handler.py",
    test_file="tests/test_jwt_handler.py",
    coverage=87,
    issue_number=42
)
```

---

### 2. Issue Template

```yaml
Title: "[{Type}] {Feature Name}"

Body:
## Goal
{goal}

## Deliverables
- [ ] `{deliverable_file}`
- [ ] `{test_file}`
- [ ] Coverage >{threshold}%
- [ ] Documentation updated

## Acceptance Criteria
{criteria_list}

## Technical Notes
{technical_notes}

## Labels
- `{type}` (enhancement/bug/docs)
- `{priority}` (P0-P3)
```

**Usage**:
```
skill.create_issue(
    type="enhancement",
    feature="OAuth Integration",
    goal="Add Google and GitHub OAuth login options",
    deliverable_file="src/auth/oauth.py",
    priority="P1"
)
```

---

### 3. PR Review Comment Template

```yaml
## Pattern: Suggest Improvement

**Code Review**: {file}:{line}

**Issue**: {issue_description}

**Suggestion**:
```{language}
{suggested_code}
```

**Reason**: {explanation}
```

**Usage**:
```
skill.add_review_comment(
    file="src/auth/handler.py",
    line=45,
    issue="Missing error handling for expired tokens",
    suggestion="try:\n    verify_token(token)\nexcept TokenExpiredError:\n    raise HTTPException(401)",
    language="python"
)
```

---

### 4. Commit Message Template

```yaml
Pattern:
[{Type}] {Module}: Brief description

{detailed_changes}

- Deliverable: {file}
- Tests: {test_file}
- Coverage: {coverage}%

Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Usage**:
```
skill.generate_commit_msg(
    type="Feature",
    module="Auth",
    description="Implement JWT token refresh",
    file="src/auth/jwt.py",
    coverage=87
)
```

**Output**:
```
[Feature] Auth: Implement JWT token refresh

- Add refresh token generation and validation
- Implement token rotation on refresh
- Add blacklist for revoked tokens

- Deliverable: src/auth/jwt.py
- Tests: tests/test_jwt.py (8 tests)
- Coverage: 87%

Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Workflow Automation

### Workflow 1: Complete PR Creation
```
User: "Create PR for feature X"

Skill Execution:
1. Read git diff
2. Extract changes summary
3. Count tests
4. Check coverage
5. Generate PR body from template
6. Call gh pr create with template
7. Add labels
8. Set draft=true (if tests incomplete)

Token Cost: ~600 (vs ~2,500 manual)
```

### Workflow 2: Feature Issue Creation
```
User: "Create issue for new feature"

Skill Execution:
1. Create issue from template
2. Add feature-specific checklist
3. Link to relevant docs
4. Assign labels

Token Cost: ~500 (vs ~1,800 manual)
```

---

## Recommended Labels

```yaml
labels:
  types:
    - enhancement
    - bug
    - docs
    - refactor
    - test
    - chore
  priorities:
    - P0-critical
    - P1-high
    - P2-medium
    - P3-low
  status:
    - needs-review
    - in-progress
    - blocked
    - ready-to-merge
```

---

## Best Practices

### PR Best Practices
- Always use draft PRs for incomplete work
- Link to related issue (#XX)
- Include test coverage in description
- List breaking changes explicitly

### Issue Best Practices
- One feature per issue
- Clear acceptance criteria
- Include technical notes
- Link to relevant documentation

### Commit Message Best Practices
- Follow [Type] prefix convention
- Be concise but descriptive
- Include deliverable file paths
- Always add Claude attribution

---

## Automatic Invocation

**Triggers**:
- "create PR for [feature/module]"
- "create issue for [feature]"
- "generate commit message for [changes]"
- "add review comment to PR [number]"

**Does NOT trigger**:
- Complex PR review reasoning (use human judgment)
- Code conflict resolution (use git tools)
- Strategic issue prioritization (use human judgment)

---

## Token Savings Summary

| Operation | Without Skill | With Skill | Savings |
|-----------|--------------|------------|---------|
| Create PR | 2,500 | 600 | **76%** |
| Create Issue | 1,800 | 500 | **72%** |
| PR Comments | 1,200 | 300 | **75%** |
| Commit Msg | 1,500 | 200 | **87%** |
| **Total** | **7,000** | **1,600** | **77%** |
