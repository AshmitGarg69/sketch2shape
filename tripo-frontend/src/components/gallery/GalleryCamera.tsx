import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { MotionValue } from "framer-motion";
import { END_Z, PIECES, pieceSlot } from "./galleryData";

const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

/** Scroll progress (0–1) travels along a smooth spline through the corridor. No React state per frame. */
export function GalleryCamera({ progress }: { progress: MotionValue<number> }) {
  const { camera, size } = useThree();

  const portrait = size.width / size.height < 0.8;

  const { pos, look } = useMemo(() => {
    const P = [V(0, 1.7, 7)];
    const T = [V(0, 1.8, -10)];
    PIECES.forEach((_, i) => {
      const { side, z } = pieceSlot(i);
      P.push(V(-side * 0.8, 1.65, z + 3.4)); // drift to the opposite side, then look across at the piece
      T.push(V(side * 1.6, 1.3, z - 1.5));
    });
    // Final frame: arch, title and lectern all in view (stands further back on narrow portrait screens).
    P.push(V(0, 2.1, END_Z + (portrait ? 11 : 8.5)));
    T.push(V(0, 2.5, END_Z + 1));
    return {
      pos: new THREE.CatmullRomCurve3(P, false, "centripetal"),
      look: new THREE.CatmullRomCurve3(T, false, "centripetal"),
    };
  }, [portrait]);

  const p = useMemo(() => new THREE.Vector3(), []);
  const l = useMemo(() => new THREE.Vector3(), []);

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    cam.fov = size.width / size.height < 0.8 ? 68 : 50; // wider lens on portrait phones
    cam.updateProjectionMatrix();
  }, [camera, size]);

  useFrame(() => {
    const t = THREE.MathUtils.clamp(progress.get(), 0, 1);
    pos.getPointAt(t, p);
    look.getPointAt(t, l);
    camera.position.copy(p);
    camera.lookAt(l);
  });
  return null;
}
