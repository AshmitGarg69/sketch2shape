"""Shared SigLIP model (spec §4.2 / §5.3): zero-shot object detection + candidate semantic scores.
Loaded once, freed after Stage 3. Falls back to CLIP; if both fail the pipeline continues with 'object'."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ..core import weights
from ..core.vram import free_cuda

VOCAB = Path(__file__).resolve().parents[3] / "config" / "object_vocab.txt"
TEMPLATES = ["a hand-drawn sketch of a {}", "a line drawing of a {}", "a simple doodle of a {}"]


class SharedSigLIP:
    def __init__(self, device: str = "cuda"):
        import torch
        from transformers import AutoModel, AutoProcessor

        self.torch, self.device = torch, device
        src = weights.path("siglip") if weights.present("siglip") else "google/siglip-base-patch16-256"
        self.model = AutoModel.from_pretrained(src, torch_dtype=torch.float16).to(device).eval()
        self.proc = AutoProcessor.from_pretrained(src)
        self.vocab = [w.strip() for w in VOCAB.read_text().splitlines() if w.strip()]
        self._text_cache = None

    def _text_emb(self, texts: list[str]):
        t = self.proc(text=texts, padding="max_length", truncation=True, max_length=64, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            e = self.model.get_text_features(**t)
        return e / e.norm(dim=-1, keepdim=True)

    def _img_emb(self, images: list[Image.Image]):
        x = self.proc(images=images, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            e = self.model.get_image_features(pixel_values=x["pixel_values"].half())
        return e / e.norm(dim=-1, keepdim=True)

    def detect(self, sketch_rgb: np.ndarray) -> tuple[str, float, list[tuple[str, float]]]:
        if self._text_cache is None:
            embs = [self._text_emb([t.format(w) for w in self.vocab]) for t in TEMPLATES]
            m = sum(embs) / len(embs)
            self._text_cache = m / m.norm(dim=-1, keepdim=True)
        img = self._img_emb([Image.fromarray(sketch_rgb)])
        logits = (img @ self._text_cache.T).float()[0] * 10.0
        p = logits.softmax(-1).cpu().numpy()
        top = np.argsort(-p)[:5]
        return self.vocab[top[0]], float(p[top[0]]), [(self.vocab[i], float(p[i])) for i in top]

    def semantic(self, images: list[Image.Image], prompt: str) -> list[float]:
        """Cosine similarity of masked candidates vs the composed prompt, as a DAMPED relative score in [0,1].
        (Min-max over candidates turned a 0.01 cosine gap into 0 vs 1 with N=2 and outvoted the shape terms.)"""
        t = self._text_emb([prompt])
        i = self._img_emb(images)
        sims = (i @ t.T).float().cpu().numpy()[:, 0]
        # 0.5 = average candidate; ±0.1 cosine from the mean saturates. Gaps of ~0.01 move the term by only ~0.05.
        return [float(np.clip(0.5 + (s - sims.mean()) / 0.2, 0.0, 1.0)) for s in sims]

    def close(self):
        del self.model
        free_cuda()
