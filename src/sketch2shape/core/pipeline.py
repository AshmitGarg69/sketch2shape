"""UI-agnostic pipeline (spec §2): S1..S8 with progress, cancel, telemetry, OOM ladder, 1-retry policy."""
from __future__ import annotations

import random
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yaml

from ..stages import s1_input, s2_understand, s3_generate, s4_prepare, s5_reconstruct, s6_cleanup, s7_export, s8_verify
from ..vision.binarize import BlankSketchError
from . import vram
from .context import ROOT, Context, Request, new_run_dir, rss_gb, write_run_json
from .errors import Cancelled, NoCudaError, OOMError, PipelineError

PROFILES = {"balanced": {"min_vram_gb": 14}, "lite": {"min_vram_gb": 5}}


@dataclass
class Result:
    ok: bool
    run_dir: Path | None = None
    glb: Path | None = None
    obj_zip: Path | None = None
    run_json: Path | None = None
    candidates: list = field(default_factory=list)   # [(path, caption)]
    selected: int | None = None
    badges: dict = field(default_factory=dict)
    message: str = ""


def load_cfg() -> dict:
    cfg = yaml.safe_load((ROOT / "config" / "default.yaml").read_text())
    prof = ROOT / "config" / "profiles.yaml"
    cfg["profiles"] = yaml.safe_load(prof.read_text())["profiles"] if prof.exists() else PROFILES
    return cfg


