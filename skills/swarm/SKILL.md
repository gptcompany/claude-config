---
name: swarm
description: Compatibility entry point for delegating work through Gobabygo Mesh Live.
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /swarm - Mesh Live delegation

Claude Flow/Ruflo is retired. Treat `/swarm` as an alias for the Gobabygo
coordinator workflow; do not start a second daemon, database or orchestration
protocol.

1. Inspect current workers with `mesh live board`.
2. Keep specification, plan and tasks in the repository's Spec Kit artifacts.
3. Create a worker only for an approved, bounded task with
   `mesh live ensure-antigravity <repo>` or `mesh live ensure-codex <repo>`.
4. Send a brief containing one delegation ID, scope, acceptance criteria,
   forbidden actions and required evidence.
5. Verify submission and completion through Mesh Live state and captured output.
6. Use Codex or Antigravity as an independent reviewer before closing risky work.

Never dispatch to a non-idle composer, bypass a trust/update/rate-limit guard, or
declare completion without test and repository evidence.
