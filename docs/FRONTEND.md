# Building a frontend for the Sketch2Shape engine

> Calling the engine hosted on Kaggle from your own app? Start with **[API.md](API.md)** (requirements, endpoints, tested examples).

The engine is UI-agnostic (`sketch2shape.core.Pipeline`). There are three ways to put a frontend on it, from least
to most work.

## 1. Use the built-in Gradio app (already done)
`make demo` (or `sketch2shape serve`) starts `src/sketch2shape/ui/gradio_app.py`: drawing canvas (brush / eraser /
undo / clear), upload tab, prompt, detected-object box, material / quality / viewpoint / seed, stage-by-stage
progress, candidate gallery (click one to rebuild the 3D model from it), interactive 3D viewer, badges, GLB / OBJ /
run.json downloads and a Stop button. To restyle it, edit `build()` in that file (Gradio Blocks + themes).

## 2. Your own web/mobile frontend on top of the server API (recommended for a custom UI)
Any running server — local `make demo`, or the Kaggle notebook's public `*.gradio.live` link — exposes:

| Endpoint | Inputs | Returns |
|---|---|---|
| `/generate_api` | `file` (sketch image), `prompt_v` (str), `preset_v` (`fast`/`balanced`/`best`), `seed_v` (str, blank = random) | `[info JSON, GLB file, OBJ-zip file]` — files come back as `{url, …}` you can download or display |
| `/capabilities` | — | GPU, VRAM, profile, backend status |

Requests go through Gradio's queue (one generation at a time on the GPU, others wait with a queue position), so
long-running jobs and status updates work out of the box.

**JavaScript / React / Next.js** — tested client: [`examples/frontend/client.mjs`](../examples/frontend/client.mjs)
```js
import { Client, handle_file } from "@gradio/client";        // npm install @gradio/client
const app = await Client.connect("http://localhost:7860/");  // or the https://xxxx.gradio.live link
const job = app.submit("/generate_api", { file: handle_file(blobFromCanvasOrFileInput),
                                          prompt_v: "red ceramic", preset_v: "balanced", seed_v: "" });
for await (const ev of job) {
  if (ev.type === "status") showProgress(ev);                 // queue position / running
  if (ev.type === "data") { const [info, glb] = ev.data; viewer.src = glb.url; break; }
}
```
In a browser, get the sketch from your own canvas with `canvas.toBlob(...)` (draw black strokes on white) or from an
`<input type="file">`. Display the result with `<model-viewer src="…glb">` or three.js `GLTFLoader`.
A typical React layout: `<SketchCanvas>` (e.g. react-sketch-canvas) → "Generate" button → status bar fed by the job
events → `<model-viewer>` + download links.

**Python**
```python
from gradio_client import Client, handle_file
info, glb_path, obj_path = Client("http://localhost:7860/").predict(
    handle_file("sketch.png"), "", "balanced", "", api_name="/generate_api")
```
or simply `sketch2shape run --remote http://localhost:7860/ --sketch sketch.png --out outputs/`.

**curl / any language** — Gradio's HTTP API: `POST /gradio_api/call/generate_api` then stream
`GET /gradio_api/call/generate_api/<event_id>`; see the "Use via API" link at the bottom of the running app for the
exact payloads.

CORS: the Node client above was tested; from a **browser** app on a different origin, recent Gradio versions may reject
cross-origin calls to a localhost server. If you hit a CORS error, call the API from your own small backend (Node/
Python) or serve your frontend from the same origin. If you host a frontend publicly, keep the engine behind your
backend rather than exposing the share link.

## 3. Call the Python engine directly (your own backend server)
```python
from sketch2shape.core.context import Request
from sketch2shape.core.pipeline import Pipeline
pipe = Pipeline()                                    # keep one instance alive: it parks SDXL in RAM between requests
res = pipe.run(Request(image=numpy_rgb_or_rgba, source="canvas", prompt="", quality="balanced"),
               progress=lambda stage, frac, msg: ...)   # stream these to your client (SSE/WebSocket)
res.glb, res.obj_zip, res.run_json, res.badges, res.candidates
```
Run one generation at a time per GPU (the pipeline is not designed for concurrent requests on one card).
