"""Stage-8 technical validation (spec §10.1): reload the GLB in a FRESH process and check it."""
from __future__ import annotations

import json
import subprocess
import sys

_CHECK = r'''
import json, sys
import numpy as np, trimesh
p = sys.argv[1]
r = {"loads": False}
try:
    s = trimesh.load(p, force="scene")
    geoms = list(s.geometry.values())
    v = np.vstack([g.vertices for g in geoms]) if geoms else np.zeros((0, 3))
    nf = int(sum(len(g.faces) for g in geoms))
    ext = (v.max(0) - v.min(0)).tolist() if len(v) else [0, 0, 0]
    tex = None; vcol = False
    for g in geoms:
        vis = g.visual
        if getattr(vis, "kind", None) == "texture":
            mat = vis.material
            img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
            if img is not None:
                a = np.asarray(img.convert("RGB"), float)
                tex = {"size": list(img.size), "std": float(a.std())}
        elif getattr(vis, "kind", None) == "vertex":
            vcol = True
    r.update(loads=True, vertices=int(len(v)), faces=nf, extent=ext, nan=bool(np.isnan(v).any()),
             texture=tex, vertex_colors=vcol, geometries=len(geoms))
except Exception as e:
    r["error"] = repr(e)
print("S2S_VAL" + json.dumps(r))
'''


def validate_glb(path, tier: int) -> dict:
    try:
        out = subprocess.run([sys.executable, "-c", _CHECK, str(path)], capture_output=True, text=True, timeout=120).stdout
        r = json.loads(next(ln for ln in out.splitlines() if ln.startswith("S2S_VAL"))[7:])
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e)}
    try:  # glTF-level facts straight from the JSON chunk (trimesh may fold COLOR_0 into a material visual)
        from .glb_patch import read_glb

        js, _ = read_glb(path)
        prims = [pr for m in js.get("meshes", []) for pr in m.get("primitives", [])]
        r["gltf_color_0"] = any("COLOR_0" in pr.get("attributes", {}) for pr in prims)
        r["gltf_base_color_texture"] = any("baseColorTexture" in m.get("pbrMetallicRoughness", {})
                                           for m in js.get("materials", []))
        r["vertex_colors"] = bool(r.get("vertex_colors") or r["gltf_color_0"])
    except Exception as e:  # noqa: BLE001
        r["gltf_error"] = repr(e)
    problems = []
    if not r.get("loads"):
        problems.append("does not load")
    else:
        if r["vertices"] == 0 or r["faces"] == 0:
            problems.append("empty geometry")
        if r["nan"]:
            problems.append("NaN vertices")
        if min(r["extent"]) <= 1e-6:
            problems.append("degenerate bbox (flat)")
        if tier == 1 and (not r["texture"] or r["texture"]["std"] < 1.0):
            problems.append("tier-1 texture missing or blank")
    r["ok"], r["problems"] = not problems, problems
    return r
