"""Stage-3 sketch-guided 2D synthesis (spec §5.1). One loader per profile; sequential residency.

balanced: SDXL base fp16 + fp16-fix VAE + xinsir scribble ControlNet + Hyper-SDXL 8-step CFG LoRA (fused), DDIM trailing, 1024 px
lite:     SD1.5 + control_v11p_sd15_scribble, Euler-A, CPU offload, 512 px
Conditioning image = WHITE strokes on BLACK (binary), at the ControlNet's trained resolution.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from ..core import weights
from ..core.vram import GpuInfo, free_cuda, torch_dtype


@dataclass
class GenSettings:
    resolution: int
    steps: int
    guidance: float
    control_guidance_end: float = 0.9


SETTINGS = {
    "balanced": GenSettings(resolution=1024, steps=8, guidance=5.5),
    "lite": GenSettings(resolution=512, steps=20, guidance=5.0),
}


def control_image(stroke_mask: np.ndarray, resolution: int, polarity: str = "white_on_black") -> Image.Image:
    """Binary strokes resized (uniformly; input is square from normalize_strokes) to the trained resolution."""
    m = cv2.resize(stroke_mask.astype(np.uint8) * 255, (resolution, resolution), interpolation=cv2.INTER_AREA)
    m = np.where(m > 64, 255, 0).astype(np.uint8)
    if polarity != "white_on_black":
        m = 255 - m
    return Image.fromarray(np.repeat(m[..., None], 3, axis=2))


class Generator:
    def __init__(self, profile: str, gpu: GpuInfo, hyper_lora_scale: float = 1.0):
        import torch

        self.profile, self.gpu = profile, gpu
        self.dtype = torch_dtype(gpu)
        self.s = SETTINGS[profile]
        self.manifest = weights.manifest()
        if profile == "balanced":
            self._load_sdxl(hyper_lora_scale)
        else:
            self._load_sd15()

    def _load_sdxl(self, lora_scale):
        from diffusers import AutoencoderKL, ControlNetModel, DDIMScheduler, StableDiffusionXLControlNetPipeline

        kw = dict(torch_dtype=self.dtype, use_safetensors=True, low_cpu_mem_usage=True)
        cn = ControlNetModel.from_pretrained(weights.path("controlnet_scribble_sdxl"), **kw)
        vae = AutoencoderKL.from_pretrained(weights.path("sdxl_vae_fp16"), **kw)
        pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
            weights.path("sdxl"), controlnet=cn, vae=vae, variant="fp16", **kw)
        pipe.load_lora_weights(str(weights.path("hyper_sdxl_lora")), weight_name="Hyper-SDXL-8steps-CFG-lora.safetensors")
        pipe.fuse_lora(lora_scale=lora_scale)
        pipe.unload_lora_weights()  # keep fused weights, drop the adapter modules
        pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")
        pipe.to("cuda")
        pipe.set_progress_bar_config(disable=True)
        try:
            pipe.enable_vae_tiling()
        except Exception:  # noqa: BLE001
            pass
        self.pipe = pipe
        self.polarity = self.manifest["controlnet_scribble_sdxl"].get("cond_polarity", "white_on_black")

    def _load_sd15(self):
        from diffusers import ControlNetModel, EulerAncestralDiscreteScheduler, StableDiffusionControlNetPipeline

        kw = dict(torch_dtype=self.dtype, use_safetensors=True, low_cpu_mem_usage=True)
        cn = ControlNetModel.from_pretrained(weights.path("controlnet_scribble_sd15"), variant="fp16", **kw)
        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            weights.path("sd15"), controlnet=cn, variant="fp16", safety_checker=None, requires_safety_checker=False, **kw)
        pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe.enable_model_cpu_offload()
        pipe.set_progress_bar_config(disable=True)
        self.pipe = pipe
        self.polarity = self.manifest["controlnet_scribble_sd15"].get("cond_polarity", "white_on_black")

    def generate(self, stroke_mask, prompts: list[str], negative: str, seeds: list[int], scales: list[float],
                 resolution: int | None = None, on_step=None) -> list[Image.Image]:
        import torch

        res = resolution or self.s.resolution
        cond = control_image(stroke_mask, res, self.polarity)
        out = []
        for i, (p, seed, sc) in enumerate(zip(prompts, seeds, scales)):
            g = torch.Generator("cuda").manual_seed(int(seed))
            img = self.pipe(prompt=p, negative_prompt=negative, image=cond, num_inference_steps=self.s.steps,
                            guidance_scale=self.s.guidance, controlnet_conditioning_scale=float(sc),
                            control_guidance_end=self.s.control_guidance_end, generator=g,
                            height=res, width=res).images[0]
            out.append(img)
            if on_step:
                on_step(i + 1, len(prompts))
        return out

    @property
    def parkable(self) -> bool:
        return self.profile == "balanced"   # lite already uses model CPU offload

    def park(self):
        """Move weights to system RAM between requests (restored with unpark() before the next run; never executed
        on CPU). diffusers warns about fp16-on-CPU on every move, so silence it for this call only."""
        from diffusers.utils import logging as dlog

        prev = dlog.get_verbosity()
        dlog.set_verbosity_error()
        try:
            self.pipe.to("cpu")
        finally:
            dlog.set_verbosity(prev)
        free_cuda()

    def unpark(self):
        self.pipe.to("cuda")

    def close(self):
        del self.pipe
        free_cuda()
