"""Generate simple SYNTHETIC line sketches (clearly labelled) for smoke/golden runs: OpenCV polylines with jitter.
Real hand-drawn sketches (e.g. tests/golden/mug_sketch.jpeg) remain the primary test inputs."""
import sys
from pathlib import Path

import cv2
import numpy as np

RNG = np.random.default_rng(0)


def jitter_line(img, pts, w=4):
    pts = np.asarray(pts, float)
    dense = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(2, int(np.linalg.norm(b - a) / 6))
        seg = np.linspace(a, b, n)
        seg += RNG.normal(0, 0.8, seg.shape)
        dense.append(seg)
    cv2.polylines(img, [np.concatenate(dense).round().astype(np.int32)], False, 0, w, cv2.LINE_AA)


def ellipse(img, c, ax, a0=0, a1=360, w=4):
    t = np.radians(np.linspace(a0, a1, 80))
    jitter_line(img, np.c_[c[0] + ax[0] * np.cos(t), c[1] + ax[1] * np.sin(t)], w)


def chair():
    im = np.full((768, 768), 255, np.uint8)
    jitter_line(im, [(250, 120), (520, 120), (520, 400), (250, 400), (250, 120)])      # backrest
    jitter_line(im, [(250, 400), (200, 470), (470, 470), (520, 400)])                    # seat
    jitter_line(im, [(200, 470), (200, 490), (470, 490), (470, 470)])
    for x0, x1 in ((205, 215), (460, 465)):
        jitter_line(im, [(x0, 490), (x0, 680)]); jitter_line(im, [(x0 + 18, 490), (x0 + 18, 680)])
    jitter_line(im, [(515, 410), (515, 640)]); jitter_line(im, [(500, 420), (500, 640)])
    return im


def car_side():
    im = np.full((768, 768), 255, np.uint8)
    jitter_line(im, [(70, 470), (70, 400), (180, 380), (270, 300), (480, 300), (580, 380), (700, 395), (705, 470),
                     (640, 470)])
    jitter_line(im, [(540, 470), (250, 470)]); jitter_line(im, [(150, 470), (70, 470)])
    for cx in (200, 590):
        ellipse(im, (cx, 470), (52, 52)); ellipse(im, (cx, 470), (20, 20))
    jitter_line(im, [(290, 315), (370, 315), (370, 380), (215, 380), (290, 315)])
    jitter_line(im, [(390, 315), (470, 315), (545, 380), (390, 380), (390, 315)])
    return im


def lamp():
    im = np.full((768, 768), 255, np.uint8)
    jitter_line(im, [(300, 120), (468, 120), (540, 330), (228, 330), (300, 120)])        # shade
    jitter_line(im, [(374, 330), (374, 600)]); jitter_line(im, [(394, 330), (394, 600)])  # stem
    ellipse(im, (384, 630), (130, 32))                                                   # base
    jitter_line(im, [(254, 630), (254, 655)]); jitter_line(im, [(514, 630), (514, 655)])
    ellipse(im, (384, 655), (130, 32), 0, 180)
    return im


def open_doodle():
    im = np.full((768, 768), 255, np.uint8)
    t = np.linspace(0, 5 * np.pi, 200)
    jitter_line(im, np.c_[384 + 18 * t * np.cos(t), 384 + 18 * t * np.sin(t)], 5)
    return im


def main(out="examples/sketches"):
    Path(out).mkdir(parents=True, exist_ok=True)
    for name, fn in (("synthetic_chair", chair), ("synthetic_car_side", car_side), ("synthetic_lamp", lamp),
                     ("synthetic_open_doodle", open_doodle)):
        cv2.imwrite(f"{out}/{name}.png", fn())
    import shutil
    shutil.copy("tests/golden/mug_sketch.jpeg", f"{out}/handdrawn_mug.jpg")


if __name__ == "__main__":
    main(*sys.argv[1:])
