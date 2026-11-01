"""Reconstructor protocol + the generic subprocess wrapper every shipped backend uses (spec §7.1)."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ..core import subproc
from ..core.errors import BackendUnavailable, OOMError, PipelineError


@dataclass
class RawMesh:
    path: Path
    meta: dict = field(default_factory=dict)
    proc: subproc.ProcResult | None = None


class Reconstructor(Protocol):
    name: str
    min_vram_gb: float
    capabilities: set[str]

    def is_available(self) -> bool: ...

    def reconstruct(self, rgba_path, *, quality, seed, out_dir) -> RawMesh: ...


class SubprocessBackend:
    """Runs `<python> adapters/<name>_run.py --input .. --out .. --quality .. --seed ..` in the backend repo."""

    capabilities: set[str] = {"vertex_color"}

    def __init__(self, name: str, cfg: dict):
        self.name, self.cfg = name, cfg
        self.min_vram_gb = float(cfg.get("min_vram_gb") or cfg["calibration"].get("peak_vram_gb") or 0)
        self.python = subproc.resolve_python(name, cfg["python"])
        self.repo = subproc.REPO_ROOT / cfg["repo"]
        self.runner = subproc.REPO_ROOT / cfg["runner"]
        self._why_not: str | None = None

    def vram_for(self, quality: str) -> float:
        return float((self.cfg.get("vram_gb_by_quality") or {}).get(quality) or self.min_vram_gb or 0)

    @property
    def calibration(self) -> dict:
        return self.cfg.get("calibration", {})

    def unavailable_reason(self) -> str | None:
        self.is_available()
        return self._why_not

    def is_available(self) -> bool:
        cal = self.calibration
        checks = [
            (cal.get("phase0_passed") and cal.get("handedness_checked"), "not calibrated (Phase 0 / handedness)"),
            (self.runner.exists(), f"adapter missing: {self.runner.name}"),
            (self.repo.exists(), f"repo missing: {self.cfg['repo']}"),
        ]
        for ok, why in checks:
            if not ok:
                self._why_not = why
                return False
        hs = subproc.handshake(str(self.python), self.cfg.get("import_check", ""), str(self.repo))
        if not hs or not hs.get("cuda"):
            self._why_not = f"interpreter handshake failed: {self.python}"
            return False
        self._why_not = None
        return True

    def reconstruct(self, rgba_path, *, quality: str, seed: int, out_dir, timeout: float | None = None,
                    on_line: Callable[[str], None] | None = None,
                    cancel: threading.Event | None = None) -> RawMesh:
        if not self.is_available():
            raise BackendUnavailable(f"{self.name} unavailable: {self._why_not}")
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        argv = [self.python, self.runner, "--input", Path(rgba_path).resolve(), "--out", out.resolve(),
                "--quality", quality, "--seed", str(seed)]
        res = subproc.run(argv, cwd=self.repo, env=subproc.backend_env(self.cfg.get("env")),
                          timeout=timeout or self.cfg.get("timeout_s", 900), on_line=on_line, cancel=cancel)
        if res.oom:
            raise OOMError(f"{self.name} ran out of GPU memory", stage="s5", detail="\n".join(res.tail[-10:]))
        meta_p = out / "meta.json"
        if res.rc != 0 or not meta_p.exists():
            why = "timed out" if res.timed_out else "was cancelled" if res.cancelled else f"exited with {res.rc}"
            raise PipelineError(f"3D backend {self.name} {why}", stage="s5", detail="\n".join(res.tail[-15:]))
        meta = json.loads(meta_p.read_text())
        return RawMesh(out / meta["mesh"], meta, res)
