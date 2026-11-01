# Sketch2Shape API — run the engine on Kaggle, call it from your own frontend

The GPU work runs in a Kaggle notebook; your frontend (React / Next.js / plain HTML / mobile) sends a sketch and gets
back a **GLB** (and a zipped OBJ) over HTTPS. Everything below was tested end-to-end (`curl`, plain `fetch()` and
`@gradio/client`).

```
Your frontend ──HTTPS──► https://xxxx.gradio.live  ──tunnel──► Kaggle T4 notebook (Sketch2Shape server)
   sketch.png  ─────────►  /gradio_api/upload, /gradio_api/call/generate_api
   GLB/OBJ URLs ◄────────  result stream (~3–4 min per model)
```

## 1. Requirements

| Need | Details |
|---|---|
| Kaggle account | **phone-verified** (required for GPU + Internet in notebooks) |
| GPU quota | T4 time is limited (we saw **30 h / week**; check with `kaggle quota` or your Kaggle settings). The server uses GPU only while the session is running |
| Notebook | `kaggle/Sketch2Shape_Kaggle_demo.ipynb` from this repo (File → Import Notebook, or upload) |
| Notebook settings | **Accelerator: GPU T4**, **Internet: on** |
| Your frontend | anything that can do HTTPS `fetch`/`POST` (browser, Node 18+, Python, mobile). Optional helper: `npm install @gradio/client` |
| Input | sketch image: PNG / JPG / WEBP / BMP, black strokes on a light background (canvas export or photo of paper) |
| No API key needed | the share link itself is the access (see §6 Security) |

## 2. Start the API (each time)
1. Open the notebook in Kaggle → *Run all* (first run: ≈ 10–15 min setup + ~25 GB pinned weights, no tokens).
2. The last cell prints:
   ```
   >>> API base URL:     https://xxxx.gradio.live
   ```
   Put that URL in your frontend's config (e.g. `NEXT_PUBLIC_S2S_API=https://xxxx.gradio.live`).
3. **Keep that cell (and the browser tab) running.** Send one warm-up request — the first model of a session takes
   ≈ 7 min (cold model loads); afterwards ≈ 3.3 min (`balanced`) / ≈ 1.8 min (`fast`).

**The URL is temporary:** it changes every time the server (re)starts, the link itself expires after **1 week**, and
Kaggle sessions stop after **12 h** at most (or earlier if the notebook is left idle). Re-run the last cell → new URL →
update your frontend config. For a fixed URL you'd need your own GPU server (`make demo` on Linux) behind a domain.

## 3. Endpoints

| Endpoint | Input | Output |
|---|---|---|
| `generate_api` | `file` (sketch image), `prompt` (str, may be empty), `preset` (`fast` \| `balanced` \| `best`), `seed` (str; empty = random) | `[info, glb, obj]` — `info` is the run summary (below); `glb`/`obj` are file objects with a downloadable `url` |
| `capabilities` | — | `{gpu, vram_gb, profile, backends}` — use as a health check |

`info` example (abridged, real output):
```json
{ "ok": true, "message": "Done",
  "badges": { "object": "lamp", "backend": "instantmesh", "profile": "balanced", "seconds": 196.6,
              "sketch_match": 0.88, "tier": 1, "warnings": [], "notice": null, "seed": 13 } }
```
* `ok=false` → `message` is a human-readable reason (e.g. *"The sketch looks empty…"*); `glb`/`obj` are `null`.
* `badges.notice` may say *"the sketch was prioritised"* when your prompt contradicted the drawing.
* `tier` 1 = textured GLB, 2 = vertex-coloured GLB.

## 4. Plain HTTP (works from any language)
Three calls: **upload → start → read result stream**.
```bash
API=https://xxxx.gradio.live
# 1) upload -> returns a server-side path
curl -s -F "files=@sketch.png" $API/gradio_api/upload
#   ["/tmp/gradio/…/sketch.png"]
# 2) start the job -> returns an event id
curl -s -H "Content-Type: application/json" \
  -d '{"data":[{"path":"/tmp/gradio/…/sketch.png","meta":{"_type":"gradio.FileData"}},"red ceramic","balanced",""]}' \
  $API/gradio_api/call/generate_api
#   {"event_id":"f0e1f52f…"}
# 3) stream the result (Server-Sent Events): "heartbeat" lines while working, then "complete" with the data
curl -sN $API/gradio_api/call/generate_api/f0e1f52f…
#   event: heartbeat … event: complete
#   data: [{"ok": true, …}, {"url": "https://xxxx.gradio.live/gradio_api/file=/tmp/gradio/…/model.glb", …}, {…obj…}]
# 4) download
curl -o model.glb "https://xxxx.gradio.live/gradio_api/file=/tmp/gradio/…/model.glb"
```
Health check: `POST $API/gradio_api/call/capabilities` with `{"data":[]}`, then GET the stream the same way.

