"""
Tests for TDDValidator.

Tests TDD compliance checking with file system operations.
"""

import pytest

from ..tdd_validator import TDDValidator
from ..base import ValidationTier


class TestTDDValidatorBasics:
    """Test TDDValidator class attributes."""

    def test_dimension(self):
        """TDDValidator has correct dimension."""
        assert TDDValidator.dimension == "tdd_compliance"

    def test_tier_is_warning(self):
        """TDDValidator is Tier 2 (WARNING)."""
        assert TDDValidator.tier == ValidationTier.WARNING

    def test_agent_name(self):
        """TDDValidator links to tdd-guide agent."""
        assert TDDValidator.agent == "tdd-guide"

    def test_default_threshold(self):
        """TDDValidator has 80% default threshold."""
        assert TDDValidator.coverage_threshold == 0.8


class TestTDDValidatorSkip:
    """Test TDDValidator skip conditions."""

    @pytest.mark.asyncio
    async def test_skip_no_source_files(self, tmp_path):
        """Skip when no source files found."""
        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert (
            "skipped" in result.message.lower() or "no source" in result.message.lower()
        )


class TestTDDValidatorPass:
    """Test TDDValidator passing scenarios."""

    @pytest.mark.asyncio
    async def test_all_files_have_tests(self, tmp_path):
        """Pass when all source files have tests."""
        # Create source files
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "validator.py").write_text("class Validator: pass")
        (src_dir / "runner.py").write_text("class Runner: pass")

        # Create corresponding test files
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_validator.py").write_text("def test_validator(): pass")
        (tests_dir / "test_runner.py").write_text("def test_runner(): pass")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details["coverage_ratio"] == 1.0
        assert result.details["files_without_tests"] == 0
        assert result.details["missing_tests"] == []

    @pytest.mark.asyncio
    async def test_pass_above_threshold(self, tmp_path):
        """Pass when coverage >= 80% threshold."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create 5 source files
        for i in range(5):
            (src_dir / f"module{i}.py").write_text(f"# Module {i}")

        # Create tests for 4 of them (80%)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        for i in range(4):
            (tests_dir / f"test_module{i}.py").write_text(f"def test_{i}(): pass")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is True
        assert result.details["coverage_ratio"] == 0.8

    @pytest.mark.asyncio
    async def test_custom_threshold(self, tmp_path):
        """Pass with custom threshold."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create 2 source files
        (src_dir / "a.py").write_text("")
        (src_dir / "b.py").write_text("")

        # Create test for 1 (50%)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_a.py").write_text("")

        # 50% coverage with 50% threshold should pass
        validator = TDDValidator(project_path=tmp_path, coverage_threshold=0.5)
        result = await validator.validate()

        assert result.passed is True


class TestTDDValidatorFail:
    """Test TDDValidator failing scenarios."""

    @pytest.mark.asyncio
    async def test_fail_below_threshold(self, tmp_path):
        """Fail when coverage < 80% threshold."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create 5 source files
        for i in range(5):
            (src_dir / f"module{i}.py").write_text(f"# Module {i}")

        # Create tests for only 2 (40%)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        for i in range(2):
            (tests_dir / f"test_module{i}.py").write_text(f"def test_{i}(): pass")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is False
        assert result.details["coverage_ratio"] == 0.4
        assert result.details["files_without_tests"] == 3
        assert len(result.details["missing_tests"]) == 3
        assert result.fix_suggestion is not None
        assert result.agent == "tdd-guide"

    @pytest.mark.asyncio
    async def test_no_tests(self, tmp_path):
        """Fail when no test files exist."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("# App code")
        (src_dir / "utils.py").write_text("# Utils code")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.passed is False
        assert result.details["coverage_ratio"] == 0.0


class TestTDDValidatorFiltering:
    """Test source file filtering logic."""

    @pytest.mark.asyncio
    async def test_excludes_test_files(self, tmp_path):
        """Exclude test files from source count."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("")
        (src_dir / "test_app.py").write_text("")  # Should be excluded

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.details["source_files"] == 1

    @pytest.mark.asyncio
    async def test_excludes_init_files(self, tmp_path):
        """Exclude __init__.py from source count."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "__init__.py").write_text("")  # Should be excluded
        (src_dir / "app.py").write_text("")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.details["source_files"] == 1

    @pytest.mark.asyncio
    async def test_matches_test_by_name(self, tmp_path):
        """Match test files by source name appearing in test name."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "auth_handler.py").write_text("")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # test file contains source name
        (tests_dir / "test_auth_handler_login.py").write_text("")

        validator = TDDValidator(project_path=tmp_path)
        result = await validator.validate()

        assert result.details["coverage_ratio"] == 1.0
