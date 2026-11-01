"""`sketch2shape doctor`: go/no-go table for GPU/CUDA/RAM/disk/deps/weights/backends + recommended profile."""
from __future__ import annotations

import importlib
import shutil

from .core import vram, weights
from .core.pipeline import load_cfg


def main() -> int:
    rows = []
    gpu = vram.detect()
    rows.append(("CUDA GPU", gpu.cuda, f"{gpu.name} {gpu.total_gb:.1f} GB (free {gpu.free_gb:.1f}) sm_{gpu.compute_cap[0]}{gpu.compute_cap[1]}"
                 if gpu.cuda else "No NVIDIA GPU detected — generation needs CUDA (use the Kaggle/Colab notebook)."))
    if gpu.cuda:
        rows.append(("dtype", True, "bf16" if gpu.bf16_ok else "fp16 (compute capability < 8.0)"))
    try:
        import psutil

        vm = psutil.virtual_memory()
        rows.append(("System RAM", vm.total / 2**30 >= 12, f"{vm.total / 2**30:.1f} GB total, {vm.available / 2**30:.1f} GB free"))
    except Exception:  # noqa: BLE001
        pass
    free = shutil.disk_usage(weights.weights_root().parent).free / 2**30
    rows.append(("Disk free", free > 15, f"{free:.1f} GB"))
    for mod in ("torch", "diffusers", "transformers", "gradio", "trimesh", "cv2", "skimage"):
        try:
            m = importlib.import_module(mod)
            rows.append((f"pkg {mod}", True, getattr(m, "__version__", "?")))
        except Exception as e:  # noqa: BLE001
            rows.append((f"pkg {mod}", False, type(e).__name__))
    cfg = load_cfg()
    prof = vram.pick_profile(gpu, cfg["profiles"])
    for name in weights.for_profile(prof or "lite"):
        rows.append((f"weights {name}", weights.present(name), str(weights.path(name))))
    try:
        from .backends.registry import BackendRegistry

        for n, st in BackendRegistry().status().items():
            rows.append((f"backend {n}", st == "ok", st))
    except Exception as e:  # noqa: BLE001
        rows.append(("backends", False, repr(e)))
    w = max(len(r[0]) for r in rows)
    for name, ok, info in rows:
        print(f"{'GO   ' if ok else 'NO-GO'}  {name:<{w}}  {info}")
    print(f"\nRecommended profile: {prof or 'none (needs a CUDA GPU with ≥ 5 GB VRAM)'}")
    return 0
