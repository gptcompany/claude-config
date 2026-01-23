#!/usr/bin/env python3
"""Unit tests for validators."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Import path setup
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestOSSReuseValidator:
    """Tests for OSSReuseValidator."""

    def test_import(self):
        """Test validator can be imported."""
        from validators.oss_reuse.validator import OSSReuseValidator, PatternMatch

        assert OSSReuseValidator is not None
        assert PatternMatch is not None

    def test_default_config(self):
        """Test default configuration."""
        from validators.oss_reuse.validator import OSSReuseValidator, ValidationTier

        validator = OSSReuseValidator()
        assert validator.min_confidence == "medium"
        assert validator.dimension == "oss_reuse"
        assert validator.tier == ValidationTier.WARNING

    def test_custom_config(self):
        """Test custom configuration."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator({"min_confidence": "high"})
        assert validator.min_confidence == "high"

    def test_confidence_order(self):
        """Test confidence ordering."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        assert validator.CONFIDENCE_ORDER["high"] > validator.CONFIDENCE_ORDER["medium"]
        assert validator.CONFIDENCE_ORDER["medium"] > validator.CONFIDENCE_ORDER["low"]

    def test_scan_file_no_matches(self):
        """Test scanning file with no pattern matches."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
# Clean Python file
def hello():
    return "Hello, world!"
"""
        matches = validator._scan_file(Path("test.py"), content)
        assert len(matches) == 0

    def test_scan_file_detects_urllib(self):
        """Test scanning detects urllib.request pattern."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import urllib.request
response = urllib.request.urlopen("http://example.com")
"""
        matches = validator._scan_file(Path("test.py"), content)
        assert len(matches) > 0
        assert any(m.pattern_name == "http_client" for m in matches)

    def test_scan_file_detects_os_system(self):
        """Test scanning detects os.system (shell injection risk)."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import os
os.system("ls -la")
"""
        matches = validator._scan_file(Path("test.py"), content)
        assert len(matches) > 0
        assert any(m.pattern_name == "subprocess_shell" for m in matches)

    def test_scan_file_detects_yaml_load(self):
        """Test scanning detects unsafe yaml.load."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import yaml
data = yaml.load(file_content)
"""
        matches = validator._scan_file(Path("test.py"), content)
        assert len(matches) > 0
        assert any(m.pattern_name == "yaml_unsafe" for m in matches)

    def test_already_using_suggestion_true(self):
        """Test _already_using_suggestion returns True when package imported."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import requests
response = requests.get("http://example.com")
"""
        assert validator._already_using_suggestion(content, "requests") is True

    def test_already_using_suggestion_false(self):
        """Test _already_using_suggestion returns False when not imported."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import urllib.request
response = urllib.request.urlopen("http://example.com")
"""
        assert validator._already_using_suggestion(content, "requests") is False

    def test_already_using_suggestion_or_syntax(self):
        """Test _already_using_suggestion handles 'X or Y' syntax."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        content = """
import httpx
client = httpx.Client()
"""
        assert validator._already_using_suggestion(content, "requests or httpx") is True

    def test_match_to_dict(self):
        """Test _match_to_dict converts PatternMatch to dict."""
        from validators.oss_reuse.validator import OSSReuseValidator, PatternMatch

        validator = OSSReuseValidator()
        match = PatternMatch(
            pattern_name="test_pattern",
            file_path="test.py",
            line_number=10,
            match_text="test match",
            suggestion="use X",
            reason="because",
            confidence="high",
        )
        d = validator._match_to_dict(match)
        assert d["pattern_name"] == "test_pattern"
        assert d["file_path"] == "test.py"
        assert d["line_number"] == 10
        assert d["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_validate_empty_dir(self):
        """Test validate in empty directory."""
        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator()
        with tempfile.TemporaryDirectory():
            with patch("validators.oss_reuse.validator.Path") as mock_path:
                mock_path.return_value.rglob.return_value = []
                result = await validator.validate()

        assert result.passed is True
        assert result.dimension == "oss_reuse"

    @pytest.mark.asyncio
    async def test_validate_with_matches(self):
        """Test validate finds patterns in files."""
        import os as os_module

        from validators.oss_reuse.validator import OSSReuseValidator

        validator = OSSReuseValidator({"min_confidence": "high"})

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with pattern (os.system is high confidence)
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
import os
os.system("ls -la")
""")
            # Change to temp dir for scan
            old_cwd = os_module.getcwd()
            try:
                os_module.chdir(tmpdir)
                result = await validator.validate()
            finally:
                os_module.chdir(old_cwd)

        assert result.passed is False
        assert "subprocess_shell" in str(result.details.get("suggestions", []))


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""

    def test_creation(self):
        """Test PatternMatch creation."""
        from validators.oss_reuse.validator import PatternMatch

        match = PatternMatch(
            pattern_name="test",
            file_path="test.py",
            line_number=1,
            match_text="test",
            suggestion="use X",
            reason="better",
            confidence="high",
        )
        assert match.pattern_name == "test"
        assert match.confidence == "high"


