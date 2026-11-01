"""Pose/scale (spec §8.4). Canonical frame: +Y up, front +Z, origin at base-centre, unit height.
Axis permutations specific to a backend live in its adapter, never here."""
from __future__ import annotations

import numpy as np
import trimesh


def normalize_pose(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    m = mesh.copy()
    v = np.asarray(m.vertices, float)
    lo, hi = v.min(0), v.max(0)
    h = max(hi[1] - lo[1], 1e-9)
    t = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    m.apply_translation(t)
    m.apply_scale(1.0 / h)
    return m
