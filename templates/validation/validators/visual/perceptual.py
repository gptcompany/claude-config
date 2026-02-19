#!/usr/bin/env python3
"""SSIM-based perceptual image comparison with graceful degradation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    import numpy as _np


@dataclass
class PerceptualResult:
    ssim_score: float
    match: bool
    error: str | None = None
    diff_image_path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class PerceptualComparator:
    DEFAULT_THRESHOLD = 0.95
    DEFAULT_WIN_SIZE = 7

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        win_size: int = DEFAULT_WIN_SIZE,
        multichannel: bool = False,
    ):
        self.threshold = threshold
        self.win_size = win_size
        self.multichannel = multichannel

    def is_available(self) -> bool:
        return SKIMAGE_AVAILABLE

    def _load_image(self, path: str) -> "tuple[_np.ndarray | None, str | None]":
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
            img = img.convert("RGB" if self.multichannel else "L")
            return np.array(img), None
        except Exception as e:
            return None, f"Failed to load image {path}: {str(e)}"

    def _center_crop(
        self, img: "_np.ndarray", target_h: int, target_w: int
    ) -> "_np.ndarray":
        h, w = img.shape[:2]
        start_h = (h - target_h) // 2
        start_w = (w - target_w) // 2
        if len(img.shape) == 3:
            return img[start_h : start_h + target_h, start_w : start_w + target_w, :]
        return img[start_h : start_h + target_h, start_w : start_w + target_w]

    def compare(
        self,
        baseline: str,
        current: str,
        diff_output: str | None = None,
    ) -> PerceptualResult:
        if not self.is_available():
            return PerceptualResult(
                ssim_score=0.0,
                match=False,
                error="Dependencies not installed. Install via: pip install scikit-image pillow",
                details={"skimage_available": False},
            )

        img1, err1 = self._load_image(baseline)
        if err1:
            return PerceptualResult(ssim_score=0.0, match=False, error=err1)

        img2, err2 = self._load_image(current)
        if err2:
            return PerceptualResult(ssim_score=0.0, match=False, error=err2)

        h1, w1 = img1.shape[:2]  # type: ignore[union-attr]
        h2, w2 = img2.shape[:2]  # type: ignore[union-attr]

        if h1 != h2 or w1 != w2:
            target_h, target_w = min(h1, h2), min(w1, w2)
            img1 = self._center_crop(img1, target_h, target_w)  # type: ignore[arg-type]
            img2 = self._center_crop(img2, target_h, target_w)  # type: ignore[arg-type]

        min_dim = min(img1.shape[0], img1.shape[1])  # type: ignore[union-attr]
        win_size = min(self.win_size, min_dim)
        if win_size % 2 == 0:
            win_size -= 1
        win_size = max(3, win_size)

        assert ssim is not None  # guaranteed by is_available() check above
        try:
            if self.multichannel and len(img1.shape) == 3:  # type: ignore[arg-type]
                score, diff_img = ssim(  # type: ignore[reportAssignmentType]
                    img1,
                    img2,
                    win_size=win_size,
                    channel_axis=2,
                    full=True,
                    data_range=255,
                )
            else:
                score, diff_img = ssim(  # type: ignore[reportAssignmentType]
                    img1, img2, win_size=win_size, full=True, data_range=255
                )
        except Exception as e:
            return PerceptualResult(
                ssim_score=0.0, match=False, error=f"SSIM computation failed: {str(e)}"
            )

        match = float(score) >= self.threshold
        diff_path = None

        if diff_output and diff_img is not None and not match:
            try:
                diff_output_path = Path(diff_output)
                diff_output_path.parent.mkdir(parents=True, exist_ok=True)
                diff_normalized = ((1 - diff_img) * 255).astype(np.uint8)
                Image.fromarray(diff_normalized).save(diff_output_path)
                diff_path = diff_output
            except Exception:
                pass

        return PerceptualResult(
            ssim_score=float(score),
            match=match,
            diff_image_path=diff_path,
            details={
                "skimage_available": True,
                "threshold": self.threshold,
                "baseline_size": (w1, h1),
                "current_size": (w2, h2),
            },
        )


__all__ = ["PerceptualComparator", "PerceptualResult", "SKIMAGE_AVAILABLE"]
