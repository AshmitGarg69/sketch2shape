"""Backend subprocess launcher (spec §7.1 launch hygiene).

argv list (no shell), interpreter invoked directly, explicit env, line-streamed stdout, hard timeout,
whole-process-tree kill on timeout/cancel, stderr tail kept, OOM marker detection.
"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable

OOM_MARKERS = ("CUDA out of memory", "OutOfMemoryError", "CUBLAS_STATUS_ALLOC_FAILED", "S2S_OOM")
OOM_EXIT_CODE = 77  # adapters exit with this code on torch.cuda.OutOfMemoryError

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class ProcResult:
    rc: int | None
    seconds: float
    tail: list[str] = field(default_factory=list)
    oom: bool = False
    timed_out: bool = False
    cancelled: bool = False


def resolve_python(name: str, configured: str) -> Path:
    """S2S_PYTHON_<NAME> overrides config; relative paths resolve against the repo root;
    `bin/python` is swapped for `Scripts/python.exe` on Windows."""
    override = os.environ.get(f"S2S_PYTHON_{name.upper()}")
    if override:
        return Path(override)
    if configured == "auto":
        return Path(sys.executable)
    p = Path(configured)
    if os.name == "nt" and p.parts[-2:] == ("bin", "python"):
        p = p.parent.parent / "Scripts" / "python.exe"
    return p if p.is_absolute() else REPO_ROOT / p


def backend_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    weights = Path(env.get("S2S_WEIGHTS", REPO_ROOT / "weights"))
    env.setdefault("HF_HOME", str(weights / "hf"))
    env.setdefault("TORCH_HOME", str(weights / "torch"))
    env.setdefault("U2NET_HOME", str(weights / "u2net"))
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("PYTHONPATH", None)  # adapters must not see the parent's packages (rule 12)
    env.update({k: str(v) for k, v in (extra or {}).items()})
    return env


@lru_cache(maxsize=None)
def handshake(python: str, import_check: str = "", cwd: str | None = None) -> dict | None:
    """Ask the backend interpreter about torch/CUDA (+ import its key module, run from the backend repo dir so
    repo-local packages such as TripoSR's `tsr` resolve). None => unusable. Cached per process."""
    code = ("import json,torch;d=dict(cuda=torch.cuda.is_available(),torch=torch.__version__,"
            "cap=list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None)"
            + (f";import sys;sys.path.insert(0,'.');import {import_check}" if import_check else "") + ";print('S2S_HS'+json.dumps(d))")
    if not Path(python).exists():
        return None
    try:
        out = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=180,
                             env=backend_env(), cwd=cwd).stdout
        line = next(ln for ln in out.splitlines() if ln.startswith("S2S_HS"))
        return json.loads(line[6:])
    except Exception:  # noqa: BLE001
        return None


def _kill_tree(proc: subprocess.Popen):
    try:
        import psutil

        parent = psutil.Process(proc.pid)
        for c in parent.children(recursive=True):
            c.kill()
        parent.kill()
    except Exception:  # noqa: BLE001
        proc.kill()


def run(argv: list[str], *, cwd: str | Path, env: dict, timeout: float,
        on_line: Callable[[str], None] | None = None, cancel: threading.Event | None = None,
        keep: int = 60) -> ProcResult:
    t0 = time.time()
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1, errors="replace", **kw)
    tail: collections.deque[str] = collections.deque(maxlen=keep)

    def pump():
        for line in proc.stdout:
            line = line.rstrip()
            tail.append(line)
            if on_line:
                try:
                    on_line(line)
                except Exception:  # noqa: BLE001
                    pass

    th = threading.Thread(target=pump, daemon=True)
    th.start()
    timed_out = cancelled = False
    while proc.poll() is None:
        if time.time() - t0 > timeout:
            timed_out = True
        elif cancel is not None and cancel.is_set():
            cancelled = True
        if timed_out or cancelled:
            _kill_tree(proc)
            break
        time.sleep(0.2)
    proc.wait()
    th.join(timeout=5)
    lines = list(tail)
    oom = proc.returncode == OOM_EXIT_CODE or any(m in ln for ln in lines for m in OOM_MARKERS)
    return ProcResult(proc.returncode, round(time.time() - t0, 2), lines, oom, timed_out, cancelled)