## 5. JavaScript

### a) Plain `fetch()` — no dependencies (browser or Node 18+)
Full tested code: [`examples/frontend/fetch_client.mjs`](../examples/frontend/fetch_client.mjs) (exports `generate3D`).
```js
import { generate3D } from "./fetch_client.mjs";
const blob = await new Promise(r => canvas.toBlob(r, "image/png"));        // or a File from <input type="file">
const { info, glbUrl, objUrl } = await generate3D(API, blob,
      { prompt: "red ceramic", preset: "balanced" },
      (event) => setStatus(event === "heartbeat" ? "working…" : event));
if (!info.ok) alert(info.message);
else viewer.src = glbUrl;                                                    // <model-viewer id="viewer" camera-controls>
```

### b) With `@gradio/client` (handles queue + status for you)
Tested code: [`examples/frontend/client.mjs`](../examples/frontend/client.mjs).
```js
import { Client, handle_file } from "@gradio/client";
const app = await Client.connect(API);
const job = app.submit("/generate_api", { file: handle_file(blob), prompt_v: "", preset_v: "balanced", seed_v: "" });
for await (const ev of job) {
  if (ev.type === "status") setStatus(ev.stage, ev.position);        // queue position while another job runs
  if (ev.type === "data") { const [info, glb, obj] = ev.data; viewer.src = glb.url; break; }
}
```

### Showing the model
```html
<script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
<model-viewer id="viewer" camera-controls auto-rotate style="width:100%;height:480px"></model-viewer>
```
(or three.js `GLTFLoader`). Offer `glbUrl` / `objUrl` as download links.

## 6. Python
```python
from gradio_client import Client, handle_file           # pip install gradio_client
info, glb_path, obj_path = Client(API).predict(handle_file("sketch.png"), "", "balanced", "", api_name="/generate_api")
```
or the bundled CLI: `sketch2shape run --remote $API --sketch sketch.png --out outputs/`.

## 7. Behaviour you must design for
| Topic | What happens | Frontend advice |
|---|---|---|
| Duration | 3–4 min per model (7 min for the first one after start) | show progress/"working…" from the stream; don't use short HTTP timeouts |
| Concurrency | **one generation at a time**; other requests wait in a queue | show "queued (position N)" (`@gradio/client` gives it); disable the Generate button while waiting |
| Result files | `glb`/`obj` URLs are served by the running notebook | download/copy them if you need them after the session ends |
| Errors | `info.ok=false` + `info.message`; network/stream errors if the session stopped | show `message`; if requests fail entirely, the Kaggle session/URL probably changed |
| CORS | allowed from **any origin** when you call the `*.gradio.live` URL (checked: the server echoes your `Origin`) | nothing to do. Exception: a server started on `localhost` only accepts frontends also on `localhost` |
| Input quality | one object, dark strokes, light background; empty/near-empty sketches are rejected | crop to the object; send ≥ 512 px images |

## 8. Security
* Anyone who has the `gradio.live` link can use your GPU and see the UI — **don't publish it**; keep it in your
  frontend's server-side config or share it only with your team/judges.
* Stop the notebook when you're done (also saves GPU quota).
* Don't send private images: the sketch is processed on Kaggle's machine.

## 9. Troubleshooting
| Symptom | Fix |
|---|---|
| Last notebook cell shows no URL | use the current notebook from the repo (it runs the server unbuffered) |
| `fetch` fails / `502` | session stopped or URL changed → re-run the last cell, update the URL |
| Request "hangs" for minutes | normal while generating (watch for `heartbeat` events); first request ≈ 7 min |
| `ok=false`, "No calibrated 3D backend…" | setup cell failed — check its output / `/kaggle/working/logs/` and re-run it |
| Browser CORS error | you're calling a `localhost` server from a non-localhost page — call the `gradio.live` URL instead, or proxy through your backend |
