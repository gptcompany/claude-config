# Plan 06-02: Accessibility Validation Templates

## Status: COMPLETED

**Completed:** 2026-01-20
**Duration:** ~10 minutes

## Objective

Create accessibility validation templates using axe-core with Playwright for WCAG 2.1 AA compliance checking in CI/CD pipelines.

## Files Created

### 1. axe.config.js.j2
**Path:** `~/.claude/templates/validation/validators/accessibility/axe.config.js.j2`

Jinja2 template for axe-core configuration with:
- WCAG tag selection (wcag2a, wcag2aa, wcag21a, wcag21aa)
- Configurable excluded selectors for third-party widgets
- Rule disable capability with justification documentation
- Export helpers for use in Playwright tests

**Variables:**
- `{{ project_name }}` - Project identifier
- `{{ wcag_level | default('wcag21aa') }}` - WCAG compliance level
- `{{ excluded_selectors | default([]) }}` - CSS selectors to exclude
- `{{ disabled_rules | default([]) }}` - Rules to disable with reasons

### 2. test_a11y.spec.ts.j2
**Path:** `~/.claude/templates/validation/validators/accessibility/test_a11y.spec.ts.j2`

Playwright accessibility test suite with:
- Per-page accessibility scanning using AxeBuilder
- WCAG tag configuration based on compliance level
- Detailed violation reporting with:
  - Impact level (critical, serious, moderate, minor)
  - Description and help URLs
  - Affected DOM nodes with HTML snippets
  - Fix suggestions
- Component state tests (loading, keyboard, forms, contrast)
- JSON report generation for CI artifacts

**Variables:**
- `{{ project_name }}` - Project identifier
- `{{ pages | default(['/']) }}` - Pages to test
- `{{ timeout | default(30000) }}` - Test timeout in ms
- `{{ wcag_level | default('wcag21aa') }}` - WCAG compliance level
- `{{ excluded_selectors | default([]) }}` - CSS selectors to exclude

### 3. accessibility.yml.j2
**Path:** `~/.claude/templates/validation/ci/accessibility.yml.j2`

GitHub Actions workflow with:
- Triggers on push/PR to main/develop
- Path filters for frontend files (tsx, jsx, vue, svelte, html, css)
- Playwright container for consistent browser testing
- Dev server startup with wait-on
- axe-html-reporter integration for detailed HTML reports
- Artifact upload (30-day retention)
- PR comment with violation summary table
- **Blocking behavior:** Exits with code 1 on violations

**Variables:**
- `{{ project_name }}` - Project identifier
- `{{ node_version | default('20') }}` - Node.js version
- `{{ start_command | default('npm run dev') }}` - Dev server command
- `{{ base_url | default('http://localhost:3000') }}` - Application URL
- `{{ test_command | default('npx playwright test tests/accessibility') }}` - Test command
- `{{ wcag_level | default('wcag21aa') }}` - WCAG compliance level

## Verification

| Check | Status |
|-------|--------|
| axe.config.js.j2 valid Jinja2 | PASS |
| test_a11y.spec.ts.j2 valid Jinja2 | PASS |
| accessibility.yml.j2 valid Jinja2 | PASS |
| Rendered YAML is valid | PASS |
| WCAG tags configured correctly | PASS |
| CI blocks PRs on violations | PASS |

## Usage Example

```bash
# Scaffold accessibility tests for a project
cd /path/to/project

# Render templates
jinja2 ~/.claude/templates/validation/validators/accessibility/axe.config.js.j2 \
  -D project_name="my-app" \
  -D wcag_level="wcag21aa" \
  -D excluded_selectors='["#third-party-widget"]' \
  > tests/accessibility/axe.config.js

jinja2 ~/.claude/templates/validation/validators/accessibility/test_a11y.spec.ts.j2 \
  -D project_name="my-app" \
  -D pages='["/", "/dashboard", "/settings"]' \
  > tests/accessibility/a11y.spec.ts

jinja2 ~/.claude/templates/validation/ci/accessibility.yml.j2 \
  -D project_name="my-app" \
  > .github/workflows/accessibility.yml
```

## Dependencies

Required npm packages (auto-installed by CI workflow):
- `@axe-core/playwright` - Playwright integration for axe-core
- `axe-html-reporter` - HTML report generation
- `playwright` - Browser automation

## WCAG Compliance Levels

| Level | Tags Checked | Use Case |
|-------|-------------|----------|
| wcag2a | wcag2a | Minimum legacy compliance |
| wcag2aa | wcag2a, wcag2aa | Legacy standard |
| wcag21a | wcag2a, wcag21a | Minimum modern compliance |
| wcag21aa | wcag2a, wcag2aa, wcag21a, wcag21aa | **Recommended** for most applications |

## Notes

- Templates follow existing patterns from `visual-regression.yml.j2` and `test_visual_regression.spec.j2`
- CI workflow uses Playwright container for consistent cross-platform testing
- Violation reports include actionable fix suggestions and links to axe-core documentation
- PR blocking ensures accessibility issues are caught before merge
