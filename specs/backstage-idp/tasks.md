# Tasks: Backstage Internal Developer Portal

**Input**: Design documents from `/specs/backstage-idp/`
**Prerequisites**: plan.md (required), spec.md (required)

**Tests**: Not required for this infrastructure project.

**Organization**: Tasks grouped by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Deployment**: `/media/sam/1TB/backstage-portal/`
- **Config**: `/media/sam/1TB/backstage-portal/app-config.yaml`
- **Repo Entities**: `{repo}/catalog-info.yaml` (standard Backstage)
- **MCP Entities**: `/media/sam/1TB/backstage-portal/catalog/mcp/` (central, global config)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create Backstage project and base configuration

- [X] T001 Create deployment directory at /media/sam/1TB/backstage-portal/
- [X] T002 Initialize Backstage app with `npx @backstage/create-app@latest`
- [X] T003 [P] Configure PostgreSQL connection in app-config.yaml (port 5433)
- [X] T004 [P] Create docker-compose.yml for Backstage deployment
- [X] T005 [P] Create .env file with database credentials

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Configure app-config.yaml with base settings (org, title, baseUrl)
- [X] T007 Setup catalog locations in app-config.yaml pointing to repo paths (file://)
- [X] T008 Create system entity in /media/sam/1TB/backstage-portal/catalog/system.yaml
- [X] T009 Verify Backstage starts with `docker-compose up` on port 7007

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Software Catalog (Priority: P1) 🎯 MVP

**Goal**: All 4 repos visible in Backstage catalog with correct metadata

**Independent Test**: Navigate to localhost:7007/catalog and verify all 4 repos appear

### Implementation for User Story 1

**Standard approach: catalog-info.yaml in each repo root**

- [X] T010 [P] [US1] Create catalog-info.yaml in /media/sam/1TB/nautilus_dev/catalog-info.yaml
- [X] T011 [P] [US1] Create catalog-info.yaml in /media/sam/1TB/N8N_dev/catalog-info.yaml
- [X] T012 [P] [US1] Create catalog-info.yaml in /media/sam/1TB/UTXOracle/catalog-info.yaml
- [X] T013 [P] [US1] Create catalog-info.yaml in /media/sam/1TB/LiquidationHeatmap/catalog-info.yaml
- [X] T014 [US1] Configure app-config.yaml catalog locations to discover all repo catalog-info.yaml files
- [X] T015 [US1] Verify all 4 repos appear in catalog UI at localhost:7007/catalog

**Checkpoint**: User Story 1 complete - repos visible in catalog

---

## Phase 4: User Story 2 - Grafana Integration (Priority: P2)

**Goal**: Embed Grafana dashboards in Backstage entity pages

**Independent Test**: Open any repo entity and see Grafana dashboard panel

### Implementation for User Story 2

- [X] T016 [US2] Install @backstage-community/plugin-grafana (yarn add) in packages/app
- [X] T017 [US2] Configure Grafana integration in app-config.yaml (localhost:3000)
- [X] T018 [US2] Add EntityGrafanaDashboardsCard to entity page in packages/app/src/components/catalog/EntityPage.tsx
- [X] T019 [P] [US2] Add grafana/dashboard-selector annotation to /media/sam/1TB/nautilus_dev/catalog-info.yaml
- [X] T020 [P] [US2] Add grafana/dashboard-selector annotation to /media/sam/1TB/N8N_dev/catalog-info.yaml
- [X] T021 [US2] Verify dashboards appear in entity pages

**Checkpoint**: User Story 2 complete - Grafana dashboards embedded

---

## Phase 5: User Story 3 - GitHub Integration (Priority: P3)

**Goal**: Show PR status and GitHub Actions in Backstage

**Independent Test**: Open any repo entity and see recent PRs and CI status

### Implementation for User Story 3

- [X] T022 [US3] Configure GitHub integration in app-config.yaml with token
- [X] T023 [US3] Install @backstage-community/plugin-github-actions (yarn add) in packages/app
- [X] T024 [US3] Install @roadiehq/backstage-plugin-github-pull-requests in packages/app
- [X] T025 [US3] Add GitHub cards to entity page in packages/app/src/components/catalog/EntityPage.tsx
- [X] T026 [P] [US3] Add github.com/project-slug annotation to all 4 repo catalog-info.yaml files
- [X] T027 [US3] Verify PRs and Actions appear in entity pages

**Checkpoint**: User Story 3 complete - GitHub integration working

---

## Phase 6: User Story 4 - MCP Profiles Tracking (Priority: P4)

**Goal**: Track MCP profiles as catalog entities

**Independent Test**: Navigate to localhost:7007/catalog and see MCP profiles listed

### Implementation for User Story 4

- [X] T028 [US4] Define Resource kind for MCP profiles in app-config.yaml
- [X] T029 [P] [US4] Create mcp-base.yaml entity in /media/sam/1TB/backstage-portal/catalog/mcp/base.yaml
- [X] T030 [P] [US4] Create mcp-live.yaml entity in /media/sam/1TB/backstage-portal/catalog/mcp/live.yaml
- [X] T031 [US4] Create mcp-profiles.yaml that imports all MCP entities in /media/sam/1TB/backstage-portal/catalog/mcp-profiles.yaml
- [X] T032 [US4] Add MCP profiles to catalog locations in app-config.yaml
- [X] T033 [US4] Verify MCP profiles appear in catalog UI

**Checkpoint**: User Story 4 complete - MCP profiles tracked

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T034 [P] Create sync script from canonical.yaml to catalog in ~/.claude/scripts/sync-to-backstage.py
- [X] T035 [P] Add docker-compose restart policy (always)
- [X] T036 [P] Document Backstage access in ~/.claude/INFRASTRUCTURE.md
- [X] T037 Run full validation: all entities load, all plugins work
- [X] T038 Create alias `ccbackstage` to open Backstage URL

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (Catalog) → US2, US3, US4 can follow
  - US2 (Grafana) and US3 (GitHub) can run in parallel
  - US4 (MCP) can run in parallel with US2/US3
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: MVP - No dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 (needs entities to add annotations)
- **User Story 3 (P3)**: Depends on US1 (needs entities to add annotations)
- **User Story 4 (P4)**: Independent of US2/US3

### Parallel Opportunities

- T003, T004, T005 can run in parallel (Setup phase)
- T010, T011, T012, T013 can run in parallel (all repo yamls)
- T019, T020 can run in parallel (grafana annotations)
- T029, T030 can run in parallel (MCP entities)
- US2, US3, US4 can start in parallel after US1

---

## Parallel Example: User Story 1

```bash
# Launch all repo entity files together:
Task: "Create nautilus-dev component in catalog/nautilus-dev.yaml"
Task: "Create n8n-dev component in catalog/n8n-dev.yaml"
Task: "Create utxoracle component in catalog/utxoracle.yaml"
Task: "Create liquidheatmap component in catalog/liquidheatmap.yaml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Catalog)
4. **STOP and VALIDATE**: All 4 repos visible in UI
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Backstage running
2. Add US1 (Catalog) → Repos visible → MVP!
3. Add US2 (Grafana) → Dashboards embedded
4. Add US3 (GitHub) → PRs/Actions visible
5. Add US4 (MCP) → Profiles tracked
6. Polish → Full integration

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 38 |
| **Phase 1 (Setup)** | 5 tasks |
| **Phase 2 (Foundational)** | 4 tasks |
| **US1 (Catalog)** | 6 tasks |
| **US2 (Grafana)** | 6 tasks |
| **US3 (GitHub)** | 6 tasks |
| **US4 (MCP)** | 6 tasks |
| **Phase 7 (Polish)** | 5 tasks |
| **Parallel Opportunities** | 15+ tasks |
| **MVP Scope** | Phases 1-3 (15 tasks) |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
