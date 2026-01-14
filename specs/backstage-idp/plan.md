# Implementation Plan: Backstage Internal Developer Portal

**Branch**: `N/A (global config)` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/backstage-idp/spec.md`

## Summary

Deploy Backstage as unified developer portal to centralize:
- Software catalog for all 4 repositories
- MCP profiles tracking
- Grafana dashboard embedding
- GitHub integration (PRs, Actions)

Technical approach: Docker Compose deployment with PostgreSQL backend, community plugins for Grafana/GitHub integration.

## Technical Context

**Language/Version**: TypeScript (Node.js 18+) - Backstage default
**Primary Dependencies**: @backstage/core, @backstage-community/plugin-grafana, @backstage-community/plugin-github-actions
**Storage**: PostgreSQL 15 (can reuse existing n8n PG or new container)
**Testing**: Manual validation (not TDD - deployment/config project)
**Target Platform**: Linux server (localhost:7007)
**Project Type**: Single deployment (Docker Compose)
**Performance Goals**: N/A - internal tool, single user
**Constraints**: Minimal resource usage, fast startup
**Scale/Scope**: 4 repos, ~10 MCP profiles, 5 dashboards

## Constitution Check

*GATE: Using simplified gates for infrastructure project*

| Gate | Status | Notes |
|------|--------|-------|
| Docker isolation | PASS | Runs in container |
| Config as code | PASS | All YAML/JSON configs |
| Minimal dependencies | PASS | Only required plugins |
| Reversible | PASS | Can remove containers |

## Project Structure

### Documentation (this feature)

```text
specs/backstage-idp/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Technology decisions
├── tasks.md             # Implementation tasks
└── catalog/             # Catalog entity templates
    ├── component-template.yaml
    └── mcp-profile-template.yaml
```

### Source Code (deployment)

```text
/media/sam/1TB/backstage-portal/    # New directory
├── docker-compose.yml              # Main deployment
├── app-config.yaml                 # Backstage config
├── app-config.local.yaml           # Local overrides
├── catalog/                        # Entity definitions
│   ├── all-repos.yaml              # All repo entities
│   └── mcp-profiles.yaml           # MCP profile entities
└── packages/                       # Custom plugins (if needed)
```

**Structure Decision**: Docker Compose deployment in dedicated directory. No custom code needed - using community plugins only.

## Phase 0: Research

### Technology Decisions

1. **Backstage Version**: Use `@backstage/create-app@latest` (stable)
   - Rationale: Stable version, active community
   - Alternative: Custom build - rejected (too complex)

2. **Database**: Reuse existing PostgreSQL (port 5433)
   - Rationale: Already running for n8n
   - Alternative: New PG container - fallback if conflicts

3. **Grafana Plugin**: `@backstage-community/plugin-grafana`
   - Rationale: Official community plugin, iframe embedding
   - Alternative: Custom iframe - more work

4. **GitHub Plugin**: Built-in `@backstage/plugin-github-actions`
   - Rationale: First-party support
   - Alternative: None needed

5. **MCP Tracking**: Custom catalog entity type
   - Rationale: No existing plugin for MCP
   - Alternative: Use Component with annotations

## Phase 1: Design

### Catalog Entity Model

```yaml
# Component (for repos)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: nautilus-dev
  annotations:
    github.com/project-slug: gptprojectmanager/nautilus_dev
    grafana/dashboard-selector: 'folder=nautilus'
    backstage.io/techdocs-ref: dir:.
spec:
  type: service
  lifecycle: production
  owner: sam
  system: claude-infrastructure

# Resource (for MCP profiles)
apiVersion: backstage.io/v1alpha1
kind: Resource
metadata:
  name: mcp-profile-live
  description: Full MCP profile with all tools
spec:
  type: mcp-profile
  owner: sam
  dependsOn:
    - resource:context7
    - resource:sentry
    - resource:linear
    - resource:claude-flow
```

### API Contracts

N/A - No custom API needed. Using Backstage REST API.

### Integration Points

1. **canonical.yaml → Catalog sync**
   - Script to generate catalog entities from canonical.yaml
   - Run on canonical.yaml changes

2. **Grafana → Backstage**
   - Configure Grafana URL in app-config.yaml
   - Use dashboard annotations on entities

3. **GitHub → Backstage**
   - Configure GitHub integration token
   - Enable discovery for gptprojectmanager org

## Complexity Tracking

| Aspect | Complexity | Justification |
|--------|------------|---------------|
| Plugins | LOW | Using only community plugins |
| Config | LOW | Standard YAML configs |
| Custom code | NONE | No custom plugins needed |
| Maintenance | LOW | Docker + auto-restart |

## Dependencies

1. Docker & Docker Compose installed
2. PostgreSQL running (port 5433)
3. Grafana running (port 3000)
4. GitHub token with repo access
5. Node.js 18+ (for backstage CLI if needed)

## Next Steps

Run `/speckit.tasks` to generate implementation tasks.
