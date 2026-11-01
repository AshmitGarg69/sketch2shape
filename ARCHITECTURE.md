# Architecture & deviations from the build spec

The authoritative design is the team's build spec (v3.1, `../architecture.txt`). This file records **what was
built differently and why** — every deviation is backed by a measurement in `docs/phase0/`, `docs/calibration/` or a
`run.json` in `examples/outputs/`.

## Code map
```
src/sketch2shape/
  core/      pipeline.py (S1–S8 orchestration, OOM ladder, retry) · context.py (request, telemetry, run.json)
             subproc.py (backend launcher: handshake, timeout, tree-kill, OOM detection) · vram.py (profile, dtype)
             weights.py (pinned Hub manifest, disk guard) · errors.py
  stages/    s1_input … s8_verify (one module per stage)
  vision/    binarize · silhouette · prompt_composer · generate (SDXL/SD1.5 + ControlNet) · understand (SigLIP)
             matting (BiRefNet → rembg → key; sketch-guided recovery) · ranker (+ ranker_stroke, Appendix B)
             prepare (RGBA contract) · silhouette_render (Appendix A)
  backends/  base.py (generic subprocess backend) · registry.py (preset chain, VRAM-aware quality step-down)
  mesh/      prune (seam-safe) · repair · decimate · orient · glb_patch · validate
  ui/        gradio_app.py      cli.py · doctor.py
adapters/    triposr_run.py · instantmesh_run.py (+ instantmesh_configs/g96, g112)   ← standalone, backend env only
scripts/     phase0.py · calibrate_backend.py · setup_backend.sh · timing_table.py · batch_run.py
             render_preview.py · make_demo_assets.py · sync_kaggle_dataset.sh
kaggle/      Sketch2Shape_Kaggle_demo.ipynb (live demo) · runner kernel + tasks.sh + runs.txt (the exact scripts behind
             every reported number) · verify_notebook/ (automated notebook check)
docs/        DEMO.md · FRONTEND.md · phase0/ (raw measurements) · calibration/ · timing_table.md · contact sheets
examples/    sketches/ (inputs) · outputs/ (14 complete runs) · frontend/client.mjs
```

## Deviations (all measured)

| Spec says | Built | Why / evidence |
|---|---|---|
| InstantMesh `instant-mesh-large` as shipped | large with FlexiCubes `grid_res` 96 (balanced) / 112 (best), in-adapter fallback 112 → 96 → base | grid 128 OOMs on a T4 (15 GiB `index_select`); 96 → 9.4 GB, 112 → 13.96 GB. `grid_res` has no learned parameters. `docs/phase0/kaggle_t4_instantmesh_large_g*.json` |
| TripoSR `--bake-texture` if headless works | not used; TripoSR = vertex colours (Tier 2) | `XOpenDisplay: cannot open display` (moderngl). `docs/phase0/kaggle_t4_triposr_bake_texture.json` |
| Adapters use the repos' display orientation helpers | both use raw `(x,y,z) → (y,z,x)` | repos' helpers add a 180° yaw for their own viewers → input view faces −Z. Calibration on the asymmetric mug: InstantMesh 0.905 direct / 0.564 mirrored, TripoSR 0.941 / 0.565 |
| Edge decontamination via `pymatting.estimate_foreground_ml` | OpenCV edge-band inpaint | pymatting measured 44 s on a laptop CPU (numba JIT + 1024² solve); inpaint 0.25 s |
| BiRefNet → cleanup | + **sketch-guided matte recovery** (new) | BiRefNet drops drawn supports (saucer probability exactly 0). The ControlNet canvas is pixel-aligned with the user's silhouette, so brighter/differently-coloured pixels inside it are recovered; shadows (pure darkening vs. a local background estimate) are rejected. Mug sketch match 0.69 → 0.86 on the RTX 4050 |
| Semantic term (normalisation unspecified) | damped relative score `0.5 + (s − mean)/0.2` | min-max over N=2 turned a 0.01 cosine gap into 0 vs 1 and picked the wrong candidate |
| Registry filters by one VRAM number | per-quality measured VRAM + step-down (e.g. balanced → fast) | 6 GB card otherwise had no backend (TripoSR balanced 5.55 GB vs 5.3 GB usable) |
| Sequential residency (free 2D models before 3D) | same, plus **park SDXL in system RAM** between server requests when ≥ 12 GB RAM is free | disk reload 48–55 s vs RAM restore 3 s on Kaggle |
| Retry thresholds 0.55 (placeholder) | recon 0.72 · closed-sketch 0.65 · open-sketch 0.60 | Phase 4: p10 of 15 known-good runs minus margin (`config/default.yaml`) |
| nvdiffrast compiled lazily | compiled during `make setup` | first InstantMesh run was ~2 min slower otherwise |
| Human runs `colab/phase0.ipynb` and pastes JSON | Kaggle runner kernel pushed via the Kaggle API (`kaggle/`) | same measurements, recorded automatically; no manual copy step |
| Weights downloaded by pinned commit | + `refs/main` written to point at the pinned commit | backends call `hf_hub_download(repo, file)` (revision "main"); offline that resolves only via `refs/main` → first offline run failed on a fresh Kaggle machine |
| `/generate_api` returns a JSON summary | returns `[JSON, GLB file, OBJ file]` | custom frontends need downloadable URLs, not server paths (tested JS client: `examples/frontend/client.mjs`) |
| Notebook = setup + `serve --share` | streaming setup cell with heartbeat; server run with `PYTHONUNBUFFERED=1`; batch ("Save & Run All") runs generate one model and exit | `%%bash` output appeared only at the end; buffered server output hid the share link; batch serve would hold the GPU 12 h |
| Backend envs from upstream requirements | + resolved lockfiles `envs/*.lock.txt`, `setuptools==69.5.1`, `huggingface_hub==0.17.3`, `numpy<2` | upstream pins conflict / rely on removed `pkg_resources` (see TROUBLESHOOTING.md) |

## Request flow & resource lifecycle
```
UI/CLI/API ─► Pipeline.run  (one request at a time per GPU; Gradio queue)
  S1-S2 CPU (+ SigLIP on GPU, freed)  ─►  S3 SDXL/SD1.5 on GPU → parked in RAM (balanced) / freed
  S3 BiRefNet on GPU (freed)  ─►  S4 CPU  ─►  S5 backend subprocess (own env, own CUDA context, exits → VRAM freed)
  S6-S8 CPU (trimesh + NumPy/OpenCV)  ─►  outputs/<run>/{mesh/model.glb, model.obj.zip, run.json, …}
```
Peak VRAM never overlaps between stages: SDXL 10.1 GB, InstantMesh 9.4 GB, TripoSR 2.4–3.4 GB (T4 has 15 GB).

## Not built (scope-cut order from the spec)
* SF3D opt-in extra (gated weights) · Florence-2 option (off by default in the spec) · `offline_check.sh`
  (TripoSR offline re-run did pass in Phase 0) · Dockerfile / Colab notebook (Kaggle runner + Makefile instead).
