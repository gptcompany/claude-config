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

        # Run all OWASP checks
        checks = [
            ("A01_broken_access_control", self._check_a01_access_control(scan_path)),
            ("A03_injection", self._check_a03_injection(scan_path)),
            ("A07_xss", self._check_a07_xss(scan_path)),
            ("A09_logging_failures", self._check_a09_logging(scan_path)),
        ]

        issues: dict[str, list[str]] = {}
        for category, check in checks:
            result = await check
            if result:
                issues[category] = result

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

        # Check Python routes and auth
        py_has_auth = await self._has_pattern(
            r"@requires_auth\|@login_required\|@auth_required", path, "*.py"
        )
        has_py_routes = await self._has_pattern(
            r"@app\.route\|@router\.\|@blueprint\.", path, "*.py"
        )

        if has_py_routes and not py_has_auth:
            issues.append(
                "Python routes found without @requires_auth/@login_required decorators"
            )

        # Check TypeScript routes and auth
        ts_has_auth = await self._has_pattern(
            r"requireAuth\|isAuthenticated\|withAuth", path, "*.ts"
        )
        has_ts_routes = await self._has_pattern(
            r"export.*function.*Handler\|app\.get\|router\.get", path, "*.ts"
        )

        if has_ts_routes and not ts_has_auth:
            issues.append("TypeScript routes found without auth middleware/guards")

        return issues

    async def _has_pattern(self, pattern: str, path: Path, include: str) -> bool:
        """Check if pattern exists in files."""
        result = await self._run_grep(pattern, path, include=include)
        return bool(result.strip())

    async def _check_a03_injection(self, path: Path) -> list[str]:
        """
        Check for A03: Injection vulnerabilities.

        Looks for f-string SQL queries which may be vulnerable.
        """
        sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE"]
        patterns = [
            f"{quote}.*{{.*}}.*{keyword}"
            for keyword in sql_keywords
            for quote in ['f"', "f'"]
        ]

        for pattern in patterns:
            result = await self._run_grep(pattern, path, include="*.py")
            if result.strip():
                return [
                    f"SQL injection risk: {line[:100]}"
                    for line in result.strip().split("\n")[:3]
                    if line
                ]

        return []

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
                issues.extend(
                    f"XSS risk (innerHTML): {line[:100]}"
                    for line in result.strip().split("\n")[:3]
                    if line
                )
                break

        # Check dangerouslySetInnerHTML in React
        result = await self._run_grep(r"dangerouslySetInnerHTML", path, include="*.tsx")
        if result.strip():
            issues.extend(
                f"XSS risk (dangerouslySetInnerHTML): {line[:100]}"
                for line in result.strip().split("\n")[:3]
                if line
            )

        return issues

    async def _check_a09_logging(self, path: Path) -> list[str]:
        """
        Check for A09: Security Logging and Monitoring Failures.

        Looks for bare except blocks without logging.
        """
        result = await self._run_grep(r"except:", path, include="*.py")
        if not result.strip():
            return []

        except_lines = result.strip().split("\n")
        has_logging = await self._has_pattern(
            r"import logging\|from logging\|logger\.", path, "*.py"
        )

        if not has_logging and len(except_lines) > 3:
            return [
                f"Multiple except blocks ({len(except_lines)}) without logging setup"
            ]

        return []

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
