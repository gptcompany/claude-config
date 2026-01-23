#!/usr/bin/env python3
"""
PostToolUse Hook for Validation Orchestrator.

Integrates Tier 1 validation into Claude Code workflow.
Reads JSON from stdin, validates Write/Edit operations, returns decision.

Usage:
    echo '{"tool_name": "Write", "tool_input": {"file_path": "test.py"}}' | python3 post_tool_hook.py

Returns:
    {"decision": "approve"} or {"decision": "block", "reason": "..."}

Behavior:
    - Only validates Write/Edit tools (others get immediate approve)
    - 30s timeout to avoid blocking workflow
    - Fail-open: returns approve on any error
    - Only checks Tier 1 (blockers) for speed
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

# Setup logging to file (not stdout - that's for hook response)
LOG_DIR = Path.home() / ".claude" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "post_tool_hook", "message": "%(message)s"}',
    handlers=[
        logging.FileHandler(LOG_DIR / "validation-hook.log"),
    ],
)
logger = logging.getLogger(__name__)

# Constants
TIMEOUT_SECONDS = 30
TOOLS_TO_VALIDATE = {"Write", "Edit", "MultiEdit"}


def approve() -> None:
    """Output approve decision and exit."""
    print(json.dumps({"decision": "approve"}))
    sys.exit(0)


def block(reason: str) -> None:
    """Output block decision and exit."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def timeout_handler(signum, frame):
    """Handle timeout - fail-open."""
    logger.warning("Timeout reached - approving (fail-open)")
    approve()


async def run_validation(file_path: str) -> tuple[bool, str]:
    """
    Run Tier 1 validation on a single file.

    Returns:
        (has_blockers: bool, summary: str)
    """
    # Add parent directory to path to import orchestrator
    templates_dir = Path(__file__).parent.parent
    if str(templates_dir) not in sys.path:
        sys.path.insert(0, str(templates_dir))

    try:
        from orchestrator import ValidationOrchestrator

        orchestrator = ValidationOrchestrator()

        # Use validate_file method if available, otherwise fall back to run_tier
        if hasattr(orchestrator, "validate_file"):
            result = await orchestrator.validate_file(file_path, tier=1)
            return result.has_blockers, result.message
        else:
            # Fallback: run Tier 1 validation
            from orchestrator import ValidationTier

            tier_result = await orchestrator.run_tier(ValidationTier.BLOCKER)

            if not tier_result.passed:
                failed = ", ".join(tier_result.failed_dimensions)
                return True, f"Tier 1 blockers: {failed}"
            return False, "Tier 1 passed"

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return False, f"Import error (skipped): {e}"
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False, f"Validation error (skipped): {e}"


def main():
    """Main entry point for PostToolUse hook."""
    # Set up timeout signal (Unix only)
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(TIMEOUT_SECONDS)
    except (AttributeError, ValueError):
        # Windows doesn't have SIGALRM - we'll rely on asyncio timeout
        pass

    try:
        # Read input from stdin
        try:
            raw_input = sys.stdin.read()
            if not raw_input.strip():
                logger.debug("Empty stdin - approving")
                approve()

            hook_input = json.loads(raw_input)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON input: {e}")
            approve()  # Fail-open

        # Extract tool info
        tool_name = hook_input.get("tool_name", "")
        tool_input = hook_input.get("tool_input", {})
        session_id = hook_input.get("session_id", "unknown")

        logger.info(f"Processing {tool_name} in session {session_id}")

        # Only validate Write/Edit tools
        if tool_name not in TOOLS_TO_VALIDATE:
            logger.debug(f"Tool {tool_name} not in validation list - approving")
            approve()

        # Extract file path from tool input
        file_path = tool_input.get("file_path") or tool_input.get("path")
        if not file_path:
            logger.warning(f"No file_path in {tool_name} input - approving")
            approve()

        # Skip non-Python files for now (Tier 1 validators are Python-focused)
        if not file_path.endswith(".py"):
            logger.debug(f"Non-Python file {file_path} - approving")
            approve()

        # Run validation with timeout
        try:
            has_blockers, summary = asyncio.run(
                asyncio.wait_for(
                    run_validation(file_path),
                    timeout=TIMEOUT_SECONDS - 5,  # Leave margin for signal
                )
            )
        except asyncio.TimeoutError:
            logger.warning("Asyncio timeout - approving (fail-open)")
            approve()

        # Return decision
        if has_blockers:
            logger.warning(f"Blocking {file_path}: {summary}")
            block(summary)
        else:
            logger.info(f"Approved {file_path}: {summary}")
            approve()

    except Exception as e:
        # Catch-all: fail-open
        logger.error(f"Unexpected error: {e}")
        approve()
    finally:
        # Cancel alarm
        try:
            signal.alarm(0)
        except (AttributeError, ValueError):
            pass


if __name__ == "__main__":
    main()
