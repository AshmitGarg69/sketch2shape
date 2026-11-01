"""Decimation (spec §8.3): ≤100k-face viewer mesh, ≤30k-face copy for fidelity rendering. Never aborts."""
from __future__ import annotations

import numpy as np
import trimesh


def decimate(mesh: trimesh.Trimesh, max_faces: int) -> tuple[trimesh.Trimesh, dict]:
    if len(mesh.faces) <= max_faces:
        return mesh, {"decimated": False}
    if getattr(mesh.visual, "uv", None) is not None:
        # Quadric decimation here is not UV-aware: keep the textured mesh intact rather than break its UVs.
        return mesh, {"decimated": False, "reason": "textured mesh kept at full resolution"}
    try:
        out = mesh.simplify_quadric_decimation(face_count=max_faces)
        vc = getattr(mesh.visual, "vertex_colors", None)
        if vc is not None and len(vc) == len(mesh.vertices):
            from scipy.spatial import cKDTree

            _, idx = cKDTree(mesh.vertices).query(out.vertices, k=1)
            out.visual = trimesh.visual.ColorVisuals(out, vertex_colors=np.asarray(vc)[idx])
        return out, {"decimated": True, "faces": int(len(out.faces))}
    except Exception as e:  # noqa: BLE001
        return mesh, {"decimated": False, "error": repr(e)}


def geometry_copy(mesh: trimesh.Trimesh, max_faces: int = 30000) -> trimesh.Trimesh:
    """Plain geometry (no visuals) at ≤ max_faces for the silhouette renderer."""
    g = trimesh.Trimesh(mesh.vertices.copy(), mesh.faces.copy(), process=False)
    if len(g.faces) > max_faces:
        try:
            g = g.simplify_quadric_decimation(face_count=max_faces)
        except Exception:  # noqa: BLE001
            sel = np.random.default_rng(0).choice(len(g.faces), max_faces, replace=False)
            g = trimesh.Trimesh(g.vertices, g.faces[sel], process=False)
    return g
