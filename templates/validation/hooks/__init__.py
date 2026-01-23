"""
Validation Hooks for Claude Code Integration.

This package provides hooks for integrating the validation orchestrator
into Claude Code's PostToolUse workflow.

Hooks:
- post_tool_hook: PostToolUse hook for Tier 1 validation on Write/Edit
- install: Helper to install hooks into settings.json
"""

from .post_tool_hook import main as post_tool_hook_main

__all__ = ["post_tool_hook_main"]
