# Troubleshooting

Every entry below was hit for real while building/running Sketch2Shape (see `docs/phase0/`).

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'pkg_resources'` while building `torchmcubes` or importing `pytorch_lightning` in a backend env | setuptools ≥ 70 no longer ships `pkg_resources`; torch 2.1's `cpp_extension` and `lightning_fabric` import it | `scripts/setup_backend.sh` pins `setuptools==69.5.1` inside each backend env. Re-run `make backends`. |
| `No solution found … tokenizers … huggingface-hub` when building a backend env | transformers 4.34/4.35 need `tokenizers<0.15` → `huggingface_hub<0.18` | Use the committed lockfiles `envs/<name>.lock.txt` (hub 0.17.3). Don't upgrade hub inside backend envs. |
| `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x` | torch 2.1 wheels are built against NumPy 1.x | Lockfiles pin `numpy==1.26.4`. |
| InstantMesh-large: `CUDA out of memory. Tried to allocate 15.00 GiB` on a 16 GB T4 | FlexiCubes `index_select` over a 128³ grid with the large model's 80-channel triplane | The adapter runs large at FlexiCubes grid 96 (`adapters/instantmesh_configs/g96/`), and falls back to `instant-mesh-base` automatically on OOM. |
| TripoSR `--bake-texture`: `XOpenDisplay: cannot open display` | `moderngl.create_context(standalone=True)` needs an X/OpenGL context | Not used. TripoSR outputs vertex colours (UI shows "vertex colours"). |
| UI says "No calibrated 3D backend is available" | backend env missing, wrong interpreter, or `config/backends.yaml` calibration flags false | Run `sketch2shape doctor`; build envs with `make backends`; run `make calibrate`. Override an interpreter with `S2S_PYTHON_TRIPOSR=/path/to/python`. |
| "Ran out of GPU memory while generating images" | other GPU processes / small card | Close other GPU apps; use the **Fast** preset; on < 14 GB cards the app uses the SD1.5 `lite` profile automatically. |
| "needs an NVIDIA GPU with CUDA" | no CUDA device visible | Run on Kaggle/Colab with the notebook in `kaggle/`, or a Linux/WSL2 machine with an NVIDIA GPU. |
| Model appears grey in Blender | Tier-2 GLBs store colours as the `COLOR_0` vertex attribute | In Blender: Material → Base Color → *Color Attribute* (or Viewport shading → Attribute). |
| Native Windows: backends unavailable | InstantMesh needs Triton/nvdiffrast builds; TripoSR's torchmcubes needs a CUDA toolchain | Use WSL2 (Ubuntu). The parent app/UI starts on Windows but 3D generation is unsupported there. |
| Kaggle: kernel stuck in `QUEUED` | T4 queue | Wait; GPU quota is shown by `kaggle quota`. Internet must be enabled for first weight download. |
| Low laptop VRAM (e.g. 6 GB card with the desktop using 3–4 GB) | TripoSR needs ≥ 3.4 GB free, InstantMesh ≥ 11.3 GB | Free VRAM (close browser/compositor GPU use) or run remotely: `sketch2shape serve --share` on Kaggle/Colab and `sketch2shape run --remote <url>`. |
| Kaggle notebook: setup cell shows nothing for 10+ minutes | old notebook used a `%%bash` cell, which only shows output when the cell ends | Use the current `kaggle/Sketch2Shape_Kaggle_demo.ipynb` (streams progress + a heartbeat every 30 s). Real progress is also in `/kaggle/working/logs/` (Output panel). |
| Kaggle notebook: last cell runs but no `Running on…` / `gradio.live` line appears | piped Python output is block-buffered (measured: nothing in 35 s) | Current notebook sets `PYTHONUNBUFFERED=1`. In an old copy, add `PYTHONUNBUFFERED='1'` to the `env = dict(...)` line and re-run only that cell. |
| 3D stage fails with `OfflineModeIsEnabled … TripoSR/resolve/main/config.yaml` | pinned downloads didn't write `refs/main`, so backends couldn't resolve "main" offline | Fixed: `make weights` now writes the refs. On an existing machine just re-run `make weights` (no re-download). |
| `GitHub … Send failure: Broken pipe` during `make setup` | transient network failure (seen on Kaggle) | Setup retries every network step 4× with backoff; re-run `make setup` if it still fails. |
| Warning: `Pipelines loaded with dtype=torch.float16 cannot run with cpu device` | printed when SDXL is parked in system RAM between requests (it is moved back to the GPU before running) | Harmless; silenced in current code. |
| "Save & Run All" on Kaggle keeps the GPU busy for hours | an old notebook served the UI forever in batch mode | Current notebook detects batch runs, generates one model and exits. Use the interactive session for the demo. |
| First generation takes ~7 min on a T4 | cold model loads (SDXL from disk, InstantMesh checkpoints) | Expected once per session; later requests ≈ 3.3 min (`balanced`), ≈ 1.8 min (`fast`). Warm up before a demo. |
| `make demo`: port already in use | another server on 7860 | `make demo PORT=7861` |
