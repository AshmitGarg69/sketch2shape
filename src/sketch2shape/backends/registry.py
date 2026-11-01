"""Backend registry: ordered fallback chain by quality preset, VRAM and calibration flags (spec §7.1/§7.2)."""
from __future__ import annotations

from pathlib import Path

import yaml

from ..core.subproc import REPO_ROOT
from .base import SubprocessBackend

QUALITY_LADDER = ["best", "balanced", "fast"]

PRESET_ORDER = {
    "fast": ["triposr", "instantmesh"],
    "balanced": ["instantmesh", "triposr"],
    "best": ["instantmesh", "triposr"],
}


def load_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or REPO_ROOT / "config" / "backends.yaml").read_text())["backends"]


class BackendRegistry:
    def __init__(self, cfg: dict | None = None):
        cfg = cfg if cfg is not None else load_config()
        self.backends = {n: SubprocessBackend(n, c) for n, c in cfg.items() if c.get("enabled", True)}

    def chain(self, preset: str, free_vram_gb: float | None = None, margin_gb: float = 0.5) -> list[tuple[SubprocessBackend, str]]:
        """Available (backend, quality) pairs for this preset, preferred first; ungated before gated. A backend that does
        not fit free VRAM at the requested quality is stepped down to the best lower quality that fits (measured
        per-quality VRAM in backends.yaml), so a 6 GB card still gets TripoSR-fast."""
        order = PRESET_ORDER.get(preset, PRESET_ORDER["balanced"])
        names = [n for n in order if n in self.backends] + [n for n in self.backends if n not in order]
        ladder = QUALITY_LADDER[QUALITY_LADDER.index(preset):] if preset in QUALITY_LADDER else ["balanced", "fast"]
        out = []
        for n in sorted(names, key=lambda n: (bool(self.backends[n].cfg.get("gated")), names.index(n))):
            b = self.backends[n]
            if not b.is_available():
                continue
            for q in ladder:
                need = b.vram_for(q)
                if free_vram_gb is None or not need or need <= free_vram_gb - margin_gb:
                    out.append((b, q))
                    break
        return out

    def status(self) -> dict:
        return {n: (b.unavailable_reason() or "ok") for n, b in self.backends.items()}
