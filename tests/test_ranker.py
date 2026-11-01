"""Stroke-fidelity ranker regression test (numpy + opencv only)."""
import cv2
import numpy as np
from sketch2shape.vision.ranker_stroke import stroke_fidelity

S = 256
def _sketch():
    sk = np.zeros((S, S), np.uint8)
    cv2.rectangle(sk, (70, 60), (170, 200), 255, 3)
    cv2.ellipse(sk, (185, 130), (28, 38), 0, -90, 90, 255, 3)
    return sk > 0

def _cand(kind):
    rgb = np.full((S, S, 3), 230, np.uint8); a = np.zeros((S, S), np.uint8)
    cv2.rectangle(a, (70, 60), (170, 200), 255, -1); cv2.ellipse(a, (185, 130), (28, 38), 0, -90, 90, 255, 6)
    rgb[a > 0] = (60, 90, 200)
    if kind == "busy":
        for x in range(60, 230, 5): cv2.line(rgb, (x, 40), (x - 40, 220), (20, 30, 90), 1)
        for y in range(40, 220, 6): cv2.line(rgb, (40, y), (230, y + 5), (200, 210, 255), 1)
    if kind == "halluc":
        cv2.circle(a, (120, 40), 30, 255, -1); cv2.rectangle(a, (40, 200), (200, 225), 255, -1)
        rgb[a > 0] = (60, 90, 200)
    return rgb, a > 0

def test_ranker_prefers_clean_over_textured_and_over_hallucinated():
    st = _sketch()
    f = {k: stroke_fidelity(*_cand(k), st)["f"] for k in ("clean", "busy", "halluc")}
    print(f)
    assert f["clean"] > 0.9
    assert f["clean"] > f["halluc"] + 0.15
    assert f["clean"] > f["busy"] + 0.4, f
