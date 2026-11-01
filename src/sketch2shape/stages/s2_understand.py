"""S2 sketch understanding (spec §4): binarise, normalise, silhouette, SigLIP object, prompt composition."""
from __future__ import annotations

import cv2
import numpy as np

from ..vision import binarize as B
from ..vision.prompt_composer import compose
from ..vision.silhouette import extract_silhouette, stroke_skeleton


def run(ctx, n_candidates: int, tau: float | None):
    rgb = ctx.data["rgb"]
    raw = B.binarize(rgb, ctx.req.source)
    ctx.data["stroke_ratio"] = B.check_not_blank(raw)
    stroke = B.normalize_strokes(raw, size=768)
    sil = extract_silhouette(stroke)
    ctx.data.update(stroke=stroke, silhouette=sil, skeleton=stroke_skeleton(stroke))
    clean = np.where(stroke, 0, 255).astype(np.uint8)
    cv2.imwrite(str(ctx.run_dir / "input" / "sketch_clean.png"), clean)
    if sil is not None:
        cv2.imwrite(str(ctx.run_dir / "input" / "silhouette.png"), sil.astype(np.uint8) * 255)

    obj, conf, top = (ctx.req.object_override.strip(), 1.0, []) if ctx.req.object_override.strip() else ("object", 0.0, [])
    if not ctx.req.object_override.strip():
        try:
            from ..vision.understand import SharedSigLIP

            sig = SharedSigLIP()
            ctx.data["siglip"] = sig
            obj, conf, top = sig.detect(np.repeat(clean[..., None], 3, axis=2))
            if tau is not None and conf < tau:
                obj = "object"
        except Exception as e:  # noqa: BLE001 - optional component (rule 9)
            ctx.tel.fallbacks.append(f"siglip_unavailable: {type(e).__name__}")
    ctx.data.update(object=obj, object_conf=conf, object_top5=top)
    ctx.data["prompts"] = compose(obj, ctx.req.prompt, material_preset=ctx.req.material,
                                  viewpoint=ctx.req.viewpoint, n=n_candidates)
