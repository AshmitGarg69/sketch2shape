# Pretrained models, third-party code and licences

Every external component used by Sketch2Shape, with the exact revision we pin. Revisions were resolved with
`huggingface_hub.HfApi().model_info()` on 2026-10-31 and live in `config/weights_manifest.yaml`. No external
paid API is called at runtime; after `make weights` the app runs with `HF_HUB_OFFLINE=1`.

## Models (weights)

| Purpose | Model | Revision | Licence | Gated | Notes |
|---|---|---|---|---|---|
| 2D base (balanced) | [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | `46216598` | CreativeML OpenRAIL++-M | no | fp16 safetensors only |
| SDXL VAE (fp16-safe) | [madebyollin/sdxl-vae-fp16-fix](https://huggingface.co/madebyollin/sdxl-vae-fp16-fix) | `207b116d` | MIT | no | avoids NaNs in fp16 on T4 |
| Sketch conditioning (balanced) | [xinsir/controlnet-scribble-sdxl-1.0](https://huggingface.co/xinsir/controlnet-scribble-sdxl-1.0) | `0bed4973` | Apache-2.0 | no | conditioning = white strokes on black, 1024 px (verified from the card's example images) |
| 8-step sampler | [ByteDance/Hyper-SD](https://huggingface.co/ByteDance/Hyper-SD) `Hyper-SDXL-8steps-CFG-lora.safetensors` | `bc08d970` | see model card (OpenRAIL++ family) | no | CFG-preserving LoRA → negative prompt still works (guidance 5–8) |
| 2D base (lite) | [stable-diffusion-v1-5/stable-diffusion-v1-5](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5) | `451f4fe1` | CreativeML OpenRAIL-M | no | same hash as `sd-legacy/…`; `runwayml/…` was taken down |
| Sketch conditioning (lite) | [lllyasviel/control_v11p_sd15_scribble](https://huggingface.co/lllyasviel/control_v11p_sd15_scribble) | `3564ec7b` | OpenRAIL | no | |
| Object detection + semantic ranking | [google/siglip-base-patch16-256](https://huggingface.co/google/siglip-base-patch16-256) | `b078df89` | Apache-2.0 | no | zero-shot over `config/object_vocab.txt` |
| Background removal | [ZhengPeng7/BiRefNet](https://huggingface.co/ZhengPeng7/BiRefNet) | `e2bf8e44` | MIT | no | `trust_remote_code` (code in pinned snapshot) |
| Background removal fallback | rembg `u2net` | rembg 2.0.59 | MIT (rembg) / Apache-2.0 (U²-Net) | no | |
| Image→3D (fast/fallback) | [stabilityai/TripoSR](https://huggingface.co/stabilityai/TripoSR) | `5b521936` | MIT | no | |
| Image→3D (heavy) | [TencentARC/InstantMesh](https://huggingface.co/TencentARC/InstantMesh) | `b785b4ec` | Apache-2.0 | no | includes custom white-bg Zero123++ UNet |
| Multi-view diffusion (inside InstantMesh) | [sudo-ai/zero123plus-v1.2](https://huggingface.co/sudo-ai/zero123plus-v1.2) | `2da07e89` | see model card | no | downloaded by InstantMesh's `run.py` |
| Image encoder (inside both backends) | [facebook/dino-vitb16](https://huggingface.co/facebook/dino-vitb16) | `f205d5d8` | Apache-2.0 | no | |

## Third-party code (pinned git commits, cloned into `third_party/`)

| Repo | Commit | Licence | Used for |
|---|---|---|---|
| [VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) | `107cefdc244c39106fa830359024f6a2f1c78871` | MIT | backend (its own `run.py`) |
| [TencentARC/InstantMesh](https://github.com/TencentARC/InstantMesh) | `08822c52fdc399b93ea00e4fa9e596344ed52ccc` | Apache-2.0 | backend (its own `run.py`) |
| [tatsy/torchmcubes](https://github.com/tatsy/torchmcubes) | `bc36b08c62c5931e1dfc666581b3a8589278647f` | MIT | TripoSR marching cubes (CUDA ext.) |
| [NVlabs/nvdiffrast](https://github.com/NVlabs/nvdiffrast) | `v0.3.3` (`729261dc`) | NVIDIA Source Code License (non-commercial) | InstantMesh rasterisation — **research/non-commercial use only** |

## Main libraries (parent env, see `requirements.lock`)

PyTorch 2.4.1 (BSD), diffusers 0.31.0 / transformers 4.46.3 / accelerate / peft (Apache-2.0), Gradio 5 (Apache-2.0),
OpenCV (Apache-2.0), scikit-image (BSD), trimesh (MIT), fast-simplification (MIT), pymatting (MIT), timm (Apache-2.0),
kornia (Apache-2.0), huggingface_hub (Apache-2.0).

## Licence flags

- **nvdiffrast** (required by InstantMesh) is licensed for non-commercial / research use. Commercial users must use the
  TripoSR path only (`--preset fast`) or obtain a licence from NVIDIA.
- SD 1.5 / SDXL / Hyper-SD carry OpenRAIL use-based restrictions (no harmful uses; see each card).

## Evaluated but not shipped

See README → "Model choices and rejected alternatives".
