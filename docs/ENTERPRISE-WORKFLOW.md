# Development Workflow

## Canonical Path

1. `/speckit.specify` defines the feature and acceptance criteria.
2. `/speckit.clarify` resolves material ambiguity.
3. `/speckit.plan` records architecture and verification strategy.
4. `/speckit.tasks` creates bounded, testable tasks.
5. The repository ledger synchronizes approved work with GitHub Issues.
6. Gobabygo Mesh Live delegates implementation and independent review.
7. CI and repository evidence determine completion.

Spec Kit artifacts remain the durable development record. GitHub is the shared
tracking surface. Tmux is the source of truth for live worker state. iTerm2 is
optional operator UI.

## Guardrails

- Use one writer per repository unless scopes are demonstrably disjoint.
- Every delegation has an ID, scope, acceptance criteria and forbidden actions.
- Do not infer completion from an idle prompt or echoed marker.
- Do not bypass trust, update, confirmation or rate-limit screens blindly.
- Bound review iterations; unresolved high-risk decisions return to the operator.
- Update tasks, review ledger and handoff before compacting or ending a session.

Claude Flow/Ruflo is not part of this workflow. Repository-specific experiments
must be explicitly enabled in that repository and must not alter the global
profile.
