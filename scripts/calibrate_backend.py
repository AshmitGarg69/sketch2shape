"""Phase-0c calibration (spec §14): run a backend adapter on the asymmetric golden RGBA, search the input view
(yaw ∈ −20…20, pitch ∈ {0,10,20,30}) and FAIL if the mirrored render fits better than the direct one.
Writes calibration.{input_view, handedness_checked, peak_vram_gb} into config/backends.yaml — the only writer
besides scripts/phase0.py (which sets phase0_passed via --mark-phase0).

    python scripts/calibrate_backend.py triposr --image tests/golden/asym_rgba.png [--mark-phase0 docs/phase0/x.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sketch2shape.backends.base import SubprocessBackend  # noqa: E402
from sketch2shape.mesh.orient import normalize_pose  # noqa: E402
from sketch2shape.stages.s6_cleanup import load_raw  # noqa: E402
from sketch2shape.vision.prepare import prepare_rgba  # noqa: E402
from sketch2shape.vision.silhouette_render import fit_letterbox, input_view_check, iou, silhouette_ortho  # noqa: E402

CFG = ROOT / "config" / "backends.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("backend")
    ap.add_argument("--image", default=str(ROOT / "tests/golden/asym_rgba.png"))
    ap.add_argument("--mark-phase0", help="phase0 JSON(s) proving the backend passed Phase 0 (comma-separated)")
    ap.add_argument("--quality", default="balanced")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    doc = yaml.safe_load(CFG.read_text())
    cfg = doc["backends"][a.backend]
    if a.mark_phase0:
        recs = [json.loads(Path(p).read_text()) for p in a.mark_phase0.split(",")]
        ok = all(r.get("passed") and r.get("backend") == a.backend for r in recs)
        cfg["calibration"]["phase0_passed"] = bool(ok)
        cfg["calibration"]["peak_vram_gb"] = max(r["online"]["vram_peak_gb"] for r in recs)
        if not ok:
            CFG.write_text(yaml.safe_dump(doc, sort_keys=False))
            raise SystemExit(f"{a.backend}: Phase-0 records do not show a pass")

    # Run the adapter directly (bypassing the calibrated-only gate, which this script exists to satisfy).
    tmp_cal = dict(cfg, calibration=dict(cfg["calibration"], phase0_passed=True, handedness_checked=True))
    b = SubprocessBackend(a.backend, tmp_cal)
    if not b.is_available():
        raise SystemExit(f"{a.backend} not runnable: {b.unavailable_reason()}")
    out = Path(a.out or tempfile.mkdtemp(prefix=f"cal_{a.backend}_"))
    out.mkdir(parents=True, exist_ok=True)
    src = np.asarray(Image.open(a.image).convert("RGBA"))
    rgba = prepare_rgba(src[..., :3], src[..., 3], size=1024)
    rgba_p = out / "asym_prepared.png"
    rgba.save(rgba_p)
    raw = b.reconstruct(rgba_p, quality=a.quality, seed=0, out_dir=out / "raw",
                        on_line=lambda ln: print(ln, flush=True))
    m = normalize_pose(load_raw(raw.path))
    V, F = np.asarray(m.vertices), np.asarray(m.faces)
    target = np.asarray(rgba)[..., 3] > 127
    t = fit_letterbox(target, 256)
    grid = []
    for pitch in (0, 10, 20, 30):
        for yaw in range(-20, 21, 5):
            r = fit_letterbox(silhouette_ortho(V, F, yaw, pitch, size=256), 256)
            grid.append((iou(r, t), iou(r[:, ::-1], t), yaw, pitch))
    best = max(grid, key=lambda g: g[0])
    best_m = max(grid, key=lambda g: g[1])
    direct, mirrored = input_view_check(V, F, target, best[2], best[3])
    report = {"backend": a.backend, "best_direct": {"iou": round(best[0], 4), "yaw": best[2], "pitch": best[3]},
              "best_mirrored": {"iou": round(best_m[1], 4), "yaw": best_m[2], "pitch": best_m[3]},
              "at_input_view": {"direct": round(direct, 4), "mirrored": round(mirrored, 4)},
              "vram_peak_gb": raw.meta.get("vram_peak_gb"), "seconds": raw.meta.get("seconds")}
    handed_ok = best[0] >= best_m[1] and direct > mirrored
    report["handedness_ok"] = bool(handed_ok)
    print(json.dumps(report, indent=2))
    (out / "calibration.json").write_text(json.dumps(report, indent=2))
    cfg["calibration"]["input_view"] = {"yaw": int(best[2]), "pitch": int(best[3])}
    cfg["calibration"]["handedness_checked"] = bool(handed_ok)
    if raw.meta.get("vram_peak_gb"):
        cfg["calibration"]["peak_vram_gb"] = max(cfg["calibration"].get("peak_vram_gb") or 0, raw.meta["vram_peak_gb"])
    CFG.write_text(yaml.safe_dump(doc, sort_keys=False))
    if not handed_ok:
        raise SystemExit(f"{a.backend}: MIRRORED render fits better — fix the axis convention in the adapter.")


if __name__ == "__main__":
    main()
