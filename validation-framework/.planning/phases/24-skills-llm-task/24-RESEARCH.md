# Phase 24: Skills & LLM Task - Research

**Researched:** 2026-02-02
**Domain:** OpenClaw Skills, LLM Task plugin, Lobster workflows
**Confidence:** HIGH

<research_summary>
## Summary

Researched OpenClaw's skills system, LLM Task plugin, and Lobster workflow engine for configuring TDD-native skills, cross-model review via LLM Task, and typed workflow automation.

**Current state:**
- `llm-task` plugin already enabled in `openclaw.json` but unconfigured (no `defaultProvider`, `allowedModels`, or `defaultModel`)
- 3 workspace skills exist on main agent (`gsd-runner`, `repo-status`, `validate-runner`) — no TDD-specific skill
- Lobster binary not installed in gateway container
- 7/49 bundled skills ready; most gated by missing binaries

**Primary recommendation:** Configure `llm-task` with provider routing (Gemini free for review, Claude for coding), create TDD-cycle skill with proper SKILL.md gating, install Lobster for workflow automation, and create a validation pipeline `.lobster` file.
</research_summary>

<standard_stack>
## Standard Stack

### Core (already available)
| Component | Status | Purpose | Config Location |
|-----------|--------|---------|-----------------|
| llm-task plugin | Enabled (bare) | JSON-only LLM calls | `plugins.entries.llm-task` |
| Skills system | Active (7/49) | Extensible agent capabilities | `~/.openclaw/skills/` + workspace |
| Skills watcher | Active | Auto-refresh on SKILL.md change | `skills.load.watch` |

### Needs Configuration
| Component | Status | Purpose | What's Needed |
|-----------|--------|---------|---------------|
| Lobster | Not installed | Typed workflow pipelines | `npm install -g @openclaw/lobster` in container |
| llm-task routing | Unconfigured | Cross-model review | `defaultProvider`, `allowedModels` |
| TDD skill | Missing | TDD cycle automation | SKILL.md in workspace skills |
| ClawHub | Ready (bundled) | Skill marketplace | Already available |

### Provider Routing for llm-task
| Provider | Model | Use Case | Cost |
|----------|-------|----------|------|
| google | gemini-2.5-pro | Cross-review, summarization | Free (1000 req/day) |
| openai | gpt-5.2 | Alternative review | Paid |
| anthropic | claude-opus-4-5 | Coding tasks (NOT review) | Paid |

`allowedModels` should restrict to: `["google/gemini-2.5-pro", "openai/gpt-5.2"]` — exclude Claude to avoid self-review.
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### SKILL.md Format
```markdown
---
name: tdd-cycle
description: Run TDD red-green-refactor cycle with validation
metadata: {"openclaw":{"requires":{"bins":["python3","pytest"],"env":[],"config":[]}}}
user-invocable: true
---

## Instructions
[skill content - the prompt that runs when invoked]
```

Key fields:
- `name`: identifier (kebab-case)
- `description`: shown in skills list
- `metadata.openclaw.requires`: gating (bins, env, config)
- `user-invocable: true`: user can invoke directly
- `disable-model-invocation: true`: prevent model from auto-invoking

### llm-task Configuration
```json
{
  "plugins": {
    "entries": {
      "llm-task": {
        "enabled": true,
        "defaultProvider": "google",
        "defaultModel": "gemini-2.5-pro",
        "allowedModels": [
          "google/gemini-2.5-pro",
          "openai/gpt-5.2"
        ],
        "maxTokens": 2000,
        "timeoutMs": 60000
      }
    }
  }
}
```

### Lobster Workflow File (.lobster)
```yaml
name: validate-and-review
args:
  target: "."
steps:
  - id: validate
    run: python3 ~/.claude/templates/validation/orchestrator.py 1
  - id: review
    run: openclaw.invoke --tool llm-task --action json --args-json '{
      "prompt": "Review this code diff for issues",
      "input": {"diff": "$validate.stdout"},
      "schema": {"type":"object","properties":{"issues":{"type":"array"},"score":{"type":"number"}},"required":["issues","score"]}
    }'
    condition: $validate.exitCode == 0
  - id: approve
    run: approve --preview-from-stdin --limit 50
    stdin: $review.json
```

### Skill Locations (precedence high→low)
1. Workspace: `<agent-workspace>/skills/` (highest)
2. Managed: `~/.openclaw/skills/`
3. Bundled: built-in (lowest)

### Tools Allow/Deny per Agent
```json
{
  "agents": {
    "list": [{
      "id": "main",
      "tools": {
        "allow": ["llm-task", "lobster"]
      }
    }]
  }
}
```

### Anti-Patterns to Avoid
- **Don't create skills without gating metadata** — ungated skills load everywhere
- **Don't allow llm-task to call the same model doing coding** — self-review is useless
- **Don't skip JSON schema in llm-task** — output is untrusted without validation
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-model review | Custom API calls | llm-task plugin | Built-in provider routing, schema validation, timeout handling |
| Multi-step pipelines | Shell scripts | Lobster .lobster files | Approval gates, resume tokens, deterministic execution |
| Skill discovery | Manual SKILL.md management | ClawHub + skills watcher | Auto-refresh, registry, version management |
| LLM output parsing | Manual JSON extraction | llm-task schema parameter | Validated against JSON Schema, type-safe |

**Key insight:** OpenClaw's plugin system handles provider routing, output validation, and safety. Custom API wrappers bypass these guarantees.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Self-Review Anti-Pattern
**What goes wrong:** Agent uses same model for coding and review — finds no issues
**Why it happens:** llm-task defaults to same provider as agent
**How to avoid:** Set `allowedModels` to exclude primary coding model
**Warning signs:** Review always returns "no issues found"

