"""S1 input layer (spec §3): flatten RGBA/EditorValue, downscale long edge to ≤2048, save."""
from __future__ import annotations

import cv2
import numpy as np

from ..vision.binarize import downscale, flatten_rgba


def run(ctx):
    img = np.asarray(ctx.req.image)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    rgb = downscale(flatten_rgba(img))
    cv2.imwrite(str(ctx.run_dir / "input" / "sketch_input.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    ctx.data["rgb"] = rgb
