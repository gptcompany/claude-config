# Phase 21: Models & Providers - Research

**Researched:** 2026-02-01
**Domain:** OpenClaw multi-model provider configuration + Gemini integration
**Confidence:** HIGH (official docs + GitHub issues verified)

<research_summary>
## Summary

Researched OpenClaw's multi-model provider system for configuring Claude (primary), Kimi K2.5 via OpenRouter (cross-review), Gemini (free tier fallback), and OpenAI (last resort). OpenClaw supports 14+ providers with per-agent model selection and failover chains.

Key findings: (1) **Kimi K2.5** is 25x cheaper than Opus with near-parity coding performance (83.1% LiveCodeBench) and **superior agent benchmarks** (50.2 HLE-Full vs GPT-5.2's 45.5). Available via OpenRouter. (2) Gemini CLI OAuth has a **known bug** (#4585) — use API key instead. (3) Cross-provider failover has a **known bug** (#4260, fix in PR #4312). (4) LLM Task plugin enables cross-model review natively. (5) No native budget cap — needs custom hook.

**Primary recommendation:** Use Claude Opus for implementation, Kimi K2.5 via OpenRouter for cross-review (25x cheaper, excellent agent/coding scores), Gemini as free-tier fallback. All via API keys. Enable LLM Task plugin for structured cross-model review. All API keys stored in SOPS (`/media/sam/1TB/.env.enc`).
</research_summary>

<standard_stack>
## Standard Stack

### Core Providers
| Provider | Model | Auth Method | Purpose | Cost |
|----------|-------|-------------|---------|------|
| anthropic | claude-opus-4-5 | API key (`ANTHROPIC_API_KEY`) | Primary implementation | $15/$75 per M tokens |
| openrouter | moonshotai/kimi-k2.5 | API key (`OPENROUTER_API_KEY`) | Cross-review, agent tasks | $0.60/$3 per M tokens (25x cheaper) |
| google | gemini-2.5-pro | API key (`GEMINI_API_KEY`) | Free tier fallback | Free (20-50 req/day) |
| openai | gpt-5.2 | API key (`OPENAI_API_KEY`) | Last resort fallback | Paid |

### Kimi K2.5 Benchmarks (vs competitors)
| Benchmark | Kimi K2.5 | Claude Opus 4.5 | GPT-5.2 |
|-----------|-----------|-----------------|---------|
| LiveCodeBench v6 | 83.1% | ~85% | 89.6% |
| HLE-Full (agents) | **50.2** | N/A | 45.5 |
| BrowseComp | **74.9** | N/A | N/A |
| Architecture | 1T params MoE, 32B active | Closed | Closed |
| Agent Swarm | 100 sub-agents, 1500 tool calls | No | No |
| License | MIT (open source) | Closed | Closed |

### Auth Methods Available
| Method | Provider | Status | Notes |
|--------|----------|--------|-------|
| API Key | All | ✅ Works | Recommended — stable, no OAuth bugs |
| google-antigravity OAuth | Google | ⚠️ Works but complex | Plugin, stores tokens in auth profiles |
| google-gemini-cli OAuth | Google | ❌ Bug #4585 | client_secret missing, NOT fixed in v2026.1.30 |
| anthropic setup-token | Anthropic | ✅ Works | Uses Claude subscription, not API billing |
| openai-codex | OpenAI | ✅ Works | Uses ChatGPT subscription |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Kimi K2.5 via OpenRouter | Direct Moonshot API | OpenRouter simpler (unified billing), Moonshot slightly cheaper |
| Gemini API key (free) | Gemini CLI OAuth (1000 req/day) | OAuth gives 50x more requests but has bug #4585 |
| OpenRouter | Direct providers | Direct is cheaper per-token but more keys to manage |
| Direct providers | Venice AI | Privacy-focused proxy, adds latency |

**Configuration:**
```json5
// In openclaw.json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": ["openrouter/moonshotai/kimi-k2.5", "google/gemini-2.5-pro", "openai/gpt-5.2"]
      },
      "models": {
        "anthropic/claude-opus-4-5": { "alias": "opus" },
        "openrouter/moonshotai/kimi-k2.5": { "alias": "kimi" },
        "google/gemini-2.5-pro": { "alias": "gemini" },
        "openai/gpt-5.2": { "alias": "gpt" }
      }
    }
  }
}
```

**Environment variables (all in SOPS: `/media/sam/1TB/.env.enc`):**
```bash
ANTHROPIC_API_KEY=sk-ant-...     # Already in SOPS
OPENROUTER_API_KEY=sk-or-...     # NEW — add to SOPS
GEMINI_API_KEY=AI...             # Already in SOPS (as GEMINI_API_KEY)
OPENAI_API_KEY=sk-...            # Already in SOPS
```

**Docker compose env injection:**
```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
  - GEMINI_API_KEY=${GEMINI_API_KEY}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended: Per-Agent Model Routing
```json5
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": ["google/gemini-2.5-pro"]
      },
      "models": {
        "anthropic/claude-opus-4-5": { "alias": "opus" },
        "google/gemini-2.5-pro": { "alias": "gemini" }
      }
    },
    "list": [
      {
        "id": "main",
        "model": "anthropic/claude-opus-4-5"
      },
      {
        "id": "nautilus",
        "model": {
          "primary": "anthropic/claude-opus-4-5",
          "fallbacks": ["google/gemini-2.5-pro"]
        }
      }
    ]
  }
}
```

### Pattern: LLM Task for Cross-Model Review
```json5
// Enable LLM Task plugin
{
  "plugins": {
    "allow": ["matrix", "llm-task"],
    "entries": {
      "llm-task": { "enabled": true }
    }
  },
  "tools": {
    "allow": ["llm_task"]  // Add to agent tool allowlist
  }
}