class TestOSSPatterns:
    """Tests for OSS_PATTERNS dictionary."""

    def test_patterns_exist(self):
        """Test OSS_PATTERNS has expected entries."""
        from validators.oss_reuse.patterns import OSS_PATTERNS

        assert "http_client" in OSS_PATTERNS
        assert "yaml_unsafe" in OSS_PATTERNS
        assert "subprocess_shell" in OSS_PATTERNS

    def test_pattern_structure(self):
        """Test each pattern has required fields."""
        from validators.oss_reuse.patterns import OSS_PATTERNS

        for name, config in OSS_PATTERNS.items():
            assert "patterns" in config, f"{name} missing patterns"
            assert "suggestion" in config, f"{name} missing suggestion"
            assert "reason" in config, f"{name} missing reason"
            assert "confidence" in config, f"{name} missing confidence"
            assert isinstance(config["patterns"], list), f"{name} patterns not list"


class TestDesignPrinciplesValidator:
    """Tests for DesignPrinciplesValidator."""

    def test_import(self):
        """Test validator can be imported."""
        from validators.design_principles.validator import DesignPrinciplesValidator

        assert DesignPrinciplesValidator is not None

    def test_default_config(self):
        """Test default configuration."""
        from validators.design_principles.validator import (
            DesignPrinciplesValidator,
            ValidationTier,
        )

        validator = DesignPrinciplesValidator()
        assert validator.dimension == "design_principles"
        assert validator.tier == ValidationTier.WARNING

    def test_custom_thresholds(self):
        """Test custom complexity thresholds."""
        from validators.design_principles.validator import DesignPrinciplesValidator

        config = {
            "design_principles": {
                "max_complexity": 20,
                "max_nesting": 6,
            }
        }
        validator = DesignPrinciplesValidator(config)
        assert validator.thresholds["max_complexity"] == 20
        assert validator.thresholds["max_nesting"] == 6


class TestMathematicalValidator:
    """Tests for MathematicalValidator."""

    def test_import(self):
        """Test validator can be imported."""
        from validators.mathematical.validator import MathematicalValidator

        assert MathematicalValidator is not None

    def test_cas_client_import(self):
        """Test CAS client can be imported."""
        from validators.mathematical.cas_client import CASClient

        assert CASClient is not None

    def test_formula_extractor_import(self):
        """Test formula extractor can be imported."""
        from validators.mathematical.formula_extractor import FormulaExtractor

        assert FormulaExtractor is not None


class TestAPIContractValidator:
    """Tests for APIContractValidator."""

    def test_import(self):
        """Test validator can be imported."""
        from validators.api_contract.validator import APIContractValidator

        assert APIContractValidator is not None

    def test_oasdiff_runner_import(self):
        """Test OASDiff runner can be imported."""
        from validators.api_contract.oasdiff_runner import OasdiffRunner

        assert OasdiffRunner is not None

    def test_spec_discovery_import(self):
        """Test spec discovery can be imported."""
        from validators.api_contract.spec_discovery import SpecDiscovery

        assert SpecDiscovery is not None


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation(self):
        """Test ValidationResult creation."""
        from validators.oss_reuse.validator import ValidationResult, ValidationTier

        result = ValidationResult(
            dimension="test",
            tier=ValidationTier.WARNING,
            passed=True,
            message="OK",
        )
        assert result.dimension == "test"
        assert result.passed is True

    def test_defaults(self):
        """Test ValidationResult default values."""
        from validators.oss_reuse.validator import ValidationResult, ValidationTier

        result = ValidationResult(
            dimension="test",
            tier=ValidationTier.WARNING,
            passed=True,
            message="OK",
        )
        assert result.details == {}
        assert result.fix_suggestion is None
        assert result.agent is None
        assert result.duration_ms == 0


class TestBaseValidator:
    """Tests for BaseValidator class."""

    def test_defaults(self):
        """Test BaseValidator default values."""
        from validators.oss_reuse.validator import BaseValidator, ValidationTier

        validator = BaseValidator()
        assert validator.dimension == "unknown"
        assert validator.tier == ValidationTier.MONITOR
        assert validator.agent is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
