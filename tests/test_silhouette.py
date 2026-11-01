import cv2
import numpy as np
from sketch2shape.vision.silhouette import extract_silhouette


def _m():
    return np.zeros((512, 512), np.uint8)


def test_closed_rect_gives_filled_interior():
    m = _m(); cv2.rectangle(m, (100, 100), (400, 400), 1, 4)
    s = extract_silhouette(m > 0)
    assert s is not None and abs(s.sum() / (300 * 300) - 1) < 0.08


def test_small_gap_is_bridged():
    m = _m(); cv2.rectangle(m, (100, 100), (400, 400), 1, 4); m[95:105, 240:255] = 0
    s = extract_silhouette(m > 0)
    assert s is not None and s.sum() > 0.85 * 300 * 300


def test_open_doodle_returns_none():
    m = _m(); pts = np.array([[60, 400], [150, 120], [250, 380], [350, 130], [450, 400]], np.int32)
    cv2.polylines(m, [pts], False, 1, 4)
    assert extract_silhouette(m > 0) is None
