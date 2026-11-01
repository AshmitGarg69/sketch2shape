"""Seam-safe island pruning (spec §8.1).

UV seams duplicate vertices, so connected components computed on the raw (UV-unwelded) mesh split one
object into many "islands". Components are therefore found on a vertex-MERGED copy and the labels are
mapped back to the faces of the original mesh, which keeps len(vertices) == len(uv).
"""
from __future__ import annotations

import numpy as np
import trimesh


def _merged_face_labels(mesh: trimesh.Trimesh, digits: int = 6) -> np.ndarray:
    v = np.round(np.asarray(mesh.vertices), digits)
    _, inverse = np.unique(v, axis=0, return_inverse=True)
    faces_merged = inverse.reshape(-1)[np.asarray(mesh.faces)]
    return trimesh.graph.connected_component_labels(trimesh.graph.face_adjacency(faces_merged),
                                                    node_count=len(faces_merged))


def prune_islands(mesh: trimesh.Trimesh, min_area_frac: float = 0.02, touch_tol: float = 1e-3) -> tuple[trimesh.Trimesh, dict]:
    if len(mesh.faces) == 0:
        return mesh, {"components": 0, "removed": 0}
    labels = _merged_face_labels(mesh)
    areas = mesh.area_faces
    total = areas.sum()
    comp_area = np.bincount(labels, weights=areas)
    main = int(np.argmax(comp_area))
    main_bounds = mesh.vertices[mesh.faces[labels == main].ravel()]
    lo, hi = main_bounds.min(0) - touch_tol, main_bounds.max(0) + touch_tol
    keep_comp = comp_area >= min_area_frac * total
    for c in np.where(~keep_comp)[0]:
        pts = mesh.vertices[mesh.faces[labels == c].ravel()]
        # "touching the main body": shares (merged) bounds region with the main component closely
        if np.all((pts >= lo) & (pts <= hi), axis=1).mean() > 0.5 and _near(pts, main_bounds, touch_tol * 10):
            keep_comp[c] = True
    keep_faces = keep_comp[labels]
    info = {"components": int(len(comp_area)), "removed": int((~keep_comp).sum()),
            "removed_area_frac": float(comp_area[~keep_comp].sum() / max(total, 1e-12))}
    if keep_faces.all():
        return mesh, info
    out = mesh.copy()
    out.update_faces(keep_faces)
    out.remove_unreferenced_vertices()
    return out, info


def _near(pts: np.ndarray, ref: np.ndarray, tol: float) -> bool:
    try:
        from scipy.spatial import cKDTree

        d, _ = cKDTree(ref).query(pts[:: max(1, len(pts) // 200)], k=1)
        return bool((d <= tol).any())
    except Exception:  # noqa: BLE001
        return False
