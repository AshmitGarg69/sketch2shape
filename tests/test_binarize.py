import cv2
import numpy as np
import pytest
from sketch2shape.vision.binarize import (BlankSketchError, binarize, check_not_blank, flatten_rgba,
                                          normalize_strokes)


def _canvas_rect():
    img = np.full((600, 800, 3), 255, np.uint8)
    cv2.rectangle(img, (200, 150), (500, 450), (0, 0, 0), 5)
    return img


def test_flatten_rgba_transparent_is_white():
    rgba = np.zeros((10, 10, 4), np.uint8)
    assert (flatten_rgba(rgba) == 255).all()


def test_canvas_binarize_and_blank_rejection():
    m = binarize(_canvas_rect(), "canvas")
    assert 0.005 < m.mean() < 0.05
    with pytest.raises(BlankSketchError):
        check_not_blank(binarize(np.full((300, 300, 3), 255, np.uint8), "canvas"))


def test_upload_binarize_survives_uneven_lighting():
    img = _canvas_rect().astype(np.float32)
    grad = np.linspace(0.45, 1.0, img.shape[1])[None, :, None]  # strong left-to-right shadow
    photo = (img * grad).astype(np.uint8)
    m = binarize(photo, "upload")
    ref = binarize(_canvas_rect(), "canvas")
    assert (m & ref).sum() / ref.sum() > 0.8      # strokes recovered
    assert m.mean() < 0.05                        # shadow not turned into ink


def test_normalize_strokes_uniform_scale_and_thickness():
    m = np.zeros((600, 800), bool)
    cv2.rectangle(m.view(np.uint8), (100, 250), (700, 350), 1, 9)  # wide 6:1 box, thick strokes
    n = normalize_strokes(m, size=768)
    ys, xs = np.where(n)
    w, h = np.ptp(xs), np.ptp(ys)
    assert abs(w - 0.8 * 768) < 10 and 4.5 < w / h < 7.5  # aspect preserved, bbox fills 80 %
    # thickness ~4 px: ink area / skeleton length
    assert n.sum() / (2 * (w + h)) < 6
