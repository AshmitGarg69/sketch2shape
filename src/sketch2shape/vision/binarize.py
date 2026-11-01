"""Stage-2 preprocessing (spec §4.1 steps 1-3): flatten, source-aware binarisation, stroke normalisation."""
from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize

MIN_STROKE_RATIO = 0.002  # spec §3: reject near-blank canvases (< 0.2 % stroke pixels)
MAX_EDGE = 2048


class BlankSketchError(ValueError):
    """Raised for empty / near-blank inputs; message is user-facing."""


def flatten_rgba(img: np.ndarray) -> np.ndarray:
    """Any HxW / HxWx3 / HxWx4 uint8 array -> HxWx3 RGB composited on white."""
    img = np.asarray(img)
    if img.ndim == 2:
        return np.repeat(img[..., None], 3, axis=2).astype(np.uint8)
    if img.shape[2] == 4:
        a = img[..., 3:4].astype(np.float32) / 255.0
        rgb = img[..., :3].astype(np.float32) * a + 255.0 * (1 - a)
        return rgb.round().astype(np.uint8)
    return img[..., :3].astype(np.uint8)


def downscale(img: np.ndarray, max_edge: int = MAX_EDGE) -> np.ndarray:
    h, w = img.shape[:2]
    s = max_edge / max(h, w)
    if s >= 1:
        return img
    return cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)


def binarize(rgb: np.ndarray, source: str = "upload") -> np.ndarray:
    """Return a boolean stroke mask (True = ink).

    canvas: strokes are drawn on pure white -> simple threshold.
    upload: photos of paper have uneven lighting -> divide by a heavy blur (illumination estimate), then Otsu.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if source == "canvas":
        mask = gray < 240
    else:
        sigma = max(gray.shape) / 30.0
        bg = cv2.GaussianBlur(gray, (0, 0), sigma).astype(np.float32) + 1.0
        norm = np.clip(gray.astype(np.float32) / bg * 255.0, 0, 255).astype(np.uint8)
        norm = cv2.GaussianBlur(norm, (3, 3), 0)
        _, th = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        mask = th > 0
        # Otsu on a clean white page with no ink would pick noise; require real contrast.
        if norm[mask].size and float(np.median(norm[~mask]) - np.median(norm[mask])) < 25:
            mask = np.zeros_like(mask)
    # drop salt noise
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    min_area = max(4, int(mask.size * 2e-5))
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[lab]


def check_not_blank(mask: np.ndarray) -> float:
    ratio = float(mask.mean())
    if ratio < MIN_STROKE_RATIO:
        raise BlankSketchError("The sketch looks empty — please draw or upload an object outline first.")
    return ratio


def normalize_strokes(mask: np.ndarray, size: int = 768, fill: float = 0.8, thickness: int = 4) -> np.ndarray:
    """Fit the stroke bbox to `fill` of a square canvas (pad, never crop; uniform scale) and
    re-thicken strokes to a consistent width via skeleton + dilation."""
    ys, xs = np.where(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    h, w = crop.shape
    s = size * fill / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    r = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR) > 127
    canvas = np.zeros((size, size), bool)
    y0, x0 = (size - nh) // 2, (size - nw) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = r
    skel = skeletonize(canvas)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))
    return cv2.dilate(skel.astype(np.uint8), k) > 0
