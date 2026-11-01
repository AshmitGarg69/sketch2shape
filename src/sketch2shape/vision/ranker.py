"""Composite candidate ranker (spec §5.3). Terms in [0,1]; weights from config/ranker.yaml.
Semantic scores come from the shared SigLIP model (vision/understand.py) and are passed in."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import yaml

from .ranker_stroke import align_candidate, stroke_fidelity
from .silhouette_render import fit_letterbox, iou

CFG = Path(__file__).resolve().parents[3] / "config" / "ranker.yaml"


@dataclass
class Score:
    total: float
    terms: dict = field(default_factory=dict)


def cleanliness(alpha_u8: np.ndarray) -> float:
    """Matte confidence (few semi-transparent pixels) x no border contact x single blob."""
    a = alpha_u8.astype(np.float32) / 255.0
    fg = a > 0.5
    if not fg.any():
        return 0.0
    confident = 1.0 - float(((a > 0.05) & (a < 0.95)).sum() / max(fg.sum(), 1))
    border = np.concatenate([fg[0], fg[-1], fg[:, 0], fg[:, -1]]).mean()
    n, _, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), connectivity=8)
    areas = np.sort(stats[1:, cv2.CC_STAT_AREA])[::-1]
    single = float(areas[0] / areas.sum()) if len(areas) else 0.0
    return float(np.clip(confident, 0, 1) * (1.0 - min(1.0, border * 10)) * single)


def score_candidate(rgb: np.ndarray, alpha_u8: np.ndarray, *, stroke: np.ndarray, skeleton: np.ndarray | None,
                    silhouette: np.ndarray | None, semantic: float, cfg: dict | None = None) -> Score:
    cfg = cfg or yaml.safe_load(CFG.read_text())
    closed = silhouette is not None
    w = cfg["closed" if closed else "open"]
    alpha = alpha_u8 > 127
    if not alpha.any():
        return Score(0.0, {"empty": 1.0})
    terms = {}
    terms["silhouette_iou"] = iou(fit_letterbox(alpha), fit_letterbox(silhouette)) if closed else 0.0
    # Align candidate to the sketch at 256 px (reference: user silhouette, or stroke bbox for open sketches).
    S = 256
    st = cv2.resize(stroke.astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST) > 0
    sk = cv2.resize(skeleton.astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST) > 0 if skeleton is not None else None
    ref = cv2.resize(silhouette.astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST) > 0 if closed else st
    rgb2, a2 = align_candidate(rgb, alpha, ref, out=S)
    sp = cfg["stroke"]
    sf = stroke_fidelity(rgb2, a2, st, sk, k=sp["k"], d0=sp["d0"], blur=sp["blur"])
    terms["stroke"] = sf["f"]
    terms["stroke_detail"] = {k: round(v, 4) for k, v in sf.items()}
    terms["semantic"] = float(np.clip(semantic, 0, 1))
    terms["clean"] = cleanliness(alpha_u8)
    total = sum(w[k] * terms[k] for k in ("silhouette_iou", "stroke", "semantic", "clean"))
    return Score(float(total), terms)
