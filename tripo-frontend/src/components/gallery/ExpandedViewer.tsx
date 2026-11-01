import {
  Component,
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Canvas, useThree } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  Html,
  Lightformer,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import { motion } from "framer-motion";
import * as THREE from "three";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";
import { measureBox } from "./GalleryModel";
import type { Piece } from "./galleryData";

/** Share of the limiting viewport dimension (height, or width on portrait screens) the model should fill. */
const VIEW_FRACTION = 0.72;

const SERIF = '"Cormorant Garamond", Georgia, serif';

/* ------------------------------------------------------------------------------------------------
 * Model preparation: independent clone -> centred on the origin -> normalised to a bounding radius of 1.
 * Exactly ONE transform is applied to the clone (its position, to centre it) and ONE to the wrapper group
 * (a uniform scale about the origin), so there are no conflicting centring transforms.
 * ---------------------------------------------------------------------------------------------- */

function hasSkin(root: THREE.Object3D) {
  let skinned = false;
  root.traverse((o) => {
    if ((o as THREE.SkinnedMesh).isSkinnedMesh || (o as THREE.Bone).isBone)
      skinned = true;
  });
  return skinned;
}

/** Largest distance from the origin to any vertex (box corners for skinned meshes). Safe for any rotation. */
function boundingRadius(root: THREE.Object3D, skinned: boolean) {
  root.updateWorldMatrix(true, true);
  if (skinned) {
    const b = measureBox(root, null);
    if (b.isEmpty()) return 1;
    const x = Math.max(Math.abs(b.min.x), Math.abs(b.max.x));
    const y = Math.max(Math.abs(b.min.y), Math.abs(b.max.y));
    const z = Math.max(Math.abs(b.min.z), Math.abs(b.max.z));
    return Math.sqrt(x * x + y * y + z * z) || 1;
  }
  const v = new THREE.Vector3();
  let r2 = 0;
  root.traverseVisible((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;
    const pos = mesh.geometry.getAttribute("position");
    if (!pos) return;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      r2 = Math.max(r2, v.lengthSq());
    }
  });
  return Math.sqrt(r2) || 1;
}

function prepareModel(scene: THREE.Object3D) {
  const skinned = hasSkin(scene);
  // SkeletonUtils.clone rebinds skeletons; scene.clone(true) is enough (and cheaper) for ordinary meshes.
  const clone = skinned ? SkeletonUtils.clone(scene) : scene.clone(true);
  clone.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) o.frustumCulled = false;
  });

  clone.position.set(0, 0, 0); // measure from a clean position, whatever the gallery did to the original
  let box = measureBox(clone, null);
  if (box.isEmpty()) box = new THREE.Box3().setFromObject(clone);
  const centre = box.getCenter(new THREE.Vector3());
  clone.position.set(-centre.x, -centre.y, -centre.z); // geometric centre now sits exactly on the origin
  clone.updateMatrixWorld(true);

  const radius = boundingRadius(clone, skinned);
  const scale = 1 / radius; // uniform: proportions are never changed
  const after = measureBox(clone, null);
  const floorY = after.isEmpty() ? -1 : after.min.y * scale;
  return { clone, scale, floorY };
}

function Model({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const prepared = useMemo(() => prepareModel(scene), [scene]);
  return (
    <>
      <group scale={prepared.scale}>
        <primitive object={prepared.clone} />
      </group>
      <ContactShadows
        position={[0, prepared.floorY - 0.02, 0]}
        opacity={0.45}
        scale={6}
        blur={2.6}
        far={2.5}
        resolution={512}
        frames={2}
        color="#000000"
      />
    </>
  );
}

/**
 * Frames the (radius 1) model for the current viewport: distance comes from the field of view and the aspect ratio,
 * so every model fills the same share of the screen, never clips, and re-frames on resize / rotation of the device.
 */
function Framing() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const width = useThree((s) => s.size.width);
  const height = useThree((s) => s.size.height);
  useLayoutEffect(() => {
    const aspect = width / Math.max(height, 1);
    const tanLimit =
      Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * Math.min(1, aspect);
    const d = 1 / (VIEW_FRACTION * tanLimit);
    const dir =
      camera.position.lengthSq() > 1e-6
        ? camera.position.clone().normalize()
        : new THREE.Vector3(0, 0.2, 1).normalize();
    camera.position.copy(dir.multiplyScalar(d)); // keep the visitor's current viewing direction, only change distance
    camera.near = 0.05;
    camera.far = d + 20;
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }, [camera, width, height]);
  return null;
}

