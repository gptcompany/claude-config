#!/usr/bin/env python3
"""
Tests for BehavioralValidator - DOM Structure Similarity Validator

Tests cover:
- Identical DOM validation
- Different DOM validation
- Similarity threshold configuration
- Ignore attributes configuration
- Focus selectors configuration
- ValidationResult structure
- Operations in details
"""

import pytest

from validators.behavioral.validator import (
    BehavioralConfig,
    BehavioralValidator,
    ValidationResult,
    ValidationTier,
)


class TestBehavioralValidatorBasic:
    """Basic validation tests."""

    @pytest.mark.asyncio
    async def test_validate_identical_dom(self):
        """Identical HTML should return confidence = 1.0."""
        html = "<div><p>Hello World</p><span>Content</span></div>"
        validator = BehavioralValidator()
        result = await validator.validate(html, html)

        assert result.confidence == 1.0
        assert result.passed == True  # noqa: E712 - use == for numpy bool
        assert "100" in result.message  # 100.0% or 100%

    @pytest.mark.asyncio
    async def test_validate_different_dom(self):
        """Different HTML should return confidence < 1.0."""
        baseline = "<div><p>Hello</p></div>"
        current = "<div><span>Hello</span><p>World</p></div>"
        validator = BehavioralValidator()
        result = await validator.validate(baseline, current)

        assert result.confidence < 1.0
        assert result.details["edit_distance"] > 0

    @pytest.mark.asyncio
    async def test_validate_empty_baseline(self):
        """Empty baseline should return low confidence."""
        baseline = ""
        current = "<div><p>Content</p></div>"
        validator = BehavioralValidator()
        result = await validator.validate(baseline, current)

        assert result.confidence == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_empty_current(self):
        """Empty current should return low confidence."""
        baseline = "<div><p>Content</p></div>"
        current = ""
        validator = BehavioralValidator()
        result = await validator.validate(baseline, current)

        assert result.confidence == 0.0
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_validate_both_empty(self):
        """Both empty should be considered identical."""
        validator = BehavioralValidator()
        result = await validator.validate("", "")

        assert result.confidence == 1.0
        assert result.passed is True


class TestSimilarityThreshold:
    """Tests for similarity threshold configuration."""

    @pytest.mark.asyncio
    async def test_config_similarity_threshold_pass(self):
        """Should pass when similarity >= threshold."""
        # Create HTML that's similar but not identical
        baseline = "<div><p>Hello</p><p>World</p></div>"
        current = "<div><p>Hello</p><span>World</span></div>"

        # Use low threshold that should pass
        config = BehavioralConfig(similarity_threshold=0.5)
        validator = BehavioralValidator(config=config)
        result = await validator.validate(baseline, current)

        # With such low threshold, even different HTML should pass
        assert result.passed is True or result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_config_similarity_threshold_fail(self):
        """Should fail when similarity < threshold."""
        baseline = "<div><p>A</p></div>"
        current = "<main><article><section>B</section></article></main>"

        # Use very high threshold
        config = BehavioralConfig(similarity_threshold=0.99)
        validator = BehavioralValidator(config=config)
        result = await validator.validate(baseline, current)

        assert result.passed is False
        assert result.confidence < 0.99

    @pytest.mark.asyncio
    async def test_threshold_in_details(self):
        """Threshold should be included in details."""
        config = BehavioralConfig(similarity_threshold=0.85)
        validator = BehavioralValidator(config=config)
        result = await validator.validate("<div></div>", "<div></div>")

        assert result.details["threshold"] == 0.85


class TestIgnoreAttributes:
    """Tests for ignore_attributes configuration."""

    @pytest.mark.asyncio
    async def test_ignore_attributes_id_class(self):
        """Ignoring id and class should make different-attributed HTML identical."""
        baseline = '<div id="a" class="foo"><p>Content</p></div>'
        current = '<div id="b" class="bar"><p>Content</p></div>'

        config = BehavioralConfig(ignore_attributes=["id", "class"])
        validator = BehavioralValidator(config=config)
        result = await validator.validate(baseline, current)

        assert result.confidence == 1.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_ignore_attributes_style(self):
        """Ignoring style should make style-different HTML identical."""
        baseline = '<div style="color: red"><p>Text</p></div>'
        current = '<div style="color: blue; font-size: 12px"><p>Text</p></div>'

        config = BehavioralConfig(ignore_attributes=["style"])
        validator = BehavioralValidator(config=config)
        result = await validator.validate(baseline, current)

        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_respect_non_ignored_attributes(self):
        """Non-ignored attributes should be preserved in comparison.

        Note: The current ZSS implementation compares tags only, not attributes.
        This test verifies the configuration is passed correctly; attribute
        comparison would require a custom distance function in the future.
        """
        baseline = '<div data-testid="foo"><p>Text</p></div>'
        current = '<div data-testid="bar"><p>Text</p></div>'

        # Only ignore class, not data-testid
        config = BehavioralConfig(ignore_attributes=["class"])
        validator = BehavioralValidator(config=config)
        result = await validator.validate(baseline, current)

        # Verify configuration was applied
        assert result.details["ignore_attributes"] == ["class"]
        # Tags are the same, so structure matches (attributes not compared by zss)
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_ignore_attributes_in_details(self):
        """Ignored attributes should be listed in details."""
        config = BehavioralConfig(ignore_attributes=["id", "class", "style"])
        validator = BehavioralValidator(config=config)
        result = await validator.validate("<div></div>", "<div></div>")

        assert result.details["ignore_attributes"] == ["id", "class", "style"]


