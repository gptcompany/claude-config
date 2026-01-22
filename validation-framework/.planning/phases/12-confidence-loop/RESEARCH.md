# Phase 12 Research: Confidence-Based Loop Extension

## Open Source Software per Visual-Driven Development

### 1. Screenshot-to-Code (Recommended for Generation)

| Tool | GitHub | Stars | Use Case |
|------|--------|-------|----------|
| **[abi/screenshot-to-code](https://github.com/abi/screenshot-to-code)** | Active | 60k+ | Screenshot → HTML/React/Vue con Claude/GPT-4V |
| **[Mrxyy/screenshot-to-page](https://github.com/Mrxyy/screenshot-to-page)** | Active | 5k+ | Supporta Qwen-VL (open source), Gemini |
| **[tonybeltramelli/pix2code](https://github.com/tonybeltramelli/pix2code)** | Research | 12k | Neural network DSL → code (foundational) |

**Raccomandazione**: `abi/screenshot-to-code` è il più maturo. Supporta Claude Sonnet che già usiamo.

---

### 2. Visual Comparison Tools

#### A. Pixel-Based (Fast, Deterministic)

| Tool | GitHub | Performance | Notes |
|------|--------|-------------|-------|
| **[ODiff](https://github.com/dmtrKovalenko/odiff)** | Active | 6x faster than pixelmatch | SIMD-optimized (Zig), Node.js API |
| **Playwright built-in** | - | Good | `expect(page).toHaveScreenshot()` |
| **[BackstopJS](https://github.com/garris/BackstopJS)** | Active | Good | Self-hosted, CI-ready, config-driven |

#### B. AI/Semantic-Based (Handles Layout Shifts)

| Tool | GitHub | Technology | Notes |
|------|--------|------------|-------|
| **[OpenAI CLIP](https://github.com/openai/CLIP)** | Official | Cosine similarity embeddings | Best for semantic comparison |
| **[visual-similarity-search](https://github.com/stxnext/visual-similarity-search)** | Active | PyTorch + Qdrant | Vector search engine |
| **[VGG16 similarity](https://github.com/SavinRazvan/image-similarity)** | Active | TensorFlow | Pre-trained feature extraction |

**Raccomandazione**: 
- **Pixel comparison**: ODiff (fastest) o Playwright built-in
- **Semantic comparison**: CLIP embeddings + cosine similarity

---

### 3. Visual Regression Testing Platforms (Self-Hosted)

| Tool | License | Features | Best For |
|------|---------|----------|----------|
| **[Visual Regression Tracker](https://github.com/Visual-Regression-Tracker/Visual-Regression-Tracker)** | MIT | Web UI, Docker, SDKs | Team review workflow |
| **[Argos CI](https://github.com/argos-ci/argos)** | MIT | Modern UI, CI/CD integration | GitHub/GitLab projects |
| **[Loki](https://github.com/oblador/loki)** | MIT | Storybook-focused | Component libraries |
| **[reg-suit](https://github.com/reg-viz/reg-suit)** | MIT | CLI, flexible | CI pipelines |
| **[Aye Spy](https://github.com/AyeSpy/AyeSpy)** | MIT | 40 comparisons/60s | High volume |

**Raccomandazione**: **Visual Regression Tracker** per review workflow, **Argos CI** per CI/CD.

---

### 4. Behavioral Testing Tools

| Tool | Technology | Features |
|------|------------|----------|
| **[Playwright](https://github.com/microsoft/playwright)** | Node.js/Python | Multi-browser, parallel, traces |
| **[Puppeteer](https://github.com/puppeteer/puppeteer)** | Node.js | Chrome-focused, mature |
| **[Cypress](https://github.com/cypress-io/cypress)** | Node.js | Real-time reloads, debugging |

**Raccomandazione**: **Playwright** (già integrato via MCP).

---

### 5. Confidence Scoring & Multi-Modal Fusion

| Component | Existing Tool | Integration |
|-----------|---------------|-------------|
| Visual similarity | CLIP + cosine | Python library |
| DOM structure | Playwright snapshot | Built-in |
| Accessibility | axe-core | Playwright integration |
| Performance | Lighthouse | CI template exists |
| Console errors | Playwright console listener | Built-in |

---

## Architettura Proposta

```
┌─────────────────────────────────────────────────────────────┐
│                 VISUAL-DRIVEN DEVELOPMENT LOOP               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT: Target screenshot (reference)                        │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  screenshot- │ →  │  Playwright  │ →  │  Comparison  │  │
│  │  to-code     │    │  Render      │    │  Engine      │  │
│  │  (generate)  │    │  (capture)   │    │  (score)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ↑                                       │           │
│         │                                       ↓           │
│         │    ┌─────────────────────────────────────┐       │
│         │    │      MULTI-MODAL CONFIDENCE         │       │
│         │    │                                     │       │
│         │    │  Visual (CLIP):      40%           │       │
│         │    │  DOM structure:      20%           │       │
│         │    │  Behavior tests:     20%           │       │
│         │    │  Accessibility:      10%           │       │
│         │    │  Performance:        10%           │       │
│         │    │  ────────────────────────          │       │
│         │    │  TOTAL CONFIDENCE:   XX%           │       │
│         │    └─────────────────────────────────────┘       │
│         │                    │                             │
│         │                    ↓                             │
│         │    ┌─────────────────────────────────────┐       │
│         │    │         CONFIDENCE CHECK            │       │
│         │    │                                     │       │
│         │    │  if confidence >= 0.85:            │       │
│         │    │      → EXIT SUCCESS                │       │
│         │    │  else:                             │       │
│         │    │      → FEEDBACK TO CLAUDE          │       │
│         │    │      → CONTINUE LOOP               │       │
│         │    └──────────────────┬──────────────────┘       │
│         │                       │                          │
│         └───────────────────────┘                          │
│                                                              │
│  BACKPRESSURE: max 15 iterations, $20 budget               │
└─────────────────────────────────────────────────────────────┘
```

---

## Stack Consigliato

### Core Tools (Already Available)
- **Playwright MCP**: Browser automation, screenshots
- **Claude Vision**: Screenshot analysis, code generation
- **Ralph Loop**: Iteration control, backpressure

### New Integrations Needed
1. **CLIP embeddings** (Python): `pip install openai-clip torch`
2. **ODiff** (Node.js): `npm install odiff-bin`
3. **Visual Regression Tracker** (Docker): Self-hosted review UI

### Optional Enhancements
- **Argos CI**: If GitHub-based review workflow preferred
- **screenshot-to-code**: If dedicated generation pipeline wanted

---

## Implementation Priority

| Priority | Component | Effort | Value |
|----------|-----------|--------|-------|
| P0 | CLIP visual similarity | 2h | High - semantic comparison |
| P0 | Playwright snapshot integration | 1h | High - DOM + behavior |
| P1 | Multi-modal confidence fusion | 4h | High - unified scoring |
| P1 | Ralph loop termination extension | 2h | High - dynamic exit |
| P2 | Visual Regression Tracker | 4h | Medium - team review |
| P2 | screenshot-to-code integration | 3h | Medium - generation boost |
| P3 | Argos CI | 4h | Low - if GitHub workflow needed |

---

## Sources

- [abi/screenshot-to-code](https://github.com/abi/screenshot-to-code) - 60k+ stars
- [ODiff](https://github.com/dmtrKovalenko/odiff) - SIMD image comparison
- [OpenAI CLIP](https://github.com/openai/CLIP) - Visual embeddings
- [Visual Regression Tracker](https://github.com/Visual-Regression-Tracker/Visual-Regression-Tracker)
- [Playwright Visual Testing](https://playwright.dev/docs/test-snapshots)
- [BackstopJS](https://github.com/garris/BackstopJS) - Self-hosted visual testing
- [Argos CI](https://github.com/argos-ci/argos) - Modern visual testing platform
