# Visual Validation Extension

## Overview

Visual validation templates for UI/UX testing with:
- Playwright screenshot capture
- Reference image comparison
- Claude Code semantic analysis
- Accessibility visual checks

## Components

### 1. Screenshot Capture (Playwright)
- `playwright-visual.config.j2` - Playwright config for screenshots
- `capture-screenshots.js.j2` - Script to capture baseline/current screenshots

### 2. Reference Comparison
- `compare-visual.py.j2` - Python script for visual diff
- `visual-report.html.j2` - HTML report template

### 3. Claude Code Integration
- `claude-visual-review.md` - Prompt template for Claude visual analysis
- Semantic diff instead of pixel diff

## Usage

```bash
# 1. Capture baseline
npm run visual:baseline

# 2. Run comparison
npm run visual:compare

# 3. Claude semantic review (interactive)
claude "Review screenshots in .visual/current vs .visual/baseline"
```

## What Claude Can Validate

| Category | Examples |
|----------|----------|
| Layout | Component alignment, spacing consistency |
| Charts | Axis labels, legend, data accuracy |
| Dashboards | Widget placement, responsive behavior |
| Forms | Field ordering, validation states |
| Accessibility | Contrast, text size, focus indicators |
| Branding | Colors, fonts, logo placement |

## Workflow Integration

```
Build → Capture Screenshot → Compare → Claude Review → Pass/Fail
```

## Best Practices

1. **Baseline Management**: Store in git LFS or S3
2. **Threshold**: 0.1% pixel diff tolerance (anti-aliasing)
3. **Component Isolation**: Test components individually (Storybook)
4. **Viewport Matrix**: Desktop, tablet, mobile
5. **CI Integration**: Block merge on visual regression
