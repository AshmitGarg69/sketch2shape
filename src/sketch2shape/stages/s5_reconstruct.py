"""S5 reconstruction via process-isolated backends with the OOM/fallback ladder (spec §7)."""
from __future__ import annotations

from ..backends.registry import BackendRegistry
from ..core.errors import BackendUnavailable, OOMError, PipelineError
from ..core.vram import detect


def run(ctx, quality: str, seed: int, attempt: int = 0):
    reg = BackendRegistry()
    free = detect().free_gb
    chain = reg.chain(quality, free_vram_gb=free)
    if not chain:
        raise BackendUnavailable("No calibrated 3D backend is available on this machine. "
                                 f"Status: {reg.status()}", stage="s5")
    last = None
    for i, (b, q) in enumerate(chain):
        if q != quality:
            ctx.tel.fallbacks.append(f"{b.name}: quality {quality} -> {q} to fit {free:.1f} GB free VRAM")
        ctx.progress("reconstruct", 0.05, f"Reconstructing with {b.name} ({q})…")
        out = ctx.run_dir / "raw" / f"{b.name}_{attempt}"
        try:
            raw = b.reconstruct(ctx.data["selected_rgba"], quality=q, seed=seed, out_dir=out,
                                on_line=lambda ln: ctx.progress("reconstruct", 0.5, ln[:120]) if ln.startswith("S2S ") else None,
                                cancel=ctx.cancel)
            ctx.data.update(raw=raw, backend=b.name, backend_cfg=b.cfg, backend_quality=q)
            return raw
        except (OOMError, BackendUnavailable, PipelineError) as e:
            last = e
            ctx.tel.fallbacks.append(f"{b.name}: {e}")
            if isinstance(e, OOMError):
                ctx.tel.warnings.append(f"oom_{b.name}")
            if ctx.cancel.is_set():
                raise
    raise last or PipelineError("All 3D backends failed", stage="s5")
