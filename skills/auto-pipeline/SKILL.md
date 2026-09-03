---
name: auto-pipeline
description: Run a bounded Spec Kit development workflow through the Gobabygo coordinator.
argument-hint: "<feature>"
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /auto-pipeline - Spec Kit coordinator workflow

Use the repository's installed Spec Kit version and Gobabygo Mesh Live. Do not
create a parallel task database.

1. Resolve the exact repository and feature. Stop if either is ambiguous.
2. Run the applicable Spec Kit stages: specify, clarify, plan and tasks.
3. Sync approved tasks to the repository's GitHub ledger when configured.
4. Delegate one bounded writer task at a time through Mesh Live.
5. Require tests and concrete evidence from the writer.
6. Delegate an independent review to a different provider where practical.
7. Apply findings, rerun tests and stop after the configured review budget.
8. Update Spec Kit tasks, review ledger and handoff before compacting or exiting.

Human approval remains mandatory for destructive actions, secrets, production,
money movement and unresolved product decisions.
