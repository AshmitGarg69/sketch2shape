"""Foreground isolation (spec §5.2): BiRefNet primary, rembg u2net fallback, then alpha cleanup.
Every optional loader is behind a broad except (rule 9)."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from ..core import weights
from ..core.vram import free_cuda


class Matter:
    def __init__(self, device: str = "cuda", log=print):
        self.device, self.kind, self.log = device, None, log
        try:
            import torch
            from transformers import AutoModelForImageSegmentation

            src = weights.path("birefnet") if weights.present("birefnet") else "ZhengPeng7/BiRefNet"
            m = AutoModelForImageSegmentation.from_pretrained(str(src), trust_remote_code=True)
            self.model = m.to(device).eval().half()
            self.torch, self.kind = torch, "birefnet"
        except Exception as e:  # noqa: BLE001
            log(f"BiRefNet unavailable ({type(e).__name__}: {e}); falling back to rembg")
            try:
                import rembg

                self.session, self.kind = rembg.new_session("u2net"), "rembg"
            except Exception as e2:  # noqa: BLE001
                log(f"rembg unavailable too ({e2}); using background-colour keying")
                self.kind = "key"

    def alpha(self, img: Image.Image) -> np.ndarray:
        rgb = img.convert("RGB")
        if self.kind == "birefnet":
            from torchvision import transforms

            tf = transforms.Compose([transforms.Resize((1024, 1024)), transforms.ToTensor(),
                                     transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
            x = tf(rgb).unsqueeze(0).to(self.device).half()
            with self.torch.no_grad():
                pred = self.model(x)[-1].sigmoid().float().cpu()[0, 0].numpy()
            a = cv2.resize(pred, rgb.size, interpolation=cv2.INTER_LINEAR)
            return (np.clip(a, 0, 1) * 255).astype(np.uint8)
        if self.kind == "rembg":
            import rembg

            return np.asarray(rembg.remove(rgb, session=self.session, only_mask=True).convert("L"))
        return key_background(np.asarray(rgb))

    def close(self):
        if self.kind == "birefnet":
            del self.model
            free_cuda()


def key_background(rgb: np.ndarray, tol: float = 18.0) -> np.ndarray:
    """Last-resort matte: pixels close to the border's median colour are background."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(np.float32)
    bg = np.median(border, axis=0)
    d = np.linalg.norm(rgb.astype(np.float32) - bg, axis=2)
    return np.where(d > tol, 255, 0).astype(np.uint8)


def local_background(rgb: np.ndarray, fg: np.ndarray, scale: int = 4) -> np.ndarray:
    """Background colour behind/around the object, estimated by inpainting the given region at low res
    (the region must cover everything that might be object, so the estimate comes only from true background)."""
    H, W = fg.shape
    small = cv2.resize(rgb, (W // scale, H // scale), interpolation=cv2.INTER_AREA)
    m = cv2.resize(fg.astype(np.uint8), (W // scale, H // scale), interpolation=cv2.INTER_NEAREST)
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    bg = cv2.inpaint(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), m * 255, 9, cv2.INPAINT_TELEA)
    bg = cv2.GaussianBlur(bg, (0, 0), 3)
    return cv2.cvtColor(cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2RGB)


def recover_with_sketch(rgb: np.ndarray, alpha: np.ndarray, silhouette: np.ndarray | None,
                        lum_up: float = 14.0, chroma: float = 16.0, dilate_frac: float = 0.02,
                        min_part_frac: float = 0.01) -> tuple[np.ndarray, float]:
    """Sketch-guided matte recovery. Salient-object matting drops "supports" (saucers, bases, plinths) that the user
    explicitly drew. The ControlNet canvas IS the normalised stroke canvas, so the user's silhouette is pixel-aligned
    with every candidate. Inside the (slightly dilated) silhouette, a pixel is recovered as object only if, relative
    to the LOCAL background estimate, it is brighter (> lum_up) or differs in hue/chroma (> chroma). Pure darkening is
    a shadow and is rejected. Holes the matting model itself enclosed (handle openings) are protected; thin rings and
    small fragments are removed. Returns (alpha_u8, fraction of frame added)."""
    if silhouette is None:
        return alpha, 0.0
    from .silhouette import fill_holes

    H, W = alpha.shape
    fg = alpha > 127
    sil = cv2.resize(silhouette.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
    r = max(1, int(round(dilate_frac * max(H, W))))
    sil = cv2.dilate(sil, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
    d = rgb.astype(np.float32) - local_background(rgb, fg | sil).astype(np.float32)
    lum = d.mean(axis=2)
    chrom = np.linalg.norm(d - lum[..., None], axis=2)
    candidate = (lum > lum_up) | (chrom > chroma)
    protected = fill_holes(fg) & ~fg
    add = candidate & sil & ~fg & ~protected
    k = max(3, int(round(0.012 * max(H, W))) | 1)               # opening removes rim halos / thin rings
    add = cv2.morphologyEx(add.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(add.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    min_area = min_part_frac * max(fg.sum(), 1)
    near_fg = cv2.dilate(fg.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    for c in range(1, n):
        comp = lab == c
        keep[c] = stats[c, cv2.CC_STAT_AREA] >= min_area and (comp & near_fg).any()   # real part, attached to object
    add = keep[lab]
    if not add.any():
        return alpha, 0.0
    return np.maximum(alpha, add.astype(np.uint8) * 255), float(add.mean())


def clean_alpha(a: np.ndarray, thresh: int = 128) -> tuple[np.ndarray, dict]:
    """threshold -> largest component -> small-hole fill -> 1-px feather. Returns (alpha_u8, report)."""
    fg = a >= thresh
    rep = {"fg_frac": float(fg.mean())}
    if not fg.any():
        rep["reject"] = "empty matte"
        return np.zeros_like(a), rep
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg.astype(np.uint8), connectivity=8)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    fg = lab == big
    inv = (~fg).astype(np.uint8)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    small = max(16, int(fg.sum() * 0.002))
    for i in range(1, n2):
        x, y, w, h, area = st2[i]
        touches = x == 0 or y == 0 or x + w == fg.shape[1] or y + h == fg.shape[0]
        if not touches and area < small:
            fg[lab2 == i] = True
    soft = cv2.GaussianBlur(fg.astype(np.float32), (3, 3), 0.7)
    out = (soft * 255).astype(np.uint8)
    frac = float(fg.mean())
    border = bool(np.concatenate([fg[0], fg[-1], fg[:, 0], fg[:, -1]]).any())
    rep.update(fg_frac=frac, touches_border=border)
    if frac < 0.05 or frac > 0.95:
        rep["reject"] = f"foreground {frac:.0%} of frame"
    elif border:
        rep["reject"] = "object touches the image border"
    return out, rep
