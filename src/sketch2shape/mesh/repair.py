"""Mesh repair (spec §8.2): degenerate/duplicate faces, winding/normals, small holes, optional Taubin."""
from __future__ import annotations

import numpy as np
import trimesh


def repair(mesh: trimesh.Trimesh, smooth_iters: int = 0) -> tuple[trimesh.Trimesh, dict]:
    info = {"faces_in": int(len(mesh.faces))}
    m = mesh.copy()
    try:
        m.update_faces(m.nondegenerate_faces())
        m.update_faces(m.unique_faces())
        m.remove_unreferenced_vertices()
    except Exception as e:  # noqa: BLE001
        info["dedupe_error"] = repr(e)
    try:
        trimesh.repair.fix_winding(m)
        trimesh.repair.fix_normals(m, multibody=True)
    except Exception as e:  # noqa: BLE001
        info["normals_error"] = repr(e)
    try:
        if not m.is_watertight and not _has_uv(m):  # hole filling adds faces without UVs
            trimesh.repair.fill_holes(m)
    except Exception as e:  # noqa: BLE001
        info["fill_error"] = repr(e)
    if smooth_iters:
        try:
            trimesh.smoothing.filter_taubin(m, iterations=smooth_iters)
        except Exception as e:  # noqa: BLE001
            info["smooth_error"] = repr(e)
    info.update(faces_out=int(len(m.faces)), watertight=bool(m.is_watertight))
    return m, info


def _has_uv(m: trimesh.Trimesh) -> bool:
    return getattr(m.visual, "uv", None) is not None
