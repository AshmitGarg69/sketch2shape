import { Component, Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Lightformer, OrbitControls, PerspectiveCamera, useGLTF, View } from "@react-three/drei";
import { cancelFrame, frame, type MotionValue } from "framer-motion";
import * as THREE from "three";

export type ModelStatus = "loading" | "ready" | "failed";

/** Start downloading GLBs ahead of time. Safe to call more than once; each URL loads once. */
export function preloadModels(urls: string[]) {
  urls.forEach((u) => useGLTF.preload(u));
}

/** One WebGL canvas for the whole page. Each card renders into it through a <View>. */
export function ModelStage({ urls }: { urls: string[] }) {
  const advance = useRef<((t: number) => void) | null>(null);

  // Render the 3D scene right after Framer Motion writes the cards' transforms,
  // so each model stays locked to its card while the carousel moves.
  useEffect(() => {
    const tick = () => advance.current?.(performance.now());
    frame.postRender(tick, true);
    return () => cancelFrame(tick);
  }, []);

  // Free cached GLTFs when the hero unmounts.
  useEffect(() => () => urls.forEach((u) => useGLTF.clear(u)), [urls]);

  return (
    <div className="pointer-events-none absolute inset-0 z-[1]" aria-hidden>
      <Canvas
        frameloop="never"
        dpr={[1, 1.5]}
        gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
        style={{ pointerEvents: "none" }}
        onCreated={(s) => {
          advance.current = (t) => s.advance(t);
        }}
      >
        <View.Port />
      </Canvas>
    </div>
  );
}

class ModelBoundary extends Component<{ children: ReactNode; onError: (e: unknown) => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.warn("3D model failed to load:", err);
    this.props.onError(err);
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

interface SceneProps {
  url: string;
  dim: MotionValue<number>;
  onStatus: (s: ModelStatus) => void;
}

function Scene({ url, dim, onStatus }: SceneProps) {
  const { scene } = useGLTF(url);
  const amb = useRef<THREE.AmbientLight>(null);
  const key = useRef<THREE.DirectionalLight>(null);

  // Centre on the origin and scale so the model (from any angle) fits its card.
  const { s, c } = useMemo(() => {
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const r = Math.max(size.y, Math.hypot(size.x, size.z));
    return { s: r > 0 ? 1.7 / r : 1, c: box.getCenter(new THREE.Vector3()) };
  }, [scene]);

  useEffect(() => {
    onStatus("ready");
    return () => {
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh) return;
        m.geometry?.dispose();
        (Array.isArray(m.material) ? m.material : [m.material]).forEach((mat) => {
          if (!mat) return;
          Object.values(mat).forEach((v) => (v as THREE.Texture)?.isTexture && (v as THREE.Texture).dispose());
          mat.dispose();
        });
      });
    };
  }, [scene, onStatus]);

  // Back-of-orbit cards are dimmed, matching the card's own opacity. No model rotation happens here.
  useFrame((state) => {
    const o = dim.get();
    (state.scene as THREE.Scene & { environmentIntensity?: number }).environmentIntensity = o;
    if (amb.current) amb.current.intensity = 0.35 * o;
    if (key.current) key.current.intensity = 1.6 * o;
  });

  return (
    <>
      <ambientLight ref={amb} />
      <directionalLight ref={key} position={[3, 4, 3]} />
      <Environment resolution={128}>
        <Lightformer form="rect" intensity={2.2} position={[0, 4, 2]} scale={[6, 3, 1]} target={[0, 0, 0]} />
        <Lightformer form="rect" intensity={1.2} color="#ffb347" position={[-5, 1, -2]} scale={[3, 6, 1]} target={[0, 0, 0]} />
        <Lightformer form="rect" intensity={1} position={[5, 1, 2]} scale={[3, 6, 1]} target={[0, 0, 0]} />
      </Environment>
      <group scale={s}>
        <primitive object={scene} position={[-c.x, -c.y, -c.z]} />
      </group>
    </>
  );
}

interface ModelViewProps extends SceneProps {
  /** Only the active (front) card can be rotated. */
  active: boolean;
  /** The card's own drag surface. Controls listen here, never on the shared canvas. */
  domElement: HTMLElement | null;
}

/** A card's window into the shared canvas. Fills its parent element. */
export function ModelView({ url, dim, onStatus, active, domElement }: ModelViewProps) {
  return (
    <View className="h-full w-full">
      <PerspectiveCamera makeDefault position={[0, 0.5, 4]} fov={30} onUpdate={(cam) => cam.lookAt(0, 0, 0)} />
      {domElement && (
        <OrbitControls
          domElement={domElement}
          enabled={active}
          enableRotate={active}
          enableZoom={false}
          enablePan={false}
          autoRotate={false}
          enableDamping
          dampingFactor={0.1}
          rotateSpeed={0.8}
        />
      )}
      <ModelBoundary onError={() => onStatus("failed")}>
        <Suspense fallback={null}>
          <Scene url={url} dim={dim} onStatus={onStatus} />
        </Suspense>
      </ModelBoundary>
    </View>
  );
}
