import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Edges } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { END_Z } from "./galleryData";
import { drawSpaced, glowTexture, makeTexture, useGalleryFont } from "./galleryText";

// All geometry below is in local space of a group sitting on the end wall: x = across, y = up, z = towards the visitor.
const R = 2.6; // arch centre-line radius
const SPRING = 2.2; // height where the arch curve starts
const OPEN = R - 0.2; // inner opening radius
const LZ = 2.2; // lectern distance in front of the wall
const PLATFORM_TOP = 0.55;
const PX = 0.075; // one "Minecraft pixel" in world units
const GOLD = { color: "#d4a84c", metalness: 1, roughness: 0.3, emissive: "#6b4a1a", emissiveIntensity: 0.6 } as const;
const REVEAL_FAR = 34; // distance from the end wall where the finale starts to appear
const REVEAL_NEAR = 24; // ...and where it is fully revealed

/* ---------- pixel-art textures (nearest filtered, so they stay crisp and blocky) ---------- */

const rnd = (i: number) => {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};

function pixelTexture(size: number, paint: (c: CanvasRenderingContext2D) => void) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  paint(cv.getContext("2d")!);
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = THREE.NearestFilter;
  t.minFilter = THREE.NearestFilter;
  t.generateMipmaps = false;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const dot = (c: CanvasRenderingContext2D, x: number, y: number, col: string, w = 1, h = 1) => {
  c.fillStyle = col;
  c.fillRect(x, y, w, h);
};

function woodTexture() {
  return pixelTexture(16, (c) => {
    dot(c, 0, 0, "#8d5f33", 16, 16);
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      const r = rnd(y * 16 + x);
      if (r < 0.18) dot(c, x, y, "#7a4f28");
      else if (r > 0.9) dot(c, x, y, "#a2703d");
    }
    for (let y = 3; y < 16; y += 4) dot(c, 0, y, "#6a4423", 16, 1); // plank seams
    dot(c, 0, 0, "#4b2f17", 16, 1);
    dot(c, 0, 15, "#4b2f17", 16, 1);
    dot(c, 0, 0, "#4b2f17", 1, 16);
    dot(c, 15, 0, "#4b2f17", 1, 16); // darker pixel edge
  });
}

function pageTexture() {
  return pixelTexture(16, (c) => {
    dot(c, 0, 0, "#f6e9c6", 16, 16);
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) if (rnd(500 + y * 16 + x) < 0.12) dot(c, x, y, "#ead9a8");
    for (let y = 3; y <= 12; y += 2) {
      for (let x = 3; x <= 12; x++) if (rnd(900 + y * 16 + x) > 0.22) dot(c, x, y, "#a68a52"); // pixel "text"
    }
    dot(c, 0, 0, "#c9b27a", 16, 1);
    dot(c, 0, 15, "#c9b27a", 16, 1);
    dot(c, 0, 0, "#c9b27a", 1, 16);
    dot(c, 15, 0, "#c9b27a", 1, 16);
  });
}

function shelfTexture() {
  return pixelTexture(16, (c) => {
    dot(c, 0, 0, "#4b2f17", 16, 16);
    dot(c, 0, 7, "#8d5f33", 16, 2); // middle shelf board
    const cols = ["#b3382c", "#3f7d3a", "#3a5fa8", "#d8b43a", "#7b3fa0", "#b3382c", "#3f7d3a"];
    for (let row = 0; row < 2; row++) {
      const top = row === 0 ? 1 : 9;
      cols.forEach((col, i) => {
        const h = 4 + Math.floor(rnd(row * 20 + i) * 3);
        dot(c, 1 + i * 2, top + (6 - h), col, 2, h);
        dot(c, 1 + i * 2, top + (6 - h), "rgba(255,255,255,0.25)", 1, h);
      });
    }
  });
}

function carpetTexture() {
  return pixelTexture(8, (c) => {
    dot(c, 0, 0, "#b0242a", 8, 8);
    dot(c, 0, 0, "#7a1519", 8, 1);
    dot(c, 0, 7, "#7a1519", 8, 1);
  });
}

/* ---------- the voxel lectern ---------- */

