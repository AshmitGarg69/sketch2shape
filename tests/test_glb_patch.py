import numpy as np
import trimesh
from sketch2shape.mesh.glb_patch import patch_pbr, read_glb
from sketch2shape.mesh.validate import validate_glb


def test_patch_vertex_colour_glb_roundtrip(tmp_path):
    m = trimesh.creation.box()
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.tile([200, 30, 30, 255], (len(m.vertices), 1)))
    p = tmp_path / "m.glb"
    m.export(p)
    n = patch_pbr(p, metallic=0.0, roughness=0.7)
    js, binary = read_glb(p)
    assert n >= 1 and binary is not None
    pbr = js["materials"][0]["pbrMetallicRoughness"]
    assert pbr["metallicFactor"] == 0.0 and pbr["roughnessFactor"] == 0.7
    attrs = js["meshes"][0]["primitives"][0]["attributes"]
    assert "COLOR_0" in attrs
    v = validate_glb(p, tier=2)
    assert v["ok"], v
    assert v["vertices"] > 0 and v["vertex_colors"]


def test_validate_rejects_flat_plane(tmp_path):
    plane = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], [[0, 1, 2], [1, 3, 2]])
    p = tmp_path / "flat.glb"
    plane.export(p)
    v = validate_glb(p, tier=2)
    assert not v["ok"] and "degenerate bbox (flat)" in v["problems"]
