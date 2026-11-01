"""S4 image preparation (spec §6): always emits a clean centred RGBA PNG."""
from __future__ import annotations

import numpy as np

from ..vision.prepare import on_grey, prepare_rgba


def run(ctx, index: int):
    c = ctx.data["candidates"][index]
    rgba = prepare_rgba(np.asarray(c["image"].convert("RGB")), c["alpha"], size=1024)
    p = ctx.run_dir / "selected_rgba.png"
    rgba.save(p)
    on_grey(rgba).save(ctx.run_dir / "preview_front.png")
    ctx.data.update(selected=index, selected_rgba=p, selected_alpha=np.asarray(rgba)[..., 3])
