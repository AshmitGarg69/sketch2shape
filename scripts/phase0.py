"""Phase-0 measurement harness (spec §14).

Runs a backend's OWN entry point (argv given after `--`) and records: host facts, wall time,
peak VRAM (nvidia-smi polling), peak system RAM of the process tree, runtime network fetches
(HF cache diff, online run then a HF_HUB_OFFLINE=1 re-run) and output-mesh validity.

    python scripts/phase0.py --backend triposr --image <img> --out docs/phase0/<host>_triposr.json \
        --cwd third_party/TripoSR --mesh-glob 'out/**/mesh.*' -- envs/triposr/bin/python run.py <img> ...

Only stdlib + psutil + trimesh + numpy are needed in the calling interpreter.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


def sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def host_facts(work: str) -> dict:
    import psutil

    gpu = sh("nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader")
    return {
        "platform": platform.platform(),
        "python_parent": sys.version.split()[0],
        "gpu": gpu,
        "gpu_count": len([g for g in gpu.splitlines() if g.strip()]),
        "nvcc": sh("nvcc --version | tail -2") or None,
        "ram_total_gb": round(psutil.virtual_memory().total / 2**30, 2),
        "ram_avail_gb": round(psutil.virtual_memory().available / 2**30, 2),
        "disk_free_gb": round(shutil.disk_usage(work).free / 2**30, 2),
        "cpus": os.cpu_count(),
    }


class Sampler(threading.Thread):
    """Polls GPU memory (nvidia-smi, GPU 0) and RSS of the process tree."""

    def __init__(self, pid: int, period: float = 0.5):
        super().__init__(daemon=True)
        self.pid, self.period = pid, period
        self.vram_peak_mb = 0.0
        self.rss_peak_gb = 0.0
        self.stop = threading.Event()

    def run(self):
        import psutil

        base = self._vram()
        while not self.stop.is_set():
            self.vram_peak_mb = max(self.vram_peak_mb, self._vram() - base)
            try:
                p = psutil.Process(self.pid)
                rss = sum(c.memory_info().rss for c in [p, *p.children(recursive=True)])
                self.rss_peak_gb = max(self.rss_peak_gb, rss / 2**30)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(self.period)

    @staticmethod
    def _vram() -> float:
        out = sh("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0")
        try:
            return float(out.splitlines()[0])
        except Exception:  # noqa: BLE001
            return 0.0


def cache_listing(roots: list[str]) -> set[str]:
    files = set()
    for r in roots:
        if r and os.path.isdir(r):
            for p in Path(r).rglob("*"):
                if p.is_file():
                    files.add(str(p))
    return files


def run_once(argv, cwd, env, log_path, timeout):
    t0 = time.time()
    with open(log_path, "w") as log:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        s = Sampler(proc.pid)
        s.start()
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = "timeout"
        s.stop.set()
        s.join()
    tail = Path(log_path).read_text(errors="replace").splitlines()[-40:]
    return {"rc": rc, "seconds": round(time.time() - t0, 2), "vram_peak_gb": round(s.vram_peak_mb / 1024, 2),
            "rss_peak_gb": round(s.rss_peak_gb, 2), "log_tail": tail}


def validate_mesh(path: str) -> dict:
    try:
        import numpy as np
        import trimesh

        m = trimesh.load(path, force="mesh", process=False)
        v, f = np.asarray(m.vertices), np.asarray(m.faces)
        ext = (v.max(0) - v.min(0)).tolist() if len(v) else None
        vis = getattr(m, "visual", None)
        return {"path": path, "ok": bool(len(v) and len(f) and not np.isnan(v).any() and min(ext) > 0),
                "vertices": int(len(v)), "faces": int(len(f)), "extent": ext,
                "visual": type(vis).__name__ if vis is not None else None,
                "has_uv": bool(getattr(vis, "uv", None) is not None),
                "bytes": os.path.getsize(path)}
    except Exception as e:  # noqa: BLE001
        return {"path": path, "ok": False, "error": repr(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--mesh-glob", required=True, help="glob (relative to --cwd) for produced meshes")
    ap.add_argument("--label", default="default")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--skip-offline", action="store_true")
    ap.add_argument("--extra", default="{}", help="JSON merged into the record (env build time/size etc.)")
    ap.add_argument("argv", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    argv = a.argv[1:] if a.argv and a.argv[0] == "--" else a.argv

    env = dict(os.environ, PYTHONUNBUFFERED="1", CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES", "0"))
    roots = [env.get("HF_HOME", ""), env.get("TORCH_HOME", ""), env.get("U2NET_HOME", ""),
             os.path.expanduser("~/.u2net"), os.path.expanduser("~/.cache")]
    log_dir = Path(a.out).with_suffix("")
    log_dir.mkdir(parents=True, exist_ok=True)

    for old in glob.glob(os.path.join(a.cwd, a.mesh_glob), recursive=True):
        os.remove(old)
    before = cache_listing(roots)
    online = run_once(argv, a.cwd, env, str(log_dir / f"{a.label}_online.log"), a.timeout)
    fetched = sorted(cache_listing(roots) - before)
    meshes = sorted(glob.glob(os.path.join(a.cwd, a.mesh_glob), recursive=True))
    online["meshes"] = [validate_mesh(m) for m in meshes]

    offline = None
    if not a.skip_offline and online["rc"] == 0:
        offline = run_once(argv, a.cwd, dict(env, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"),
                           str(log_dir / f"{a.label}_offline.log"), a.timeout)
        offline.pop("log_tail") if offline["rc"] == 0 else None

    rec = {"backend": a.backend, "label": a.label, "image": a.image, "argv": argv,
           "host": host_facts(a.cwd), "online": online, "offline_rerun": offline,
           "network_fetches": [f for f in fetched if not f.endswith((".lock", ".incomplete"))][:200],
           "passed": online["rc"] == 0 and any(m.get("ok") for m in online["meshes"]),
           **json.loads(a.extra)}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(rec, indent=2))
    print(json.dumps({k: rec[k] for k in ("backend", "label", "passed")} |
                     {"seconds": online["seconds"], "vram_peak_gb": online["vram_peak_gb"]}))


if __name__ == "__main__":
    main()