class TestFocusSelectors:
    """Tests for focus_selectors configuration."""

    @pytest.mark.asyncio
    async def test_focus_selectors_stored(self):
        """Focus selectors should be stored in config."""
        config = BehavioralConfig(focus_selectors=["main", "article", ".content"])
        validator = BehavioralValidator(config=config)

        assert validator.config.focus_selectors == ["main", "article", ".content"]

    @pytest.mark.asyncio
    async def test_focus_selectors_none_default(self):
        """Focus selectors should default to None."""
        validator = BehavioralValidator()

        assert validator.config.focus_selectors is None


class TestValidationResult:
    """Tests for ValidationResult structure."""

    @pytest.mark.asyncio
    async def test_returns_validation_result(self):
        """Should return ValidationResult instance."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert isinstance(result, ValidationResult)

    @pytest.mark.asyncio
    async def test_result_has_dimension(self):
        """Result should have correct dimension."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert result.dimension == "behavioral"

    @pytest.mark.asyncio
    async def test_result_has_tier(self):
        """Result should have correct tier (MONITOR)."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert result.tier == ValidationTier.MONITOR

    @pytest.mark.asyncio
    async def test_result_has_confidence(self):
        """Result should have confidence field."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert hasattr(result, "confidence")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_result_has_duration(self):
        """Result should have duration_ms."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert result.duration_ms >= 0


class TestOperationsInDetails:
    """Tests for operations list in details."""

    @pytest.mark.asyncio
    async def test_operations_in_details(self):
        """Operations should be stored in details."""
        baseline = "<div><p>A</p></div>"
        current = "<div><span>B</span></div>"

        validator = BehavioralValidator()
        result = await validator.validate(baseline, current)

        assert "operations" in result.details
        assert isinstance(result.details["operations"], list)
        assert len(result.details["operations"]) > 0

    @pytest.mark.asyncio
    async def test_edit_distance_in_details(self):
        """Edit distance should be in details."""
        validator = BehavioralValidator()
        result = await validator.validate(
            "<div><p>A</p></div>", "<div><span>B</span></div>"
        )

        assert "edit_distance" in result.details
        assert isinstance(result.details["edit_distance"], int)

    @pytest.mark.asyncio
    async def test_tree_sizes_in_details(self):
        """Tree sizes should be in details."""
        validator = BehavioralValidator()
        result = await validator.validate(
            "<div><p>A</p><p>B</p></div>", "<div><p>A</p></div>"
        )

        assert "tree1_size" in result.details
        assert "tree2_size" in result.details
        assert result.details["tree1_size"] == 3  # div + 2 p
        assert result.details["tree2_size"] == 2  # div + 1 p

    @pytest.mark.asyncio
    async def test_similarity_score_in_details(self):
        """Similarity score should be in details."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert "similarity_score" in result.details
        assert result.details["similarity_score"] == result.confidence

    @pytest.mark.asyncio
    async def test_zss_available_in_details(self):
        """ZSS availability should be in details."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert "zss_available" in result.details
        assert isinstance(result.details["zss_available"], bool)


class TestConfigFromDict:
    """Tests for config initialization from dict."""

    @pytest.mark.asyncio
    async def test_config_from_dict(self):
        """Should initialize from dict config."""
        config_dict = {
            "similarity_threshold": 0.85,
            "ignore_attributes": ["id", "data-testid"],
            "focus_selectors": ["main"],
        }
        validator = BehavioralValidator(config=config_dict)

        assert validator.config.similarity_threshold == 0.85
        assert validator.config.ignore_attributes == ["id", "data-testid"]
        assert validator.config.focus_selectors == ["main"]

    @pytest.mark.asyncio
    async def test_config_from_partial_dict(self):
        """Should use defaults for missing dict keys."""
        config_dict = {"similarity_threshold": 0.75}
        validator = BehavioralValidator(config=config_dict)

        assert validator.config.similarity_threshold == 0.75
        assert validator.config.ignore_attributes == ["id", "class", "style"]  # default
        assert validator.config.focus_selectors is None  # default

    @pytest.mark.asyncio
    async def test_config_none(self):
        """Should use defaults when config is None."""
        validator = BehavioralValidator(config=None)

        assert validator.config.similarity_threshold == 0.90
        assert validator.config.ignore_attributes == ["id", "class", "style"]
        assert validator.config.focus_selectors is None


class TestBaseValidator:
    """Tests for BaseValidator default implementation."""

    @pytest.mark.asyncio
    async def test_base_validator_default(self):
        """BaseValidator.validate() returns default result."""
        from validators.behavioral.validator import BaseValidator

        base = BaseValidator()
        result = await base.validate()
        assert result.passed is True
        assert result.message == "No validation implemented"


class TestMessageFormatting:
    """Tests for message formatting."""

    @pytest.mark.asyncio
    async def test_pass_message_format(self):
        """Pass message should indicate match."""
        validator = BehavioralValidator()
        result = await validator.validate("<div></div>", "<div></div>")

        assert "match" in result.message.lower()
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_fail_message_format(self):
        """Fail message should indicate mismatch and threshold."""
        config = BehavioralConfig(similarity_threshold=0.99)
        validator = BehavioralValidator(config=config)
        result = await validator.validate(
            "<div><p>A</p></div>", "<div><span>B</span></div>"
        )

        assert "mismatch" in result.message.lower()
        assert "threshold" in result.message.lower()
        assert result.passed == False  # noqa: E712 - use == for numpy bool
