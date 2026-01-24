"""
Security Enhanced Validator - OWASP Top 10 pattern checks.

Adds OWASP-specific grep-based checks from ECC security-reviewer agent.
These are heuristic pattern checks, not full security scanning.
Use alongside bandit/Trivy for comprehensive security validation.

Source: /media/sam/1TB/everything-claude-code/agents/security-reviewer.md
"""

import subprocess
from datetime import datetime
from pathlib import Path

from .base import ECCValidatorBase, ValidationResult, ValidationTier

__all__ = ["SecurityEnhancedValidator"]


class SecurityEnhancedValidator(ECCValidatorBase):
    """
    OWASP Top 10 pattern checker.

    Performs grep-based heuristic checks for common vulnerability patterns:
    - A01: Broken Access Control (missing auth decorators)
    - A03: Injection (f-string SQL queries)
    - A07: XSS (innerHTML usage)
    - A09: Logging failures (bare except without logging)

    These are quick pattern checks, not exhaustive security scanning.
    Use with bandit/Trivy/Semgrep for full coverage.

    Tier: BLOCKER (Tier 1) - Security issues block CI/CD
    Agent: security-reviewer
    """

    dimension = "security_enhanced"
    tier = ValidationTier.BLOCKER
    agent = "security-reviewer"
    timeout = 60  # Grep checks are fast

    def __init__(self, project_path: str | Path = "."):
        """
        Initialize SecurityEnhancedValidator.

        Args:
            project_path: Path to project root to scan
        """
        self.project_path = Path(project_path)

    async def validate(self) -> ValidationResult:
        """
        Run OWASP pattern checks and return validation result.

        Returns:
            ValidationResult with:
            - passed: True if no patterns found
            - message: Summary of issues found
            - details: Dict with issues by category
            - fix_suggestion: How to address found issues
        """
        start = datetime.now()

        # Check if src/ directory exists (common project structure)
        src_dir = self.project_path / "src"
        scan_path = src_dir if src_dir.exists() else self.project_path

        issues: dict[str, list[str]] = {}

        # A01: Broken Access Control - check for auth decorators
        a01_issues = await self._check_a01_access_control(scan_path)
        if a01_issues:
            issues["A01_broken_access_control"] = a01_issues

        # A03: Injection - check for f-string SQL
        a03_issues = await self._check_a03_injection(scan_path)
        if a03_issues:
            issues["A03_injection"] = a03_issues

        # A07: XSS - check for innerHTML
        a07_issues = await self._check_a07_xss(scan_path)
        if a07_issues:
            issues["A07_xss"] = a07_issues

        # A09: Logging failures - check for bare except
        a09_issues = await self._check_a09_logging(scan_path)
        if a09_issues:
            issues["A09_logging_failures"] = a09_issues

        total_issues = sum(len(v) for v in issues.values())

        if total_issues == 0:
            return ValidationResult(
                dimension=self.dimension,
                tier=self.tier,
                passed=True,
                message="No OWASP pattern issues found",
                details={"scanned_path": str(scan_path)},
                duration_ms=self._format_duration(start),
            )

        # Build issue summary
        issue_summary = ", ".join(f"{k}: {len(v)}" for k, v in issues.items() if v)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=False,
            message=f"OWASP issues found: {issue_summary}",
            details=issues,
            fix_suggestion="Review flagged patterns. See OWASP Top 10 for remediation.",
            agent=self.agent,
            duration_ms=self._format_duration(start),
        )

    async def _check_a01_access_control(self, path: Path) -> list[str]:
        """
        Check for A01: Broken Access Control.

        Looks for route handlers without auth decorators.
        This is a heuristic - checks if common auth patterns exist.
        """
        issues = []

        # Check Python auth decorators
        result = await self._run_grep(
            r"@requires_auth\|@login_required\|@auth_required", path, include="*.py"
        )
        py_has_auth = bool(result.strip())

        # Check if there are route handlers but no auth
        route_result = await self._run_grep(
            r"@app\.route\|@router\.\|@blueprint\.", path, include="*.py"
        )
        has_routes = bool(route_result.strip())

        if has_routes and not py_has_auth:
            issues.append(
                "Python routes found without @requires_auth/@login_required decorators"
            )

        # Check TypeScript/JS auth patterns
        ts_result = await self._run_grep(
            r"requireAuth\|isAuthenticated\|withAuth", path, include="*.ts"
        )
        ts_has_auth = bool(ts_result.strip())

        route_ts_result = await self._run_grep(
            r"export.*function.*Handler\|app\.get\|router\.get", path, include="*.ts"
        )
        has_ts_routes = bool(route_ts_result.strip())

        if has_ts_routes and not ts_has_auth:
            issues.append("TypeScript routes found without auth middleware/guards")

        return issues

    async def _check_a03_injection(self, path: Path) -> list[str]:
        """
        Check for A03: Injection vulnerabilities.

        Looks for f-string SQL queries which may be vulnerable.
        """
        issues = []

        # Check for f-string SQL patterns
        patterns = [
            r'f".*{.*}.*SELECT',
            r"f'.*{.*}.*SELECT",
            r'f".*{.*}.*INSERT',
            r"f'.*{.*}.*INSERT",
            r'f".*{.*}.*UPDATE',
            r"f'.*{.*}.*UPDATE",
            r'f".*{.*}.*DELETE',
            r"f'.*{.*}.*DELETE",
        ]

        for pattern in patterns:
            result = await self._run_grep(pattern, path, include="*.py")
            if result.strip():
                # Extract just the filename:line for each match
                for line in result.strip().split("\n")[:3]:  # Limit to 3 examples
                    if line:
                        issues.append(f"SQL injection risk: {line[:100]}")
                break  # Don't duplicate if multiple patterns match

        return issues

    async def _check_a07_xss(self, path: Path) -> list[str]:
        """
        Check for A07: XSS vulnerabilities.

        Looks for innerHTML usage which can lead to XSS.
        """
        issues = []

        # Check innerHTML usage in JS/TS/TSX files
        for ext in ["*.js", "*.ts", "*.tsx", "*.jsx"]:
            result = await self._run_grep(r"innerHTML\s*=", path, include=ext)
            if result.strip():
                for line in result.strip().split("\n")[:3]:
                    if line:
                        issues.append(f"XSS risk (innerHTML): {line[:100]}")
                break

        # Check dangerouslySetInnerHTML in React
        result = await self._run_grep(r"dangerouslySetInnerHTML", path, include="*.tsx")
        if result.strip():
            for line in result.strip().split("\n")[:3]:
                if line:
                    issues.append(f"XSS risk (dangerouslySetInnerHTML): {line[:100]}")

        return issues

    async def _check_a09_logging(self, path: Path) -> list[str]:
        """
        Check for A09: Security Logging and Monitoring Failures.

        Looks for bare except blocks without logging.
        """
        issues = []

        # Check for bare except without logging
        # This is a simplified heuristic - checks for "except:" not followed by logging
        result = await self._run_grep(r"except:", path, include="*.py")
        if result.strip():
            except_lines = result.strip().split("\n")

            # Check if logging is used in the project
            log_result = await self._run_grep(
                r"import logging\|from logging\|logger\.", path, include="*.py"
            )
            has_logging = bool(log_result.strip())

            if not has_logging and len(except_lines) > 3:
                issues.append(
                    f"Multiple except blocks ({len(except_lines)}) without logging setup"
                )

        return issues

    async def _run_grep(self, pattern: str, path: Path, include: str = "*") -> str:
        """
        Run grep with pattern on path.

        Args:
            pattern: Grep pattern to search
            path: Directory to search
            include: File pattern to include (e.g., "*.py")

        Returns:
            Grep output (empty string if no matches)
        """
        try:
            result = await self._run_tool(
                [
                    "grep",
                    "-r",
                    "-n",
                    "--include",
                    include,
                    pattern,
                    str(path),
                ],
                timeout=30,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        except Exception:
            return ""
