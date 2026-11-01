"""GPU detection, profile choice and dtype policy (spec §0 rule 8, §1).

Never imports torch at module import time: the CLI `doctor` and tests must run without it.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class GpuInfo:
    cuda: bool
    name: str = ""
    total_gb: float = 0.0
    free_gb: float = 0.0
    compute_cap: tuple[int, int] = (0, 0)

    @property
    def bf16_ok(self) -> bool:
        return self.compute_cap >= (8, 0)


def detect() -> GpuInfo:
    try:
        import torch

        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info(0)
            return GpuInfo(True, torch.cuda.get_device_name(0), total / 2**30, free / 2**30,
                           torch.cuda.get_device_capability(0))
    except Exception:  # noqa: BLE001 - fall through to nvidia-smi
        pass
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.free,compute_cap",
                              "--format=csv,noheader,nounits", "-i", "0"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        name, total, free, cap = [x.strip() for x in out.split(",")]
        major, minor = cap.split(".")
        return GpuInfo(True, name, float(total) / 1024, float(free) / 1024, (int(major), int(minor)))
    except Exception:  # noqa: BLE001
        return GpuInfo(False)


def torch_dtype(info: GpuInfo):
    import torch

    return torch.bfloat16 if info.bf16_ok else torch.float16


def pick_profile(info: GpuInfo, profiles: dict) -> str | None:
    """profiles: {name: {min_vram_gb: float}} from config/profiles.yaml; highest requirement that fits wins."""
    if not info.cuda:
        return None
    fitting = [(p["min_vram_gb"], n) for n, p in profiles.items() if info.total_gb >= p["min_vram_gb"]]
    return max(fitting)[1] if fitting else None


def free_cuda(reset_peak: bool = False):
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if reset_peak:  # only at stage boundaries, so models freed mid-stage don't erase the stage's peak
                torch.cuda.reset_peak_memory_stats()
    except Exception:  # noqa: BLE001
        pass


def peak_gb() -> float:
    try:
        import torch

        return torch.cuda.max_memory_allocated() / 2**30 if torch.cuda.is_available() else 0.0
    except Exception:  # noqa: BLE001
        return 0.0