function Lectern() {
  const m = useMemo(() => {
    const wood = woodTexture();
    const page = pageTexture();
    const shelf = shelfTexture();
    const carpet = carpetTexture();
    const mat = (map: THREE.Texture) => new THREE.MeshStandardMaterial({ map, roughness: 0.9, metalness: 0 });
    const flat = (color: string) => new THREE.MeshStandardMaterial({ color, roughness: 0.85 });
    const pageSide = flat("#d9c795");
    return {
      textures: [wood, page, shelf, carpet],
      wood: mat(wood),
      shelf: mat(shelf),
      carpet: mat(carpet),
      leather: flat("#6b3a1a"),
      pageSide,
      pageFaces: [pageSide, pageSide, mat(page), pageSide, pageSide, pageSide], // +x -x +y -y +z -z
      gold: new THREE.MeshStandardMaterial({ color: "#f6b72d", emissive: "#a86a00", emissiveIntensity: 0.7, metalness: 0.5, roughness: 0.35 }),
    };
  }, []);

  useEffect(
    () => () => {
      m.textures.forEach((t) => t.dispose());
      [m.wood, m.shelf, m.carpet, m.leather, m.pageSide, m.gold, m.pageFaces[2]].forEach((x) => (x as THREE.Material).dispose());
    },
    [m],
  );

  const u = (n: number) => n * PX;
  const box = (w: number, h: number, d: number): [number, number, number] => [u(w), u(h), u(d)];

  return (
    <group position={[0, PLATFORM_TOP, LZ]}>
      {/* thick square base + red carpet strip on its front edge */}
      <mesh position={[0, u(1.5), 0]} material={m.wood}>
        <boxGeometry args={box(16, 3, 16)} />
      </mesh>
      <mesh position={[0, u(3.2), u(3)]} material={m.carpet}>
        <boxGeometry args={box(6, 0.4, 10)} />
      </mesh>

      {/* central support with the little bookshelf on its front */}
      <mesh position={[0, u(9), 0]} material={m.wood}>
        <boxGeometry args={box(8, 12, 8)} />
      </mesh>
      <mesh position={[0, u(9.5), u(4.3)]} material={m.shelf}>
        <boxGeometry args={box(6, 7, 0.6)} />
      </mesh>

      {/* slanted top (front edge lower) with the open book */}
      <group position={[0, u(17), 0]} rotation={[0.39, 0, 0]}>
        <mesh material={m.wood}>
          <boxGeometry args={box(16, 3, 16)} />
        </mesh>
        <group position={[0, u(1.5), 0]} rotation={[0, -0.45, 0]}>
          <mesh position={[0, u(0.5), 0]} material={m.leather}>
            <boxGeometry args={box(15, 1, 10.5)} />
          </mesh>
          <mesh position={[-u(3.5), u(1.4), 0]} material={m.pageFaces}>
            <boxGeometry args={box(6.8, 0.8, 9)} />
          </mesh>
          <mesh position={[u(3.5), u(1.4), 0]} material={m.pageFaces}>
            <boxGeometry args={box(6.8, 0.8, 9)} />
          </mesh>
          <mesh position={[0, u(1.5), 0]} material={m.leather}>
            <boxGeometry args={box(0.7, 1.1, 9.4)} />
          </mesh>
          {/* golden corner details */}
          {[
            [-1, -1],
            [1, -1],
            [-1, 1],
            [1, 1],
          ].map(([sx, sz]) => (
            <mesh key={`${sx}${sz}`} position={[sx * u(7.2), u(1.15), sz * u(5)]} material={m.gold}>
              <boxGeometry args={box(1.6, 1.4, 1.6)} />
            </mesh>
          ))}
        </group>
      </group>
    </group>
  );
}

/* ---------- text ---------- */

type TextOpts = { w: number; h: number; text: string; size: number; weight: number; spacing: number; fill: [string, string, string]; fit: number; glow: number };

function textTexture({ w, h, text, size, weight, spacing, fill, fit, glow }: TextOpts) {
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  const c = cv.getContext("2d")!;
  const g = c.createLinearGradient(0, h * 0.15, 0, h * 0.85);
  g.addColorStop(0, fill[0]);
  g.addColorStop(0.55, fill[1]);
  g.addColorStop(1, fill[2]);
  c.fillStyle = g;
  c.shadowColor = "rgba(255,190,90,0.7)";
  c.shadowBlur = glow;
  // measured and shrunk to fit, so nothing can be cut off at the canvas edge
  drawSpaced(c, text, w / 2, h / 2, size, weight, spacing, w * fit);
  return makeTexture(cv);
}

