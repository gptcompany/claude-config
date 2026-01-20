# Plan 06-04 Summary: Performance Validation Templates

**Status:** COMPLETED
**Date:** 2026-01-20
**Phase:** 06 - Hybrid UAT Validators

## Objective

Create performance validation templates using Lighthouse CI for Core Web Vitals testing.

## Files Created

### 1. Lighthouse CI Configuration
**Path:** `~/.claude/templates/validation/validators/performance/lighthouserc.js.j2`
**Size:** 88 lines

Core features:
- Multi-run testing (default: 5 runs) to reduce variance
- Optimistic aggregation method to reduce flakiness
- Core Web Vitals assertions:
  - First Contentful Paint (FCP): max 2000ms
  - Largest Contentful Paint (LCP): max 2500ms
  - Cumulative Layout Shift (CLS): max 0.1
  - Total Blocking Time (TBT): max 300ms
- Category score assertions (performance, accessibility, best practices, SEO)
- Resource budget assertions (scripts, CSS, images, total)
- Upload configuration for temporary public storage or LHCI server
- Optional strict mode for additional assertions

### 2. Performance Budgets
**Path:** `~/.claude/templates/validation/validators/performance/budgets.json.j2`
**Size:** 130 lines

Features:
- Resource size budgets (KB):
  - Scripts: 300KB
  - Stylesheets: 100KB
  - Images: 500KB
  - Fonts: 100KB
  - Total: 1500KB
  - Third-party: 200KB
- Resource count limits
- Core Web Vitals timing budgets
- Support for additional path-specific budgets

### 3. GitHub Actions Workflow
**Path:** `~/.claude/templates/validation/ci/performance.yml.j2`
**Size:** 213 lines

Features:
- Triggers on push, pull request, and manual dispatch
- Concurrency management to cancel in-progress runs
- Uses `treosh/lighthouse-ci-action@v11`
- wait-on package for server readiness
- GitHub Step Summary with results table
- PR comments with Lighthouse scores and report links
- Optional performance budget check job
- Optional Slack notifications on failure
- Artifact upload for report retention

## Jinja2 Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | Required | Project identifier |
| `urls` | `['http://localhost:3000/']` | URLs to test |
| `number_of_runs` | `5` | Lighthouse runs per URL |
| `fcp_max` | `2000` | FCP threshold (ms) |
| `lcp_max` | `2500` | LCP threshold (ms) |
| `cls_max` | `0.1` | CLS threshold |
| `tbt_max` | `300` | TBT threshold (ms) |
| `script_budget_kb` | `300` | Script size budget |
| `css_budget_kb` | `100` | CSS size budget |
| `image_budget_kb` | `500` | Image size budget |
| `total_budget_kb` | `1500` | Total size budget |
| `perf_score_min` | `0.8` | Min performance score |
| `a11y_score_min` | `0.9` | Min accessibility score |
| `aggregation_method` | `'optimistic'` | Result aggregation |
| `upload_target` | `'temporary-public-storage'` | Where to upload |

## Validation

All templates passed Jinja2 syntax validation:
- `lighthouserc.js.j2` - OK
- `budgets.json.j2` - OK
- `performance.yml.j2` - OK

## Usage Example

```yaml
# In project's validation config
performance:
  enabled: true
  variables:
    project_name: "my-app"
    urls:
      - "http://localhost:3000/"
      - "http://localhost:3000/dashboard"
    fcp_max: 1800
    lcp_max: 2200
    script_budget_kb: 250
```

## Core Web Vitals Thresholds Reference

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| FCP | < 1.8s | 1.8s - 3s | > 3s |
| LCP | < 2.5s | 2.5s - 4s | > 4s |
| CLS | < 0.1 | 0.1 - 0.25 | > 0.25 |
| TBT | < 200ms | 200ms - 600ms | > 600ms |

## Integration Notes

1. **CI Integration:** Works with existing workflow structure in `~/.claude/templates/validation/ci/`
2. **Wait-on:** Uses npm `wait-on` package for reliable server startup detection
3. **Aggregation:** Optimistic aggregation takes best of N runs to reduce CI flakiness
4. **Reports:** Uploads to temporary public storage by default, or configurable LHCI server

## Next Steps

- Plan 06-05: Visual regression testing templates (if applicable)
- Integration with validation-config.json schema for project-level customization