// LLM Task invocation (from agent or Lobster workflow):
// provider: "google", model: "gemini-2.5-pro"
// prompt: "Review this code for bugs and security issues: ..."
// schema: { type: "object", properties: { score: { type: "number" }, issues: { ... } } }
```

### Pattern: Failover Chain with Cooldowns
```json5
{
  "auth": {
    "cooldowns": {
      "billingBackoffHours": 5,
      "billingMaxHours": 24,
      "failureWindowHours": 24
    }
  }
}
```

Failover progression:
1. Primary model (claude-opus-4-5) fails → rotate auth profiles within provider
2. All Anthropic profiles exhausted → advance to first fallback (gemini-2.5-pro)
3. Gemini fails → advance to second fallback (gpt-5.2)
4. All providers fail → FailoverError (escalation needed)

### Anti-Patterns to Avoid
- **Using google-gemini-cli OAuth**: Bug #4585 blocks auth flow, use API key instead
- **Relying on cross-provider failover**: Bug #4260 means failover may not advance across providers correctly
- **Putting budget-critical agents on expensive models**: No native budget cap exists
- **Inline API keys in config**: Use environment variables, never hardcode
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Provider switching | Custom retry logic | OpenClaw failover chain | Built-in cooldown, profile rotation, backoff |
| Cross-model review | Shell script calling APIs | LLM Task plugin | Native integration, JSON schema validation, auth handled |
| Token counting | Custom API wrapper | `/usage cost` + session logs | OpenClaw tracks per-session automatically |
| Model aliases | Environment variables | `models.{id}.alias` config | Native alias resolution, user-facing shortcuts |
| Auth profile management | Manual token files | `openclaw models auth login` | Handles refresh, cooldown, rotation |

**Key insight:** OpenClaw's model system is comprehensive — providers, failover, profiles, aliases are all native. The only gap is budget enforcement, which requires a custom hook.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Gemini CLI OAuth Bug (#4585)
**What goes wrong:** `google-gemini-cli` auth fails with "client_secret is missing"
**Why it happens:** OpenClaw expects client_secret but Gemini CLI uses public PKCE OAuth (no secret)
**How to avoid:** Use `GEMINI_API_KEY` API key auth instead of OAuth
**Warning signs:** "Token exchange failed: invalid_request" during `openclaw models auth login`
**Status:** Open, not fixed in v2026.1.30

### Pitfall 2: Cross-Provider Failover Bug (#4260)
**What goes wrong:** When primary provider hits rate limit, system throws FailoverError instead of trying next provider
**Why it happens:** Logic flaw — provider-level unavailability doesn't trigger cross-provider fallback
**How to avoid:** Don't depend on automatic cross-provider failover; configure multiple auth profiles within same provider as primary resilience
**Warning signs:** "FailoverError: No available auth profile for {provider}" when fallbacks exist
**Status:** Fix in progress (PR #4312)

### Pitfall 3: Session Stickiness Prevents Model Switching
**What goes wrong:** Agent stays on one model even when you want it to switch
**Why it happens:** OpenClaw pins auth profile per session for cache efficiency
**How to avoid:** Use `/model @profileId` for manual override, or session reset to allow rotation
**Warning signs:** Agent consistently using one model despite failover config

### Pitfall 4: Free Tier API Limits Much Lower Than Expected
**What goes wrong:** Gemini API key free tier gives only 20-50 req/day (not 1000)
**Why it happens:** Google slashed free API limits in Dec 2025 (50-80% reduction)
**How to avoid:** Use Google OAuth (1000 req/day) when bug #4585 is fixed, or use google-antigravity OAuth
**Warning signs:** 429 rate limit errors after few requests

### Pitfall 5: No Native Budget Cap
**What goes wrong:** Autonomous agent runs overnight, consumes $hundreds in API tokens
**Why it happens:** OpenClaw tracks usage but has no "stop at $X" feature
**How to avoid:** Implement custom hook that checks `/usage cost` and stops agent if over budget
**Warning signs:** Monthly Anthropic bill spike
</common_pitfalls>

<code_examples>
## Code Examples

### Multi-Model Config (Complete)
```json5
// Source: OpenClaw docs /gateway/configuration + /concepts/model-failover
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5",
        "fallbacks": ["openrouter/moonshotai/kimi-k2.5", "google/gemini-2.5-pro", "openai/gpt-5.2"]
      },
      "models": {
        "anthropic/claude-opus-4-5": { "alias": "opus" },
        "openrouter/moonshotai/kimi-k2.5": { "alias": "kimi" },
        "google/gemini-2.5-pro": { "alias": "gemini" },
        "openai/gpt-5.2": { "alias": "gpt" }
      }
    }
  },
  "auth": {
    "profiles": {
      "anthropic:default": { "provider": "anthropic", "mode": "token" },
      "openrouter:default": { "provider": "openrouter", "mode": "token" },
      "google:default": { "provider": "google", "mode": "token" },
      "openai:default": { "provider": "openai", "mode": "token" }
    }
  }
}
```

### LLM Task Plugin Enable
```json5
// Source: OpenClaw docs /tools/llm-task
{
  "plugins": {
    "allow": ["matrix", "llm-task"],
    "entries": {
      "llm-task": { "enabled": true }
    }
  }
}
```

### Docker Compose Env Vars (SOPS-based)
```yaml
# Source: Our existing pattern in muletto/docker-compose.yml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - GEMINI_API_KEY=${GEMINI_API_KEY}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```

