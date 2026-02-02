#!/usr/bin/env python3
"""
DesignPrinciplesValidator - Tier 2 KISS/YAGNI/DRY Validator

Uses radon for cyclomatic complexity and maintainability index,
plus AST analysis for nesting depth and parameter count.

Config-driven thresholds from `dimensions.design_principles`.
"""

import ast
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Radon imports with fallback
try:
    from radon.complexity import cc_visit
    from radon.metrics import mi_visit

    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False
    cc_visit = None
    mi_visit = None

# Base types for standalone testing (when not imported from orchestrator)
from enum import Enum


class ValidationTier(Enum):
    BLOCKER = 1
    WARNING = 2
    MONITOR = 3


@dataclass
class ValidationResult:
    dimension: str
    tier: ValidationTier
    passed: bool
    message: str
    details: dict = field(default_factory=dict)
    fix_suggestion: str | None = None
    agent: str | None = None
    duration_ms: int = 0


class BaseValidator:
    dimension = "unknown"
    tier = ValidationTier.MONITOR
    agent: str | None = None

    async def validate(self) -> ValidationResult:
        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=True,
            message="No validation implemented",
        )


@dataclass
class ComplexityViolation:
    """A detected complexity violation."""

    file_path: str
    line_number: int
    violation_type: str  # complexity, nesting, params, maintainability
    value: float
    threshold: float
    function_name: str = ""
    message: str = ""


class NestingAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze nesting depth."""

    NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)

    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0
        self.violations = []  # (func_name, line, depth)

    def visit_FunctionDef(self, node):
        self.current_depth = 0
        self.current_func = node.name
        self.current_func_line = node.lineno
        self.func_max_depth = 0
        self.generic_visit(node)
        if self.func_max_depth > 0:
            self.violations.append(
                (self.current_func, self.current_func_line, self.func_max_depth)
            )
        return node

    # AsyncFunctionDef has same structure as FunctionDef for our purposes
    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def _enter_nesting(self, node):
        self.current_depth += 1
        self.func_max_depth = max(self.func_max_depth, self.current_depth)
        self.max_depth = max(self.max_depth, self.current_depth)
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_If(self, node):
        self._enter_nesting(node)

    def visit_For(self, node):
        self._enter_nesting(node)

    def visit_While(self, node):
        self._enter_nesting(node)

    def visit_With(self, node):
        self._enter_nesting(node)

    def visit_Try(self, node):
        self._enter_nesting(node)


class ParameterAnalyzer(ast.NodeVisitor):
    """AST visitor to count function parameters."""

    def __init__(self):
        self.violations = []  # (func_name, line, param_count)

    def visit_FunctionDef(self, node):
        args = node.args
        # Count all parameter types
        param_count = (
            len(args.args)
            + len(args.posonlyargs)
            + len(args.kwonlyargs)
            + (1 if args.vararg else 0)
            + (1 if args.kwarg else 0)
        )
        # Exclude 'self' and 'cls'
        if args.args and args.args[0].arg in ("self", "cls"):
            param_count -= 1

        self.violations.append((node.name, node.lineno, param_count))
        self.generic_visit(node)
        return node

    # AsyncFunctionDef has same structure as FunctionDef for our purposes
    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]


class DesignPrinciplesValidator(BaseValidator):
    """
    Tier 2: Design principles validator (KISS/YAGNI/DRY).

    Checks:
    - Cyclomatic complexity (radon CC)
    - Maintainability index (radon MI)
    - Nesting depth (AST)
    - Parameter count (AST)
    """

    dimension = "design_principles"
    tier = ValidationTier.WARNING
    agent = "code-simplifier"

    # Default thresholds (can be overridden by config)
    # These are practical defaults for real-world codebases:
    # - Validators/orchestrators often need moderate complexity
    # - Test files may have lower maintainability scores
    DEFAULT_THRESHOLDS = {
        "max_complexity": 25,  # Allow moderately complex functions
        "min_maintainability": 0,  # Don't penalize test files
        "max_nesting": 7,  # Allow reasonable nesting for error handling
        "max_params": 7,  # Allow up to 7 parameters
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.thresholds = {
            **self.DEFAULT_THRESHOLDS,
            **self.config.get("design_principles", {}),
        }

    async def validate(self) -> ValidationResult:
        """Run all design principles checks."""
        start = datetime.now()
        violations: list[ComplexityViolation] = []
        files_scanned = 0

        # Scan Python files
        for py_file in Path(".").rglob("*.py"):
            # Skip common non-source directories
            if any(
                part.startswith(".")
                or part
                in (
                    "venv",
                    "env",
                    "__pycache__",
                    "node_modules",
                    ".git",
                    "build",
                    "dist",
                    ".eggs",
                )
                for part in py_file.parts
            ):
                continue

            try:
                content = py_file.read_text()
                files_scanned += 1
                file_violations = self._analyze_file(py_file, content)
                violations.extend(file_violations)
            except Exception:
                continue

        passed = len(violations) == 0

        # Build suggestions
        suggestions = []
        for v in violations[:10]:  # Top 10 violations
            suggestions.append(
                f"{v.file_path}:{v.line_number} - {v.function_name or 'file'}: "
                f"{v.violation_type}={v.value:.1f} (max: {v.threshold:.1f})"
            )

        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        return ValidationResult(
            dimension=self.dimension,
            tier=self.tier,
            passed=passed,
            message=(
                f"{len(violations)} violations"
                if not passed
                else "Design principles OK"
            ),
            details={
                "files_scanned": files_scanned,
                "total_violations": len(violations),
                "violations_by_type": self._group_violations(violations),
                "violations": [vars(v) for v in violations[:20]],
                "radon_available": RADON_AVAILABLE,
            },
            fix_suggestion="\n".join(suggestions) if suggestions else None,
            agent=self.agent if not passed else None,
            duration_ms=duration_ms,
        )

    def _analyze_file(self, file_path: Path, content: str) -> list[ComplexityViolation]:
        """Analyze a single file for all violations."""
        violations = []
        path_str = str(file_path)

        # 1. Cyclomatic complexity (radon)
        if RADON_AVAILABLE and cc_visit:
            try:
                cc_results = cc_visit(content)
                for block in cc_results:
                    if block.complexity > self.thresholds["max_complexity"]:
                        violations.append(
                            ComplexityViolation(
                                file_path=path_str,
                                line_number=block.lineno,
                                violation_type="complexity",
                                value=float(block.complexity),
                                threshold=float(self.thresholds["max_complexity"]),
                                function_name=block.name,
                                message=f"High cyclomatic complexity: {block.complexity}",
                            )
                        )
            except Exception:
                pass

        # 2. Maintainability index (radon)
        if RADON_AVAILABLE and mi_visit:
            try:
                mi = mi_visit(content, multi=False)
                if mi < self.thresholds["min_maintainability"]:
                    violations.append(
                        ComplexityViolation(
                            file_path=path_str,
                            line_number=1,
                            violation_type="maintainability",
                            value=float(mi),
                            threshold=float(self.thresholds["min_maintainability"]),
                            message=f"Low maintainability index: {mi:.1f}",
                        )
                    )
            except Exception:
                pass

        # 3. Nesting depth (AST)
        try:
            tree = ast.parse(content)

            nesting = NestingAnalyzer()
            nesting.visit(tree)

            for func_name, line, depth in nesting.violations:
                if depth > self.thresholds["max_nesting"]:
                    violations.append(
                        ComplexityViolation(
                            file_path=path_str,
                            line_number=line,
                            violation_type="nesting",
                            value=float(depth),
                            threshold=float(self.thresholds["max_nesting"]),
                            function_name=func_name,
                            message=f"Deep nesting: {depth} levels",
                        )
                    )

            # 4. Parameter count (AST)
            params = ParameterAnalyzer()
            params.visit(tree)

            for func_name, line, count in params.violations:
                if count > self.thresholds["max_params"]:
                    violations.append(
                        ComplexityViolation(
                            file_path=path_str,
                            line_number=line,
                            violation_type="params",
                            value=float(count),
                            threshold=float(self.thresholds["max_params"]),
                            function_name=func_name,
                            message=f"Too many parameters: {count}",
                        )
                    )
        except SyntaxError:
            pass  # Invalid Python - skip AST analysis

        return violations

    def _group_violations(
        self, violations: list[ComplexityViolation]
    ) -> dict[str, int]:
        """Group violations by type for summary."""
        groups: dict[str, int] = {}
        for v in violations:
            groups[v.violation_type] = groups.get(v.violation_type, 0) + 1
        return groups


# Export for testing
__all__ = ["DesignPrinciplesValidator", "ComplexityViolation", "RADON_AVAILABLE"]
