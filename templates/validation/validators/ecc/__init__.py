"""
ECC Validators - Validators ported from everything-claude-code agents.

This module contains validator implementations that wrap ECC agent patterns.
ECC agents are markdown prompt files that orchestrate CLI tools for validation.
We port their logic as Python validators that invoke the same CLI tools.

Source: /media/sam/1TB/everything-claude-code/agents/

Available validators (implemented in Plan 13-02):
- E2EValidator: Playwright E2E testing (wraps e2e-runner agent)
- TDDValidator: TDD workflow enforcement (wraps tdd-guide agent)
- EvalValidator: pass@k eval metrics (wraps eval-harness skill)
- SecurityEnhanced: OWASP Top 10 checks (enhances security-reviewer)

Usage:
    from validators.ecc import ECCValidatorBase

    class MyValidator(ECCValidatorBase):
        dimension = "my_dimension"
        tier = ValidationTier.BLOCKER
        agent = "my-agent"

        async def validate(self) -> ValidationResult:
            result = await self._run_tool(["my-tool", "--json"])
            data = self._parse_json_output(result.stdout)
            ...
"""

from .base import ECCValidatorBase
from .e2e_validator import E2EValidator
from .eval_validator import EvalValidator
from .security_enhanced import SecurityEnhancedValidator
from .tdd_validator import TDDValidator

__all__ = [
    "ECCValidatorBase",
    "E2EValidator",
    "SecurityEnhancedValidator",
    "TDDValidator",
    "EvalValidator",
]
