"""Stage-2 silhouette extraction (spec §4.1 step 4): progressive dilate -> fill -> erode.

Small gaps in a hand-drawn outline are bridged by dilating with increasing radii; the first radius at
which the outline encloses a real interior wins.  Open doodles return None (ranker uses stroke terms only).
"""
from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize

RADII = (2, 5, 8, 12, 16, 22, 30)


def _disk(r: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Pixels not reachable from the border through background become foreground."""
    m = mask.astype(np.uint8)
    h, w = m.shape
    pad = np.zeros((h + 2, w + 2), np.uint8)
    pad[1:-1, 1:-1] = m
    ff = pad.copy()
    cv2.floodFill(ff, np.zeros((h + 4, w + 4), np.uint8), (0, 0), 1)
    holes = ff[1:-1, 1:-1] == 0
    return mask | holes


def extract_silhouette(stroke: np.ndarray, radii=RADII, min_interior_ratio: float = 1.0,
                       min_area_frac: float = 0.01) -> np.ndarray | None:
    """Return a boolean interior mask, or None when the sketch is open at every radius.

    "Closed" = after filling, the newly enclosed area is at least `min_interior_ratio` x the dilated stroke
    area and covers >= `min_area_frac` of the frame.
    """
    stroke = stroke.astype(bool)
    if not stroke.any():
        return None
    for r in radii:
        k = _disk(r)
        dil = cv2.dilate(stroke.astype(np.uint8), k) > 0
        filled = fill_holes(dil)
        interior = filled & ~dil
        if interior.sum() >= min_interior_ratio * dil.sum() * 0.25 and filled.mean() >= min_area_frac \
                and interior.sum() > 0:
            sil = cv2.erode(filled.astype(np.uint8), k) > 0
            sil |= fill_holes(stroke) & filled  # never lose original ink
            return _largest_component(sil)
    return None


def _largest_component(mask: np.ndarray) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if n <= 2:
        return mask
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return lab == big


def stroke_skeleton(stroke: np.ndarray) -> np.ndarray:
    return skeletonize(stroke.astype(bool))
