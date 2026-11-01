"""Seam-safe pruning: a UV-unwelded body must NOT be split into islands; a real floater is removed."""
import numpy as np
import trimesh
from PIL import Image
from sketch2shape.mesh.prune import prune_islands


def _unwelded_textured_sphere():
    s = trimesh.creation.icosphere(subdivisions=3)
    # Unweld every face (worst-case UV seams): each face gets its own 3 vertices.
    v = s.vertices[s.faces].reshape(-1, 3)
    f = np.arange(len(v)).reshape(-1, 3)
    uv = np.random.default_rng(0).random((len(v), 2))
    tex = trimesh.visual.TextureVisuals(uv=uv, image=Image.new("RGB", (8, 8), (200, 50, 50)))
    return trimesh.Trimesh(v, f, visual=tex, process=False)


def test_unwelded_body_is_one_component_and_uv_preserved():
    body = _unwelded_textured_sphere()
    out, info = prune_islands(body)
    assert info["components"] == 1 and info["removed"] == 0
    assert len(out.faces) == len(body.faces) and len(out.vertices) == len(out.visual.uv)


def test_far_floater_is_removed_and_uv_stays_aligned():
    body = _unwelded_textured_sphere()
    fl = trimesh.creation.icosphere(subdivisions=1, radius=0.05)
    fl.apply_translation([5, 0, 0])
    v = np.vstack([body.vertices, fl.vertices])
    f = np.vstack([body.faces, fl.faces + len(body.vertices)])
    uv = np.vstack([body.visual.uv, np.zeros((len(fl.vertices), 2))])
    m = trimesh.Trimesh(v, f, visual=trimesh.visual.TextureVisuals(uv=uv, image=Image.new("RGB", (8, 8))), process=False)
    out, info = prune_islands(m)
    assert info["components"] == 2 and info["removed"] == 1
    assert len(out.faces) == len(body.faces)
    assert len(out.vertices) == len(out.visual.uv)
    assert out.vertices[:, 0].max() < 2
