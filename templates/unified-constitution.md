# Project Constitution Template (Unified)

**Project**: {PROJECT_NAME}
**Created**: {DATE}
**Version**: 1.0.0

## Core Principles (Inherited from Global)

> These principles apply to ALL projects. Project-specific additions below.

### I. KISS + YAGNI (MUST)
- **Keep It Simple, Stupid** - Boring technology wins
- **You Ain't Gonna Need It** - Build for today, not hypothetical futures
- The best code is no code. The second best is deleted code.

### II. Token Efficiency (SHOULD)
- Measure context reduction in every skill/template
- Progressive disclosure over comprehensive dumps
- Target: 60-80% token reduction vs naive approach

### III. Documentation-First (MUST)
- README.md required for every significant module
- ARCHITECTURE.md auto-validated on commits
- ALWAYS look up docs before implementing

### IV. TDD When Applicable (SHOULD)
- Red-Green-Refactor for core business logic
- Tests before implementation for critical paths
- Coverage targets defined per project

### V. Safety-First for Production (MUST for financial systems)
- All safety limits are FIXED, never adaptive
- 90%+ coverage for risk-critical modules
- Knight Capital rule: "Code bugs cause real losses"

---

## Project-Specific Principles

> Add domain-specific principles here. Examples:

### {PROJECT_NAME}-Specific

1. **[Principle Name]** (MUST/SHOULD)
   - Rationale: {why}
   - Implementation: {how}

---

## Quality Gates

### Before Merge
- [ ] All tests pass
- [ ] Coverage meets project threshold
- [ ] No secrets in code
- [ ] Documentation updated

### Before Deploy (Production Systems)
- [ ] Integration tests pass
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured

---

## Governance

- **Constitution Versioning**: SemVer (MAJOR.MINOR.PATCH)
- **Amendment Process**: PR to `.specify/memory/constitution.md`
- **Sync Check**: Templates must align with constitution
