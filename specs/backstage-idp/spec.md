# Backstage Internal Developer Portal

## Overview

Deploy Backstage as unified developer portal to track and manage:
- Repository catalog (nautilus-dev, n8n-dev, utxoracle, liquidheatmap)
- MCP profiles configuration
- Grafana dashboards integration
- GitHub integration (PRs, Actions)

### Future Enhancements (Post-MVP)
- ClaudeFlow orchestration status tracking
- Environment variables SSOT visualization
- Hooks configuration tracking

## Goals

1. **Single pane of glass** - All repos, MCP profiles, status in one UI
2. **Config tracking** - MCP profiles as catalog entities
3. **Grafana integration** - Embed existing dashboards in entity pages
4. **GitHub integration** - PR status and Actions visible per repo
5. **Programmatic config** - Update catalog via YAML files (no UI required)

## Non-Goals

- Replace existing tools (Grafana, Linear, Sentry)
- Complex plugin development (use community plugins)
- Multi-tenant enterprise setup (single user)

## Technical Requirements

### Deployment
- Docker Compose based (self-hosted)
- Port: 7007 (default Backstage)
- PostgreSQL backend (reuse existing PG or new container)

### Catalog Structure
```yaml
# Component (for repos)
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: nautilus-dev
  annotations:
    github.com/project-slug: gptprojectmanager/nautilus_dev
    grafana/dashboard-selector: 'folder=nautilus'
spec:
  type: service
  lifecycle: production
  owner: user:default/sam
  system: claude-infrastructure

# Resource (for MCP profiles)
apiVersion: backstage.io/v1alpha1
kind: Resource
metadata:
  name: mcp-live
  description: Full MCP profile with all tools
spec:
  type: mcp-profile
  owner: user:default/sam
```

### Plugins Required

| Plugin | Package | Status |
|--------|---------|--------|
| Catalog | Built-in | ✅ Core |
| Grafana | `@backstage-community/plugin-grafana` | ✅ Community |
| GitHub Actions | `@backstage-community/plugin-github-actions` | ✅ Community |
| GitHub PRs | `@roadiehq/backstage-plugin-github-pull-requests` | ⚠️ Third-party |

**Note**: All @backstage-community plugins are officially maintained in [backstage/community-plugins](https://github.com/backstage/community-plugins)

### Integration Points

1. **Grafana** - Embed dashboards via iframe/plugin
2. **GitHub** - PR status, Actions, Issues
3. **MCP Profiles** - Custom catalog entity type
4. **canonical.yaml** - Sync catalog from SSOT

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Backstage Portal (7007)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Software Catalog          Grafana Plugin     GitHub Plugin │
│  ├── nautilus-dev          (embedded)         (PR/Actions)  │
│  ├── n8n-dev                                                │
│  ├── utxoracle                                              │
│  └── liquidheatmap                                          │
│                                                             │
│  MCP Profiles (Resource)                                    │
│  ├── mcp-base                                               │
│  └── mcp-live                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    /catalog/*.yaml       localhost:3000       github.com/
    (entity definitions)  (Grafana)            gptprojectmanager
```

## Success Criteria

- [ ] Backstage running on localhost:7007
- [ ] All 4 repos visible in catalog
- [ ] Grafana dashboards embedded
- [ ] MCP profiles tracked as entities
- [ ] GitHub PR/Actions visible
- [ ] Can update config via YAML (no UI required)

## Risks

1. **Plugin compatibility** - Community plugins may break
   - Mitigation: Pin versions, test before upgrade

2. **Maintenance overhead** - Another service to manage
   - Mitigation: Docker Compose, auto-restart

3. **Config sync complexity** - canonical.yaml → Backstage
   - Mitigation: Simple script, not real-time sync

## Timeline Estimate

- Day 1: Docker setup + basic catalog
- Day 2: Grafana plugin + GitHub integration
- Day 3: MCP profiles custom entity
- Day 4: Testing + documentation

## References

- [Backstage.io](https://backstage.io/)
- [Backstage Grafana Plugin](https://github.com/K-Phoen/backstage-plugin-grafana)
- [Backstage GitHub Plugin](https://backstage.io/docs/integrations/github/discovery)
