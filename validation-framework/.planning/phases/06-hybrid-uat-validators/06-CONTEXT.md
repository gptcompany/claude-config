# Phase 6: Hybrid UAT & Validators - Context

**Gathered:** 2026-01-20
**Status:** Ready for research

<vision>
## How This Should Work

The validation workflow runs in **four staged rounds**, each building on the previous:

**Round 1: Auto-Check**
- Claude runs all automated checks: file existence, API health, screenshots, accessibility (axe-core), security (Trivy), performance (Lighthouse)
- Each check gets a **confidence score** (HIGH/MEDIUM/LOW) + **type classification**
- Results stream to a live dashboard showing progress

**Round 2: Human Review (Prove Me Wrong)**
- Human reviews ALL items, not just low-confidence ones
- Confidence scores guide attention: HIGH = quick glance, LOW = deep dive
- Even high-confidence items get sanity check - "prove me wrong" approach
- Interactive dashboard for marking pass/fail with notes

**Round 3: Fix + Re-test**
- Failures from Round 2 get fixed
- Re-run affected auto-checks to verify fixes
- Update confidence scores based on fix success

**Round 4: Edge Cases + Regression**
- Test edge cases identified during Rounds 1-3
- Full regression check to ensure fixes didn't break other things
- Final sign-off before closing UAT

The dashboard should work in **three modes**:
- **Live Monitor**: Watch tests run in real-time, intervene when needed
- **Review Station**: Click through items, mark pass/fail, see overall progress
- **Report Viewer**: After tests complete, review results and drill into failures

</vision>

<essential>
## What Must Be Nailed

- **Four-round workflow** - Auto → Human-All → Fix → Edge+Regression
- **Confidence + Type filtering** - Both dimensions for intelligent prioritization
- **Prove-me-wrong human review** - Even HIGH confidence gets sanity check
- **Multi-mode dashboard** - Live monitor, review station, report viewer
- **All validators integrated** - axe-core, Trivy, Lighthouse as part of Round 1
- **CI/CD ready** - All validators run in GitHub Actions, block PRs on failures
- **Deep integration** - Validator results feed into confidence scoring and dashboard

</essential>

<specifics>
## Specific Ideas

- Dashboard should be both **interactive (terminal or web)** AND have **clickable sections**
- Need to research OSS tools that enable this dual-mode experience
- Validators should be:
  - Easy to run (single command, minimal config)
  - Deeply integrated (results in dashboard, affect confidence)
  - CI/CD ready (GitHub Actions, PR blocking)
- All three validators (axe-core, Trivy, Lighthouse) ship in parallel, no priority ordering
- Build on existing AI Validation Service (localhost:3848) for integration

</specifics>

<notes>
## Additional Context

User emphasized "prove me wrong" philosophy - even when auto-checks are confident, human review provides sanity check. This is about catching what automation misses, not just rubber-stamping.

The four-round approach is deliberate:
1. Auto-check gives initial assessment
2. Human review validates everything (guided by confidence)
3. Fix cycle addresses issues
4. Edge cases + regression ensures completeness

Research phase should investigate:
- OSS dashboard tools with live + interactive + report modes
- Best practices for confidence scoring
- Integration patterns for axe-core + Playwright
- Trivy container + dependency scanning setup
- Lighthouse CI configuration

</notes>

---

*Phase: 06-hybrid-uat-validators*
*Context gathered: 2026-01-20*
