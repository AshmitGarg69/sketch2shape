"""InstantMesh adapter (standalone: stdlib + InstantMesh's own env only; spec §0 rule 12).

Wraps the repo's OWN entry point `run.py` (pinned 08822c52) with `--no_rembg` (Stage 4 supplies alpha;
never double-matte). Axis convention: raw frame is Objaverse-style (Z up, input camera on +X); canonical is
+Y up / front +Z, i.e. raw (x,y,z) -> (y, z, x) — the same permutation app.py applies (app.py's save_glb then adds a
180° yaw for Gradio's camera, which we do not want). run.py writes two different frames:
  * vertex-colour OBJ via save_obj:          file = (x, y, -z), faces reversed  -> undo, then map
  * texture-map OBJ via save_obj_with_mtl:    file = raw (x, y, z)
These fixes live only here. Verified by scripts/calibrate_backend.py (handedness test).

    <python> adapters/instantmesh_run.py --input selected_rgba.png --out raw/ --quality balanced --seed 0
"""
import argparse, glob, json, os, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
# Phase 0 (Kaggle T4): base@grid128 -> 11.3 GB peak, 85 s; large@grid128 -> OOM (FlexiCubes index_select wants 15 GiB).
# Large therefore runs at a lower FlexiCubes grid (README: "set a lower iso-surface extraction resolution in the config
# file"). grid_res has no learned parameters. The yaml MUST keep the upstream basename because run.py derives the
# checkpoint filename from it, hence one directory per variant. On OOM we fall back to instant-mesh-base.
# Measured (Kaggle T4): large@g112 74 s / 13.96 GB; large@g96 9.4 GB; large@g96 --export_texmap 80 s / 9.44 GB (UV texture).
G96 = os.path.join(HERE, "instantmesh_configs", "g96", "instant-mesh-large.yaml")
G112 = os.path.join(HERE, "instantmesh_configs", "g112", "instant-mesh-large.yaml")
BASE = "configs/instant-mesh-base.yaml"
QUALITY = {
    "fast": {"configs": [BASE], "texmap": False, "steps": 75},
    "balanced": {"configs": [G96, BASE], "texmap": True, "steps": 75},
    "best": {"configs": [G112, G96, BASE], "texmap": True, "steps": 75},
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
    ap.add_argument("--quality", default="balanced", choices=list(QUALITY)); ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    q = QUALITY[a.quality]
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    work = os.path.join(a.out, "instantmesh")
    inp = os.path.join(a.out, "input.png")
    import shutil
    shutil.copy(a.input, inp)
    used, tail, rc = None, [], 1
    poll = VramPoll(); poll.start()
    for cfg in q["configs"]:
        shutil.rmtree(work, ignore_errors=True)
        cmd = [sys.executable, "run.py", cfg, inp, "--no_rembg", "--output_path", work, "--seed", str(a.seed),
               "--diffusion_steps", str(q["steps"])]
        if q["texmap"]:
            cmd.append("--export_texmap")
        print(f"S2S running InstantMesh ({os.path.basename(os.path.dirname(cfg)) or 'upstream'}/{os.path.basename(cfg)})", flush=True)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        tail = []
        for line in p.stdout:
            tail = (tail + [line])[-80:]
            if any(k in line for k in ("Imagining", "Creating", "Mesh saved", "Loading")):
                print("S2S " + line.strip(), flush=True)
        rc = p.wait()
        if rc == 0:
            used = cfg
            break
        oom = "out of memory" in "".join(tail).lower()
        print(f"S2S config failed ({'OOM' if oom else rc}); " + ("trying fallback" if cfg != q["configs"][-1] else "no fallback left"), flush=True)
        if not oom:
            break
    poll.stop.set()
    if rc != 0:
        sys.stdout.write("".join(tail))
        if "out of memory" in "".join(tail).lower():
            print("S2S_OOM"); sys.exit(OOM_EXIT)
        sys.exit(rc)
    import numpy as np
    import trimesh
    objs = glob.glob(os.path.join(work, "*", "meshes", "*.obj"))
    if not objs:
        print("no mesh produced"); sys.exit(3)
    mesh = trimesh.load(objs[0], process=False, force="mesh")
    V = np.asarray(mesh.vertices, dtype=np.float64)
    F = np.asarray(mesh.faces)
    if q["texmap"]:
        raw = V
    else:
        raw = V * np.array([1, 1, -1]); F = F[:, ::-1]          # undo save_obj's z-mirror + face flip
    target = raw[:, [1, 2, 0]]                                 # cyclic permutation => proper rotation
    mesh.vertices = target
    mesh.faces = F
    out_mesh = os.path.join(a.out, "mesh.glb")
    mesh.export(out_mesh)
    meta = {"backend": "instantmesh", "mesh": "mesh.glb", "config": used, "fallback_used": used != q["configs"][0], "texmap": q["texmap"],
            "seconds": round(time.time() - t0, 2), "vram_peak_gb": round(poll.peak / 1024, 2),
            "has_uv": bool(q["texmap"]), "has_pbr": False, "faces": int(len(F))}
    json.dump(meta, open(os.path.join(a.out, "meta.json"), "w"))
    print("S2S done", json.dumps(meta), flush=True)


if __name__ == "__main__":
    main()