function buttonTexture(hot: boolean) {
  const w = 1024;
  const h = 200;
  const cv = document.createElement("canvas");
  cv.width = w;
  cv.height = h;
  const c = cv.getContext("2d")!;
  c.beginPath();
  c.roundRect(16, 16, w - 32, h - 32, 30);
  c.fillStyle = hot ? "rgba(120,80,20,0.92)" : "rgba(35,22,8,0.9)";
  c.fill();
  c.lineWidth = hot ? 8 : 5;
  c.strokeStyle = hot ? "#fff0b8" : "#c9a24f";
  c.shadowColor = "rgba(255,190,90,0.8)";
  c.shadowBlur = hot ? 30 : 14;
  c.stroke();
  c.shadowBlur = hot ? 18 : 8;
  c.fillStyle = hot ? "#fff7d6" : "#f0d58a";
  drawSpaced(c, "GO TO MAIN MENU", w / 2, h / 2 + 2, 76, 700, 10, w - 150);
  return makeTexture(cv);
}

/** The end of the corridor: a voxel lectern on a golden-trimmed platform under an archway. Appears only near the end. */
export function FinalDestination({ onNavigateToMain }: { onNavigateToMain?: () => void } = {}) {
  const fontReady = useGalleryFont();
  const { camera } = useThree();
  const [hot, setHot] = useState(false);
  const content = useRef<THREE.Group>(null);
  const reveal = useRef(0);
  const spot = useRef<THREE.SpotLight>(null);
  const aim = useRef<THREE.Object3D>(null);
  const warm = useRef<THREE.PointLight>(null);
  const mounted = useRef(true);
  const leaving = useRef(false);
  const veil = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    if (spot.current && aim.current) spot.current.target = aim.current;
  });

  const title = useMemo(
    () => textTexture({ w: 2048, h: 330, text: "THE BOOK LANTERN", size: 190, weight: 700, spacing: 20, fill: ["#fff0b8", "#e2b45a", "#b98a34"], fit: 0.9, glow: 26 }),
    [fontReady],
  );
  const sub = useMemo(
    () => textTexture({ w: 2048, h: 200, text: "YOU HAVE REACHED THE END", size: 96, weight: 600, spacing: 16, fill: ["#fbf3dc", "#f0e2b8", "#d9c28a"], fit: 0.92, glow: 14 }),
    [fontReady],
  );
  const button = useMemo(() => buttonTexture(hot), [fontReady, hot]);
  const glow = useMemo(() => glowTexture(), []);
  useEffect(() => () => title.dispose(), [title]);
  useEffect(() => () => sub.dispose(), [sub]);
  useEffect(() => () => button.dispose(), [button]);
  useEffect(() => () => glow.dispose(), [glow]);

  const archShape = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-OPEN, 0);
    s.lineTo(-OPEN, SPRING);
    s.absarc(0, SPRING, OPEN, Math.PI, 0, true);
    s.lineTo(OPEN, 0);
    s.closePath();
    return s;
  }, []);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      document.body.style.cursor = "auto";
      const v = veil.current;
      if (v) {
        v.style.opacity = "0"; // new page is now showing underneath: fade the curtain away
        window.setTimeout(() => v.remove(), 600);
      }
    };
  }, []);

  // Reveal: the finale grows out of the end wall as the camera nears it, so it is only seen at the end of the journey.
  useFrame(() => {
    const g = content.current;
    if (!g) return;
    const d = camera.position.z - END_Z;
    const t = THREE.MathUtils.smoothstep(REVEAL_FAR - d, 0, REVEAL_FAR - REVEAL_NEAR);
    reveal.current = t;
    g.visible = t > 0.001;
    g.scale.setScalar(Math.max(t, 0.0001));
    // lights stay mounted (adding/removing lights would recompile every material); only their strength changes
    if (spot.current) spot.current.intensity = 190 * t;
    if (warm.current) warm.current.intensity = 9 * t;
  });

  const goHome = (e: ThreeEvent<MouseEvent>) => {
    if (e.delta > 6 || leaving.current || reveal.current < 0.95) return;
    e.stopPropagation();
    leaving.current = true;
    document.body.style.cursor = "auto";
    const v = document.createElement("div");
    v.style.cssText = "position:fixed;inset:0;z-index:100;background:#050403;opacity:0;transition:opacity .4s ease;pointer-events:all";
    document.body.appendChild(v);
    veil.current = v;
    requestAnimationFrame(() => (v.style.opacity = "1"));
    window.setTimeout(() => {
      if (onNavigateToMain) {
        onNavigateToMain();
      } else {
        // client-side navigation to the home route: no page reload when the app uses a history-based router
        window.history.pushState({}, "", "/main");
        window.dispatchEvent(new PopStateEvent("popstate"));
        // if this gallery is still mounted the app did not react to the route change, so fall back to a normal load
        window.setTimeout(() => {
          if (mounted.current) window.location.assign("/main");
        }, 700);
      }
    }, 400);
  };

  const zWall = 0.04;
  const zArch = 0.25;
  const zText = 0.12;
  return (
    <group position={[0, 0, END_Z]}>
      <group ref={content} visible={false} scale={0.0001}>
        {/* doorway backdrop + halo */}
        <mesh position={[0, 0, zWall]}>
          <shapeGeometry args={[archShape]} />
          <meshBasicMaterial color="#4a2c10" toneMapped={false} />
        </mesh>
        <mesh position={[0, 2.6, zWall + 0.02]}>
          <planeGeometry args={[10, 8]} />
          <meshBasicMaterial map={glow} transparent blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>
        <mesh rotation-x={-Math.PI / 2} position={[0, 0.02, LZ]}>
          <planeGeometry args={[8, 6]} />
          <meshBasicMaterial map={glow} transparent blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
        </mesh>

        {/* golden arch: pillars, plinths, capitals, rings, keystone */}
        {[-1, 1].map((s) => (
          <group key={s} position={[s * R, 0, zArch]}>
            <mesh position={[0, SPRING / 2, 0]}>
              <boxGeometry args={[0.5, SPRING, 0.5]} />
              <meshStandardMaterial {...GOLD} />
            </mesh>
            <mesh position={[0, 0.14, 0]}>
              <boxGeometry args={[0.85, 0.28, 0.85]} />
              <meshStandardMaterial {...GOLD} roughness={0.4} />
            </mesh>
            <mesh position={[0, SPRING + 0.05, 0]}>
              <boxGeometry args={[0.72, 0.2, 0.72]} />
              <meshStandardMaterial {...GOLD} roughness={0.4} />
            </mesh>
          </group>
        ))}
        <group position={[0, SPRING, zArch]}>
          <mesh>
            <torusGeometry args={[R, 0.2, 20, 80, Math.PI]} />
            <meshStandardMaterial {...GOLD} />
          </mesh>
          <mesh>
            <torusGeometry args={[R + 0.32, 0.055, 12, 80, Math.PI]} />
            <meshStandardMaterial color="#000" emissive="#ffb45c" emissiveIntensity={2.2} toneMapped={false} />
          </mesh>
          <mesh>
            <torusGeometry args={[OPEN - 0.14, 0.04, 12, 80, Math.PI]} />
            <meshStandardMaterial color="#000" emissive="#ffd08a" emissiveIntensity={2.2} toneMapped={false} />
          </mesh>
          <mesh position={[0, R, 0.05]} rotation={[0, 0, Math.PI / 4]}>
            <boxGeometry args={[0.36, 0.36, 0.24]} />
            <meshStandardMaterial {...GOLD} emissiveIntensity={1} />
          </mesh>
        </group>

        {/* raised two-tier platform with gold trim */}
        <mesh position={[0, 0.15, LZ]}>
          <boxGeometry args={[3.4, 0.3, 3.2]} />
          <meshStandardMaterial color="#1c1510" roughness={0.5} metalness={0.3} />
          <Edges color="#c9a24f" />
        </mesh>
        <mesh position={[0, 0.425, LZ]}>
          <boxGeometry args={[2.4, 0.25, 2.2]} />
          <meshStandardMaterial color="#2a1f16" roughness={0.45} metalness={0.35} />
          <Edges color="#e2b45a" />
        </mesh>

        <Lectern />

        {/* text, all inside the arch above the lectern */}
        <mesh position={[0, 3.7, zText]}>
          <planeGeometry args={[3.5, 0.564]} />
          <meshBasicMaterial map={title} transparent toneMapped={false} />
        </mesh>
        <mesh position={[0, 3.15, zText]}>
          <planeGeometry args={[3.3, 0.322]} />
          <meshBasicMaterial map={sub} transparent toneMapped={false} />
        </mesh>
        <mesh
          position={[0, 2.62, zText]}
          onClick={goHome}
          onPointerOver={() => {
            setHot(true);
            document.body.style.cursor = "pointer";
          }}
          onPointerOut={() => {
            setHot(false);
            document.body.style.cursor = "auto";
          }}
        >
          <planeGeometry args={[3.0, 0.586]} />
          <meshBasicMaterial map={button} transparent toneMapped={false} />
        </mesh>
      </group>

      {/* warm golden spotlight on the lectern */}
      <spotLight ref={spot} position={[0, 5, LZ + 4]} angle={0.45} penumbra={0.8} intensity={0} distance={14} decay={2} color="#ffc872" />
      <object3D ref={aim} position={[0, PLATFORM_TOP + 0.8, LZ]} />
      <pointLight ref={warm} position={[0, 2.4, LZ + 1.6]} intensity={0} distance={9} color="#ffb45c" />
    </group>
  );
}
