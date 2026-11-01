"""sketch2shape CLI: run | doctor | serve | weights (spec §11)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_image(p: str):
    import numpy as np
    from PIL import Image

    im = Image.open(p)
    return np.asarray(im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"))


def cmd_run(a):
    if a.remote:
        from gradio_client import Client, handle_file

        c = Client(a.remote)
        out = c.predict(handle_file(a.sketch), a.prompt or "", a.preset, "" if a.seed is None else str(a.seed),
                        api_name="/generate_api")
        print(json.dumps(out, indent=2))
        return 0
    from .core.context import Request
    from .core.pipeline import Pipeline

    req = Request(image=_load_image(a.sketch), source="upload", prompt=a.prompt or "", quality=a.preset,
                  seed=a.seed, out_root=a.out, object_override=a.object or "", viewpoint=a.view, material=a.material)
    res = Pipeline().run(req, progress=lambda s, f, m: print(f"[{s:11s} {f:4.0%}] {m}", flush=True))
    print(json.dumps({"ok": res.ok, "message": res.message, "glb": str(res.glb), "obj_zip": str(res.obj_zip),
                      "run_json": str(res.run_json), "badges": res.badges}, indent=2, default=str))
    return 0 if res.ok else 1


def cmd_doctor(a):
    from .doctor import main as doctor

    return doctor()


def cmd_serve(a):
    from .ui.gradio_app import build

    demo = build()
    demo.queue(default_concurrency_limit=1, max_size=8).launch(server_name=a.host, server_port=a.port, share=a.share,
                                                                allowed_paths=[str(Path(a.out).resolve())])
    return 0


def cmd_weights(a):
    from .core import weights

    weights.download(a.profile, a.backends.split(",") if a.backends else [], a.extras.split(",") if a.extras else [])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser("sketch2shape")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--sketch", required=True)
    r.add_argument("--prompt", default="")
    r.add_argument("--object", default="", help="override the detected object noun")
    r.add_argument("--preset", default="balanced", choices=["fast", "balanced", "best"])
    r.add_argument("--view", default="Auto", choices=["Auto", "front", "side profile", "back", "top-down", "front three-quarter"])
    r.add_argument("--material", default="Auto")
    r.add_argument("--seed", type=int)
    r.add_argument("--remote", help="URL of a running sketch2shape Gradio app")
    r.add_argument("--out", default="outputs")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=7860)
    s.add_argument("--share", action="store_true")
    s.add_argument("--out", default="outputs")
    s.set_defaults(fn=cmd_serve)
    w = sub.add_parser("weights")
    w.add_argument("--profile", required=True, choices=["lite", "balanced"])
    w.add_argument("--backends", default="")
    w.add_argument("--extras", default="")
    w.set_defaults(fn=cmd_weights)
    a = ap.parse_args(argv)
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
