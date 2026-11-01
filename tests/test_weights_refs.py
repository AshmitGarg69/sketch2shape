"""Offline backends resolve revision "main" via refs/main; pinned downloads must write it (Kaggle offline bug)."""
import pytest
from sketch2shape.core.weights import pin_ref

SHA = "5b521936b01fbe1890f6f9baed0254ab6351c04a"


def test_pin_ref_writes_main(tmp_path):
    snap = tmp_path / "models--stabilityai--TripoSR" / "snapshots" / SHA
    snap.mkdir(parents=True)
    (snap / "config.yaml").write_text("x")
    p = pin_ref(tmp_path, "stabilityai/TripoSR", SHA)
    assert p.read_text() == SHA


def test_pin_ref_refuses_missing_snapshot(tmp_path):
    with pytest.raises(FileNotFoundError):
        pin_ref(tmp_path, "stabilityai/TripoSR", SHA)
