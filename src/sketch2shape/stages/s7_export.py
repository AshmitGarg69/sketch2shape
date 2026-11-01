"""S7 export (spec §9): Tier-1 textured GLB if the backend gave a base-colour texture, else Tier-2 vertex colours.
Always also writes model.obj(+mtl+texture) zipped."""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import yaml

from ..mesh.glb_patch import patch_pbr

CFG = Path(__file__).resolve().parents[3] / "config" / "materials.yaml"


def tier_of(mesh) -> int:
    vis = mesh.visual
    if getattr(vis, "kind", None) == "texture" and getattr(vis, "uv", None) is not None:
        mat = vis.material
        img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
        if img is not None:
            return 1
    return 2


def run(ctx):
    mesh = ctx.data["mesh_viewer"]
    tier = tier_of(mesh)
    out = ctx.run_dir / "mesh"
    glb = out / "model.glb"
    mesh.export(glb)
    mats = yaml.safe_load(CFG.read_text())
    material = ctx.data["prompts"].material if "prompts" in ctx.data else "plastic"
    metallic, rough = mats["pbr"].get(material, mats["pbr"]["plastic"])
    patch_pbr(glb, metallic=metallic, roughness=rough, name=material)
    with tempfile.TemporaryDirectory() as td:
        ctx.data["mesh_full"].export(Path(td) / "model.obj")
        with zipfile.ZipFile(out / "model.obj.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for p in Path(td).iterdir():
                z.write(p, p.name)
    ctx.data.update(glb=glb, obj_zip=out / "model.obj.zip", tier=tier, material=material)
