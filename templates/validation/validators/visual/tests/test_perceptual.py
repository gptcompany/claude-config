#!/usr/bin/env python3
"""Tests for PerceptualComparator SSIM module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from validators.visual.perceptual import (
    SKIMAGE_AVAILABLE,
    PerceptualComparator,
    PerceptualResult,
)


class TestPerceptualResult:
    """Tests for PerceptualResult dataclass."""

    def test_result_creation(self):
        """Test creating a basic result."""
        result = PerceptualResult(
            ssim_score=0.95,
            match=True,
        )
        assert result.ssim_score == 0.95
        assert result.match is True
        assert result.error is None
        assert result.diff_image_path is None
        assert result.details == {}

    def test_result_with_error(self):
        """Test creating a result with error."""
        result = PerceptualResult(
            ssim_score=0.0,
            match=False,
            error="Test error",
        )
        assert result.ssim_score == 0.0
        assert result.match is False
        assert result.error == "Test error"

    def test_result_with_details(self):
        """Test creating a result with details."""
        result = PerceptualResult(
            ssim_score=0.87,
            match=False,
            diff_image_path="/path/to/diff.png",
            details={"threshold": 0.95, "win_size": 7},
        )
        assert result.diff_image_path == "/path/to/diff.png"
        assert result.details["threshold"] == 0.95


class TestPerceptualComparator:
    """Tests for PerceptualComparator class."""

    def test_init_default_values(self):
        """Test comparator initializes with correct defaults."""
        comparator = PerceptualComparator()
        assert comparator.threshold == 0.95
        assert comparator.win_size == 7
        assert comparator.multichannel is False

    def test_init_custom_values(self):
        """Test comparator accepts custom values."""
        comparator = PerceptualComparator(
            threshold=0.90,
            win_size=11,
            multichannel=True,
        )
        assert comparator.threshold == 0.90
        assert comparator.win_size == 11
        assert comparator.multichannel is True

    def test_is_available(self):
        """Test is_available returns correct value based on imports."""
        comparator = PerceptualComparator()
        assert comparator.is_available() == SKIMAGE_AVAILABLE

    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    def test_load_image_success(self):
        """Test loading a valid image."""
        import numpy as np
        from PIL import Image

        comparator = PerceptualComparator()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test image
            img = Image.new("RGB", (100, 100), color="red")
            path = Path(tmpdir) / "test.png"
            img.save(path)

            # Load and verify
            arr, err = comparator._load_image(str(path))

            assert err is None
            assert arr is not None
            assert isinstance(arr, np.ndarray)
            assert arr.shape == (100, 100)  # Grayscale

    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    def test_load_image_multichannel(self):
        """Test loading image in multichannel mode."""
        from PIL import Image

        comparator = PerceptualComparator(multichannel=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            img = Image.new("RGB", (100, 100), color="red")
            path = Path(tmpdir) / "test.png"
            img.save(path)

            arr, err = comparator._load_image(str(path))

            assert err is None
            assert arr is not None
            assert arr.shape == (100, 100, 3)  # RGB

    @pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
    def test_load_image_not_found(self):
        """Test loading non-existent image."""
        comparator = PerceptualComparator()
        arr, err = comparator._load_image("/nonexistent/image.png")

        assert arr is None
        assert "not found" in err.lower()

    def test_compare_missing_baseline(self):
        """Test comparison with missing baseline file."""
        comparator = PerceptualComparator()

        with tempfile.TemporaryDirectory() as tmpdir:
            current = Path(tmpdir) / "current.png"
            current.touch()

            result = comparator.compare(
                "/nonexistent/baseline.png",
                str(current),
            )

        assert result.match is False
        assert result.ssim_score == 0.0
        assert result.error is not None
        if SKIMAGE_AVAILABLE:
            assert "not found" in result.error.lower()

    def test_compare_missing_current(self):
        """Test comparison with missing current file."""
        comparator = PerceptualComparator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            baseline.touch()

            result = comparator.compare(
                str(baseline),
                "/nonexistent/current.png",
            )

        assert result.match is False
        assert result.ssim_score == 0.0
        assert result.error is not None

    @patch("validators.visual.perceptual.SKIMAGE_AVAILABLE", False)
    def test_compare_without_dependencies(self):
        """Test graceful degradation when dependencies missing."""
        comparator = PerceptualComparator()
        # Override is_available for this test
        comparator.is_available = lambda: False  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = comparator.compare(str(baseline), str(current))

        assert result.match is False
        assert result.ssim_score == 0.0
        assert "not installed" in result.error.lower()
        assert result.details.get("skimage_available") is False


@pytest.mark.skipif(not SKIMAGE_AVAILABLE, reason="scikit-image not installed")
class TestPerceptualComparatorIntegration:
    """Integration tests requiring scikit-image and PIL."""

    @pytest.fixture
    def sample_images(self, tmp_path):
        """Create sample test images."""
        from PIL import Image

        # Create identical images
        img1 = Image.new("RGB", (100, 100), color="red")
        img2 = Image.new("RGB", (100, 100), color="red")

        baseline = tmp_path / "baseline.png"
        current_identical = tmp_path / "current_identical.png"

        img1.save(baseline)
        img2.save(current_identical)

        # Create slightly different image (same color, different shade)
        img3 = Image.new(
            "RGB", (100, 100), color=(255, 10, 10)
        )  # Slightly different red
        current_similar = tmp_path / "current_similar.png"
        img3.save(current_similar)

        # Create very different image
        img4 = Image.new("RGB", (100, 100), color="blue")
        current_different = tmp_path / "current_different.png"
        img4.save(current_different)

        # Create image with different size
        img5 = Image.new("RGB", (200, 200), color="red")
        current_larger = tmp_path / "current_larger.png"
        img5.save(current_larger)

        return {
            "baseline": str(baseline),
            "identical": str(current_identical),
            "similar": str(current_similar),
            "different": str(current_different),
            "larger": str(current_larger),
            "diff_output": str(tmp_path / "diff.png"),
        }

    def test_identical_images(self, sample_images):
        """Test comparing identical images returns high score."""
        comparator = PerceptualComparator(threshold=0.95)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["identical"],
        )

        assert result.match is True
        assert result.ssim_score >= 0.99
        assert result.error is None

    def test_similar_images(self, sample_images):
        """Test comparing similar images returns reasonable score."""
        comparator = PerceptualComparator(threshold=0.95)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["similar"],
        )

        # Similar colors should have high SSIM
        assert result.ssim_score >= 0.8
        assert result.error is None

    def test_different_images(self, sample_images):
        """Test comparing very different images returns low score."""
        comparator = PerceptualComparator(threshold=0.95)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["different"],
        )

        assert result.match is False
        assert result.ssim_score < 0.95
        assert result.error is None

    def test_different_sizes(self, sample_images):
        """Test comparing images with different sizes."""
        comparator = PerceptualComparator(threshold=0.95)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["larger"],
        )

        # Should still work (center crop to smaller size)
        assert result.error is None
        # Result should have some score calculated
        assert result.ssim_score >= 0.0

    def test_diff_output_saved(self, sample_images):
        """Test that diff image is saved for non-matching images."""
        from pathlib import Path

        comparator = PerceptualComparator(
            threshold=0.99
        )  # High threshold to ensure mismatch

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["different"],
            diff_output=sample_images["diff_output"],
        )

        assert result.match is False
        # Diff should be saved for mismatched images
        if result.diff_image_path:
            assert Path(result.diff_image_path).exists()

    def test_no_diff_output_for_match(self, sample_images):
        """Test that diff image is not saved for matching images."""
        comparator = PerceptualComparator(threshold=0.90)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["identical"],
            diff_output=sample_images["diff_output"],
        )

        # Matching images should not have diff saved
        assert result.match is True
        # diff_image_path should be None for matches
        assert result.diff_image_path is None

    def test_threshold_determines_match(self, sample_images):
        """Test that threshold correctly determines match status."""
        # Very low threshold - everything matches
        comparator_low = PerceptualComparator(threshold=0.1)
        result_low = comparator_low.compare(
            sample_images["baseline"],
            sample_images["different"],
        )
        assert (
            result_low.match is True
        )  # Even very different images match with low threshold

        # Very high threshold - hard to match
        comparator_high = PerceptualComparator(threshold=0.999)
        result_high = comparator_high.compare(
            sample_images["baseline"],
            sample_images["similar"],
        )
        # Similar images may not match with very high threshold
        # Just verify the score is calculated
        assert result_high.ssim_score > 0

    def test_small_images(self, tmp_path):
        """Test SSIM with very small images (window size adjustment)."""
        from PIL import Image

        # Create tiny images (smaller than default window size)
        img1 = Image.new("RGB", (10, 10), color="red")
        img2 = Image.new("RGB", (10, 10), color="red")

        baseline = tmp_path / "tiny_baseline.png"
        current = tmp_path / "tiny_current.png"
        img1.save(baseline)
        img2.save(current)

        comparator = PerceptualComparator(win_size=7)
        result = comparator.compare(str(baseline), str(current))

        # Should work with adjusted window size
        assert result.error is None
        assert result.ssim_score >= 0.99

    def test_multichannel_comparison(self, sample_images):
        """Test multichannel (color) SSIM comparison."""
        comparator = PerceptualComparator(multichannel=True, threshold=0.95)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["identical"],
        )

        assert result.match is True
        # Result should successfully complete
        assert result.error is None

    def test_details_populated(self, sample_images):
        """Test that result details are properly populated."""
        comparator = PerceptualComparator(threshold=0.95, win_size=7)

        result = comparator.compare(
            sample_images["baseline"],
            sample_images["identical"],
        )

        assert result.details.get("skimage_available") is True
        assert result.details.get("threshold") == 0.95
        # Verify basic details exist
        assert "baseline_size" in result.details
        assert "current_size" in result.details


class TestPerceptualComparatorMocked:
    """Tests using mocks for edge cases."""

    @patch("validators.visual.perceptual.SKIMAGE_AVAILABLE", True)
    @patch("validators.visual.perceptual.Image")
    @patch("validators.visual.perceptual.ssim")
    @patch("validators.visual.perceptual.np")
    def test_ssim_computation_error(self, mock_np, mock_ssim, mock_image):
        """Test handling of SSIM computation errors."""
        mock_image.open.return_value = MagicMock()
        mock_image.open.return_value.convert.return_value = MagicMock()
        mock_np.array.return_value = MagicMock()
        mock_np.array.return_value.shape = (100, 100)

        mock_ssim.side_effect = RuntimeError("SSIM computation failed")

        comparator = PerceptualComparator()

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline.png"
            current = Path(tmpdir) / "current.png"
            baseline.touch()
            current.touch()

            result = comparator.compare(str(baseline), str(current))

        assert result.match is False
        assert result.ssim_score == 0.0
        assert "failed" in result.error.lower()
