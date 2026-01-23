#!/usr/bin/env python3
"""
PerceptualComparator - SSIM-based perceptual image comparison.

Uses Structural Similarity Index (SSIM) to compare images based on
perceptual similarity rather than pixel-by-pixel differences.

Graceful degradation: Returns error with explanatory message
when scikit-image or PIL are not installed.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Check for optional dependencies
try:
    import numpy as np
    from PIL import Image
    from skimage.metrics import structural_similarity as ssim

    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    np = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment, misc]
    ssim = None  # type: ignore[assignment]


@dataclass
class PerceptualResult:
    """Result from perceptual comparison."""

    ssim_score: float  # 0.0 to 1.0 (1.0 = identical)
    match: bool  # True if ssim_score >= threshold
    error: str | None = None
    diff_image_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class PerceptualComparator:
    """
    SSIM-based perceptual image comparator.

    SSIM (Structural Similarity Index) measures perceptual similarity
    by comparing luminance, contrast, and structure. More robust than
    pixel-by-pixel comparison for detecting meaningful visual differences.

    Usage:
        comparator = PerceptualComparator(threshold=0.95)
        result = comparator.compare("baseline.png", "current.png")

        if result.match:
            print("Images are perceptually similar!")
        else:
            print(f"SSIM score: {result.ssim_score:.3f}")
    """

    DEFAULT_THRESHOLD = 0.95  # 95% similarity
    DEFAULT_WIN_SIZE = 7  # SSIM window size (must be odd, <= image dimensions)

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        win_size: int = DEFAULT_WIN_SIZE,
        multichannel: bool = False,
    ):
        """
        Initialize perceptual comparator.

        Args:
            threshold: Minimum SSIM score for match (0.0 to 1.0)
            win_size: SSIM window size (must be odd)
            multichannel: Compare color channels separately (slower, more accurate)
        """
        self.threshold = threshold
        self.win_size = win_size
        self.multichannel = multichannel

    def is_available(self) -> bool:
        """Check if required dependencies are installed."""
        return SKIMAGE_AVAILABLE

    def _load_image(self, path: str) -> tuple["np.ndarray | None", str | None]:
        """
        Load image and convert to grayscale array.

        Args:
            path: Path to image file

        Returns:
            Tuple of (numpy array, error message) - one will be None
        """
        if not SKIMAGE_AVAILABLE:
            return (
                None,
                "scikit-image not installed. Install via: pip install scikit-image pillow",
            )

        file_path = Path(path)
        if not file_path.exists():
            return None, f"Image not found: {path}"

        try:
            img = Image.open(file_path)

            # Convert to grayscale for SSIM (more robust, faster)
            if not self.multichannel:
                img = img.convert("L")
            else:
                img = img.convert("RGB")

            return np.array(img), None
        except Exception as e:
            return None, f"Failed to load image {path}: {str(e)}"

    def _resize_to_match(
        self, img1: "np.ndarray", img2: "np.ndarray"
    ) -> tuple["np.ndarray", "np.ndarray"]:
        """
        Resize images to match dimensions (use smaller).

        Args:
            img1: First image array
            img2: Second image array

        Returns:
            Tuple of resized arrays with matching dimensions
        """
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]

        if h1 == h2 and w1 == w2:
            return img1, img2

        # Use smaller dimensions
        target_h = min(h1, h2)
        target_w = min(w1, w2)

        # Crop to target size (center crop)
        def center_crop(img: "np.ndarray", th: int, tw: int) -> "np.ndarray":
            h, w = img.shape[:2]
            start_h = (h - th) // 2
            start_w = (w - tw) // 2
            if len(img.shape) == 3:
                return img[start_h : start_h + th, start_w : start_w + tw, :]
            return img[start_h : start_h + th, start_w : start_w + tw]

        return center_crop(img1, target_h, target_w), center_crop(
            img2, target_h, target_w
        )

    def _compute_ssim(
        self, img1: "np.ndarray", img2: "np.ndarray"
    ) -> tuple[float, "np.ndarray | None"]:
        """
        Compute SSIM between two images.

        Args:
            img1: First image array
            img2: Second image array

        Returns:
            Tuple of (ssim_score, diff_image)
        """
        # Ensure images match
        img1, img2 = self._resize_to_match(img1, img2)

        # Adjust window size if images are small
        min_dim = min(img1.shape[0], img1.shape[1])
        win_size = min(self.win_size, min_dim)
        if win_size % 2 == 0:
            win_size -= 1  # Must be odd
        win_size = max(3, win_size)  # Minimum 3

        # Compute SSIM
        if self.multichannel and len(img1.shape) == 3:
            # Color comparison
            score, diff_img = ssim(
                img1,
                img2,
                win_size=win_size,
                channel_axis=2,
                full=True,
                data_range=255,
            )
        else:
            # Grayscale comparison
            score, diff_img = ssim(
                img1,
                img2,
                win_size=win_size,
                full=True,
                data_range=255,
            )

        return float(score), diff_img

    def compare(
        self,
        baseline: str,
        current: str,
        diff_output: str | None = None,
    ) -> PerceptualResult:
        """
        Compare two images using SSIM.

        Args:
            baseline: Path to baseline/expected image
            current: Path to current/actual image
            diff_output: Optional path to save SSIM diff visualization

        Returns:
            PerceptualResult with ssim_score and match status
        """
        # Check dependencies
        if not self.is_available():
            return PerceptualResult(
                ssim_score=0.0,
                match=False,
                error="Dependencies not installed. Install via: pip install scikit-image pillow",
                details={"skimage_available": False},
            )

        # Load images
        img1, err1 = self._load_image(baseline)
        if err1:
            return PerceptualResult(
                ssim_score=0.0,
                match=False,
                error=err1,
            )

        img2, err2 = self._load_image(current)
        if err2:
            return PerceptualResult(
                ssim_score=0.0,
                match=False,
                error=err2,
            )

        # Compute SSIM
        try:
            score, diff_img = self._compute_ssim(img1, img2)  # type: ignore[arg-type]
        except Exception as e:
            return PerceptualResult(
                ssim_score=0.0,
                match=False,
                error=f"SSIM computation failed: {str(e)}",
            )

        # Determine if match based on threshold
        match = score >= self.threshold

        # Save diff image if requested and not matching
        diff_path = None
        if diff_output and diff_img is not None and not match:
            try:
                diff_output_path = Path(diff_output)
                diff_output_path.parent.mkdir(parents=True, exist_ok=True)

                # Convert diff to visible image (invert so differences are bright)
                diff_normalized = ((1 - diff_img) * 255).astype(np.uint8)
                diff_pil = Image.fromarray(diff_normalized)
                diff_pil.save(diff_output_path)
                diff_path = diff_output
            except Exception:
                pass  # Non-critical, ignore save errors

        # Get image dimensions for details
        h1, w1 = img1.shape[:2]  # type: ignore[union-attr]
        h2, w2 = img2.shape[:2]  # type: ignore[union-attr]

        return PerceptualResult(
            ssim_score=score,
            match=match,
            diff_image_path=diff_path,
            details={
                "skimage_available": True,
                "threshold": self.threshold,
                "win_size": self.win_size,
                "multichannel": self.multichannel,
                "baseline_size": (w1, h1),
                "current_size": (w2, h2),
                "sizes_matched": (h1 == h2 and w1 == w2),
            },
        )


__all__ = ["PerceptualComparator", "PerceptualResult", "SKIMAGE_AVAILABLE"]
