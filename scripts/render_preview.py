"""Pure NumPy/OpenCV turntable preview of a GLB (no OpenGL): per-face base colour (texture at face-centroid UV,
or vertex colours) with Lambert shading and a painter's-algorithm z-order. For quick visual checks / README."""
import sys

import cv2
import numpy as np
import trimesh


def glb_color0(path):
    """Read COLOR_0 straight from the GLB buffer (trimesh 5.x drops it on load when a material is present)."""
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
    from sketch2shape.mesh.glb_patch import read_glb

    js, binary = read_glb(path)
    prim = js["meshes"][0]["primitives"][0]
    if "COLOR_0" not in prim["attributes"]:
        return None
    acc = js["accessors"][prim["attributes"]["COLOR_0"]]
    bv = js["bufferViews"][acc["bufferView"]]
    dt = {5121: np.uint8, 5123: np.uint16, 5126: np.float32}[acc["componentType"]]
    ncomp = {"VEC3": 3, "VEC4": 4}[acc["type"]]
    off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    a = np.frombuffer(binary, dt, acc["count"] * ncomp, off).reshape(-1, ncomp)[:, :3].astype(float)
    return a if dt == np.float32 and a.max() > 1.0 else a * (255.0 / (np.iinfo(dt).max if dt != np.float32 else 1.0))


def face_colors(m, vcol=None):
    if vcol is not None and len(vcol) == len(m.vertices):
        return vcol[m.faces].mean(1)
    vis = m.visual
    if getattr(vis, "kind", None) == "texture" and getattr(vis, "uv", None) is not None:
        mat = vis.material
        img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
        if img is not None:
            tex = np.asarray(img.convert("RGB"))
            uv = vis.uv[m.faces].mean(1)
            h, w = tex.shape[:2]
            x = np.clip((uv[:, 0] % 1) * (w - 1), 0, w - 1).astype(int)
            y = np.clip((1 - uv[:, 1] % 1) * (h - 1), 0, h - 1).astype(int)
            return tex[y, x].astype(float)
    try:
        return np.asarray(vis.vertex_colors)[m.faces][:, :, :3].mean(1).astype(float)
    except Exception:
        return np.full((len(m.faces), 3), 180.0)


def render(m, yaw, pitch=15, size=384, vcol=None):
    ry, rp = np.radians(yaw), np.radians(pitch)
    R = np.array([[1, 0, 0], [0, np.cos(rp), -np.sin(rp)], [0, np.sin(rp), np.cos(rp)]]) @ \
        np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    v = (m.vertices - m.bounds.mean(0)) @ R.T
    s = size * 0.85 / np.ptp(v[:, :2], axis=0).max()
    px = np.c_[v[:, 0] * s + size / 2, size / 2 - v[:, 1] * s]
    n = m.face_normals @ R.T
    shade = np.clip(0.35 + 0.65 * np.abs(n @ np.array([0.3, 0.4, 0.87])), 0, 1)
    col = face_colors(m, vcol) * shade[:, None]
    img = np.full((size, size, 3), 235, np.uint8)
    order = np.argsort(v[m.faces][:, :, 2].mean(1))
    tris = px[m.faces].round().astype(np.int32)
    for i in order:
        cv2.fillConvexPoly(img, tris[i], tuple(int(c) for c in col[i][::-1]))
    return img


if __name__ == "__main__":
    m = trimesh.load(sys.argv[1], force="mesh", process=False)
    vc = glb_color0(sys.argv[1]) if sys.argv[1].endswith(".glb") else None
    cv2.imwrite(sys.argv[2], np.hstack([render(m, y, vcol=vc) for y in (0, 60, 150, 270)]))
