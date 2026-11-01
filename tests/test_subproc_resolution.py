"""A backend with a wrong/missing interpreter is skipped by the handshake; the next one is used (acceptance #11)."""
import sys

from sketch2shape.backends import base
from sketch2shape.backends.registry import BackendRegistry
from sketch2shape.core import subproc

CAL = {"phase0_passed": True, "handedness_checked": True, "input_view": {"yaw": 0, "pitch": 0}}


def _cfg(python):
    return {"python": python, "repo": "src", "runner": "pyproject.toml", "calibration": dict(CAL)}


def test_missing_interpreter_is_skipped(monkeypatch):
    real = subproc.handshake.__wrapped__

    def fake(python, import_check="", cwd=None):
        if python == sys.executable:
            return {"cuda": True, "torch": "stub", "cap": [7, 5]}
        return real(python, import_check, cwd)

    monkeypatch.setattr(base.subproc, "handshake", fake)
    reg = BackendRegistry({"instantmesh": _cfg("envs/does_not_exist/bin/python"), "triposr": _cfg(sys.executable)})
    chain = [b.name for b, _ in reg.chain("balanced")]
    assert chain == ["triposr"]
    assert "handshake failed" in reg.status()["instantmesh"]


def test_uncalibrated_backend_refused():
    cfg = _cfg(sys.executable); cfg["calibration"]["handedness_checked"] = False
    reg = BackendRegistry({"triposr": cfg})
    assert reg.chain("fast") == [] and "not calibrated" in reg.status()["triposr"]


def test_env_override(monkeypatch):
    monkeypatch.setenv("S2S_PYTHON_TRIPOSR", "/opt/x/python")
    assert str(subproc.resolve_python("triposr", "envs/triposr/bin/python")) == "/opt/x/python"


def test_run_streams_and_kills_on_timeout(tmp_path):
    lines = []
    r = subproc.run([sys.executable, "-c", "print('hi', flush=True); import time; time.sleep(30)"],
                    cwd=tmp_path, env=subproc.backend_env(), timeout=2, on_line=lines.append)
    assert r.timed_out and lines == ["hi"] and r.seconds < 10


def test_oom_marker_detected(tmp_path):
    r = subproc.run([sys.executable, "-c", "print('torch.cuda.OutOfMemoryError: CUDA out of memory'); raise SystemExit(1)"],
                    cwd=tmp_path, env=subproc.backend_env(), timeout=20)
    assert r.oom and r.rc == 1


def test_quality_steps_down_to_fit_vram(monkeypatch):
    monkeypatch.setattr(base.subproc, "handshake", lambda *a, **k: {"cuda": True})
    cfg = _cfg(sys.executable); cfg["vram_gb_by_quality"] = {"fast": 3.41, "balanced": 5.55, "best": 5.55}
    big = _cfg(sys.executable); big["vram_gb_by_quality"] = {"fast": 11.3, "balanced": 9.44, "best": 9.44}
    reg = BackendRegistry({"instantmesh": big, "triposr": cfg})
    assert [(b.name, q) for b, q in reg.chain("balanced", free_vram_gb=5.8)] == [("triposr", "fast")]
    assert [(b.name, q) for b, q in reg.chain("balanced", free_vram_gb=14.5)] == [("instantmesh", "balanced"), ("triposr", "balanced")]
