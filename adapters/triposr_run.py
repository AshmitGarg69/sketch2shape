"""TripoSR adapter (standalone: stdlib + TripoSR's own env only; spec §0 rule 12).

Wraps the repo's OWN entry point `run.py` (pinned 107cefdc). Preprocessing follows run.py exactly:
RGBA composited on 0.5 grey with the object at ~85 % (Stage 4 already centres/pads to 85 %), then
`--no-remove-bg` so TripoSR does not re-matte (never double-matte).
Axis fix (lives only here): TripoSR's raw frame is Objaverse-style (Z up, input camera on +X). Our canonical frame is
+Y up / front +Z, i.e. raw (x, y, z) -> (y, z, x). (tsr.utils.to_gradio_3d_orientation adds a further 180° yaw for
Gradio's camera; using it would make the input view face away from +Z — verified with the silhouette renderer on the
Phase-0 chair mesh and by scripts/calibrate_backend.py on the asymmetric mug.)
--bake-texture is NOT used: Phase 0 showed moderngl needs an X display (headless failure).

    <python> adapters/triposr_run.py --input selected_rgba.png --out raw/ --quality balanced --seed 0
"""
import argparse, json, os, subprocess, sys, threading, time

QUALITY = {  # Phase 0 (Kaggle T4): mc192/chunk2048 -> 3.41 GB peak; mc256/chunk8192 -> 5.55 GB peak
    "fast": {"mc": 192, "chunk": 2048, "bake": False},
    "balanced": {"mc": 256, "chunk": 8192, "bake": False},
    "best": {"mc": 256, "chunk": 8192, "bake": False},
}
OOM_EXIT = 77


class VramPoll(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.peak = 0.0; self.stop = threading.Event(); self.base = self.q()
    @staticmethod
    def q():
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-i",
                                  os.environ.get("CUDA_VISIBLE_DEVICES", "0").split(",")[0]],
                                 capture_output=True, text=True, timeout=10).stdout
            return float(out.split()[0])
        except Exception:
            return 0.0
    def run(self):
        while not self.stop.is_set():
            self.peak = max(self.peak, self.q() - self.base); time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--quality", default="balanced", choices=list(QUALITY)); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import numpy as np
    from PIL import Image
    q = QUALITY[a.quality]
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    print("S2S preprocessing", flush=True)
    rgba = np.asarray(Image.open(a.input).convert("RGBA")).astype(np.float32) / 255.0
    rgb = rgba[..., :3] * rgba[..., 3:4] + 0.5 * (1 - rgba[..., 3:4])        # run.py's own compositing
    grey_path = os.path.join(a.out, "input_grey.png")
    Image.fromarray((rgb * 255).round().astype(np.uint8)).resize((512, 512), Image.LANCZOS).save(grey_path)
    work = os.path.join(a.out, "triposr")
    os.makedirs(os.path.join(work, "0"), exist_ok=True)  # run.py only creates <out>/0 on its rembg path
    cmd = [sys.executable, "run.py", grey_path, "--no-remove-bg", "--output-dir", work, "--mc-resolution", str(q["mc"]),
           "--chunk-size", str(q["chunk"]), "--model-save-format", "obj"]
    if q["bake"]:
        cmd += ["--bake-texture", "--texture-resolution", "1024"]
    print("S2S running TripoSR", flush=True)
    poll = VramPoll(); poll.start()
    p = subprocess.run(cmd, capture_output=True, text=True)
    poll.stop.set()
    sys.stdout.write(p.stdout[-4000:]); sys.stdout.write(p.stderr[-4000:])
    if p.returncode != 0:
        if "out of memory" in (p.stderr + p.stdout).lower():
            print("S2S_OOM"); sys.exit(OOM_EXIT)
        sys.exit(p.returncode)
    import trimesh
    src = os.path.join(work, "0", "mesh.obj")
    mesh = trimesh.load(src, process=False, force="mesh")
    import numpy as np
    mesh.vertices = np.asarray(mesh.vertices)[:, [1, 2, 0]]   # raw (x,y,z) -> (y,z,x): cyclic => proper rotation
    out_mesh = os.path.join(a.out, "mesh.glb")
    mesh.export(out_mesh)
    meta = {"backend": "triposr", "mesh": "mesh.glb", "resolution": q["mc"], "seconds": round(time.time() - t0, 2),
            "vram_peak_gb": round(poll.peak / 1024, 2), "has_uv": bool(q["bake"]), "has_pbr": False,
            "faces": int(len(mesh.faces))}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))
    print("S2S done", json.dumps(meta), flush=True)


if __name__ == "__main__":
    main()
