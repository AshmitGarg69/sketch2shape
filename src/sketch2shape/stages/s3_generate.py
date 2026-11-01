"""S3 generate-N-and-rank (spec §5): ControlNet candidates -> matting -> composite ranker."""
from __future__ import annotations

import numpy as np
from PIL import Image

import time

from ..core.vram import free_cuda

# Parked generators (CPU RAM) keyed by profile — only used when the host has plenty of system RAM (e.g. Kaggle 31 GB),
# so a long-running server does not re-read ~10 GB of SDXL weights from disk for every request.
_PARKED: dict = {}
PARK_MIN_FREE_RAM_GB = 12.0   # parked SDXL+ControlNet fp16 ≈ 8 GB; measured: 20 GB was too strict after the first cycle


def _ram_free_gb() -> float:
    try:
        import psutil

        return psutil.virtual_memory().available / 2**30
    except Exception:  # noqa: BLE001
        return 0.0
from ..vision.matting import Matter, clean_alpha, recover_with_sketch
from ..vision.prepare import on_grey
from ..vision.ranker import score_candidate


def run(ctx, profile: str, n: int, scales: list[float], seed: int, resolution: int | None = None):
    from ..vision.generate import Generator

    ps = ctx.data["prompts"]
    prompts = ps.positive[:n] if n >= len(ps.positive) else ps.positive[: n - 1] + [ps.positive[-1]]
    hedge_idx = len(prompts) - 1 if ps.hedge_index is not None and n >= 2 else None
    seeds = [seed + i for i in range(len(prompts))]
    sc = [scales[i % len(scales)] for i in range(len(prompts))]
    t0 = time.time()
    gen = _PARKED.pop(profile, None)
    if gen is not None:
        ctx.progress("generate", 0.0, f"Restoring {profile} image generator from RAM…")
        gen.unpark()
        how = "ram"
    else:
        ctx.progress("generate", 0.0, f"Loading {profile} image generator…")
        gen = Generator(profile, ctx.gpu)
        how = "disk"
    t_load = time.time() - t0
    try:
        imgs = gen.generate(ctx.data["stroke"], prompts, ps.negative, seeds, sc, resolution,
                            on_step=lambda i, k: ctx.progress("generate", i / k, f"Candidate {i}/{k}"))
    finally:
        ram_free = _ram_free_gb()
        if gen.parkable and ram_free > PARK_MIN_FREE_RAM_GB:
            gen.park()
            _PARKED[profile] = gen
        else:
            gen.close()
        del gen
        free_cuda()
    ctx.data["s3_timing"] = {"load_s": round(t_load, 2), "load_from": how, "generate_s": round(time.time() - t0 - t_load, 2),
                             "n": len(prompts), "ram_free_gb_after": round(ram_free, 1), "parked": profile in _PARKED}

    ctx.progress("generate", 1.0, "Isolating foreground…")
    matter = Matter(log=lambda m: ctx.tel.fallbacks.append(m))
    if matter.kind != "birefnet":
        ctx.tel.fallbacks.append(f"matting={matter.kind}")
    cands = []
    for i, im in enumerate(imgs):
        rgb = np.asarray(im.convert("RGB"))
        a_raw = matter.alpha(im)
        a_raw, added = recover_with_sketch(rgb, a_raw, ctx.data["silhouette"])
        a, rep = clean_alpha(a_raw)
        rep["sketch_recovered_frac"] = round(added, 4)
        cands.append({"index": i, "image": im, "alpha": a, "matte": rep, "seed": seeds[i], "scale": sc[i],
                      "prompt": prompts[i], "hedge": i == hedge_idx})
        im.save(ctx.run_dir / "candidates" / f"cand_{i}.png")
        Image.fromarray(np.dstack([rgb, a])).save(ctx.run_dir / "candidates" / f"cand_{i}_rgba.png")
    matter.close()

    sig = ctx.data.get("siglip")
    sem = [0.5] * len(cands)
    if sig is not None:
        try:
            masked = [on_grey(Image.fromarray(np.dstack([np.asarray(c["image"].convert("RGB")), c["alpha"]])))
                      for c in cands]
            sem = sig.semantic(masked, prompts[0])
        except Exception as e:  # noqa: BLE001
            ctx.tel.fallbacks.append(f"semantic_score_failed: {type(e).__name__}")
        sig.close()
        ctx.data.pop("siglip", None)
    for c, s in zip(cands, sem):
        sc_ = score_candidate(np.asarray(c["image"].convert("RGB")), c["alpha"], stroke=ctx.data["stroke"],
                              skeleton=ctx.data["skeleton"], silhouette=ctx.data["silhouette"], semantic=s)
        c["score"], c["terms"] = (0.0 if "reject" in c["matte"] else sc_.total), sc_.terms
    order = sorted(range(len(cands)), key=lambda i: -cands[i]["score"])
    ctx.data.update(candidates=cands, rank=order)
    win = cands[order[0]]
    # Only meaningful if the hedge prompt actually dropped words (an all-allowlisted prompt makes it just another seed).
    if win["hedge"] and ps.user_text and win["prompt"] != prompts[0]:
        ctx.tel.warnings.append("prompt_conflict_suspected")
        ctx.data["notice"] = "Your prompt seemed to pull the result away from your sketch; the sketch was prioritised."
