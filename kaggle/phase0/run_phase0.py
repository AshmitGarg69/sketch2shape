# Phase 0 on a Kaggle T4 (spec §14): build per-backend uv envs, run each repo's OWN run.py on its bundled
# example image, record measurements to /kaggle/working/docs/phase0/*.json.  Everything heavy lives in /tmp.
import glob, json, os, shutil, subprocess, sys, time

def sh(cmd, check=False, **kw):
    print(f"\n$ {cmd}", flush=True)
    r = subprocess.run(cmd, shell=True, **kw)
    if check and r.returncode:
        raise SystemExit(f"FAILED ({r.returncode}): {cmd}")
    return r.returncode

hits = glob.glob("/kaggle/input/**/scripts/phase0.py", recursive=True)
if not hits:  # dataset uploaded as a zip that Kaggle did not expand
    z = glob.glob("/kaggle/input/**/*.zip", recursive=True)[0]
    shutil.unpack_archive(z, "/tmp/s2s_src"); hits = glob.glob("/tmp/s2s_src/**/scripts/phase0.py", recursive=True)
src = os.path.dirname(hits[0]) + "/.."
W = "/tmp/s2s"; R = f"{W}/repo"; OUT = "/kaggle/working"
shutil.copytree(src, R, dirs_exist_ok=True)
os.makedirs(f"{OUT}/docs/phase0", exist_ok=True)
os.environ.update(HF_HOME=f"{W}/weights/hf", TORCH_HOME=f"{W}/weights/torch", U2NET_HOME=f"{W}/weights/u2net",
                  CUDA_VISIBLE_DEVICES="0", PATH=f"/usr/local/cuda/bin:{os.environ['PATH']}")
sh("pip install -q uv psutil trimesh", check=True)
sh("nvidia-smi; nvcc --version; df -h /tmp /kaggle/working; free -g")
host = "kaggle_t4"
P0 = f"python {R}/scripts/phase0.py"

def phase0(backend, label, image, cwd, glob_, argv, extra, timeout=2400, skip_offline=False):
    out = f"{OUT}/docs/phase0/{host}_{backend}_{label}.json"
    sh(f"{P0} --backend {backend} --label {label} --image {image} --out {out} --cwd {cwd} --mesh-glob '{glob_}' "
       f"--timeout {timeout} {'--skip-offline' if skip_offline else ''} --extra '{json.dumps(extra)}' -- {argv}")

# ---------- 0a TripoSR ----------
rc = sh(f"bash {R}/scripts/setup_backend.sh triposr {W}/envs 2>&1 | tail -30")
b = json.load(open(f"{W}/envs/triposr.build.json")) if os.path.exists(f"{W}/envs/triposr.build.json") else {"build_failed": True}
TP = f"{W}/envs/triposr/bin/python"; TD = f"{R}/third_party/TripoSR"
if os.path.exists(TP):
    sh(f"{TP} -c \"import torch,torchmcubes_module as m;print(torch.__version__,torch.cuda.is_available(),hasattr(m,'mcubes_cuda'))\"")
    sh(f"cd {TD} && {TP} run.py --help | head -50")
    phase0("triposr", "default", "examples/chair.png", TD, "p0out/default/**/mesh.*",
           f"{TP} run.py examples/chair.png --output-dir p0out/default/", b)
    phase0("triposr", "glb_mc256", "examples/chair.png", TD, "p0out/glb/**/mesh.*",
           f"{TP} run.py examples/chair.png --output-dir p0out/glb/ --model-save-format glb", b, skip_offline=True)
    phase0("triposr", "bake_texture", "examples/chair.png", TD, "p0out/bake/**/mesh.*",
           f"{TP} run.py examples/chair.png --output-dir p0out/bake/ --bake-texture --texture-resolution 1024", b, skip_offline=True)
    phase0("triposr", "lowvram_c2048_mc192", "examples/chair.png", TD, "p0out/low/**/mesh.*",
           f"{TP} run.py examples/chair.png --output-dir p0out/low/ --chunk-size 2048 --mc-resolution 192", b, skip_offline=True)
    # golden asymmetric RGBA (spec §14 prerequisite) via the repo's own rembg in this env
    sh(f"{TP} -c \"import rembg;from PIL import Image;im=Image.open('{R}/tests/golden/asym_photo.jpeg');"
       f"rembg.remove(im).save('{OUT}/asym_rgba.png')\"")
    os.path.isdir(f"{TD}/p0out") and shutil.copytree(f"{TD}/p0out", f"{OUT}/meshes/triposr", dirs_exist_ok=True)

# ---------- 0b InstantMesh ----------
rc = sh(f"bash {R}/scripts/setup_backend.sh instantmesh {W}/envs 2>&1 | tail -30")
b = json.load(open(f"{W}/envs/instantmesh.build.json")) if os.path.exists(f"{W}/envs/instantmesh.build.json") else {"build_failed": True}
IP = f"{W}/envs/instantmesh/bin/python"; ID = f"{R}/third_party/InstantMesh"
if os.path.exists(IP):
    sh(f"{IP} -c \"import torch,xformers,diffusers,nvdiffrast.torch as dr;print(torch.__version__,xformers.__version__,diffusers.__version__);"
       f"ctx=dr.RasterizeCudaContext(device='cuda');print('nvdiffrast cuda ctx OK')\"")
    phase0("instantmesh", "large_norembg", "examples/blue_cat.png", ID, "p0out/a/**/*.obj",
           f"{IP} run.py configs/instant-mesh-large.yaml examples/blue_cat.png --no_rembg --output_path p0out/a", b)
    phase0("instantmesh", "large_texmap", "examples/blue_cat.png", ID, "p0out/b/**/*.obj",
           f"{IP} run.py configs/instant-mesh-large.yaml examples/blue_cat.png --no_rembg --export_texmap --output_path p0out/b", b, skip_offline=True)
    phase0("instantmesh", "base_norembg", "examples/blue_cat.png", ID, "p0out/c/**/*.obj",
           f"{IP} run.py configs/instant-mesh-base.yaml examples/blue_cat.png --no_rembg --output_path p0out/c", b, skip_offline=True)
    os.path.isdir(f"{ID}/p0out") and shutil.copytree(f"{ID}/p0out", f"{OUT}/meshes/instantmesh", dirs_exist_ok=True)

sh(f"du -sh {W}/envs/* {W}/weights/* 2>/dev/null; df -h /tmp")
sh(f"du -sm {W}/envs/* {W}/weights/* > {OUT}/docs/phase0/{host}_disk_mb.txt 2>/dev/null")
print("PHASE0 DONE")
