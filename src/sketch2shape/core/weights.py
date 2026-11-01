"""Weights: pinned manifest, local paths, Hub-only download with a disk guard (spec §13, rules 7/10/13)."""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def weights_root() -> Path:
    return Path(os.environ.get("S2S_WEIGHTS", ROOT / "weights"))


@lru_cache(maxsize=1)
def manifest() -> dict:
    return yaml.safe_load((ROOT / "config" / "weights_manifest.yaml").read_text())["models"]


@lru_cache(maxsize=1)
def backend_cache() -> dict:
    return yaml.safe_load((ROOT / "config" / "weights_manifest.yaml").read_text()).get("backend_cache", {})


def path(name: str) -> Path:
    return weights_root() / name


def present(name: str) -> bool:
    p = path(name)
    return p.exists() and any(p.rglob("*.safetensors"))


def for_profile(profile: str) -> dict:
    return {k: v for k, v in manifest().items() if profile in v.get("profile", [])}


def download(profile: str, backends: list[str], extras: list[str] = (), log=print, margin_gb: float = 10.0) -> dict:
    from huggingface_hub import snapshot_download

    items = {k: v for k, v in for_profile(profile).items() if not v.get("gated") or k in extras}
    skipped = [k for k, v in for_profile(profile).items() if v.get("gated") and k not in extras]
    for k in skipped:
        log(f"skip gated weight '{k}' (opt-in: EXTRAS={k} with HF_TOKEN set)")
    need = sum(v.get("expected_gb", 1) for k, v in items.items() if not present(k))
    root = weights_root()
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free / 2**30
    log(f"profile={profile}: {len(items)} models, ~{need:.1f} GB to fetch, {free:.1f} GB free")
    if free < need + margin_gb:
        raise SystemExit(f"Not enough disk: need ~{need:.1f} GB + {margin_gb:.0f} GB margin, have {free:.1f} GB free.")
    for k, v in items.items():
        log(f"  {k}: {v['repo_id']}@{v['revision'][:8]} (~{v.get('expected_gb', '?')} GB)")
        snapshot_download(v["repo_id"], revision=v["revision"], allow_patterns=v.get("allow_patterns"),
                          local_dir=str(path(k)))
    hf_home = Path(os.environ.get("HF_HOME", root / "hf"))
    for b in backends:
        for e in backend_cache().get(b, []):
            log(f"  [{b}] {e['repo_id']}@{e['revision'][:8]} -> {hf_home}")
            snapshot_download(e["repo_id"], revision=e["revision"], cache_dir=str(hf_home / "hub"),
                              allow_patterns=e.get("allow_patterns"))
    return {"downloaded": list(items), "skipped_gated": skipped}