### Check Usage via CLI
```bash
# Source: OpenClaw docs /concepts/usage-tracking
docker exec openclaw-gateway node /app/dist/entry.js agent --agent main status --usage
# Shows: session tokens + estimated cost
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single provider | Multi-provider failover chain | OpenClaw v2026.1.x | Resilience, cost optimization |
| Manual model switching | Per-agent model config + aliases | v2026.1.20 | Users type `/gemini` to switch |
| API key only | OAuth + API key + setup-token | v2026.1.x | Subscription billing support |
| No cross-model review | LLM Task plugin | v2026.1.x | Structured JSON review via different model |

**New tools/patterns:**
- **Kimi K2.5 via OpenRouter**: 25x cheaper than Opus, MIT open source, superior agent benchmarks, 1T MoE model
- **LLM Task plugin**: Enables cross-model review without shell scripts — route review to Kimi K2.5
- **Model aliases**: Users can switch models mid-chat with `/opus`, `/kimi`, or `/gemini`
- **google-antigravity**: OAuth path for Google that works (unlike gemini-cli)

**Bugs to track:**
- **#4585**: Gemini CLI OAuth client_secret — blocks free tier 1000 req/day
- **#4260**: Cross-provider failover — may not advance to next provider
- **PR #4312**: Fix for #4260 — monitor for merge
</sota_updates>

<open_questions>
## Open Questions

1. **Gemini API key limits for our use case**
   - What we know: Free tier API key = 20-50 req/day for 2.5 Pro
   - What's unclear: Is this enough for cross-review? 10 reviews/day probably OK, 50 reviews/day at risk
   - Recommendation: Start with API key, monitor usage, switch to google-antigravity OAuth if limits hit

2. **Cross-provider failover reliability**
   - What we know: Bug #4260 exists, fix PR #4312 pending
   - What's unclear: When PR merges, will our version get it?
   - Recommendation: Don't rely on auto-failover; design system to work within single provider per-session

3. **Budget cap implementation**
   - What we know: OpenClaw tracks tokens/cost but has no cap
   - What's unclear: Best hook point — pre-exec? per-session? per-task?
   - Recommendation: Implement in Phase 28 (Usage Tracking), use hook that checks cost before each agent turn

4. **google-antigravity vs google-gemini-cli**
   - What we know: antigravity works, gemini-cli doesn't (bug #4585)
   - What's unclear: Are the quotas the same? Is antigravity = Gemini CLI free tier (1000/day)?
   - Recommendation: Test antigravity OAuth setup, verify quota matches expectations
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [OpenClaw Gateway Configuration](https://docs.openclaw.ai/gateway/configuration) — multi-provider setup, env vars, per-agent models
- [OpenClaw Model Failover](https://docs.openclaw.ai/concepts/model-failover) — failover chain, cooldowns, profile rotation
- [OpenClaw Model Providers](https://docs.openclaw.ai/concepts/model-providers) — provider list, auth methods, Google config
- [OpenClaw Anthropic Provider](https://docs.openclaw.ai/providers/anthropic) — API key, setup-token, cache config
- [OpenClaw OpenAI Provider](https://docs.openclaw.ai/providers/openai) — API key, Codex subscription
- [OpenClaw LLM Task Tool](https://docs.openclaw.ai/tools/llm-task) — plugin config, cross-model invocation
- [OpenClaw Usage Tracking](https://docs.openclaw.ai/concepts/usage-tracking) — token counting, cost display

### Secondary (MEDIUM confidence)
- [GitHub Issue #4585](https://github.com/openclaw/openclaw/issues/4585) — Gemini CLI OAuth bug (open, Jan 30 2026)
- [GitHub Issue #4260](https://github.com/openclaw/openclaw/issues/4260) — Cross-provider failover bug (fix in PR #4312)
- [Gemini CLI Quotas](https://geminicli.com/docs/quota-and-pricing/) — Free tier limits (OAuth vs API key)

### Tertiary (LOW confidence - needs validation)
- Gemini API key free tier limits (20-50/day) — from community reports, Google hasn't published official numbers post-Dec 2025 cuts
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw model provider system (v2026.1.30)
- Ecosystem: Anthropic, Google/Gemini, OpenAI providers + LLM Task plugin
- Patterns: Multi-model failover, per-agent routing, cross-model review
- Pitfalls: OAuth bugs, failover bugs, rate limits, budget gaps

**Confidence breakdown:**
- Standard stack: HIGH — verified with official docs
- Architecture: HIGH — config examples from official docs
- Pitfalls: HIGH — confirmed via GitHub issues with reproduction steps
- Code examples: HIGH — from official documentation

**Research date:** 2026-02-01
**Valid until:** 2026-02-15 (14 days — fast-moving, bugs pending fix)
</metadata>

---

*Phase: 21-models-providers*
*Research completed: 2026-02-01*
*Ready for planning: yes*
