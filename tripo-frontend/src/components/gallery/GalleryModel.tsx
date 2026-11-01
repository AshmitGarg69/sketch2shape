import { Component, Suspense, useLayoutEffect, useRef, type ReactNode } from "react";
import { Html, useGLTF } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { PED_H, pieceSlot, plaqueSlot, type Piece } from "./galleryData";
import { Plaque } from "./Plaque";

const _tmpBox = new THREE.Box3();
const _tmpMat = new THREE.Matrix4();

/**
 * Bounding box of every visible mesh under `root`, expressed in the local space of `frame` (or world space when
 * `frame` is null). Skinned meshes are posed first so their real, skinned extent is used. Because each mesh's own
 * transform is applied, GLB roots with odd origins, pivots, rotations or scales are handled correctly.
 */
export function measureBox(root: THREE.Object3D, frame: THREE.Object3D | null) {
  root.updateWorldMatrix(true, true);
  frame?.updateWorldMatrix(true, false);
  const inv = new THREE.Matrix4();
  if (frame) inv.copy(frame.matrixWorld).invert();
  const box = new THREE.Box3();
  root.traverseVisible((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;
    let bb: THREE.Box3 | null | undefined;
    const skinned = o as unknown as THREE.SkinnedMesh & { computeBoundingBox?: () => void; boundingBox?: THREE.Box3 };
    if (skinned.isSkinnedMesh) {
      skinned.skeleton.update();
      if (typeof skinned.computeBoundingBox === "function") {
        skinned.computeBoundingBox();
        bb = skinned.boundingBox;
      }
    }
    if (!bb) {
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      bb = mesh.geometry.boundingBox;
    }
    if (!bb || bb.isEmpty()) return;
    _tmpBox.copy(bb).applyMatrix4(_tmpMat.multiplyMatrices(inv, mesh.matrixWorld));
    box.union(_tmpBox);
  });
  return box;
}

/** Largest dimension (in pedestal units) a gallery model may occupy. */
const FIT_SIZE = 1.7;

/**
 * Normalises any model: resets the root's position, measures a precise Box3 (skinned meshes included) and returns a
 * uniform scale plus an offset that centres it.
 *  - "box":    `target` is the largest bounding-box dimension; `grounded` puts the base on y = 0 (for pedestals).
 *  - "sphere": `target` is the diameter of the bounding sphere, so the model never clips while it rotates.
 * Call before the object is attached to a scaled parent.
 */
export function fitModel(root: THREE.Object3D, target: number, grounded: boolean, mode: "box" | "sphere" = "box") {
  root.position.set(0, 0, 0);
  const box = measureBox(root, null);
  if (box.isEmpty()) return { scale: 1, offset: new THREE.Vector3() };
  const size = box.getSize(new THREE.Vector3());
  const c = box.getCenter(new THREE.Vector3());
  const extent = mode === "sphere" ? size.length() : Math.max(size.x, size.y, size.z);
  const scale = target / (extent || 1);
  return { scale, offset: new THREE.Vector3(-c.x, grounded ? -box.min.y : -c.y, -c.z) };
}

class Guard extends Component<{ children: ReactNode; fallback: ReactNode }, { bad: boolean }> {
  state = { bad: false };
  static getDerivedStateFromError() {
    return { bad: true };
  }
  componentDidCatch(e: unknown) {
    console.warn("Gallery model failed to load:", e);
  }
  render() {
    return this.state.bad ? this.props.fallback : this.props.children;
  }
}

function Showpiece({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const fit = useRef<THREE.Group>(null);

  // Runs after the model is mounted on its pedestal and before the first paint. Everything is measured in the
  // pedestal-top frame, so the result is independent of the model's own origin/pivot and of the pedestal's rotation.
  useLayoutEffect(() => {
    const g = fit.current;
    if (!g || !g.parent) return;
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.castShadow = m.receiveShadow = true;
      m.frustumCulled = false; // skinned/animated bounds can be stale and make parts vanish
    });

    g.position.set(0, 0, 0); // measure from a clean identity transform (safe to re-run)
    g.scale.setScalar(1);
    const box = measureBox(scene, g.parent);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3());
    const c = box.getCenter(new THREE.Vector3());
    const k = FIT_SIZE / (Math.max(size.x, size.y, size.z) || 1); // one uniform factor: never stretches
    g.scale.setScalar(k);
    // centre x/z on the pedestal axis and put the lowest point exactly on the pedestal top (y = 0 in this frame)
    g.position.set(-c.x * k, -box.min.y * k, -c.z * k);
    // Geometry/materials are shared with the expanded viewer and the loader cache, so they are not disposed here;
    // GalleryPage clears the cache when it unmounts.
  }, [scene]);

  return (
    <group position={[0, PED_H, 0]}>
      <group ref={fit}>
        <primitive object={scene} />
      </group>
    </group>
  );
}

