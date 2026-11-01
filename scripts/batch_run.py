"""Run several sketches through ONE in-process Pipeline (like the Gradio server does), so warm-path behaviour
(e.g. the generator parked in RAM) is measured. Args file: one `sketch2shape run`-style arg line per row."""
import argparse
import json
import shlex
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sketch2shape.core.context import Request  # noqa: E402
from sketch2shape.core.pipeline import Pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs"); ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    p = argparse.ArgumentParser()
    for k in ("--sketch", "--prompt", "--object", "--view", "--material"):
        p.add_argument(k, default="")
    p.add_argument("--preset", default="balanced"); p.add_argument("--seed", type=int)
    pipe = Pipeline()
    for line in Path(a.runs).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        r = p.parse_args(shlex.split(line))
        im = Image.open(r.sketch)
        img = np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))
        res = pipe.run(Request(image=img, source="upload", prompt=r.prompt, object_override=r.object,
                               viewpoint=r.view or "Auto", material=r.material or "Auto", quality=r.preset,
                               seed=r.seed, out_root=a.out))
        rj = json.loads(res.run_json.read_text())
        print(json.dumps({"sketch": r.sketch, "ok": res.ok, "msg": res.message, "total": rj.get("total_seconds"),
                          "s3": rj.get("s3_timing"), "s5": rj["stages"].get("s5_reconstruct", {}).get("seconds"),
                          "match": rj.get("sketch_fidelity"), "notice": rj.get("notice"), "fallbacks": rj.get("fallbacks")}),
              flush=True)


if __name__ == "__main__":
    main()
