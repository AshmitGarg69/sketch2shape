# Example runs (real pipeline output)

Each folder is one complete run: `input/` (sketch, cleaned strokes, silhouette), `candidates/` (all 2D candidates,
stored as JPEG to keep the repo small; per-candidate RGBA mattes omitted), `selected_rgba.png` (Stage-4 output fed to
the 3D backend), `preview_front.png`, `turntable_preview.png` (NumPy preview render of the GLB), `mesh/model.glb`,
`mesh/model.obj.zip` and the full `run.json` telemetry.

`*_balanced` / `*_fast`: Kaggle Tesla T4. `*_rtx4050`: RTX 4050 Laptop 6 GB (`lite` profile).
