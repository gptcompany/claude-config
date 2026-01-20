# Phase 6: Hybrid UAT & Validators - Research

**Researched:** 2026-01-20
**Domain:** Hybrid UAT workflow, accessibility testing (axe-core), security scanning (Trivy), performance testing (Lighthouse CI)
**Confidence:** HIGH

<research_summary>
## Summary

Researched the ecosystem for building a hybrid auto/manual UAT system with integrated validators. The standard approach uses **@axe-core/playwright** for accessibility, **Trivy** for security, and **Lighthouse CI** for performance, all feeding into a unified dashboard.

Key findings:
1. **axe-playwright** provides seamless WCAG compliance checking directly in Playwright tests
2. **Trivy** is the standard for container + dependency scanning, with first-class GitHub Actions support
3. **Lighthouse CI** offers assertion-based performance budgets with CI integration
4. **Allure Report** and **ReportPortal** are the leading OSS dashboards for test result visualization
5. Confidence scoring should be based on test stability, defect detection rate, and coverage metrics

**Primary recommendation:** Use @axe-core/playwright + Trivy action + Lighthouse CI with Allure Report as the unified dashboard. For terminal TUI, consider Textual (Python) for real-time live monitoring.
</research_summary>

<standard_stack>
## Standard Stack

### Core Validators
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @axe-core/playwright | 4.8.x | Accessibility testing | Official Deque package, full WCAG support |
| trivy-action | master | Security scanning | Aqua Security official, 820+ code snippets in docs |
| @lhci/cli | 0.15.x | Performance testing | Google Chrome official, CI-native |

### Dashboard & Reporting
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| allure-report | 3.x | Test visualization | Framework-agnostic, interactive HTML reports |
| reportportal | 5.x | Real-time dashboard | ML-powered analysis, live monitoring |
| textual | 0.50.x | Terminal TUI | Python, 60 FPS, React-inspired components |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| axe-html-reporter | 2.x | A11y HTML reports | Standalone a11y reports |
| lighthouse | 12.x | Programmatic perf | Direct API access needed |
| budgets.json | - | Perf budgets | Define resource limits |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @axe-core/playwright | axe-playwright (community) | Official has better support |
| Allure | Jest HTML Reporter | Allure is more interactive |
| ReportPortal | Grafana | ReportPortal is test-specific |
| Textual | Rich | Textual has proper TUI widgets |

**Installation:**
```bash
# Validators
npm install @axe-core/playwright axe-html-reporter
npm install -g @lhci/cli@0.15.x

# Dashboard (Python)
pip install allure-pytest textual

# Trivy (binary)
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
validation/
├── config.json                    # Validation config
├── validators/
│   ├── accessibility/
│   │   ├── axe.config.js          # axe-core config
│   │   └── test_a11y.spec.ts      # Playwright + axe tests
│   ├── security/
│   │   ├── trivy.yaml             # Trivy config
│   │   └── .trivyignore           # Known issues to skip
│   └── performance/
│       ├── lighthouserc.js        # Lighthouse CI config
│       └── budgets.json           # Performance budgets
├── dashboard/
│   ├── allure-results/            # Raw test results
│   └── reports/                   # Generated reports
└── ci/
    ├── accessibility.yml          # A11y workflow
    ├── security.yml               # Security workflow
    └── performance.yml            # Perf workflow
```

### Pattern 1: axe-core with Playwright
**What:** Run accessibility checks as part of Playwright tests
**When to use:** Any web UI validation
**Example:**
```typescript
// Source: @axe-core/playwright docs
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('should not have accessibility violations', async ({ page }) => {
  await page.goto('/');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();

  expect(results.violations).toEqual([]);
});
```

### Pattern 2: Trivy GitHub Actions
**What:** Scan containers and dependencies in CI
**When to use:** Every push/PR
**Example:**
```yaml
# Source: trivy.dev/latest/docs
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: '${{ env.IMAGE }}'
    format: 'table'
    exit-code: '1'
    ignore-unfixed: true
    severity: 'CRITICAL,HIGH'
```

### Pattern 3: Lighthouse CI Assertions
**What:** Assert performance budgets in CI
**When to use:** Pre-merge performance gates
**Example:**
```javascript
// Source: lighthouse-ci docs
module.exports = {
  ci: {
    collect: { numberOfRuns: 5 },
    assert: {
      preset: 'lighthouse:recommended',
      assertions: {
        'first-contentful-paint': ['error', { maxNumericValue: 2000 }],
        'interactive': ['error', { maxNumericValue: 5000 }],
        'resource-summary:document:size': ['error', { maxNumericValue: 14000 }]
      }
    }
  }
};
```

