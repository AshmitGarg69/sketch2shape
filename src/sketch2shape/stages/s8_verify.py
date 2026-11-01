"""S8 verification (spec §10): technical validation + closed-loop fidelity (pure NumPy/OpenCV) + mirror check."""
from __future__ import annotations

import cv2
import numpy as np

from ..mesh.validate import validate_glb
from ..vision.ranker_stroke import align_candidate, stroke_fidelity
from ..vision.silhouette_render import fidelity_near_input_view, input_view_check, silhouette_ortho


def run(ctx, mirror_margin: float = 0.10) -> dict:
    v = validate_glb(ctx.data["glb"], ctx.data["tier"])
    g = ctx.data["mesh_render"]
    V, F = np.asarray(g.vertices), np.asarray(g.faces)
    cal = (ctx.data.get("backend_cfg") or {}).get("calibration", {}).get("input_view", {})
    yaw, pitch = float(cal.get("yaw") or 0), float(cal.get("pitch") or 0)
    cand_alpha = ctx.data["selected_alpha"] > 127
    recon, best_view = fidelity_near_input_view(V, F, cand_alpha, yaw, pitch)
    direct, mirrored = input_view_check(V, F, cand_alpha, yaw, pitch)
    if mirrored - direct > mirror_margin:
        ctx.tel.warnings.append("mirror_suspect")
    sil = ctx.data["silhouette"]
    if sil is not None:
        sketch_fid, sketch_view = fidelity_near_input_view(V, F, sil, yaw, pitch)
        kind = "silhouette"
    else:
        render = silhouette_ortho(V, F, best_view[0], best_view[1], size=256)
        st = cv2.resize(ctx.data["stroke"].astype(np.uint8), (256, 256), interpolation=cv2.INTER_NEAREST) > 0
        grey = np.full((256, 256, 3), 128, np.uint8)
        _, a2 = align_candidate(grey, render, st, out=256)
        sketch_fid = stroke_fidelity(grey, a2, st)["f"] if a2.any() else 0.0
        sketch_view, kind = best_view, "stroke"
    return {"validation": v, "recon_consistency": round(float(recon), 4), "sketch_fidelity": round(float(sketch_fid), 4),
            "sketch_match_kind": kind, "best_view": list(best_view), "input_view": [yaw, pitch],
            "mirror_direct": round(float(direct), 4), "mirror_flipped": round(float(mirrored), 4)}
