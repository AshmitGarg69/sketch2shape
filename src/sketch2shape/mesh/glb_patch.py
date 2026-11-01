"""Patch PBR scalars in a GLB's JSON chunk without re-encoding the binary buffer (spec §9)."""
from __future__ import annotations

import json
import struct
from pathlib import Path

GLB_MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942


def read_glb(path) -> tuple[dict, bytes | None]:
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    off, js, binary = 12, None, None
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == JSON_CHUNK:
            js = json.loads(chunk.decode("utf-8").rstrip(" \x00"))
        elif ctype == BIN_CHUNK:
            binary = chunk
        off += 8 + clen
    return js, binary


def write_glb(path, js: dict, binary: bytes | None):
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * (-len(jb) % 4)
    parts = [struct.pack("<II", len(jb), JSON_CHUNK), jb]
    if binary is not None:
        bb = binary + b"\x00" * (-len(binary) % 4)
        parts += [struct.pack("<II", len(bb), BIN_CHUNK), bb]
    body = b"".join(parts)
    Path(path).write_bytes(struct.pack("<III", GLB_MAGIC, 2, 12 + len(body)) + body)


def patch_pbr(path, *, metallic: float, roughness: float, double_sided: bool = True, name: str | None = None) -> int:
    """Set metallic/roughness on every material (adding a default one if a primitive has none). Returns #materials."""
    js, binary = read_glb(path)
    mats = js.setdefault("materials", [])
    if not mats:
        mats.append({"pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1]}})
        for mesh in js.get("meshes", []):
            for prim in mesh.get("primitives", []):
                prim.setdefault("material", 0)
    for m in mats:
        pbr = m.setdefault("pbrMetallicRoughness", {})
        pbr["metallicFactor"] = float(metallic)
        pbr["roughnessFactor"] = float(roughness)
        m["doubleSided"] = bool(double_sided)
        if name:
            m["name"] = name
    write_glb(path, js, binary)
    return len(mats)