### Pattern 4: Confidence Scoring
**What:** Calculate confidence based on test metrics
**When to use:** Hybrid UAT for filtering
**Example:**
```python
def calculate_confidence(test_result):
    """Calculate confidence score (0-100) for a test result."""
    score = 100

    # Reduce for flakiness
    if test_result.flaky_rate > 0.1:
        score -= 30

    # Reduce for low coverage
    if test_result.coverage < 0.8:
        score -= 20

    # Reduce for known issues
    score -= len(test_result.known_issues) * 5

    # Classify
    if score >= 80:
        return 'HIGH', score
    elif score >= 50:
        return 'MEDIUM', score
    else:
        return 'LOW', score
```

### Anti-Patterns to Avoid
- **Running all validators sequentially:** Run in parallel for speed
- **No failure thresholds:** Always set exit-code for CI gates
- **Ignoring false positives:** Use .trivyignore, axe excludes properly
- **No baseline comparison:** Track trends, not just pass/fail
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WCAG compliance | Custom DOM checks | axe-core | 100+ rules, maintained by Deque |
| Vulnerability scanning | grep for CVEs | Trivy | Multiple DBs (NVD, GitHub, etc.) |
| Performance metrics | Custom timing | Lighthouse | Core Web Vitals are standardized |
| Test dashboard | Custom HTML reports | Allure/ReportPortal | Interactive, ML-powered analysis |
| TUI framework | curses/blessed | Textual | 60 FPS, proper widgets |
| Confidence scoring | Static thresholds | Metrics-based calculation | Adapts to test history |

**Key insight:** All three validators (accessibility, security, performance) have mature OSS solutions with years of development. Custom solutions miss edge cases that these tools handle. The dashboard problem is also solved - Allure and ReportPortal are widely adopted.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: axe-core False Positives
**What goes wrong:** Tests fail on valid accessible elements
**Why it happens:** Color contrast rules can't detect background images
**How to avoid:** Use `axe.configure()` to disable specific rules when justified
**Warning signs:** Lots of color-contrast violations on image backgrounds

### Pitfall 2: Trivy Exit Code Confusion
**What goes wrong:** CI passes despite vulnerabilities
**Why it happens:** Default exit-code is 0, need to set to 1
**How to avoid:** Always use `exit-code: '1'` with severity filter
**Warning signs:** Vulnerabilities in logs but green CI

### Pitfall 3: Lighthouse Variance
**What goes wrong:** Flaky performance tests
**Why it happens:** Single run has variance, network conditions vary
**How to avoid:** Use `numberOfRuns: 5` with `aggregationMethod: 'optimistic'`
**Warning signs:** Random perf failures on same code

### Pitfall 4: Dashboard Data Overload
**What goes wrong:** Dashboard shows too much, nothing actionable
**Why it happens:** All results dumped without filtering
**How to avoid:** Focus on failures, trends, and regressions only
**Warning signs:** Dashboard has thousands of green checks, failures buried

### Pitfall 5: Confidence Score Gaming
**What goes wrong:** High confidence scores on unreliable tests
**Why it happens:** Score based only on pass/fail, not stability
**How to avoid:** Include flaky rate, historical trends in calculation
**Warning signs:** HIGH confidence tests that frequently need re-runs
</common_pitfalls>

<code_examples>
## Code Examples

### axe-core with Playwright (Full Example)
```typescript
// Source: playwright.dev/docs/accessibility-testing
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility Tests', () => {
  test('home page WCAG 2.1 AA', async ({ page }) => {
    await page.goto('/');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .exclude('.third-party-widget') // Skip third-party
      .analyze();

    // Detailed failure output
    if (results.violations.length > 0) {
      console.log('Violations:', JSON.stringify(results.violations, null, 2));
    }

    expect(results.violations).toEqual([]);
  });
});
```

### Trivy CI Workflow (Complete)
```yaml
# Source: trivy.dev
name: Security Scan
on: [push, pull_request]

jobs:
  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t app:${{ github.sha }} .

      - name: Container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'app:${{ github.sha }}'
          format: 'sarif'
          output: 'trivy-container.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Dependency scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-deps.sarif'

      - name: Upload results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-container.sarif'
```

