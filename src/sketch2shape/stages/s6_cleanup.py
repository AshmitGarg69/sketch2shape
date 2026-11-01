"""S6 mesh cleanup (spec §8)."""
from __future__ import annotations

import trimesh

from ..mesh.decimate import decimate, geometry_copy
from ..mesh.orient import normalize_pose
from ..mesh.prune import prune_islands
from ..mesh.repair import repair


def load_raw(path) -> trimesh.Trimesh:
    m = trimesh.load(str(path), process=False, force="mesh")
    if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0:
        raise ValueError("backend produced an empty mesh")
    return m


def run(ctx, max_viewer_faces: int, max_render_faces: int):
    m = load_raw(ctx.data["raw"].path)
    info = {"raw_faces": int(len(m.faces)), "raw_vertices": int(len(m.vertices))}
    m, info["prune"] = prune_islands(m)
    m, info["repair"] = repair(m)
    m = normalize_pose(m)
    full = m
    viewer, info["decimate"] = decimate(m, max_viewer_faces)
    ctx.data.update(mesh_full=full, mesh_viewer=viewer, mesh_render=geometry_copy(viewer, max_render_faces),
                    cleanup=info)
