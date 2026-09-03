# Development Orchestration Architecture

## Supported Layers

| Concern | Source of truth | Role |
|---|---|---|
| Feature intent and acceptance criteria | Spec Kit artifacts in the repository | Versioned specification, plan and tasks |
| Task/review visibility | GitHub Issues plus the repository ledger | Shared status and durable evidence |
| Live execution | Gobabygo Mesh Live over tmux | Persistent Claude, Codex and Antigravity sessions |
| Operator layout | Terminal or iTerm2 | Optional presentation only |

Claude Flow/Ruflo is retired from the global Claude profile. It is not required
for Spec Kit, task sync, worker delegation or session persistence.

## Workflow

1. Select one repository and one feature.
2. Create or update `spec.md`, `plan.md` and `tasks.md` with Spec Kit.
3. Sync approved tasks to GitHub when the repository enables the ledger.
4. Start the Gobabygo coordinator with `mcoordinator --workflow speckit`.
5. Delegate bounded tasks to persistent workers through Mesh Live.
6. Require tests and immutable evidence before marking a task complete.
7. Use a different provider for independent review when practical.
8. Persist review decisions and handoff state in the repository.

The coordinator may operate across repositories, but every delegation must name
the exact repository, scope and acceptance criteria. Production, secrets,
destructive actions, money movement and unresolved product choices remain manual
approval boundaries.

## Optional Integrations

Backstage, observability systems and repository-specific MCP servers may enrich
the workflow. They do not become control-plane dependencies and belong in the
repository that owns them.
