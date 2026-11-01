"""Gradio 5 UI (spec §11): canvas/upload -> generator handler with stage progress, candidate gallery,
Model3D viewer, downloads, Stop, capabilities endpoint. Calls core.Pipeline in-process."""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

import gradio as gr
import numpy as np

from ..core.context import ROOT, Request
from ..core.pipeline import Pipeline

PIPE = Pipeline()
EXAMPLES = sorted(str(p) for p in (ROOT / "examples" / "sketches").glob("*.png"))
STAGES = ["input", "understand", "generate", "reconstruct", "cleanup", "export", "verify"]
MATERIALS = ["Auto", "Wood", "Metal", "Plastic", "Ceramic", "Glass", "Fabric", "Leather", "Stone"]
VIEWS = ["Auto", "front", "side profile", "back", "top-down", "front three-quarter"]


def _image_from_inputs(tab, canvas, upload):
    if tab == "draw":
        if canvas is None:
            return None, "canvas"
        img = canvas.get("composite") if isinstance(canvas, dict) else canvas
        return (None if img is None else np.asarray(img)), "canvas"
    return (None if upload is None else np.asarray(upload)), "upload"


def _badges_md(res) -> str:
    if not res.ok:
        return f"**⚠️ {res.message}**"
    b = res.badges
    match = b.get("sketch_match")
    lines = [f"**Detected object:** {b.get('object')}  |  **Backend:** {b.get('backend')} ({b.get('profile')})  |  "
             f"**Time:** {b.get('seconds')} s  |  **Seed:** {b.get('seed')}"]
    if match is not None:
        label = "Sketch match" if b.get("sketch_match_kind") == "silhouette" else "Stroke match"
        lines.append(f"**{label}:** {round(100 * match)} %")
    lines.append("**Texture:** " + ("baked texture map" if b.get("tier") == 1 else "vertex colours"))
    if b.get("notice"):
        lines.append(f"ℹ️ {b['notice']}")
    if b.get("warnings"):
        lines.append("**Warnings:** " + ", ".join(b["warnings"]))
    if b.get("fallbacks"):
        lines.append("<details><summary>Fallbacks used</summary>\n\n" + "\n".join(f"- {f}" for f in b["fallbacks"]) + "\n</details>")
    return "\n\n".join(lines)


def _run_streaming(req: Request, cancel: threading.Event):
    """Run the pipeline in a worker thread; yield ("progress", msg) events then ("done", Result)."""
    q: queue.Queue = queue.Queue()

    def prog(stage, frac, msg):
        q.put(("progress", stage, frac, msg))

    def work():
        try:
            q.put(("done", PIPE.run(req, progress=prog, cancel=cancel)))
        except Exception as e:  # noqa: BLE001 - Pipeline.run already catches; belt and braces
            q.put(("error", repr(e)))

    t = threading.Thread(target=work, daemon=True)
    t.start()
    while True:
        try:
            yield q.get(timeout=0.5)
        except queue.Empty:
            if not t.is_alive() and q.empty():
                return
            continue


