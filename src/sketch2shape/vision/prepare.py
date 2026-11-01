"""Stage-4 RGBA contract (spec §6): crop to alpha bbox, pad so the object fills ~85 %, centre, square,
colour-decontaminate the edge band so background fringes don't bleed into textures."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def decontaminate(rgb: np.ndarray, alpha: np.ndarray, band: int = 3) -> np.ndarray:
    """Replace colours in the soft/edge band with colours inpainted from the confident interior.
    (pymatting's estimate_foreground_ml was measured at 44 s on a laptop CPU incl. numba JIT; this band inpaint is
    ~0.1 s and our alphas are near-binary after clean_alpha, so only a 2–3 px fringe needs fixing.)"""
    solid = cv2.erode((alpha > 250).astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1)
    edge = ((alpha > 0) & (solid == 0)).astype(np.uint8)
    edge = cv2.dilate(edge, np.ones((3, 3), np.uint8), iterations=band - 1) & (alpha > 0).astype(np.uint8)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    out = cv2.inpaint(bgr, edge * 255, band, cv2.INPAINT_TELEA)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def prepare_rgba(rgb: np.ndarray, alpha: np.ndarray, size: int = 1024, fill: float = 0.85) -> Image.Image:
    ys, xs = np.where(alpha > 127)
    if len(ys) == 0:
        raise ValueError("empty alpha")
    rgb = decontaminate(rgb, alpha)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    crop_rgb, crop_a = rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
    h, w = crop_a.shape
    s = size * fill / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    r_rgb = cv2.resize(crop_rgb, (nw, nh), interpolation=interp)
    r_a = cv2.resize(crop_a, (nw, nh), interpolation=interp)
    out = np.zeros((size, size, 4), np.uint8)
    oy, ox = (size - nh) // 2, (size - nw) // 2
    out[oy:oy + nh, ox:ox + nw, :3] = r_rgb
    out[oy:oy + nh, ox:ox + nw, 3] = r_a
    out[..., :3][out[..., 3] == 0] = 0
    return Image.fromarray(out, "RGBA")


def on_grey(rgba: Image.Image, grey: int = 128) -> Image.Image:
    a = np.asarray(rgba).astype(np.float32)
    al = a[..., 3:4] / 255.0
    return Image.fromarray((a[..., :3] * al + grey * (1 - al)).round().astype(np.uint8))
