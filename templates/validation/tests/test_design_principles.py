#!/usr/bin/env python3
"""Unit tests for design_principles validator."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from validators.design_principles.validator import (
    RADON_AVAILABLE,
    ComplexityViolation,
    DesignPrinciplesValidator,
    NestingAnalyzer,
    ParameterAnalyzer,
)


class TestComplexityViolation:
    """Tests for ComplexityViolation dataclass."""

    def test_creation(self):
        """Test ComplexityViolation creation."""
        violation = ComplexityViolation(
            file_path="test.py",
            line_number=10,
            violation_type="complexity",
            value=15.0,
            threshold=10.0,
            function_name="complex_func",
            message="High complexity",
        )
        assert violation.file_path == "test.py"
        assert violation.line_number == 10
        assert violation.violation_type == "complexity"
        assert violation.value == 15.0
        assert violation.threshold == 10.0
        assert violation.function_name == "complex_func"

    def test_defaults(self):
        """Test ComplexityViolation defaults."""
        violation = ComplexityViolation(
            file_path="test.py",
            line_number=1,
            violation_type="test",
            value=1.0,
            threshold=0.5,
        )
        assert violation.function_name == ""
        assert violation.message == ""


class TestNestingAnalyzer:
    """Tests for NestingAnalyzer class."""

    def test_no_nesting(self):
        """Test code with no nesting."""
        import ast

        code = """
def simple():
    return 1
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 0

    def test_if_nesting(self):
        """Test if statement nesting."""
        import ast

        code = """
def nested():
    if True:
        if True:
            if True:
                return 1
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 3

    def test_loop_nesting(self):
        """Test loop nesting."""
        import ast

        code = """
def loops():
    for i in range(10):
        for j in range(10):
            pass
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 2

    def test_with_nesting(self):
        """Test with statement nesting."""
        import ast

        code = """
def with_blocks():
    with open('a') as f:
        with open('b') as g:
            pass
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 2

    def test_try_nesting(self):
        """Test try/except nesting."""
        import ast

        code = """
def error_handling():
    try:
        try:
            pass
        except:
            pass
    except:
        pass
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth >= 2

    def test_while_nesting(self):
        """Test while loop nesting."""
        import ast

        code = """
def while_loops():
    while True:
        while False:
            break
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 2

    def test_async_function(self):
        """Test async function nesting."""
        import ast

        code = """
async def async_nested():
    if True:
        if True:
            return 1
"""
        tree = ast.parse(code)
        analyzer = NestingAnalyzer()
        analyzer.visit(tree)
        assert analyzer.max_depth == 2


class TestParameterAnalyzer:
    """Tests for ParameterAnalyzer class."""

    def test_no_params(self):
        """Test function with no parameters."""
        import ast

        code = """
def no_params():
    pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert len(analyzer.violations) == 1
        assert analyzer.violations[0][2] == 0  # param count

    def test_regular_params(self):
        """Test function with regular parameters."""
        import ast

        code = """
def with_params(a, b, c):
    pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert analyzer.violations[0][2] == 3

    def test_self_excluded(self):
        """Test that self is excluded from count."""
        import ast

        code = """
class Test:
    def method(self, a, b):
        pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        # Should be 2 (a, b) not 3 (self, a, b)
        assert analyzer.violations[0][2] == 2

    def test_cls_excluded(self):
        """Test that cls is excluded from count."""
        import ast

        code = """
class Test:
    @classmethod
    def class_method(cls, a):
        pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert analyzer.violations[0][2] == 1

    def test_args_kwargs(self):
        """Test *args and **kwargs."""
        import ast

        code = """
def variadic(a, *args, **kwargs):
    pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert analyzer.violations[0][2] == 3  # a, args, kwargs

    def test_kwonly_params(self):
        """Test keyword-only parameters."""
        import ast

        code = """
def kwonly(a, *, b, c):
    pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert analyzer.violations[0][2] == 3  # a, b, c

    def test_async_function(self):
        """Test async function parameters."""
        import ast

        code = """
async def async_func(a, b):
    pass
