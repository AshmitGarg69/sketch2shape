import cv2
import numpy as np
from sketch2shape.vision.matting import clean_alpha
from sketch2shape.vision.prepare import prepare_rgba


def test_prepare_centres_and_fills_85pct():
    rgb = np.full((600, 900, 3), 200, np.uint8); a = np.zeros((600, 900), np.uint8)
    cv2.rectangle(a, (600, 100), (800, 500), 255, -1); rgb[a > 0] = (10, 120, 200)
    out = np.asarray(prepare_rgba(rgb, a, size=512))
    ys, xs = np.where(out[..., 3] > 127)
    assert out.shape == (512, 512, 4)
    assert abs((ys.max() - ys.min() + 1) - 0.85 * 512) < 4
    assert abs((xs.min() + xs.max()) / 2 - 256) < 3 and abs((ys.min() + ys.max()) / 2 - 256) < 3


def test_clean_alpha_keeps_largest_and_rejects_border():
    a = np.zeros((400, 400), np.uint8); cv2.circle(a, (200, 200), 100, 255, -1); cv2.circle(a, (30, 30), 8, 255, -1)
    out, rep = clean_alpha(a)
    assert out[30, 30] == 0 and "reject" not in rep
    a2 = a.copy(); a2[:, :5] = 255; a2[195:205, :110] = 255
    _, rep2 = clean_alpha(a2)
    assert rep2.get("reject") == "object touches the image border"


def test_sketch_recovery_adds_dropped_support_but_keeps_handle_hole():
    from sketch2shape.vision.matting import recover_with_sketch
    rgb = np.full((512, 512, 3), 128, np.uint8)
    cv2.rectangle(rgb, (180, 120), (320, 380), (240, 240, 240), -1)        # mug body
    cv2.rectangle(rgb, (320, 180), (390, 300), (240, 240, 240), -1)        # handle
    cv2.rectangle(rgb, (340, 205), (370, 275), (100, 100, 100), -1)        # handle hole (shadowed bg)
    cv2.ellipse(rgb, (250, 400), (150, 30), 0, 0, 360, (150, 90, 40), -1)  # saucer (dropped by matting)
    alpha = np.zeros((512, 512), np.uint8)
    cv2.rectangle(alpha, (180, 120), (320, 380), 255, -1); cv2.rectangle(alpha, (320, 180), (390, 300), 255, -1)
    alpha[205:276, 340:371] = 0
    sil = np.zeros((512, 512), bool)
    sil[110:390, 175:395] = True; sil[365:435, 95:405] = True
    out, added = recover_with_sketch(rgb, alpha, sil)
    assert added > 0.02 and out[400, 150] == 255      # saucer recovered
    assert out[240, 355] == 0                         # handle hole preserved
