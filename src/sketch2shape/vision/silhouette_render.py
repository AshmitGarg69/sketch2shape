"""
Pure NumPy + OpenCV orthographic silhouette renderer and aspect-preserving mask comparison.
No OpenGL / EGL / pyrender.  Lives at: src/sketch2shape/vision/silhouette_render.py

Conventions (must match the adapters' canonical orientation): +Y up, model front = +Z,
camera looks along -Z from +Z, +X appears on the RIGHT of the image at yaw=0.
yaw rotates about +Y, pitch about +X.

One fillConvexPoly per face (v3 used a single cv2.fillPoly over all faces): fillPoly applies the
even-odd rule across ALL polygons of one call, so wherever projections of front and back faces
overlap the pixel cancels out and stays EMPTY (icosphere IoU ~0.14-0.18 vs a true disk, axis-aligned
box ~1% filled).  A silhouette is the UNION of projected triangles, so each triangle is filled on its
own.  Holes (mug handle) survive because a hole is a region no triangle projects onto.
"""
from __future__ import annotations
import cv2
import numpy as np

def _rotation(yaw_deg, pitch_deg):
    ry, rp = np.radians(yaw_deg), np.radians(pitch_deg)
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(rp), -np.sin(rp)], [0, np.sin(rp), np.cos(rp)]])
    return Rx @ Ry

class OrthoView:
    def __init__(self, vertices, yaw_deg=0.0, pitch_deg=0.0, size=512, fill=0.85):
        self.R = _rotation(yaw_deg, pitch_deg)
        self.size = size
        xy = (np.asarray(vertices, float) @ self.R.T)[:, :2]
        lo, hi = xy.min(0), xy.max(0)
        span = max(float((hi - lo).max()), 1e-9)
        self.center = (lo + hi) / 2
        self.scale = size * fill / span
    def project(self, pts3):
        xy = (np.asarray(pts3, float) @ self.R.T)[:, :2]
        px = (xy - self.center) * self.scale + self.size / 2
        px[:, 1] = self.size - px[:, 1]
        return px

def silhouette_ortho(vertices, faces, yaw_deg=0.0, pitch_deg=0.0, size=512, fill=0.85):
    view = OrthoView(vertices, yaw_deg, pitch_deg, size, fill)
    px = np.round(view.project(vertices)).astype(np.int32)
    canvas = np.zeros((size, size), np.uint8)
    for tri in px[np.asarray(faces)]:
        cv2.fillConvexPoly(canvas, tri, 255)
    canvas = cv2.morphologyEx(canvas, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return canvas > 0

def fit_letterbox(mask, out=256, fill=0.9):
    ys, xs = np.where(mask)
    canvas = np.zeros((out, out), np.uint8)
    if len(ys) == 0:
        return canvas > 0
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8)
    h, w = crop.shape
    s = out * fill / max(h, w)
    nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
    r = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_NEAREST)
    y0, x0 = (out - nh) // 2, (out - nw) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = r
    return canvas > 0

def iou(a, b):
    return float((a & b).sum() / max((a | b).sum(), 1))

def input_view_check(vertices, faces, target_mask, yaw_deg=0.0, pitch_deg=0.0, size=256):
    """Handedness / mirror test at the backend's calibrated INPUT view. Returns (iou_direct, iou_mirrored).
    A best-of-all-yaws search can NOT detect mirroring: yaw 180 is the mirror image of yaw 0."""
    r = fit_letterbox(silhouette_ortho(vertices, faces, yaw_deg, pitch_deg, size=size), size)
    t = fit_letterbox(target_mask, size)
    return iou(r, t), iou(r[:, ::-1], t)

def fidelity_near_input_view(vertices, faces, target_mask, input_yaw=0.0, input_pitch=0.0,
                             yaw_span=(-20, -10, 0, 10, 20), pitch_span=(-10, 0, 10), size=256):
    """Best IoU in a small neighbourhood of the calibrated input view (aspect-preserving)."""
    t = fit_letterbox(target_mask, size)
    best = (0.0, (input_yaw, input_pitch))
    for dy in yaw_span:
        for dp in pitch_span:
            r = fit_letterbox(silhouette_ortho(vertices, faces, input_yaw + dy, input_pitch + dp, size=size), size)
            s = iou(r, t)
            if s > best[0]:
                best = (s, (input_yaw + dy, input_pitch + dp))
    return best
