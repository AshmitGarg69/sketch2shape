"""Renderer / comparison regression tests (numpy + opencv only)."""
import time
import cv2
import numpy as np
from sketch2shape.vision.silhouette_render import (OrthoView, fit_letterbox, fidelity_near_input_view,
                                                   input_view_check, iou, silhouette_ortho)

def icosphere(sub=3):
    t = (1 + 5 ** 0.5) / 2
    v = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    f = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2],
                  [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9], [4, 9, 5],
                  [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    for _ in range(sub):
        cache, nv, nf = {}, list(v), []
        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = nv[a] + nv[b]
                cache[key] = len(nv)
                nv.append(m / np.linalg.norm(m))
            return cache[key]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        v, f = np.array(nv), np.array(nf)
    return v, f

def box(sx=1.0, sy=1.0, sz=1.0):
    x, y, z = sx / 2, sy / 2, sz / 2
    v = np.array([[-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z], [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z]], float)
    f = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
                  [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3]])
    return v, f

def _merge(*meshes):
    vs, fs, off = [], [], 0
    for v, f in meshes:
        vs.append(v); fs.append(f + off); off += len(v)
    return np.vstack(vs), np.vstack(fs)

def _cylinder(r=1.0, h=2.0, n=64):
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    bot = np.c_[r * np.cos(th), np.full(n, -h / 2), r * np.sin(th)]
    top = np.c_[r * np.cos(th), np.full(n, h / 2), r * np.sin(th)]
    v = np.vstack([bot, top, [[0, -h / 2, 0], [0, h / 2, 0]]])
    f = []
    for i in range(n):
        j = (i + 1) % n
        f += [[i, j, n + j], [i, n + j, n + i], [2 * n, j, i], [2 * n + 1, n + i, n + j]]
    return v, np.array(f)

def _torus(R=0.5, r=0.12, n=40, m=16):
    u = np.linspace(0, 2 * np.pi, n, endpoint=False); w = np.linspace(0, 2 * np.pi, m, endpoint=False)
    U, W = np.meshgrid(u, w, indexing="ij")
    v = np.c_[((R + r * np.cos(W)) * np.cos(U)).ravel(), ((R + r * np.cos(W)) * np.sin(U)).ravel(), (r * np.sin(W)).ravel()]
    f = []
    for i in range(n):
        for j in range(m):
            a, b = i * m + j, ((i + 1) % n) * m + j
            c, d = ((i + 1) % n) * m + (j + 1) % m, i * m + (j + 1) % m
            f += [[a, b, c], [a, c, d]]
    return v, np.array(f)

HANDLE_CENTRE = np.array([[1.05, 0.0, 0.0]])

def mug_handle_right():
    hv, hf = _torus()
    return _merge(_cylinder(), (hv + HANDLE_CENTRE[0], hf))

def mirrored(mesh):
    v, f = mesh
    v = v.copy(); v[:, 0] *= -1
    return v, f[:, ::-1]

def test_sphere_matches_true_disk():
    v, f = icosphere(3)
    size, fill = 512, 0.85
    disk = np.zeros((size, size), np.uint8)
    cv2.circle(disk, (size // 2, size // 2), int(round(size * fill / 2)), 255, -1)
    assert iou(silhouette_ortho(v, f, size=size, fill=fill), disk > 0) > 0.97

def test_axis_aligned_box_is_filled():
    v, f = box()
    m = silhouette_ortho(v, f, size=512, fill=0.85)
    assert 0.95 < m.sum() / (512 * 0.85) ** 2 < 1.06

def test_hole_is_preserved():
    v, f = mug_handle_right()
    m = silhouette_ortho(v, f, size=512, fill=0.85)
    cx, cy = OrthoView(v, 0, 0, 512, 0.85).project(HANDLE_CENTRE)[0]
    assert not m[int(round(cy)), int(round(cx))], "handle hole was filled"
    assert m.sum() > 0.2 * m.size * 0.5

def test_speed_30k_faces():
    v, f = icosphere(5)
    t = time.perf_counter(); silhouette_ortho(v, f); dt = time.perf_counter() - t
    assert dt < 0.5, dt

def test_letterbox_sees_aspect_ratio():
    wide = np.zeros((512, 512), bool); wide[200:312, 56:456] = True
    tall = np.zeros((512, 512), bool); tall[56:456, 200:312] = True
    assert iou(fit_letterbox(wide), fit_letterbox(tall)) < 0.3

def test_letterbox_is_scale_and_translation_invariant():
    a = np.zeros((512, 512), bool); a[100:400, 100:400] = True
    b = np.zeros((512, 512), bool); b[150:300, 250:400] = True
    assert iou(fit_letterbox(a), fit_letterbox(b)) > 0.97

def test_best_of_all_views_cannot_see_mirroring():
    mesh = mug_handle_right(); sketch = silhouette_ortho(*mesh, 0, 0)
    mv, mf = mirrored(mesh)
    best, _ = fidelity_near_input_view(mv, mf, sketch, 180, 0)
    assert best > 0.97

def test_input_view_check_detects_mirrored_mesh():
    mesh = mug_handle_right(); sketch = silhouette_ortho(*mesh, 0, 0)
    d, m = input_view_check(*mesh, sketch)
    assert d > 0.97 and d > m + 0.1
    mv, mf = mirrored(mesh)
    d2, m2 = input_view_check(mv, mf, sketch)
    assert m2 > 0.9 and m2 > d2 + 0.1

