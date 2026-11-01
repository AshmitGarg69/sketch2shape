"""End-to-end smoke test on CPU: real S1/S2/S4/S6/S7/S8, stubbed generator (S3) and a stub 3D backend.
Stubs live ONLY here (spec: stubs never ship in backends/)."""
import json

import cv2
import numpy as np
import trimesh
from PIL import Image

from sketch2shape.core import pipeline as P
from sketch2shape.core import vram
from sketch2shape.core.context import Request
from sketch2shape.core.errors import OOMError
from sketch2shape.stages import s3_generate, s5_reconstruct
from sketch2shape.vision.prompt_composer import compose


def _sketch():
    img = np.full((600, 600, 3), 255, np.uint8)
    cv2.rectangle(img, (200, 120), (400, 480), (0, 0, 0), 4)
    return img


def _fake_s3(ctx, profile, n, scales, seed, resolution=None):
    cands = []
    for i in range(n):
        im = np.full((512, 512, 3), 200, np.uint8); a = np.zeros((512, 512), np.uint8)
        if i == 0:
            cv2.rectangle(a, (170, 60), (340, 450), 255, -1)
        else:
            cv2.circle(a, (256, 256), 150, 255, -1)
        im[a > 0] = (30, 100, 200)
        Image.fromarray(im).save(ctx.run_dir / "candidates" / f"cand_{i}.png")
        cands.append({"index": i, "image": Image.fromarray(im), "alpha": a, "matte": {}, "seed": seed + i,
                      "scale": 0.7, "prompt": "p", "hedge": i == n - 1, "score": 0.9 - 0.1 * i, "terms": {}})
    ctx.data.update(candidates=cands, rank=list(range(n)), gen_profile=profile)


class _StubBackend:
    name = "stub"; cfg = {"calibration": {"input_view": {"yaw": 0, "pitch": 0}}}

    def reconstruct(self, rgba, *, quality, seed, out_dir, on_line=None, cancel=None):
        out_dir.mkdir(parents=True, exist_ok=True)
        m = trimesh.creation.box(extents=[0.45, 1.0, 0.45])
        m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.tile([30, 100, 200, 255], (len(m.vertices), 1)))
        m.export(out_dir / "mesh.obj")
        from sketch2shape.backends.base import RawMesh
        return RawMesh(out_dir / "mesh.obj", {"backend": "stub"})


def _patch(monkeypatch, chain):
    monkeypatch.setattr(vram, "detect", lambda: vram.GpuInfo(True, "FakeGPU", 16.0, 15.0, (7, 5)))
    monkeypatch.setattr(s3_generate, "run", _fake_s3)

    class Reg:
        def chain(self, *a, **k): return [(b, "balanced") for b in chain]
        def status(self): return {}
    monkeypatch.setattr(s5_reconstruct, "BackendRegistry", Reg)


def test_smoke_end_to_end(monkeypatch, tmp_path):
    _patch(monkeypatch, [_StubBackend()])
    res = P.Pipeline().run(Request(image=_sketch(), source="canvas", object_override="box", seed=1, out_root=str(tmp_path)))
    assert res.ok, res.message
    rj = json.loads(res.run_json.read_text())
    assert res.glb.exists() and res.obj_zip.exists()
    assert rj["validation"]["ok"] and rj["tier"] == 2 and rj["selected_candidate"] == 0
    assert rj["sketch_fidelity"] > 0.8 and rj["recon_consistency"] > 0.8
    assert set(rj["stages"]) >= {"s1_input", "s2_understand", "s4_prepare", "s5_reconstruct", "s8_verify"}


def test_blank_canvas_is_friendly(monkeypatch, tmp_path):
    _patch(monkeypatch, [_StubBackend()])
    res = P.Pipeline().run(Request(image=np.full((300, 300, 3), 255, np.uint8), source="canvas", out_root=str(tmp_path)))
    assert not res.ok and "empty" in res.message


def test_no_cuda_message(monkeypatch, tmp_path):
    monkeypatch.setattr(vram, "detect", lambda: vram.GpuInfo(False))
    res = P.Pipeline().run(Request(image=_sketch(), out_root=str(tmp_path)))
    assert not res.ok and "NVIDIA GPU" in res.message


def test_backend_oom_falls_through_to_next(monkeypatch, tmp_path):
    class OomBackend(_StubBackend):
        name = "oomy"
        def reconstruct(self, *a, **k): raise OOMError("oomy ran out of GPU memory")
    _patch(monkeypatch, [OomBackend(), _StubBackend()])
    res = P.Pipeline().run(Request(image=_sketch(), source="canvas", object_override="box", seed=1, out_root=str(tmp_path)))
    rj = json.loads(res.run_json.read_text())
    assert res.ok and rj["backend"] == "stub" and "oom_oomy" in rj["warnings"]


def test_s3_oom_ladder(monkeypatch, tmp_path):
    calls = []
    def flaky(ctx, profile, n, *a, **k):
        calls.append((profile, n))
        if len(calls) < 3:
            raise RuntimeError("CUDA out of memory. Tried to allocate")
        return _fake_s3(ctx, profile, n, *a, **k)
    _patch(monkeypatch, [_StubBackend()])
    monkeypatch.setattr(s3_generate, "run", flaky)
    res = P.Pipeline().run(Request(image=_sketch(), source="canvas", object_override="box", seed=1, out_root=str(tmp_path)))
    assert res.ok and calls == [("balanced", 4), ("balanced", 2), ("lite", 2)]