class Pipeline:
    def __init__(self, cfg: dict | None = None):
        self.cfg = cfg or load_cfg()

    def _stage(self, ctx: Context, name: str, fn: Callable, *a, **kw):
        if ctx.cancel.is_set():
            raise Cancelled("Cancelled by user", stage=name)
        vram.free_cuda(reset_peak=True)
        t = time.time()
        try:
            return fn(ctx, *a, **kw)
        finally:
            ctx.tel.stage(name, time.time() - t, vram.peak_gb(), rss_gb())

    def run(self, req: Request, progress: Callable[[str, float, str], None] | None = None,
            cancel: threading.Event | None = None) -> Result:
        progress = progress or (lambda s, f, m: None)
        cancel = cancel or threading.Event()
        gpu = vram.detect()
        seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)
        req.seed = seed
        reuse = req.reuse_run_dir and req.selected_candidate is not None
        run_dir = Path(req.reuse_run_dir) if reuse else new_run_dir(req.out_root, req.image)
        ctx = Context(req, run_dir, progress, cancel, gpu=gpu)
        extra: dict = {"seed": seed}
        try:
            if not gpu.cuda:
                raise NoCudaError("Sketch2Shape needs an NVIDIA GPU with CUDA for generation. "
                                  "Run `sketch2shape doctor` for details, or use the Kaggle/Colab notebook.")
            ctx.profile = vram.pick_profile(gpu, self.cfg["profiles"])
            if ctx.profile is None:
                raise NoCudaError(f"GPU {gpu.name} has {gpu.total_gb:.1f} GB VRAM; at least "
                                  f"{min(p['min_vram_gb'] for p in self.cfg['profiles'].values())} GB is required.")
            n = int(self.cfg["n_candidates"][ctx.profile])
            if reuse:
                cache = getattr(self, "_cache", {})
                if cache.get("run_dir") != str(run_dir):
                    raise PipelineError("Those candidates are no longer in memory — please press Generate again.")
                ctx.data.update(cache["data"])
            else:
                progress("input", 0.0, "Reading sketch…")
                self._stage(ctx, "s1_input", s1_input.run)
                progress("understand", 0.0, "Understanding sketch…")
                self._stage(ctx, "s2_understand", s2_understand.run, n, self.cfg.get("object_conf_tau"))
                self._generate_with_ladder(ctx, n, seed)
                self._cache = {"run_dir": str(run_dir), "data": {k: v for k, v in ctx.data.items() if k != "siglip"}}
            extra.update(self._reconstruct_loop(ctx, seed))
            extra.update(self._summary(ctx))
            res = self._result(ctx, ok=True)
        except BlankSketchError as e:
            res = Result(False, run_dir, message=str(e))
        except PipelineError as e:
            res = Result(False, run_dir, message=str(e))
            extra["error"] = {"stage": e.stage, "message": str(e), "detail": e.detail}
        except Exception as e:  # noqa: BLE001 - never show a stack trace in the UI
            res = Result(False, run_dir, message=f"Something went wrong ({type(e).__name__}). Details are in run.json.")
            extra["error"] = {"message": repr(e), "traceback": traceback.format_exc()[-4000:]}
        finally:
            vram.free_cuda()
        try:
            res.run_json = write_run_json(ctx, extra)
        except Exception:  # noqa: BLE001
            pass
        if not res.candidates and "candidates" in ctx.data:
            res.candidates = self._gallery(ctx)
        return res

    # ---- S3 with the OOM ladder: free & retry -> fewer candidates -> lite generator -> fail clearly
    def _generate_with_ladder(self, ctx, n, seed):
        scales = self.cfg["controlnet_scales"]
        ladder = [(ctx.profile, n), (ctx.profile, max(2, n // 2))]
        if ctx.profile == "balanced":
            ladder.append(("lite", 2))
        last = None
        for prof, k in ladder:
            try:
                ctx.progress("generate", 0.0, f"Generating {k} candidates ({prof})…")
                self._stage(ctx, "s3_generate", s3_generate.run, prof, k, scales, seed)
                if prof != ctx.profile or k != n:
                    ctx.tel.fallbacks.append(f"s3 ladder -> profile={prof} n={k}")
                ctx.data["gen_profile"] = prof
                return
            except Exception as e:  # noqa: BLE001
                if "out of memory" not in str(e).lower() and not isinstance(e, OOMError):
                    raise
                last = e
                ctx.tel.warnings.append(f"oom_s3_{prof}_{k}")
                vram.free_cuda()
        raise OOMError("Ran out of GPU memory while generating images. Try the Fast preset or close other GPU apps.",
                       stage="s3", detail=repr(last))

    # ---- S4..S8 with at most one retry inside retry_budget_s (spec §10.2)
    def _reconstruct_loop(self, ctx, seed) -> dict:
        th = self.cfg["thresholds"]
        rank = ctx.data["rank"]
        idx = ctx.req.selected_candidate if ctx.req.selected_candidate is not None else rank[0]
        best = None
        for attempt in range(2):
            self._stage(ctx, "s4_prepare", s4_prepare.run, idx)
            self._stage(ctx, "s5_reconstruct", s5_reconstruct.run, ctx.req.quality, seed + attempt, attempt)
            ctx.progress("cleanup", 0.0, "Cleaning mesh…")
            self._stage(ctx, "s6_cleanup", s6_cleanup.run, self.cfg["max_viewer_faces"], self.cfg["max_render_faces"])
            ctx.progress("export", 0.0, "Exporting GLB/OBJ…")
            self._stage(ctx, "s7_export", s7_export.run)
            ctx.progress("verify", 0.0, "Verifying…")
            ver = self._stage(ctx, "s8_verify", s8_verify.run, th["mirror_margin"])
            rec = {"attempt": attempt, "candidate": idx, "backend": ctx.data["backend"], "seed": seed + attempt,
                   **{k: ver[k] for k in ("recon_consistency", "sketch_fidelity")}, "valid": ver["validation"]["ok"]}
            ctx.tel.attempts.append(rec)
            score = (ver["validation"]["ok"], ver["sketch_fidelity"] + ver["recon_consistency"])
            if best is None or score > best[0]:
                best = (score, ver, {k: ctx.data[k] for k in ("glb", "obj_zip", "tier", "backend", "selected", "cleanup", "raw")})
            low_recon = ver["recon_consistency"] < th["recon_consistency"]
            sk_th = th["sketch_fidelity"] if ctx.data["silhouette"] is not None else th.get("sketch_fidelity_open", th["sketch_fidelity"])
            low_sketch = ver["sketch_fidelity"] < sk_th
            if attempt == 1 or ctx.elapsed() > self.cfg["retry_budget_s"] or not (low_recon or low_sketch) \
                    or ctx.req.selected_candidate is not None:
                break
            if low_recon:
                ctx.tel.fallbacks.append("retry: low recon_consistency -> new seed, same candidate")
                # keep idx, new seed
            else:
                nxt = [i for i in rank if i != idx]
                if not nxt:
                    break
                ctx.tel.fallbacks.append("retry: low sketch_fidelity -> next-best candidate")
                idx = nxt[0]
            # move this attempt's outputs aside so the retry does not overwrite the kept best
            for k in ("glb", "obj_zip"):
                p = ctx.data[k]
                p.rename(p.with_name(f"attempt{attempt}_{p.name}"))
                if best[2][k] == p:
                    best[2][k] = p.with_name(f"attempt{attempt}_{p.name}")
        _, ver, keep = best
        ctx.data.update(keep)
        if not ver["validation"]["ok"]:
            raise PipelineError("The exported 3D file failed validation: " + ", ".join(ver["validation"].get("problems", [])),
                                stage="s8")
        return ver

    def _gallery(self, ctx):
        out = []
        for i in ctx.data.get("rank", []):
            c = ctx.data["candidates"][i]
            cap = f"#{i} score {c['score']:.2f}" + (" (hedge)" if c["hedge"] else "") + \
                  (f" — rejected: {c['matte']['reject']}" if "reject" in c["matte"] else "")
            out.append((str(ctx.run_dir / "candidates" / f"cand_{i}.png"), cap))
        return out

    def _summary(self, ctx) -> dict:
        c = ctx.data["candidates"]
        return {"object": ctx.data.get("object"), "object_conf": ctx.data.get("object_conf"),
                "object_top5": ctx.data.get("object_top5"), "closed_sketch": ctx.data["silhouette"] is not None,
                "prompts": {"positive": ctx.data["prompts"].positive, "negative": ctx.data["prompts"].negative},
                "candidate_scores": [{"index": x["index"], "score": round(x["score"], 4), "seed": x["seed"],
                                      "controlnet_scale": x["scale"], "hedge": x["hedge"], "matte": x["matte"],
                                      "terms": x["terms"]} for x in c],
                "selected_candidate": ctx.data["selected"], "backend": ctx.data["backend"],
                "backend_meta": getattr(ctx.data.get("raw"), "meta", None),
                "gen_profile": ctx.data.get("gen_profile"), "s3_timing": ctx.data.get("s3_timing"), "tier": ctx.data["tier"],
                "material": ctx.data.get("material"), "cleanup": ctx.data.get("cleanup"),
                "files": {k: {"path": str(ctx.data[k]), "bytes": Path(ctx.data[k]).stat().st_size}
                          for k in ("glb", "obj_zip")},
                "notice": ctx.data.get("notice")}

    def _result(self, ctx, ok) -> Result:
        last = ctx.tel.attempts[-1] if ctx.tel.attempts else {}
        best = max(ctx.tel.attempts, key=lambda a: (a["valid"], a["sketch_fidelity"] + a["recon_consistency"])) \
            if ctx.tel.attempts else last
        badges = {"object": ctx.data.get("object"), "backend": ctx.data.get("backend"), "profile": ctx.profile,
                  "seconds": round(ctx.elapsed(), 1), "sketch_match": best.get("sketch_fidelity"),
                  "sketch_match_kind": "silhouette" if ctx.data["silhouette"] is not None else "stroke",
                  "tier": ctx.data.get("tier"), "warnings": list(ctx.tel.warnings), "notice": ctx.data.get("notice"),
                  "seed": ctx.req.seed, "fallbacks": list(ctx.tel.fallbacks)}
        return Result(ok, ctx.run_dir, ctx.data.get("glb"), ctx.data.get("obj_zip"), None, self._gallery(ctx),
                      ctx.data.get("selected"), badges, "Done")
