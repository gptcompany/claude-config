#!/usr/bin/env python3
"""Tests for VisualTargetValidator combined visual comparison."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from validators.visual.perceptual import SKIMAGE_AVAILABLE
from validators.visual.validator import (
    ValidationResult,
    ValidationTier,
    VisualComparisonResult,
    VisualTargetValidator,
)


class TestVisualComparisonResult:
    """Tests for VisualComparisonResult dataclass."""

    def test_result_creation(self):
        """Test creating a basic result."""
        result = VisualComparisonResult(
            confidence=0.92,
            match=True,
            pixel_score=0.95,
            ssim_score=0.88,
        )
        assert result.confidence == 0.92
        assert result.match is True
        assert result.pixel_score == 0.95
        assert result.ssim_score == 0.88
        assert result.diff_path is None
        assert result.error is None
        assert result.details == {}

    def test_result_with_error(self):
        """Test creating a result with error."""
        result = VisualComparisonResult(
            confidence=0.0,
            match=False,
            pixel_score=0.0,
            ssim_score=0.0,
            error="Test error",
        )
        assert result.match is False
        assert result.error == "Test error"

    def test_result_with_details(self):
        """Test creating a result with details."""
        result = VisualComparisonResult(
            confidence=0.75,
            match=False,
            pixel_score=0.7,
            ssim_score=0.8,
            diff_path="/path/to/diff.png",
            details={"threshold": 0.85, "availability": {"odiff": True, "ssim": True}},
        )
        assert result.diff_path == "/path/to/diff.png"
        assert result.details["threshold"] == 0.85


class TestVisualTargetValidator:
    """Tests for VisualTargetValidator class."""

    def test_init_default_config(self):
        """Test validator initializes with correct defaults."""
        validator = VisualTargetValidator()

        assert validator.config["threshold"] == 0.85
        assert validator.config["pixel_weight"] == 0.6
        assert validator.config["ssim_weight"] == 0.4
        assert validator.dimension == "visual_target"
        assert validator.tier == ValidationTier.MONITOR

    def test_init_custom_config(self):
        """Test validator accepts custom config."""
        config = {
            "threshold": 0.90,
            "pixel_weight": 0.7,
            "ssim_weight": 0.3,
            "baseline_dir": "/baselines",
            "current_dir": "/current",
        }
        validator = VisualTargetValidator(config=config)

        assert validator.config["threshold"] == 0.90
        assert validator.config["pixel_weight"] == 0.7
        assert validator.config["baseline_dir"] == "/baselines"

    def test_is_available(self):
        """Test availability check returns dict."""
        validator = VisualTargetValidator()
        availability = validator.is_available()

        assert isinstance(availability, dict)
        assert "odiff" in availability
        assert "ssim" in availability
        assert isinstance(availability["odiff"], bool)
        assert isinstance(availability["ssim"], bool)

    @patch.object(VisualTargetValidator, "is_available")
    def test_compare_no_tools_available(self, mock_available):
        """Test comparison when no tools are available."""
        mock_available.return_value = {"odiff": False, "ssim": False}

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        assert result.match is False
        assert result.confidence == 0.0
        assert "no comparison tools" in result.error.lower()

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_only_odiff_available(self, mock_perceptual_cls, mock_odiff_cls):
        """Test comparison using only ODiff when SSIM unavailable."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.8,
            error=None,
            diff_path="/tmp/diff.png",  # nosec B108 - test fixture path
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = False
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        # When only ODiff available, confidence = pixel_score
        assert result.confidence == 0.8
        assert result.pixel_score == 0.8
        assert result.ssim_score == 0.0

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_only_ssim_available(self, mock_perceptual_cls, mock_odiff_cls):
        """Test comparison using only SSIM when ODiff unavailable."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = False
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.9,
            error=None,
            diff_image_path="/tmp/ssim_diff.png",  # nosec B108 - test fixture path
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        # When only SSIM available, confidence = ssim_score
        assert result.confidence == 0.9
        assert result.pixel_score == 0.0
        assert result.ssim_score == 0.9

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_both_available(self, mock_perceptual_cls, mock_odiff_cls):
        """Test comparison using both ODiff and SSIM."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.8,
            error=None,
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.9,
            error=None,
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        # Fused score: 0.8 * 0.6 + 0.9 * 0.4 = 0.48 + 0.36 = 0.84
        assert result.confidence == pytest.approx(0.84)
        assert result.pixel_score == 0.8
        assert result.ssim_score == 0.9

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_match_above_threshold(self, mock_perceptual_cls, mock_odiff_cls):
        """Test match=True when confidence >= threshold."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.95,
            error=None,
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.95,
            error=None,
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator(config={"threshold": 0.85})

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        # Confidence = 0.95 >= 0.85 threshold
        assert result.match is True

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_mismatch_below_threshold(
        self, mock_perceptual_cls, mock_odiff_cls
    ):
        """Test match=False when confidence < threshold."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.5,
            error=None,
            diff_path="/tmp/diff.png",  # nosec B108 - test fixture path
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.5,
            error=None,
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator(config={"threshold": 0.85})

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = validator.compare(str(baseline), str(current))

        # Confidence = 0.5 < 0.85 threshold
        assert result.match is False
        assert result.diff_path is not None