### Lighthouse CI Configuration (Complete)
```javascript
// lighthouserc.js - Source: lighthouse-ci docs
module.exports = {
  ci: {
    collect: {
      url: ['http://localhost:3000/', 'http://localhost:3000/dashboard'],
      numberOfRuns: 5,
      settings: {
        budgetPath: './budgets.json'
      }
    },
    assert: {
      preset: 'lighthouse:recommended',
      assertions: {
        // Core Web Vitals
        'first-contentful-paint': ['error', { maxNumericValue: 2000 }],
        'largest-contentful-paint': ['error', { maxNumericValue: 2500 }],
        'cumulative-layout-shift': ['error', { maxNumericValue: 0.1 }],
        'total-blocking-time': ['error', { maxNumericValue: 300 }],
        // Resource budgets
        'resource-summary:script:size': ['warn', { maxNumericValue: 300000 }],
        'resource-summary:image:count': ['warn', { maxNumericValue: 20 }],
        // Categories
        'categories:accessibility': ['error', { minScore: 0.9 }],
        'categories:best-practices': ['warn', { minScore: 0.8 }]
      }
    },
    upload: {
      target: 'temporary-public-storage'
    }
  }
};
```

### Allure Report Generation
```python
# conftest.py - Source: allure-pytest docs
import allure
import pytest

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    if result.when == 'call' and result.failed:
        # Attach screenshot on failure
        if hasattr(item, 'page'):
            allure.attach(
                item.page.screenshot(),
                name='failure_screenshot',
                attachment_type=allure.attachment_type.PNG
            )

# Generate report: allure generate allure-results -o allure-report
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| axe-core standalone | @axe-core/playwright | 2023 | Native Playwright integration |
| Trivy 0.x | Trivy 0.50+ | 2025 | Improved SBOM, VEX support |
| Lighthouse 10 | Lighthouse 12 | 2024 | Better CWV metrics |
| Allure 2 | Allure 3 | 2024 | Rebuilt for usability |
| ReportPortal 5.7 | ReportPortal 5.11+ | 2025 | Enhanced ML analysis |
| curses/blessed | Textual 0.50+ | 2024 | 60 FPS, modern TUI |

**New tools/patterns to consider:**
- **axe DevTools Pro**: Extended rules beyond open-source axe-core
- **Trivy SBOM**: Generate Software Bill of Materials
- **Lighthouse User Flows**: Test multi-page journeys
- **Textual Web**: Browser-based terminal UI

**Deprecated/outdated:**
- **pa11y standalone**: Use axe-core with Playwright instead
- **OWASP ZAP for deps**: Trivy is more comprehensive
- **Manual perf testing**: Lighthouse CI handles it
</sota_updates>

<open_questions>
## Open Questions

1. **Dashboard selection for dual-mode (terminal + web)**
   - What we know: Allure/ReportPortal are web-only, Textual is terminal-only
   - What's unclear: Best way to unify both experiences
   - Recommendation: Use Allure for reports, Textual for live monitoring, shared data layer

2. **Confidence score algorithm tuning**
   - What we know: Should include flakiness, coverage, history
   - What's unclear: Optimal weights for each factor
   - Recommendation: Start with equal weights, tune based on user feedback

3. **ReportPortal vs Allure choice**
   - What we know: Both are excellent, ReportPortal has ML, Allure is simpler
   - What's unclear: Which fits better with existing infrastructure
   - Recommendation: Start with Allure (lighter), migrate to ReportPortal if ML needed
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [/dequelabs/axe-core](https://context7.com/dequelabs/axe-core) - WCAG rules, API usage, integration patterns
- [/websites/trivy_dev](https://context7.com/websites/trivy_dev) - CI/CD integration, configuration
- [/googlechrome/lighthouse-ci](https://context7.com/googlechrome/lighthouse-ci) - Assertions, budgets, CI setup
- [Playwright Accessibility Testing](https://playwright.dev/docs/accessibility-testing) - Official integration guide

### Secondary (MEDIUM confidence)
- [Allure Report](https://allurereport.org/) - Official documentation
- [ReportPortal](https://reportportal.io/) - Official documentation
- [Textual TUI](https://textual.textualize.io/) - Terminal UI framework

### Tertiary (Verified)
- [awesome-tuis](https://github.com/rothgar/awesome-tuis) - TUI tool list
- [BrowserStack QA Metrics](https://www.browserstack.com/guide/essential-qa-metrics) - Confidence scoring patterns
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Hybrid UAT workflow with validators
- Ecosystem: axe-core, Trivy, Lighthouse CI, Allure, ReportPortal, Textual
- Patterns: CI integration, confidence scoring, dashboard architecture
- Pitfalls: False positives, exit codes, variance, data overload

**Confidence breakdown:**
- Standard stack: HIGH - verified with Context7, official docs
- Architecture: HIGH - from official examples and docs
- Pitfalls: HIGH - documented in official troubleshooting
- Code examples: HIGH - from Context7/official sources

**Research date:** 2026-01-20
**Valid until:** 2026-02-20 (30 days - validator ecosystem stable)
</metadata>

---

*Phase: 06-hybrid-uat-validators*
*Research completed: 2026-01-20*
*Ready for planning: yes*
