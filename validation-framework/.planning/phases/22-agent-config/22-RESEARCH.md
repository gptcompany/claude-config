# Phase 22: Agent Config & System Prompts - Research

**Researched:** 2026-02-01
**Domain:** OpenClaw per-agent configuration, system prompts, sandbox, thinking levels
**Confidence:** HIGH (official docs verified + live gateway inspection)

<research_summary>
## Summary

Researched OpenClaw's agent configuration system for customizing 4 agents (main, nautilus, utxoracle, n8n) with per-agent system prompts, sandbox policies, thinking levels, sub-agent config, and tool restrictions.

Key findings: (1) **System prompts are NOT a config field** — they're assembled from workspace bootstrap files (SOUL.md, AGENTS.md, TOOLS.md, USER.md, IDENTITY.md, HEARTBEAT.md). Per-agent customization = per-agent workspace files. (2) **Per-agent workspaces are empty** for nautilus, utxoracle, n8n — they have no SOUL.md or instructions. (3) **Sandbox `"non-main"` mode** (default) isolates group/channel sessions in Docker while keeping DMs on host. (4) **Thinking levels** support 6 levels (off→xhigh) with configurable default per-agent. (5) **Sub-agent model override has a bug** (#6295) — spawned sub-agents inherit caller's model regardless of config. (6) Our validation framework (14-dimension, 3-tier) and TDD guard exist in `~/.claude/templates/validation/` and can be referenced in agent system prompts.

**Primary recommendation:** Create per-agent workspace bootstrap files (SOUL.md + AGENTS.md) for each agent with TDD/quality instructions. Set `thinkingDefault: "medium"` for implementation agents. Keep sandbox `"off"` (our gateway runs inside Docker already — double-containerization adds no value). Configure `maxConcurrent: 4` and `subagents.maxConcurrent: 8` (already set).
</research_summary>

<standard_stack>
## Standard Stack

### System Prompt Assembly
| Component | File | Purpose | Injected |
|-----------|------|---------|----------|
| Personality | `SOUL.md` | Core identity, principles, working style | Always (up to 20K chars) |
| Agent instructions | `AGENTS.md` | Per-agent capabilities, repo-specific context | Always |
| Tools | `TOOLS.md` | Custom tool docs and usage patterns | Always |
| User info | `USER.md` | User preferences, communication style | Always |
| Identity | `IDENTITY.md` | Name, emoji, theme | Always |
| Heartbeat | `HEARTBEAT.md` | Periodic task instructions | Always |
| Bootstrap | `BOOTSTRAP.md` | First-run instructions (new workspaces only) | Once |

### Agent Config Hierarchy
| Level | Config Location | Priority |
|-------|----------------|----------|
| Global defaults | `agents.defaults.*` | Lowest |
| Per-agent override | `agents.list[].{field}` | Higher |
| Workspace files | `{workspace}/SOUL.md` etc. | Highest (for prompt) |
| Session directive | `/think:high`, `/model @profile` | Highest (runtime) |

### Current State (Live Gateway)
| Agent | Workspace | Has SOUL.md | Has AGENTS.md | Model |
|-------|-----------|-------------|---------------|-------|
| main | `/home/node/clawd` | **YES** | YES | claude-opus-4-5 |
| nautilus | `/home/node/clawd-nautilus` | **NO** (empty) | NO | inherit |
| utxoracle | `/home/node/clawd-utxoracle` | **NO** (empty) | NO | inherit |
| n8n | `/home/node/clawd-n8n` | **NO** (empty) | NO | inherit |

### Agent → Repo Mapping (Workstation /media/sam/1TB/)
**All 5 active repos:**
| Repo | Domain |
|------|--------|
| nautilus_dev | Discord scraper, data pipeline |
| LiquidationHeatmap | Crypto liquidation heatmaps |
| openBB_liquidity | Market-wide liquidity analytics (OpenBB) |
| N8N_dev | Workflow automation |
| UTXOracle | Crypto oracle/analytics |

**Agent assignment (TBD in planning):**
| Agent | Candidate repos |
|-------|----------------|
| main | validation-framework, moltbot-infra, claude-config |
| nautilus | nautilus_dev |
| utxoracle | UTXOracle, LiquidationHeatmap, openBB_liquidity |
| n8n | N8N_dev |

