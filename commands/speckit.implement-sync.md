---
description: Implement Spec Kit tasks while keeping repository and GitHub state synchronized.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, Skill
---

# /speckit.implement-sync

1. Resolve the active Spec Kit feature and read `spec.md`, `plan.md` and
   `tasks.md`.
2. Reconcile the repository ledger before selecting work.
3. Execute only the next approved task, directly or through the active Gobabygo
   coordinator contract.
4. Run the task's acceptance checks and collect immutable evidence.
5. Obtain independent review when required by risk or policy.
6. Mark the task complete and sync GitHub only after checks pass.
7. Update the review ledger and handoff before exiting or compacting.

Use repository files for crash recovery. Do not invoke Claude Flow/Ruflo or
create a second task database.
