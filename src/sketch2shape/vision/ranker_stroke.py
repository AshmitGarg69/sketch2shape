"""
Stroke-fidelity term for the candidate ranker (spec 5.3).  Lives at: src/sketch2shape/vision/ranker_stroke.py
All inputs are same-size arrays (e.g. 256x256) AFTER align_candidate().

v3 term = recall of the user's strokes against (alpha contour U Canny edges): a texture-covered candidate
has edges everywhere so recall ~1.0 regardless of shape.  v3.1 term = F-score of
  recall'   : strokes -> candidate edges, multiplied by min(1, d0 / interior_edge_density)
  precision : candidate alpha CONTOUR -> nearest user stroke
so texture cannot buy recall and hallucinated extra parts cost precision.
k in pixels at 256 px; d0 = tolerated interior-edge density (edge px / alpha px) - calibrate in Phase 2.
"""
from __future__ import annotations
import cv2
import numpy as np

def _dt_to(mask):
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 3)

def align_candidate(rgb, alpha, ref_mask, out=256):
    def bbox(m):
        ys, xs = np.where(m)
        return xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    cx0, cx1, cy0, cy1 = bbox(alpha)
    rx0, rx1, ry0, ry1 = bbox(ref_mask)
    s = max(ry1 - ry0, rx1 - rx0) / max(cy1 - cy0, cx1 - cx0)
    M = np.array([[s, 0, (rx0 + rx1) / 2 - s * (cx0 + cx1) / 2],
                  [0, s, (ry0 + ry1) / 2 - s * (cy0 + cy1) / 2]], np.float32)
    rgb2 = cv2.warpAffine(rgb, M, (out, out), flags=cv2.INTER_AREA, borderValue=(230, 230, 230))
    a2 = cv2.warpAffine(alpha.astype(np.uint8), M, (out, out), flags=cv2.INTER_NEAREST) > 0
    return rgb2, a2

def candidate_edges(rgb, alpha, blur=1.5, canny=(50, 150)):
    flat = np.where(alpha[..., None], rgb, 230).astype(np.uint8)
    g = cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY)
    if blur > 0:
        g = cv2.GaussianBlur(g, (0, 0), blur)
    a8 = alpha.astype(np.uint8)
    contour = alpha & ~cv2.erode(a8, np.ones((3, 3), np.uint8)).astype(bool)
    near = cv2.dilate(a8, np.ones((5, 5), np.uint8)).astype(bool)
    return contour, (cv2.Canny(g, *canny) > 0) & near

def stroke_fidelity(rgb, alpha, stroke, skeleton=None, k=6, d0=0.02, blur=1.5):
    skeleton = stroke if skeleton is None else skeleton
    contour, edges = candidate_edges(rgb, alpha, blur)
    interior = edges & (_dt_to(contour) > 3) if contour.any() else edges
    if not skeleton.any() or not contour.any():
        return dict(recall=0.0, precision=0.0, f=0.0, interior_density=0.0)
    recall = float((_dt_to(contour | edges)[skeleton] <= k).mean())
    density = float(interior.sum() / max(alpha.sum(), 1))
    recall_adj = recall * min(1.0, d0 / max(density, 1e-9))
    precision = float((_dt_to(stroke)[contour] <= k + 2).mean())
    f = 2 * recall_adj * precision / max(recall_adj + precision, 1e-9)
    return dict(recall=recall_adj, precision=precision, f=f, interior_density=density)