**Inactive repos (legacy):**
- liquidations-chart, py-liquidation-map, nautilus_scraper

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-workspace SOUL.md | Single shared SOUL.md via symlinks | Less customization per agent |
| `thinkingDefault: "medium"` | `thinkingDefault: "high"` | High uses more tokens, medium is good balance |
| Sandbox off (already in Docker) | Sandbox all (Docker-in-Docker) | DinD adds complexity, our gateway IS the container |
| Custom validation hook | Direct /validate in SOUL.md instructions | Hook is automated, SOUL.md relies on agent following instructions |
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Pattern 1: Per-Agent Workspace Bootstrap Files
**What:** Each agent gets its own workspace directory with customized SOUL.md and AGENTS.md
**When to use:** When agents need different instructions (nautilus=scraper, utxoracle=crypto, n8n=workflow)
**Example:**
```
/home/node/clawd-nautilus/
├── SOUL.md        # Shared base + nautilus-specific principles
├── AGENTS.md      # nautilus_dev repo agents, capabilities
├── TOOLS.md       # Available MCPorter tools for this agent
└── USER.md        # Sam's preferences (shared across agents)
```

### Pattern 2: Layered Quality Instructions in SOUL.md
**What:** Embed TDD/quality instructions directly in SOUL.md — the agent reads them every session
**When to use:** Always — this is how we enforce quality standards
**Example:**
```markdown
## Quality Standards (MANDATORY)

### TDD Workflow
1. RED: Write failing test first
2. GREEN: Minimal code to pass
3. REFACTOR: Clean up

### Validation Framework
Before declaring work complete, run validation:
- Tier 1 (Blockers): Tests pass, no security issues, imports resolve
- Tier 2 (Warnings): Design principles, code coverage > 80%
- Tier 3 (Monitors): Performance, mathematical accuracy

### Anti-Superficialità
- "It works" → Show test output
- "Almost done" → Show exact % and what's missing
- Never accept claims without evidence
```

### Pattern 3: Thinking Level Configuration
**What:** Set default thinking level per config, allow runtime override via directive
**When to use:** For all implementation agents
**Config:**
```json
{
  "agents": {
    "defaults": {
      "thinkingDefault": "medium"
    }
  }
}
```
**Resolution order:** inline directive > session override > config default > fallback (low)
**Levels:** off | minimal | low | medium | high | xhigh (GPT-5.2 only)

### Anti-Patterns to Avoid
- **Docker-in-Docker sandbox**: Our gateway already runs in Docker. Enabling sandbox creates container-inside-container. Keep `sandbox.mode: "off"`
- **Shared agentDir across agents**: Causes auth/session collisions. Each agent needs its own agentDir
- **Relying on sub-agent model override**: Bug #6295 — sub-agents inherit caller's model regardless of config. Don't depend on this until fixed
- **Putting validation instructions only in hooks**: Hooks are mechanical. SOUL.md instructions make the agent understand *why* to validate
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System prompt customization | Custom hook to inject text | Workspace bootstrap files (SOUL.md, AGENTS.md) | Native mechanism, 20K chars/file, auto-injected |
| Per-agent model routing | env var switching | `agents.list[].model` config | Native per-agent model support |
| Thinking level control | Custom prompt engineering | `thinkingDefault` + `/think:` directive | Built-in 6-level system |
| Tool restriction | Prompt instructions | `agents.list[].tools.allow/deny` | Enforced at runtime, not advisory |
| Agent identity | Manual persona in prompt | `identity.name/emoji/theme` config | Proper ack reactions, display names |
| Session isolation | Custom state management | `session.scope: "per-sender"` (default) | Built-in per-sender sessions |

**Key insight:** OpenClaw's agent system is highly configurable via JSON config + workspace files. The config handles *runtime behavior* (tools, sandbox, thinking, model). Workspace files handle *personality and instructions* (what the agent knows and does). Don't conflate them.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Empty Agent Workspaces
**What goes wrong:** Agents without SOUL.md/AGENTS.md get generic behavior — no repo context, no quality standards
**Why it happens:** Only main workspace was configured; other agents created with just an `id` and `workspace` path
**How to avoid:** Create bootstrap files for every agent. At minimum: SOUL.md (principles), AGENTS.md (repo context)
**Warning signs:** Agent gives generic responses, doesn't know about the project's codebase or conventions
**Current state:** nautilus, utxoracle, n8n workspaces are EMPTY

