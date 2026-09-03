---
description: Show durable workflow state and live Gobabygo worker state.
allowed-tools: Read, Glob, Grep, Bash
---

# /pipeline:status

Summarize, without mutation:

1. the current Spec Kit or GSD spec, plan and task files;
2. pending/completed entries in the repository GitHub/review ledger;
3. the latest coordinator handoff;
4. live worker state from `mesh live board`.

Clearly separate durable repository state from live tmux state. Do not infer
completion from an idle prompt or an echoed completion marker.
