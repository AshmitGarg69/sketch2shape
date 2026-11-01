# Final demonstration script (≈ 8 minutes)

## Before judging (T − 30 min)
1. Open `kaggle/Sketch2Shape_Kaggle_demo.ipynb` in Kaggle (Accelerator **GPU T4**, Internet **on**) → *Run all*.
   Setup ≈ 10–15 min; the last cell prints the `https://….gradio.live` link.
2. **Warm it up:** generate one sketch (the first request of a session takes ≈ 7 min; later ones ≈ 3.3 min `balanced`,
   ≈ 1.8 min `fast`).
3. Backup in case the network/queue misbehaves: the laptop (`make demo`, `lite`, ≈ 40 s per sketch) and the 14 finished
   runs in `examples/outputs/` (open the GLBs in Blender).

## Live run (judge's fresh sketch)
1. **Draw tab** → judge draws (or **Upload tab** → photo of a paper sketch). Optional prompt, e.g. "red leather".
2. **Generate** → narrate the streamed stages:
   understand (object detected) → 4 sketch-conditioned candidates → ranker picks the most sketch-faithful →
   matting → 3D reconstruction in an isolated process → cleanup → export → verification.
3. Show the **candidate gallery** (click another candidate to rebuild only the 3D part), rotate the **3D viewer**, point
   at the badges (detected object, backend, time, **Sketch match %**, texture tier), download **GLB / OBJ / run.json**.
4. Open the downloaded GLB in Blender / any glTF viewer to prove it is real, exportable geometry.
5. Conflict test: same chair sketch + prompt "a fire-breathing dragon" → result stays a chair, UI shows
   *"the sketch was prioritised"*.

## Key implementation decisions (one line each, with evidence)
| Decision | Why (measured) |
|---|---|
| ControlNet sees only the user's strokes (white-on-black, 1024 px) | sketch structure is preserved; format verified on the model card's own examples |
| Generate **N** candidates + composite **ranker** (silhouette IoU, stroke F-score, semantics, matte quality) | one sample is a lottery; ranker picks the most sketch-faithful (`candidate_scores` in every `run.json`) |
| **Hedge candidate** with allowlisted prompt words only | prompts can't override the sketch's shape (dragon → still a chair) |
| **Sketch-guided matte recovery** | BiRefNet dropped drawn saucers (probability exactly 0); recovery took mug sketch-match 0.69 → 0.86, while rejecting shadows |
| 3D backends in **separate processes + envs** | incompatible pins (torch 2.1 vs 2.4); a crash/OOM can't kill the UI; VRAM fully released |
| InstantMesh-large at FlexiCubes grid 96 | default grid OOMs on a T4 (15 GiB alloc); grid 96 → 9.4 GB with a texture map |
| **Calibrated orientation** with a mirror test | both repos' display transforms would have shown the model from behind (mirrored); calibration: 0.94 / 0.91 direct vs 0.56 mirrored |
| Closed-loop **verification** with a NumPy silhouette renderer | no OpenGL needed on servers; every result gets a "Sketch match %" and an automatic retry if it is low |
| VRAM-aware profiles + quality step-down | same code runs on a 15 GB T4 (SDXL + InstantMesh) and a 6 GB laptop (SD1.5 + TripoSR) |
| SDXL parked in system RAM between requests | 3 s restore vs 48–55 s reload from disk |

## Honest limitations to mention
Hidden sides are inferred; thin parts/text can be lost; ≈ 3.3 min per model on a T4 (first one ≈ 7 min); object
detection uses a closed vocabulary (editable box); InstantMesh needs Linux + NVIDIA.