"""
        tree = ast.parse(code)
        analyzer = ParameterAnalyzer()
        analyzer.visit(tree)
        assert analyzer.violations[0][2] == 2


class TestDesignPrinciplesValidator:
    """Tests for DesignPrinciplesValidator class."""

    def test_init_defaults(self):
        """Test default initialization."""
        validator = DesignPrinciplesValidator()
        # Practical defaults for real-world codebases
        assert validator.thresholds["max_complexity"] == 25
        assert validator.thresholds["min_maintainability"] == 0
        assert validator.thresholds["max_nesting"] == 7
        assert validator.thresholds["max_params"] == 7

    def test_init_custom_thresholds(self):
        """Test custom thresholds from config."""
        config = {
            "design_principles": {
                "max_complexity": 15,
                "max_nesting": 6,
            }
        }
        validator = DesignPrinciplesValidator(config)
        assert validator.thresholds["max_complexity"] == 15
        assert validator.thresholds["max_nesting"] == 6

    def test_attributes(self):
        """Test validator attributes."""
        validator = DesignPrinciplesValidator()
        assert validator.dimension == "design_principles"
        assert validator.agent == "code-simplifier"

    @pytest.mark.asyncio
    async def test_validate_empty_dir(self):
        """Test validation in empty directory."""
        validator = DesignPrinciplesValidator()
        with tempfile.TemporaryDirectory():
            with patch.object(Path, "rglob", return_value=[]):
                result = await validator.validate()
        assert result.passed is True
        assert "OK" in result.message

    @pytest.mark.asyncio
    async def test_validate_clean_code(self):
        """Test validation with clean code."""
        validator = DesignPrinciplesValidator()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple clean Python file
            test_file = Path(tmpdir) / "clean.py"
            test_file.write_text("""
def simple_function(a, b):
    if a:
        return b
    return a
""")
            # Mock Path(".").rglob to return our test file
            with patch("validators.design_principles.validator.Path") as mock_path:
                mock_path.return_value.rglob.return_value = [test_file]
                result = await validator.validate()

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_validate_deep_nesting(self):
        """Test validation detects deep nesting."""
        validator = DesignPrinciplesValidator({"design_principles": {"max_nesting": 2}})
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "nested.py"
            test_file.write_text("""
def deeply_nested():
    if True:
        if True:
            if True:
                if True:
                    return 1
""")
            with patch("validators.design_principles.validator.Path") as mock_path:
                mock_path.return_value.rglob.return_value = [test_file]
                result = await validator.validate()

        assert result.passed is False
        assert "violations" in result.message

    @pytest.mark.asyncio
    async def test_validate_too_many_params(self):
        """Test validation detects too many parameters."""
        validator = DesignPrinciplesValidator({"design_principles": {"max_params": 3}})
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "params.py"
            test_file.write_text("""
def too_many_params(a, b, c, d, e, f, g):
    pass
""")
            with patch("validators.design_principles.validator.Path") as mock_path:
                mock_path.return_value.rglob.return_value = [test_file]
                result = await validator.validate()

        assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_skips_venv(self):
        """Test validation skips venv directory."""
        validator = DesignPrinciplesValidator()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file in venv (should be skipped)
            venv = Path(tmpdir) / "venv"
            venv.mkdir()
            test_file = venv / "bad.py"
            test_file.write_text("def bad(a,b,c,d,e,f,g,h): pass")

            with patch("validators.design_principles.validator.Path") as mock_path:
                # Return the venv file
                mock_path.return_value.rglob.return_value = [test_file]
                result = await validator.validate()

        # Should pass because venv is skipped
        assert result.passed is True

    def test_analyze_file_syntax_error(self):
        """Test _analyze_file handles syntax errors."""
        validator = DesignPrinciplesValidator()
        violations = validator._analyze_file(Path("bad.py"), "def broken(")
        # Should return empty list (syntax error handled)
        assert violations == []

    def test_group_violations(self):
        """Test _group_violations groups by type."""
        validator = DesignPrinciplesValidator()
        violations = [
            ComplexityViolation("a.py", 1, "complexity", 15, 10),
            ComplexityViolation("b.py", 1, "complexity", 12, 10),
            ComplexityViolation("c.py", 1, "nesting", 5, 4),
        ]
        groups = validator._group_violations(violations)
        assert groups["complexity"] == 2
        assert groups["nesting"] == 1

    @pytest.mark.skipif(not RADON_AVAILABLE, reason="radon not installed")
    def test_analyze_file_with_radon(self):
        """Test _analyze_file uses radon when available."""
        # Use lower threshold to trigger violations
        validator = DesignPrinciplesValidator(
            {"design_principles": {"max_complexity": 3}}
        )
        # Complex function that should trigger CC violation
        code = """
def complex_function(a, b, c, d, e):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return 1
                    else:
                        return 2
                else:
                    return 3
            else:
                return 4
        else:
            return 5
    else:
        return 6
"""
        violations = validator._analyze_file(Path("test.py"), code)
        # Should have violations - either complexity or nesting
        assert len(violations) > 0


class TestRadonAvailability:
    """Tests for RADON_AVAILABLE flag."""

    def test_radon_available_is_bool(self):
        """Test RADON_AVAILABLE is a boolean."""
        assert isinstance(RADON_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