### Pitfall 2: Lobster Not in PATH
**What goes wrong:** `openclaw.invoke --tool lobster` fails silently
**Why it happens:** Lobster binary not installed in container or not in PATH
**How to avoid:** Install globally in container, verify with `lobster --version`
**Warning signs:** Tool returns error or empty result

### Pitfall 3: Skill Token Overhead
**What goes wrong:** Too many skills bloat system prompt
**Why it happens:** Each skill adds ~24+ tokens of prompt overhead
**How to avoid:** Use gating (`requires.bins`, `requires.env`) to filter irrelevant skills
**Warning signs:** Slow responses, higher token usage

### Pitfall 4: Workspace Skills Not Picked Up
**What goes wrong:** New SKILL.md not appearing in `skills list`
**Why it happens:** Skills folder not in agent workspace, or watcher debounce
**How to avoid:** Place in `<agent-workspace>/skills/<name>/SKILL.md`, wait 250ms
**Warning signs:** `skills list` doesn't show new skill after creation
</common_pitfalls>

<code_examples>
## Code Examples

### llm-task Invocation from Lobster
```lobster
openclaw.invoke --tool llm-task --action json --args-json '{
  "prompt": "Review this code for bugs, security issues, and style problems. Return structured feedback.",
  "input": {"code": "$stdin"},
  "schema": {
    "type": "object",
    "properties": {
      "score": {"type": "number", "minimum": 0, "maximum": 100},
      "issues": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "severity": {"type": "string", "enum": ["critical","major","minor"]},
            "description": {"type": "string"},
            "suggestion": {"type": "string"}
          }
        }
      }
    },
    "required": ["score", "issues"]
  }
}'
```
Source: OpenClaw docs + Context7

### SKILL.md with Gating
```markdown
---
name: tdd-cycle
description: Run TDD red-green-refactor with pytest validation
metadata: {"openclaw":{"requires":{"bins":["python3","pytest"],"env":[],"config":[]}}}
user-invocable: true
---

## TDD Cycle

Run red-green-refactor for a given feature:
1. Write failing test (RED)
2. Implement minimal code (GREEN)
3. Refactor if needed
4. Run validation: `python3 ~/.claude/templates/validation/orchestrator.py 1`
```
Source: OpenClaw skills docs

### Enable llm-task + Lobster per Agent
```json
{
  "plugins": {
    "entries": {
      "llm-task": {
        "enabled": true,
        "defaultProvider": "google",
        "defaultModel": "gemini-2.5-pro",
        "allowedModels": ["google/gemini-2.5-pro", "openai/gpt-5.2"],
        "maxTokens": 2000,
        "timeoutMs": 60000
      }
    }
  },
  "agents": {
    "list": [{
      "id": "main",
      "tools": { "allow": ["llm-task", "lobster"] }
    }]
  }
}
```
Source: OpenClaw configuration docs
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom API calls for cross-model | llm-task plugin | 2025 Q4 | Built-in routing, schema, safety |
| Shell scripts for pipelines | Lobster .lobster files | 2025 Q4 | Resume tokens, approval gates |
| Manual skill management | ClawHub registry | 2025 Q3 | Version management, marketplace |
| Per-agent custom hooks | SKILL.md with gating | 2025 | Load-time filtering, token efficiency |

**New patterns:**
- Lobster `approve` step for human-in-the-loop workflows
- llm-task `schema` parameter for typed LLM output
- Skills `metadata.openclaw.requires` for zero-overhead gating
</sota_updates>

<open_questions>
## Open Questions

1. **Lobster installation in Docker container**
   - What we know: Not currently installed, available as `@openclaw/lobster` npm package
   - What's unclear: Whether persistent deps volume covers lobster or needs separate install
   - Recommendation: Install in container, add to entrypoint or Dockerfile

2. **llm-task Gemini authentication**
   - What we know: Gemini provider configured in Phase 21 with OAuth
   - What's unclear: Whether llm-task honors the same auth profile as main agent
   - Recommendation: Test with explicit `authProfileId` parameter first
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [OpenClaw Skills docs](https://docs.openclaw.ai/tools/skills) — SKILL.md format, gating, locations
- [OpenClaw LLM Task docs](https://docs.openclaw.ai/tools/llm-task) — plugin config, allowedModels, schema
- [OpenClaw Lobster docs](https://docs.openclaw.ai/tools/lobster) — workflow syntax, steps, approval gates
- Context7 `/llmstxt/openclaw_ai_llms-full_txt` — code examples, integration patterns

### Secondary (MEDIUM confidence)
- [GitHub openclaw/lobster](https://github.com/openclaw/lobster) — repository, README
- Live `openclaw config get` output — current state verification

### Tertiary (LOW confidence)
- None — all findings verified against official docs
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: OpenClaw Skills, LLM Task, Lobster
- Ecosystem: ClawHub, provider routing, JSON Schema validation
- Patterns: SKILL.md gating, llm-task cross-model review, Lobster pipelines
- Pitfalls: Self-review, token overhead, installation

**Confidence breakdown:**
- Skills system: HIGH — verified with docs + live `skills list` output
- llm-task: HIGH — verified with docs + live `config get` output
- Lobster: HIGH — verified with docs, confirmed not installed via live check
- Integration patterns: MEDIUM — code examples from docs, not yet tested

**Research date:** 2026-02-02
**Valid until:** 2026-03-04 (30 days — OpenClaw ecosystem stable)
</metadata>

---

*Phase: 24-skills-llm-task*
*Research completed: 2026-02-02*
*Ready for planning: yes*
