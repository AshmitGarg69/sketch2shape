"""Run request/context/result and telemetry (spec §2, §10.4)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Request:
    image: np.ndarray                    # HxWx{3,4} uint8 as received
    source: str = "upload"               # "canvas" | "upload"
    prompt: str = ""
    object_override: str = ""            # editable "Detected object" box
    material: str = "Auto"
    quality: str = "balanced"            # fast | balanced | best
    viewpoint: str = "Auto"
    seed: int | None = None
    out_root: str = "outputs"
    selected_candidate: int | None = None  # re-run S4-S8 on a chosen candidate
    reuse_run_dir: str | None = None


@dataclass
class Telemetry:
    stages: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    fallbacks: list = field(default_factory=list)
    attempts: list = field(default_factory=list)

    def stage(self, name: str, seconds: float, vram_peak_gb: float, rss_gb: float, **extra):
        self.stages[name] = {"seconds": round(seconds, 2), "vram_peak_gb": round(vram_peak_gb, 2),
                             "rss_gb": round(rss_gb, 2), **extra}


@dataclass
class Context:
    req: Request
    run_dir: Path
    progress: Callable[[str, float, str], None]
    cancel: threading.Event
    profile: str | None = None
    gpu: Any = None
    tel: Telemetry = field(default_factory=Telemetry)
    data: dict = field(default_factory=dict)   # stage outputs (arrays, paths, scores)
    t0: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        return time.time() - self.t0


def new_run_dir(out_root: str, image: np.ndarray) -> Path:
    h = hashlib.sha1(np.ascontiguousarray(image).tobytes()).hexdigest()[:8]
    d = Path(out_root) / f"{time.strftime('%Y%m%d_%H%M%S')}_{h}"
    for sub in ("input", "candidates", "mesh", "raw"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def _git(cwd: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(cwd), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def config_hash() -> str:
    h = hashlib.sha1()
    for p in sorted((ROOT / "config").glob("*")):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def environment_facts(gpu) -> dict:
    facts = {"platform": platform.platform(), "python": platform.python_version(),
             "git_commit": _git(ROOT), "config_hash": config_hash(),
             "third_party": {p.name: _git(p) for p in (ROOT / "third_party").glob("*") if p.is_dir()}}
    if gpu is not None:
        facts["gpu"] = {"name": gpu.name, "total_gb": round(gpu.total_gb, 2), "compute_cap": list(gpu.compute_cap)}
    try:
        import torch

        facts["torch"] = torch.__version__
        facts["cuda"] = torch.version.cuda
    except Exception:  # noqa: BLE001
        pass
    try:
        facts["driver"] = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                         capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return facts


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def write_run_json(ctx: Context, extra: dict) -> Path:
    req = {k: v for k, v in asdict(ctx.req).items() if k != "image"}
    rec = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "request": req, "profile": ctx.profile,
           "environment": environment_facts(ctx.gpu), "stages": ctx.tel.stages, "warnings": ctx.tel.warnings,
           "fallbacks": ctx.tel.fallbacks, "attempts": ctx.tel.attempts,
           "total_seconds": round(ctx.elapsed(), 2), **extra}
    p = ctx.run_dir / "run.json"
    p.write_text(json.dumps(rec, indent=2, default=_jsonable))
    return p


def rss_gb() -> float:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / 2**30
    except Exception:  # noqa: BLE001
        return 0.0