def build() -> gr.Blocks:
    with gr.Blocks(title="Sketch2Shape AI", theme=gr.themes.Soft()) as demo:
        run_state = gr.State({})       # {"run_dir": str} for candidate re-runs
        cancel_state = gr.State(None)
        gr.Markdown("# ✏️ → 🧊 Sketch2Shape AI\nDraw (or upload) a single object, optionally describe it, press **Generate**. "
                    "You get a 3D model you can rotate and download as **.glb** / **.obj**.")
        with gr.Row():
            with gr.Column(scale=5):
                tab = gr.State("draw")
                with gr.Tabs():
                    with gr.Tab("Draw") as t_draw:
                        canvas = gr.ImageEditor(type="numpy", image_mode="RGBA", canvas_size=(768, 768), layers=False,
                                                brush=gr.Brush(colors=["#000000"], default_size=4, color_mode="fixed"),
                                                eraser=gr.Eraser(default_size=16), label="Sketch canvas (brush · eraser · undo · clear)",
                                                value={"background": np.full((768, 768, 4), 255, np.uint8), "layers": [], "composite": None})
                    with gr.Tab("Upload") as t_up:
                        upload = gr.Image(type="numpy", image_mode="RGBA", label="Sketch image (PNG/JPG/WEBP/BMP, photos of paper OK)",
                                          sources=["upload", "clipboard"])
                        if EXAMPLES:
                            gr.Examples(EXAMPLES, inputs=upload, label="Built-in example sketches")
                t_draw.select(lambda: "draw", None, tab)
                t_up.select(lambda: "upload", None, tab)
                prompt = gr.Textbox(label="Optional description (material, colour, style…)", placeholder="e.g. red leather, vintage")
                with gr.Row():
                    obj = gr.Textbox(label="Detected object (editable)", placeholder="auto-detected")
                    material = gr.Dropdown(MATERIALS, value="Auto", label="Material")
                with gr.Row():
                    quality = gr.Radio(["fast", "balanced", "best"], value="balanced", label="Quality")
                    view = gr.Dropdown(VIEWS, value="Auto", label="Sketch viewpoint")
                    seed = gr.Textbox(label="Seed (blank = random)", value="")
                with gr.Row():
                    go = gr.Button("Generate", variant="primary")
                    stop = gr.Button("Stop", variant="stop")
            with gr.Column(scale=6):
                status = gr.Markdown("Ready.")
                gallery = gr.Gallery(label="2D candidates (click one to rebuild the 3D model from it)", columns=4, height=200,
                                     allow_preview=False)
                viewer = gr.Model3D(label="3D model", clear_color=(0.92, 0.92, 0.92, 1.0), height=420)
                badges = gr.Markdown()
                with gr.Row():
                    f_glb = gr.File(label="GLB")
                    f_obj = gr.File(label="OBJ (zip)")
                    f_json = gr.File(label="run.json")

        def generate(tab_v, canvas_v, upload_v, prompt_v, obj_v, mat_v, q_v, view_v, seed_v, rs, progress=gr.Progress()):
            img, src = _image_from_inputs(tab_v, canvas_v, upload_v)
            if img is None:
                yield gr.update(value="**⚠️ Please draw or upload a sketch first.**"), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), rs
                return
            s = int(seed_v) if str(seed_v).strip().lstrip("-").isdigit() else None
            req = Request(image=img, source=src, prompt=prompt_v or "", object_override=obj_v or "", material=mat_v,
                          quality=q_v, viewpoint=view_v, seed=s, out_root=str(ROOT / "outputs"))
            yield from _drive(req, rs, progress)

        def rerun(evt: gr.SelectData, rs, q_v, progress=gr.Progress()):
            if not rs.get("run_dir") or not rs.get("rank"):
                yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), rs
                return
            cand = rs["rank"][evt.index]
            req = Request(image=np.zeros((8, 8, 3), np.uint8), quality=q_v, seed=rs.get("seed"),
                          selected_candidate=cand, reuse_run_dir=rs["run_dir"], out_root=str(ROOT / "outputs"))
            yield from _drive(req, rs, progress)

        def _drive(req, rs, progress):
            cancel = threading.Event()
            try:
                for ev in _run_streaming(req, cancel):
                    if ev[0] == "progress":
                        _, stage, frac, msg = ev
                        i = STAGES.index(stage) if stage in STAGES else 0
                        progress((i + frac) / len(STAGES), desc=msg)
                        yield f"⏳ **{stage}** — {msg}", gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), rs
                    elif ev[0] == "done":
                        res = ev[1]
                        rank = [int(Path(p).stem.split("_")[1]) for p, _ in res.candidates]
                        rs = {"run_dir": str(res.run_dir), "rank": rank, "seed": res.badges.get("seed", req.seed)}
                        obj_v = res.badges.get("object") if res.ok else gr.skip()
                        yield ("✅ Done." if res.ok else f"**⚠️ {res.message}**", res.candidates or None,
                               str(res.glb) if res.glb else None, _badges_md(res),
                               str(res.glb) if res.glb else None, str(res.obj_zip) if res.obj_zip else None,
                               str(res.run_json) if res.run_json else None, obj_v, rs)
                    else:
                        yield f"**⚠️ Unexpected error:** {ev[1]}", gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), rs
            finally:
                cancel.set()  # Stop / disconnect -> cooperative cancel (kills backend subprocess tree)

        outs = [status, gallery, viewer, badges, f_glb, f_obj, f_json, obj, run_state]
        ev = go.click(generate, [tab, canvas, upload, prompt, obj, material, quality, view, seed, run_state], outs)
        ev_sel = gallery.select(rerun, [run_state, quality], outs)
        stop.click(lambda: "⏹️ Stopped.", None, status, cancels=[ev, ev_sel])

        # --- API-only endpoints (gradio_client / CLI --remote) ---
        with gr.Row(visible=False):
            api_in = gr.File()
            api_prompt, api_preset, api_seed = gr.Textbox(), gr.Textbox(), gr.Textbox()
            api_out = gr.JSON()
            api_glb, api_obj = gr.File(), gr.File()   # downloadable URLs for custom frontends
            api_btn, cap_btn = gr.Button(), gr.Button()

        def generate_api(file, prompt_v, preset_v, seed_v):
            from PIL import Image

            img = np.asarray(Image.open(file).convert("RGBA"))
            s = int(seed_v) if str(seed_v).strip().lstrip("-").isdigit() else None
            res = PIPE.run(Request(image=img, source="upload", prompt=prompt_v or "", quality=preset_v or "balanced",
                                   seed=s, out_root=str(ROOT / "outputs")))
            info = {"ok": res.ok, "message": res.message, "glb": str(res.glb), "obj_zip": str(res.obj_zip),
                    "run_json": str(res.run_json), "badges": res.badges}
            return info, (str(res.glb) if res.glb else None), (str(res.obj_zip) if res.obj_zip else None)

        def capabilities():
            from ..backends.registry import BackendRegistry
            from ..core import vram

            g = vram.detect()
            return {"gpu": g.name, "vram_gb": round(g.total_gb, 1), "profile": vram.pick_profile(g, PIPE.cfg["profiles"]),
                    "backends": BackendRegistry().status()}

        api_btn.click(generate_api, [api_in, api_prompt, api_preset, api_seed], [api_out, api_glb, api_obj],
                      api_name="generate_api")
        cap_btn.click(capabilities, None, api_out, api_name="capabilities")
    return demo