class TestBaseValidator:
    """Tests for BaseValidator."""

    @pytest.mark.asyncio
    async def test_base_validator_validate(self):
        """Test BaseValidator.validate() default implementation."""
        from validators.visual.validator import BaseValidator

        v = BaseValidator()
        result = await v.validate()
        assert result.passed is True
        assert result.message == "No validation implemented"


class TestVisualTargetValidatorEdgeCases:
    """Edge case tests for compare() method."""

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_odiff_error(self, mock_perceptual_cls, mock_odiff_cls):
        """Test compare when odiff returns an error."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.0,
            error="ODiff crashed",
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.9,
            error=None,
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            b = Path(tmpdir) / "b.png"
            b.touch()
            c = Path(tmpdir) / "c.png"
            c.touch()
            result = validator.compare(str(b), str(c))

        # pixel_score=0, ssim_score=0.9 -> confidence=ssim_score
        assert result.confidence == 0.9
        assert "ODiff" in result.error

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_ssim_error(self, mock_perceptual_cls, mock_odiff_cls):
        """Test compare when ssim returns an error."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.8,
            error=None,
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.0,
            error="SSIM failed",
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            b = Path(tmpdir) / "b.png"
            b.touch()
            c = Path(tmpdir) / "c.png"
            c.touch()
            result = validator.compare(str(b), str(c))

        # ssim_score=0, pixel_score=0.8 -> confidence=pixel_score
        assert result.confidence == 0.8
        assert "SSIM" in result.error

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_both_error_zero_scores(self, mock_perceptual_cls, mock_odiff_cls):
        """Test compare when both tools error with zero scores."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.0,
            error="ODiff crashed",
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.0,
            error="SSIM failed",
            diff_image_path=None,
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            b = Path(tmpdir) / "b.png"
            b.touch()
            c = Path(tmpdir) / "c.png"
            c.touch()
            result = validator.compare(str(b), str(c))

        assert result.confidence == 0.0
        assert result.match is False
        assert "ODiff" in result.error
        assert "SSIM" in result.error

    @patch("validators.visual.validator.ODiffRunner")
    @patch("validators.visual.validator.PerceptualComparator")
    def test_compare_mismatch_ssim_diff_path(self, mock_perceptual_cls, mock_odiff_cls):
        """Test diff_path falls back to ssim when pixel has no diff."""
        mock_odiff = MagicMock()
        mock_odiff.is_available.return_value = True
        mock_odiff.compare.return_value = MagicMock(
            pixel_score=0.3,
            error=None,
            diff_path=None,
            details={},
        )
        mock_odiff_cls.return_value = mock_odiff

        mock_perceptual = MagicMock()
        mock_perceptual.is_available.return_value = True
        mock_perceptual.compare.return_value = MagicMock(
            ssim_score=0.3,
            error=None,
            diff_image_path="/tmp/ssim.png",
            details={},
        )
        mock_perceptual_cls.return_value = mock_perceptual

        validator = VisualTargetValidator(config={"threshold": 0.85})

        with tempfile.TemporaryDirectory() as tmpdir:
            b = Path(tmpdir) / "b.png"
            b.touch()
            c = Path(tmpdir) / "c.png"
            c.touch()
            result = validator.compare(str(b), str(c))

        assert result.match is False
        assert result.diff_path == "/tmp/ssim.png"


class TestVisualTargetValidatorAsync:
    """Tests for async validate() method."""

    @pytest.mark.asyncio
    async def test_validate_no_directories_configured(self):
        """Test validation when no directories are configured."""
        validator = VisualTargetValidator()

        result = await validator.validate()

        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.dimension == "visual_target"
        assert result.tier == ValidationTier.MONITOR
        assert result.details.get("configured") is False

    @pytest.mark.asyncio
    async def test_validate_baseline_dir_not_found(self):
        """Test validation when baseline directory doesn't exist."""
        validator = VisualTargetValidator(
            config={
                "baseline_dir": "/nonexistent/baseline",
                "current_dir": "/tmp",  # nosec B108 - test fixture path
            }
        )

        result = await validator.validate()

        assert result.passed is True  # Tier 3 doesn't block
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_current_dir_not_found(self):
        """Test validation when current directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = VisualTargetValidator(
                config={
                    "baseline_dir": tmpdir,
                    "current_dir": "/nonexistent/current",
                }
            )

            result = await validator.validate()

        assert result.passed is True  # Tier 3 doesn't block
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_validate_no_baseline_images(self):
        """Test validation when no baseline images found."""
        with tempfile.TemporaryDirectory() as baseline_dir:
            with tempfile.TemporaryDirectory() as current_dir:
                validator = VisualTargetValidator(
                    config={
                        "baseline_dir": baseline_dir,
                        "current_dir": current_dir,
                    }
                )

                result = await validator.validate()

        assert result.passed is True
        assert "no baseline images" in result.message.lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    async def test_validate_with_matching_images(self):
        """Test validation with matching images."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            current_dir = Path(tmpdir) / "current"
            baseline_dir.mkdir()
            current_dir.mkdir()

            # Create identical images
            img = Image.new("RGB", (100, 100), color="red")
            img.save(baseline_dir / "test.png")
            img.save(current_dir / "test.png")

            validator = VisualTargetValidator(
                config={
                    "baseline_dir": str(baseline_dir),
                    "current_dir": str(current_dir),
                    "threshold": 0.85,
                }
            )

            result = await validator.validate()

        assert result.passed is True
        assert result.details.get("images_compared") == 1
        assert result.details.get("matches") == 1

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    async def test_validate_with_mismatched_images(self):
        """Test validation with mismatched images."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            current_dir = Path(tmpdir) / "current"
            baseline_dir.mkdir()
            current_dir.mkdir()

            # Create different images
            img1 = Image.new("RGB", (100, 100), color="red")
            img2 = Image.new("RGB", (100, 100), color="blue")
            img1.save(baseline_dir / "test.png")
            img2.save(current_dir / "test.png")

            validator = VisualTargetValidator(
                config={
                    "baseline_dir": str(baseline_dir),
                    "current_dir": str(current_dir),
                    "threshold": 0.95,  # High threshold
                }
            )

            result = await validator.validate()

        # Tier 3 still passes
        assert result.passed is True
        assert result.details.get("images_compared") == 1
        assert result.details.get("mismatches") >= 1

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    async def test_validate_with_diff_dir(self):
        """Test validation creates diff_dir when configured."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            current_dir = Path(tmpdir) / "current"
            diff_dir = Path(tmpdir) / "diffs"
            baseline_dir.mkdir()
            current_dir.mkdir()

            img1 = Image.new("RGB", (100, 100), color="red")
            img2 = Image.new("RGB", (100, 100), color="blue")
            img1.save(baseline_dir / "test.png")
            img2.save(current_dir / "test.png")

            validator = VisualTargetValidator(
                config={
                    "baseline_dir": str(baseline_dir),
                    "current_dir": str(current_dir),
                    "diff_dir": str(diff_dir),
                    "threshold": 0.99,
                }
            )

            result = await validator.validate()
            assert diff_dir.exists()

        assert result.passed is True

    @pytest.mark.asyncio
    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    async def test_validate_missing_current_image(self):
        """Test validation when current image is missing."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            current_dir = Path(tmpdir) / "current"
            baseline_dir.mkdir()
            current_dir.mkdir()

            # Create only baseline image
            img = Image.new("RGB", (100, 100), color="red")
            img.save(baseline_dir / "test.png")
            # Don't create current/test.png

            validator = VisualTargetValidator(
                config={
                    "baseline_dir": str(baseline_dir),
                    "current_dir": str(current_dir),
                }
            )

            result = await validator.validate()

        assert result.passed is True  # Tier 3 doesn't block
        assert result.details.get("mismatches") == 1
        assert "missing" in str(result.details.get("mismatch_details", []))


@pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
class TestVisualTargetValidatorIntegration:
    """Integration tests with real images."""

    @pytest.fixture
    def sample_images(self, tmp_path):
        """Create sample test images."""
        from PIL import Image

        baseline = tmp_path / "baseline.png"
        identical = tmp_path / "identical.png"
        different = tmp_path / "different.png"

        img1 = Image.new("RGB", (100, 100), color="red")
        img2 = Image.new("RGB", (100, 100), color="red")
        img3 = Image.new("RGB", (100, 100), color="blue")

        img1.save(baseline)
        img2.save(identical)
        img3.save(different)

        return {
            "baseline": str(baseline),
            "identical": str(identical),
            "different": str(different),
            "diff_output": str(tmp_path / "diff.png"),
        }

    def test_compare_identical_images(self, sample_images):
        """Integration test: identical images should have high confidence."""
        validator = VisualTargetValidator(config={"threshold": 0.85})

        result = validator.compare(
            sample_images["baseline"],
            sample_images["identical"],
            sample_images["diff_output"],
        )

        assert result.match is True
        assert result.confidence >= 0.95
        assert result.error is None

    def test_compare_different_images(self, sample_images):
        """Integration test: different images should have low confidence."""
        validator = VisualTargetValidator(config={"threshold": 0.95})

        result = validator.compare(
            sample_images["baseline"],
            sample_images["different"],
            sample_images["diff_output"],
        )

        assert result.match is False
        assert result.confidence < 0.95
        assert result.error is None

    def test_compare_with_diff_output(self, sample_images):
        """Integration test: diff images should be created."""
        validator = VisualTargetValidator(config={"threshold": 0.99})

        result = validator.compare(
            sample_images["baseline"],
            sample_images["different"],
            sample_images["diff_output"],
        )

        assert result.match is False
        # Diff should be saved for mismatched images
        if result.diff_path:
            assert Path(result.diff_path).exists()
