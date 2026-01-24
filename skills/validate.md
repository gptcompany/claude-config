# /validate - Unified Validation Command

Run the 14-dimension ValidationOrchestrator.

## Usage

- `/validate` - Run all tiers (full validation)
- `/validate 1` or `/validate quick` - Run Tier 1 blockers only
- `/validate 2` - Run Tier 2 warnings only
- `/validate 3` - Run Tier 3 monitors only

## What it does

1. Loads validation config from `.claude/validation/config.json`
2. Runs ValidationOrchestrator with specified tier filter
3. Outputs results using TerminalReporter (rich if available)
4. Returns exit code: 0 if passed, 1 if Tier 1 failures

## Tier Summary

| Tier | Purpose | Behavior |
|------|---------|----------|
| 1 | Blockers | MUST pass - blocks CI/merge |
| 2 | Warnings | SHOULD fix - agents suggest fixes |
| 3 | Monitors | Track metrics - emit to Grafana |

## Exit Codes

- 0: All specified tiers passed
- 1: Tier 1 blockers failed
- 2: Validation error (config not found, etc.)