class LoadGuard extends Component<{ children: ReactNode }, { bad: boolean }> {
  state = { bad: false };
  static getDerivedStateFromError() {
    return { bad: true };
  }
  componentDidCatch(e: unknown) {
    console.warn("Expanded model failed to load:", e);
  }
  render() {
    return this.state.bad ? (
      <Html center>
        <span
          style={{
            color: "#d9c9a3",
            fontFamily: SERIF,
            letterSpacing: "0.3em",
            fontSize: 12,
          }}
        >
          MODEL UNAVAILABLE
        </span>
      </Html>
    ) : (
      this.props.children
    );
  }
}

interface Props {
  piece: Piece;
  /** Kept for compatibility with GalleryPage; the modal no longer animates from gallery coordinates. */
  origin?: { x: number; y: number };
  onClose: () => void;
}

/** Independent full-screen examination modal with its own Canvas. Independent of the gallery scene, camera and lights. */
export function ExpandedViewer({ piece, onClose }: Props) {
  // Remember where the gallery was scrolled to and put it back exactly when the modal closes.
  useEffect(() => {
    const y = window.scrollY;
    return () => {
      requestAnimationFrame(() =>
        window.scrollTo({ top: y, behavior: "instant" as ScrollBehavior }),
      );
    };
  }, []);

  return createPortal(
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={piece.label}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35 }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        width: "100vw",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(5,4,3,0.82)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
      }}
    >
      {/* the canvas fills the modal, so the model (at the world origin) is in the exact centre of the viewport */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          touchAction: "none",
        }}
      >
        <Canvas
          dpr={[1, 1.75]}
          camera={{ fov: 35, near: 0.05, far: 100, position: [0, 0.35, 4.5] }}
          gl={{ alpha: true, antialias: true }}
          style={{ background: "transparent" }}
        >
          <ambientLight intensity={0.7} />
          <directionalLight
            position={[4, 6, 5]}
            intensity={2.6}
            color="#fff1d6"
          />
          <directionalLight
            position={[-5, 2, -4]}
            intensity={0.9}
            color="#ffb347"
          />
          <pointLight
            position={[-3, 1.5, 3]}
            intensity={25}
            distance={14}
            color="#ffc27a"
          />
          <Environment resolution={128}>
            <Lightformer
              form="rect"
              intensity={2}
              position={[0, 4, 2]}
              scale={[6, 3, 1]}
              target={[0, 0, 0]}
            />
            <Lightformer
              form="rect"
              intensity={1.2}
              color="#ffb347"
              position={[-5, 1, -2]}
              scale={[3, 6, 1]}
              target={[0, 0, 0]}
            />
          </Environment>
          <Framing />
          <LoadGuard>
            <Suspense
              fallback={
                <Html center>
                  <span
                    style={{
                      color: "#d9c9a3",
                      fontFamily: SERIF,
                      letterSpacing: "0.35em",
                      fontSize: 12,
                      whiteSpace: "nowrap",
                    }}
                  >
                    LOADING…
                  </span>
                </Html>
              }
            >
              <Model url={piece.url} />
            </Suspense>
          </LoadGuard>
          <OrbitControls
            makeDefault
            target={[0, 0, 0]}
            autoRotate={false}
            enableRotate
            enableZoom={false}
            enablePan={false}
            enableDamping
            dampingFactor={0.1}
            rotateSpeed={0.8}
          />
        </Canvas>

        <p
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: 22,
            textAlign: "center",
            fontFamily: SERIF,
            fontSize: 12,
            letterSpacing: "0.3em",
            color: "#d9c9a3",
            pointerEvents: "none",
          }}
        >
          {piece.label.toUpperCase()} · DRAG TO ROTATE
        </p>
      </div>

      <button
        onClick={onClose}
        aria-label="Close"
        className="flex items-center justify-center rounded-full border border-[#c9a24f]/70 bg-black/50 text-[28px] leading-none text-[#f0d58a] transition duration-200 hover:scale-110 hover:bg-[#c9a24f]/30 hover:text-white"
        style={{
          position: "fixed",
          top: 20,
          right: 20,
          zIndex: 10000,
          width: 48,
          height: 48,
          cursor: "pointer",
        }}
      >
        ×
      </button>
    </motion.div>,
    document.body,
  );
}
