"""
TDD Validator - Test-Driven Development compliance checking.

Checks that source files have corresponding test files.
Based on ECC tdd-guide agent patterns.

Source: /media/sam/1TB/everything-claude-code/agents/tdd-guide.md
"""

from datetime import datetime
from pathlib import Path

from .base import ECCValidatorBase, ValidationResult, ValidationTier

__all__ = ["TDDValidator"]


class TDDValidator(ECCValidatorBase):
    """
    TDD compliance validator.

    Checks that source files have corresponding test files.
    Calculates coverage ratio (test_files / source_files) and
    passes if ratio >= threshold (default 80%).

    Tier: WARNING (Tier 2) - Missing tests are warnings, not blockers
    Agent: tdd-guide
    """

    dimension = "tdd_compliance"
    tier = ValidationTier.WARNING
    agent = "tdd-guide"
    timeout = 60  # File scanning is fast

    # Default threshold for test coverage ratio
    coverage_threshold: float = 0.8  # 80% of source files should have tests

    def __init__(
        self,
        project_path: str | Path = ".",
        coverage_threshold: float | None = None,
    ):
        """
        Initialize TDDValidator.

        Args:
            project_path: Path to project root
            coverage_threshold: Override default 80% threshold
        """
        self.project_path = Path(project_path)
        if coverage_threshold is not None:
            self.coverage_threshold = coverage_threshold

    async def validate(self) -> ValidationResult:
        """
        Check TDD compliance by comparing source and test files.

        Returns:
            ValidationResult with:
            - passed: True if coverage_ratio >= threshold
            - message: Summary with coverage percentage
            - details: Dict with source files, test files, missing tests
            - fix_suggestion: List of files that need tests
        """
        start = datetime.now()

        source_files = self._find_source_files()
        if not source_files:
            return self._skip_result("No source files found")

        test_files = self._find_test_files()
        files_with_tests = [
            str(f) for f in source_files if self._has_test_file(f, test_files)
        ]
        files_without_tests = [
            str(f) for f in source_files if not self._has_test_file(f, test_files)
        ]

        total = len(source_files)
        covered = len(files_with_tests)
        coverage_ratio = covered / total if total > 0 else 0
        is_passed = coverage_ratio >= self.coverage_threshold

        fix_suggestion = None
        if not is_passed and files_without_tests:
            shown = files_without_tests[:5]
            fix_suggestion = f"Add tests for: {', '.join(shown)}"
            if len(files_without_tests) > 5:
                fix_suggestion += "..."

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=is_passed,
            message=f"TDD: {covered}/{total} files ({coverage_ratio:.0%}) have tests",
            details={
                "source_files": total,
                "files_with_tests": covered,
                "files_without_tests": len(files_without_tests),
                "coverage_ratio": round(coverage_ratio, 2),
                "threshold": self.coverage_threshold,
                "missing_tests": files_without_tests[:10],
            },
            fix_suggestion=fix_suggestion,
            agent=self.agent if not is_passed else None,
            duration_ms=self._format_duration(start),
        )

    def _find_source_files(self) -> list[Path]:
        """
        Find source files in the project.

        Looks for Python files in src/, lib/, or root,
        excluding test files, __pycache__, and hidden dirs.
        """
        src_dirs = [
            self.project_path / "src",
            self.project_path / "lib",
            self.project_path,
        ]

        for src_dir in src_dirs:
            if not src_dir.exists():
                continue

            source_files = [
                py_file
                for py_file in src_dir.rglob("*.py")
                if self._is_source_file(py_file)
            ]

            if source_files:
                return source_files

        return []

    def _is_source_file(self, py_file: Path) -> bool:
        """Check if file is a valid source file to test."""
        if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
            return False
        if py_file.name in ("__init__.py", "conftest.py"):
            return False
        if "tests" in py_file.parts or "__pycache__" in py_file.parts:
            return False
        if any(p.startswith(".") for p in py_file.parts):
            return False
        return True

    def _find_test_files(self) -> list[Path]:
        """
        Find test files in the project.

        Looks for test_*.py and *_test.py patterns.
        """
        test_dirs = [
            self.project_path / "tests",
            self.project_path / "test",
            self.project_path / "src" / "tests",
            self.project_path,
        ]

        test_files = set()
        for test_dir in test_dirs:
            if not test_dir.exists():
                continue

            for pattern in ("test_*.py", "*_test.py"):
                for py_file in test_dir.rglob(pattern):
                    if "__pycache__" not in py_file.parts:
                        test_files.add(py_file)

        return list(test_files)

    def _has_test_file(self, source_file: Path, test_files: list[Path]) -> bool:
        """
        Check if a source file has a corresponding test file.

        Checks for:
        - test_{source_name}.py
        - {source_name}_test.py
        - test_{source_name} in any test file path
        """
        source_name = source_file.stem
        expected_patterns = {f"test_{source_name}.py", f"{source_name}_test.py"}

        return any(
            test_file.name in expected_patterns or source_name in test_file.name
            for test_file in test_files
        )
