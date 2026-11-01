"""Prompt composer (spec §4.3): allowlist + hedge candidate. No VLM, no text-to-text conflict gate."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parents[3] / "config"

SUFFIX = ("single object, centered, full object visible, studio product render, soft diffuse lighting, "
          "neutral light-grey seamless background, high detail, sharp focus")
NEGATIVE = ("text, watermark, logo, multiple objects, cropped, out of frame, hard shadows, cast shadow, floor reflection, "
            "ground plane, motion blur, flat illustration, cartoon outline, low quality")
VIEW_PHRASES = {
    "Auto": None,
    "front": "front view",
    "side profile": "side profile view",
    "back": "back view",
    "top-down": "top-down view",
    "front three-quarter": "front three-quarter view",
}
MATERIAL_WORD = {"Wood": "wooden", "Metal": "metal", "Plastic": "plastic", "Ceramic": "ceramic", "Glass": "glass",
                 "Fabric": "fabric", "Leather": "leather", "Stone": "stone"}


@dataclass
class PromptSet:
    positive: list[str]      # one per candidate
    negative: str
    hedge_index: int | None  # candidate that uses the allowlist-only prompt
    material: str            # resolved material key (for PBR scalars)
    user_text: str


def _load(name):
    return yaml.safe_load((CFG / name).read_text())


def allowlisted(text: str, allow: dict | None = None) -> str:
    allow = allow or _load("prompt_allowlist.yaml")
    words = {w.lower() for group in allow.values() for w in group}
    toks = re.findall(r"[A-Za-z][A-Za-z\-]*", text or "")
    kept, seen = [], set()
    for t in toks:
        tl = t.lower()
        if tl in words and tl not in seen:
            kept.append(tl)
            seen.add(tl)
    return " ".join(kept)


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip(" ,")
    return s[:300]


def compose(obj: str, user_text: str = "", *, material_preset: str = "Auto", viewpoint: str = "Auto",
            n: int = 4) -> PromptSet:
    mats = _load("materials.yaml")
    obj = _clean(obj) or "object"
    entry = mats["objects"].get(obj.lower(), mats["default"])
    material = entry["material"] if material_preset == "Auto" else material_preset.lower()
    mat_word = MATERIAL_WORD.get(material_preset)
    view = VIEW_PHRASES.get(viewpoint)
    user_text = _clean(user_text)

    def build(desc: str) -> str:
        parts = [obj, desc]
        if mat_word and mat_word not in desc.lower():
            parts.append(f"made of {mat_word}" if mat_word != "wooden" else "wooden")
        if view:
            parts.append(view)
        parts.append(SUFFIX)
        return ", ".join(p for p in parts if p)

    full = build(user_text if user_text else entry["palette"])
    if user_text:
        hedge_desc = allowlisted(user_text) or entry["palette"]
        hedge = build(hedge_desc)
    else:
        hedge = full  # blank prompt: the hedge slot is simply another seed
    if n < 2:
        return PromptSet([full], NEGATIVE, None, material, user_text)
    return PromptSet([full] * (n - 1) + [hedge], NEGATIVE, n - 1, material, user_text)
