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

    def test_fuse_scores_default_weights(self):
        """Test score fusion with default weights (60/40)."""
        validator = VisualTargetValidator()

        # pixel=1.0, ssim=1.0 -> 1.0
        assert validator._fuse_scores(1.0, 1.0) == pytest.approx(1.0)

        # pixel=0.0, ssim=0.0 -> 0.0
        assert validator._fuse_scores(0.0, 0.0) == pytest.approx(0.0)

        # pixel=1.0, ssim=0.0 -> 0.6
        assert validator._fuse_scores(1.0, 0.0) == pytest.approx(0.6)

        # pixel=0.0, ssim=1.0 -> 0.4
        assert validator._fuse_scores(0.0, 1.0) == pytest.approx(0.4)

        # pixel=0.5, ssim=0.5 -> 0.5
        assert validator._fuse_scores(0.5, 0.5) == pytest.approx(0.5)

    def test_fuse_scores_custom_weights(self):
        """Test score fusion with custom weights."""
        validator = VisualTargetValidator(
            config={"pixel_weight": 0.3, "ssim_weight": 0.7}
        )

        # pixel=1.0, ssim=0.0 -> 0.3
        assert validator._fuse_scores(1.0, 0.0) == pytest.approx(0.3)

        # pixel=0.0, ssim=1.0 -> 0.7
        assert validator._fuse_scores(0.0, 1.0) == pytest.approx(0.7)

    def test_fuse_scores_normalizes_weights(self):
        """Test that weights are normalized if they don't sum to 1."""
        validator = VisualTargetValidator(
            config={"pixel_weight": 6, "ssim_weight": 4}  # Sum = 10
        )

        # Should still work as 60/40
        assert validator._fuse_scores(1.0, 0.0) == pytest.approx(0.6)

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
            diff_path="/tmp/diff.png",
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
            diff_image_path="/tmp/ssim_diff.png",
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
            diff_path="/tmp/diff.png",
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
                "current_dir": "/tmp",
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
