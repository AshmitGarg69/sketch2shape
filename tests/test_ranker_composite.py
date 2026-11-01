import cv2
import numpy as np
from sketch2shape.vision.ranker import cleanliness, score_candidate
from sketch2shape.vision.silhouette import extract_silhouette

S = 512


def _sketch():
    m = np.zeros((S, S), np.uint8); cv2.rectangle(m, (150, 100), (350, 420), 1, 5)
    return m > 0


def _cand(shape):
    rgb = np.full((S, S, 3), 230, np.uint8); a = np.zeros((S, S), np.uint8)
    if shape == "match":
        cv2.rectangle(a, (120, 90), (400, 500), 255, -1)   # same aspect-ish tall box, different position/scale
    else:
        cv2.circle(a, (256, 256), 180, 255, -1)
    rgb[a > 0] = (40, 90, 200)
    return rgb, a


def test_matching_shape_outranks_wrong_shape():
    st = _sketch(); sil = extract_silhouette(st)
    good = score_candidate(*_cand("match"), stroke=st, skeleton=None, silhouette=sil, semantic=0.5)
    bad = score_candidate(*_cand("circle"), stroke=st, skeleton=None, silhouette=sil, semantic=0.5)
    assert good.total > bad.total + 0.1, (good, bad)


def test_cleanliness_penalises_border_and_fragments():
    a = np.zeros((S, S), np.uint8); cv2.circle(a, (256, 256), 100, 255, -1)
    b = a.copy(); b[:, :20] = 255
    assert cleanliness(a) > 0.9 and cleanliness(b) < 0.5