interface Props {
  piece: Piece;
  index: number;
  hidden: boolean; // true while this piece is expanded in the centre viewer
  shadows: boolean;
  onPick: (piece: Piece, origin: { x: number; y: number }) => void;
}

export function GalleryModel({ piece, index, hidden, shadows, onPick }: Props) {
  const { side, x, z } = pieceSlot(index);
  const plaque = plaqueSlot(index);
  const { camera } = useThree();
  const spot = useRef<THREE.SpotLight>(null);
  const aim = useRef<THREE.Object3D>(null);
  const tag = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (spot.current && aim.current) spot.current.target = aim.current;
  });

  // Nameplate fades in as the camera passes this piece.
  useFrame(() => {
    if (!tag.current) return;
    const d = Math.abs(camera.position.z - z);
    tag.current.style.opacity = String(THREE.MathUtils.clamp(1 - (d - 3.5) / 4.5, 0, 1));
  });

  const pick = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 6) return; // that was a scroll-drag, not a click
    e.stopPropagation();
    const v = new THREE.Vector3();
    e.eventObject.getWorldPosition(v);
    v.y += PED_H + 0.8;
    v.project(e.camera);
    onPick(piece, { x: ((v.x + 1) / 2) * window.innerWidth, y: ((1 - v.y) / 2) * window.innerHeight });
  };

  return (
    <>
      <Plaque position={plaque.position} rotationY={plaque.rotationY} title={piece.plaqueTitle} text={piece.plaqueText} />
      <group position={[x, 0, z]} rotation={[0, -side * 0.6, 0]}>
        {/* stone pedestal with bronze base and cap */}
        <mesh position={[0, PED_H / 2, 0]} castShadow receiveShadow>
          <boxGeometry args={[0.9, PED_H, 0.9]} />
          <meshStandardMaterial color="#2a211a" roughness={0.6} metalness={0.2} />
        </mesh>
        <mesh position={[0, 0.05, 0]}>
          <boxGeometry args={[1.1, 0.1, 1.1]} />
          <meshStandardMaterial color="#8a6234" roughness={0.4} metalness={0.8} />
        </mesh>
        <mesh position={[0, PED_H - 0.04, 0]}>
          <boxGeometry args={[1.05, 0.08, 1.05]} />
          <meshStandardMaterial color="#8a6234" roughness={0.4} metalness={0.8} />
        </mesh>

        <spotLight
          ref={spot}
          position={[0, 4.8, 1.4]}
          angle={0.5}
          penumbra={0.85}
          intensity={140}
          distance={11}
          decay={2}
          color="#ffc98a"
          castShadow={shadows}
          shadow-mapSize={[512, 512]}
          shadow-bias={-0.0004}
        />
        <object3D ref={aim} position={[0, PED_H + 0.6, 0]} />

        <Html center position={[0, 0.55, 0.55]} zIndexRange={[5, 0]} style={{ pointerEvents: "none" }}>
          <div
            ref={tag}
            style={{ opacity: 0, fontFamily: '"Cormorant Garamond", Georgia, serif' }}
            className="whitespace-nowrap text-[11px] tracking-[0.28em] text-[#d9c9a3]"
          >
            {piece.label.toUpperCase()}
          </div>
        </Html>

        <group
          visible={!hidden}
          onClick={pick}
          onPointerOver={() => (document.body.style.cursor = "pointer")}
          onPointerOut={() => (document.body.style.cursor = "auto")}
        >
          <Guard
            fallback={
              <Html center position={[0, PED_H + 0.5, 0]}>
                <span className="text-[11px] text-white/40">Model unavailable</span>
              </Html>
            }
          >
            <Suspense fallback={null}>
              <Showpiece url={piece.url} />
            </Suspense>
          </Guard>
        </group>
      </group>
    </>
  );
}