### Pitfall 2: Sub-Agent Model Override Bug (#6295)
**What goes wrong:** `subagents.model` config is ignored — sub-agents always use caller's model
**Why it happens:** Bug in sessions_spawn model resolution (GitHub #6295, reported 2026-02-01)
**How to avoid:** Don't rely on automatic sub-agent model routing. Use `llm-task` tool for cross-model calls instead
**Warning signs:** Sub-agents consistently using primary model despite config

### Pitfall 3: Sandbox in Docker-in-Docker
**What goes wrong:** Enabling sandbox when gateway already runs in Docker creates DinD, with mount path confusion and performance overhead
**Why it happens:** Default `sandbox.mode: "non-main"` assumes host execution
**How to avoid:** Set `sandbox.mode: "off"` when gateway is containerized. Use Docker socket only for node exec
**Warning signs:** Sandbox container creation fails, mount paths reference host paths inside container

### Pitfall 4: bootstrapMaxChars Truncation
**What goes wrong:** Large SOUL.md or AGENTS.md gets silently truncated at 20K chars
**Why it happens:** `bootstrapMaxChars` default is 20000 — shared across all workspace files
**How to avoid:** Keep each file under 8K chars. Focus on essential instructions. Use `systemPromptReport` in agent response metadata to verify injected sizes
**Warning signs:** Agent doesn't follow instructions that appear in the file — they were likely truncated

### Pitfall 5: Thinking Overhead on Simple Tasks
**What goes wrong:** `thinkingDefault: "high"` wastes tokens on simple cron heartbeats and status checks
**Why it happens:** Config applies globally unless overridden per-session
**How to avoid:** Set `thinkingDefault: "low"` as default. Use `"medium"` or `"high"` only for implementation sessions. Cron tasks should use inline `/think:off`
**Warning signs:** Token costs spike without corresponding quality improvement
</common_pitfalls>

<code_examples>
## Code Examples

### Per-Agent Config with Overrides
```json5
// Source: OpenClaw docs /gateway/configuration
{
  "agents": {
    "defaults": {
      "thinkingDefault": "low",
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8,
        "archiveAfterMinutes": 60
      }
    },
    "list": [
      {
        "id": "main",
        "workspace": "/home/node/clawd",
        "default": true,
        "identity": {
          "name": "Bambam",
          "emoji": "🦞",
          "theme": "Senior dev, direct, competent"
        }
      },
      {
        "id": "nautilus",
        "workspace": "/home/node/clawd-nautilus",
        "identity": {
          "name": "Nautilus",
          "emoji": "🐙",
          "theme": "Scraper specialist"
        }
      },
      {
        "id": "utxoracle",
        "workspace": "/home/node/clawd-utxoracle",
        "identity": {
          "name": "Oracle",
          "emoji": "🔮",
          "theme": "Crypto analyst"
        }
      },
      {
        "id": "n8n",
        "workspace": "/home/node/clawd-n8n",
        "identity": {
          "name": "Flow",
          "emoji": "⚡",
          "theme": "Workflow automation"
        }
      }
    ]
  }
}
```

### SOUL.md Template for Quality Agents
```markdown
# SOUL.md - Who You Are

You're [Name], Sam's [role]. Not a chatbot — a competent engineer.

## Principles
- KISS / YAGNI — no over-engineering
- Anti-superficialità — never accept claims without evidence
- Prove concrete — LOC, test results, coverage %

## Quality Standards (MANDATORY)
### TDD Workflow
1. RED: Write failing test first
2. GREEN: Minimal code to pass
3. REFACTOR: Clean up

### Validation (Before Declaring Complete)
- Tier 1 (Blockers): Tests pass, imports resolve, no security issues
- Tier 2 (Warnings): Design principles, coverage > 80%
- Tier 3 (Monitors): Performance baselines

### Anti-Superficialità
- "It works" → show pytest output
- "Almost done" → show exact % and remaining items
- Evidence required for every claim

## Security (MANDATORY)
- NEVER read or expose secrets
- Use grep -q for verification, not grep
- All repos on /media/sam/1TB/

## Working Style
- Be concise. Skip filler.
- Try before asking.
- Small, focused commits.
```

### Thinking Level Configuration
```json5
// Source: OpenClaw docs /tools/thinking
{
  "agents": {
    "defaults": {
      "thinkingDefault": "low"  // off | minimal | low | medium | high | xhigh
    }
  }
}
// Runtime override: user sends "/think:high" to boost for current session
// Cron jobs: use "--thinking off" flag to minimize token usage
```

### System Prompt Report (Verify Injection)
```bash
# Source: Phase 21 E2E test — systemPromptReport in agent response metadata
ssh 192.168.1.100 'docker exec openclaw-gateway node /app/dist/entry.js agent \
  --agent main --message "what files were injected?" --json --timeout 30 > /tmp/test.json 2>&1'
# Check systemPromptReport.injectedWorkspaceFiles for each file's chars/truncated status
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single agent | Multi-agent with deterministic routing | v2025.12 | Per-repo specialization |
| No thinking control | 6-level thinking system | v2026.1 | Token/quality optimization |
| Host-only execution | Optional Docker sandbox per-session | v2026.1 | Security isolation for untrusted inputs |
| Manual model switch | Per-agent model config + aliases | v2026.1 | Cost optimization per-agent |
| No workspace files | 7 bootstrap files auto-injected | v2025.12+ | Rich per-agent personality |

**New tools/patterns:**
- **`agent:bootstrap` hook**: Can intercept and mutate injected bootstrap files at runtime
- **`tools.profile`**: Preset tool bundles (`minimal`, `coding`, `messaging`, `full`) instead of manual allow/deny
- **`/think:` directive**: Runtime thinking level override per-session

**Deprecated/outdated:**
- **Custom system prompt field**: Never existed — always workspace files
- **Shared agentDir**: Causes collisions, each agent needs its own

**Bugs to track:**
- **#6295**: Sub-agent model override ignored (2026-02-01, open)
</sota_updates>

<open_questions>
## Open Questions

1. **AGENTS.md per-repo content**
   - What we know: Each agent needs repo-specific context (structure, conventions, key files)
   - What's unclear: How much detail to include without hitting 20K char limit
   - Recommendation: Keep AGENTS.md to architecture summary + key conventions. Full codebase docs go in repo's .claude/ directory (on Workstation node, not gateway workspace)

2. **Thinking level for cron jobs**
   - What we know: Cron uses `--thinking` CLI flag, can override config default
   - What's unclear: Does our existing cron config pass `--thinking off`?
   - Recommendation: Check cron entries in openclaw.json, add `--thinking off` for heartbeat/health checks

3. **Validation framework in agent context**
   - What we know: Our 14-dimension validator lives in `~/.claude/templates/validation/` on Workstation
   - What's unclear: How to make agents invoke it (they run via gateway, not directly on Workstation)
   - Recommendation: Phase 26 (Quality Gates) will integrate this. For Phase 22, just put instructions in SOUL.md to encourage TDD and quality checks

4. **bootstrap hook for dynamic SOUL.md**
   - What we know: `agent:bootstrap` hook can mutate workspace files at runtime
   - What's unclear: Use cases — could dynamically inject current task context
   - Recommendation: Skip for now. Static SOUL.md is simpler and sufficient
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [OpenClaw Gateway Configuration](https://docs.openclaw.ai/gateway/configuration) — full config reference, all agent fields
- [OpenClaw System Prompt](https://docs.openclaw.ai/concepts/system-prompt) — bootstrap file injection, prompt assembly
- [OpenClaw Sandboxing](https://docs.openclaw.ai/gateway/sandboxing) — modes, scope, Docker settings
- [OpenClaw Thinking](https://docs.openclaw.ai/tools/thinking) — 6 levels, directives, resolution order
- [OpenClaw Multi-Agent](https://docs.openclaw.ai/concepts/multi-agent) — routing, per-agent config, identity

### Secondary (MEDIUM confidence)
- [GitHub Issue #6295](https://github.com/openclaw/openclaw/issues/6295) — sub-agent model override bug (open, 2026-02-01)
- Live gateway inspection (SSH + docker exec) — verified current config and workspace state

### Tertiary (LOW confidence - needs validation)
- Cron `--thinking` flag behavior — from CLI help, not tested in our setup
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw agent configuration (v2026.1.30)
- Ecosystem: System prompt assembly, sandbox modes, thinking levels, multi-agent routing
- Patterns: Per-workspace bootstrap, layered quality instructions, thinking optimization
- Pitfalls: Empty workspaces, DinD sandbox, sub-agent model bug, truncation

**Confidence breakdown:**
- Standard stack: HIGH — verified with official docs + live inspection
- Architecture: HIGH — patterns from official docs
- Pitfalls: HIGH — confirmed via live gateway + GitHub issues
- Code examples: HIGH — from official documentation + verified config

**Research date:** 2026-02-01
**Valid until:** 2026-02-15 (14 days — active development, bugs pending)
</metadata>

---

*Phase: 22-agent-config*
*Research completed: 2026-02-01*
*Ready for planning: yes*
