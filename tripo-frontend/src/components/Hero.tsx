import { useEffect, useRef, useState, type DragEvent } from "react";
import {
  animate,
  motion,
  useAnimationFrame,
  useMotionValue,
  useReducedMotion,
  useTransform,
  type MotionValue,
} from "framer-motion";

import { useGLTF } from "@react-three/drei";
import { ModelStage, ModelView, type ModelStatus } from "./ModelViewer";
import ApiSettingsModal from "./ApiSettingsModal";
import { checkApiHealth } from "../services/apiConfig";

/* ------------------------------------------------------------------ */
/* Data: replace `src` (pre-rendered transparent PNG/WebP of a 3D model)
   and optionally add `glb` for a live, rotatable model on hover.      */
/* ------------------------------------------------------------------ */
interface Showcase {
  id: string;
  label: string;
  glb: string;
}

const SHOWCASE: Showcase[] = [
  { id: "chair", label: "Designer Chair", glb: "/models/chair.glb" },
  { id: "car", label: "Vehicles", glb: "/models/car.glb" },
  { id: "mug", label: "Ceramic Mug", glb: "/models/mug.glb" },
  { id: "lamp", label: "Studio Lamp", glb: "/models/lamp.glb" },
  { id: "character", label: "Game Character", glb: "/models/character.glb" },
  { id: "spacecraft", label: "Spacecraft", glb: "/models/spacecraft.glb" },
  { id: "flower", label: "Nature & Botanical", glb: "/models/flower.glb" },
  { id: "suv", label: "Concept SUV", glb: "/models/suv.glb" },
  { id: "table", label: "Furniture", glb: "/models/table.glb" },
  { id: "bottle", label: "Product Design", glb: "/models/bottle.glb" },
  { id: "train", label: "Industrial Transport", glb: "/models/train.glb" },
  { id: "doodle", label: "Abstract Art", glb: "/models/doodle.glb" },
];

const MODEL_URLS = SHOWCASE.map((s) => s.glb);
MODEL_URLS.forEach((u) => useGLTF.preload(u)); // start downloading all GLBs once, up front

const STEP = 360 / SHOWCASE.length;
const FRONT = -90; // top of the ellipse = highlighted position

/* ------------------------------------------------------------------ */
/* Orbit                                                               */
/* ------------------------------------------------------------------ */
function useSize() {
  const [s, setS] = useState({ w: 1280, h: 800 });
  useEffect(() => {
    const on = () => setS({ w: window.innerWidth, h: window.innerHeight });
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return s;
}

/** Shared geometry so the orbit, hero content and navbar clearance always agree. */
const NAV_BOTTOM = 60; // navbar: top-3 (12px) + h-12 (48px)
function layout(w: number, h: number) {
  const mobile = w < 768;
  const base = mobile ? 96 : Math.min(190, Math.max(130, w * 0.12));
  const cardH = base * 1.15;
  const orbitTop = NAV_BOTTOM + (mobile ? 90 : 100); // ~90–110px clear of the navbar
  const contentTop = orbitTop + cardH + 16; // heading starts just below the top card
  const minH = Math.max(h, contentTop + 460);
  const rx = w * (mobile ? 0.36 : 0.41);
  const ry = Math.max(40, (minH - orbitTop) / 2 - cardH / 2 - 8);
  return { base, rx, ry, orbitTop, contentTop, minH };
}

interface CardProps {
  item: Showcase;
  index: number;
  rot: MotionValue<number>;
  rx: number;
  ry: number;
  base: number;
  active: boolean;
  onSelect: (i: number) => void;
  onHover: (hovered: boolean) => void;
}

function OrbitCard({
  item,
  index,
  rot,
  rx,
  ry,
  base,
  active,
  onSelect,
  onHover,
}: CardProps) {
  const [hover, setHover] = useState(false);
  const [status, setStatus] = useState<ModelStatus>("loading");
  const [surface, setSurface] = useState<HTMLDivElement | null>(null); // the model's drag surface
  const down = useRef<{ x: number; y: number } | null>(null);
  const rad = (r: number) => ((r + index * STEP) * Math.PI) / 180;
  const depth = (r: number) => (1 - Math.sin(rad(r))) / 2; // 1 at top, 0 at bottom

  const x = useTransform(rot, (r) => Math.cos(rad(r)) * rx);
  const y = useTransform(rot, (r) => Math.sin(rad(r)) * ry);
  const scale = useTransform(rot, (r) => 0.7 + 0.3 * depth(r));
  const opacity = useTransform(rot, (r) => 0.5 + 0.5 * depth(r));

  return (
    <motion.button
      type="button"
      aria-label={`Show ${item.label}`}
      onPointerDown={(e) => (down.current = { x: e.clientX, y: e.clientY })}
      onClick={(e) => {
        const d = down.current;
        if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 6) return; // a model drag, not a click
        onSelect(index);
      }}
      onHoverStart={() => {
        setHover(true);
        onHover(true);
      }}
      onHoverEnd={() => {
        setHover(false);
        onHover(false);
      }}
      onFocus={() => {
        setHover(true);
        onHover(true);
      }}
      onBlur={() => {
        setHover(false);
        onHover(false);
      }}
      // negative margins centre the card on its orbit point
      style={{
        x,
        y,
        scale,
        opacity,
        width: base,
        height: base * 1.15,
        marginLeft: -base / 2,
        marginTop: -(base * 1.15) / 2,
      }}
      className="pointer-events-auto absolute left-1/2 top-1/2 flex flex-col items-center outline-none will-change-transform"
    >
      <motion.div
        animate={{
          y: hover ? -6 : 0,
          borderColor:
            hover || active
              ? "rgba(250,204,21,0.45)"
              : "rgba(255,255,255,0.08)",
        }}
        transition={{ type: "spring", stiffness: 220, damping: 22 }}
        className="relative h-full w-full overflow-hidden rounded-2xl border bg-white/[0.04] shadow-[0_20px_50px_-20px_rgba(0,0,0,0.9)] backdrop-blur-sm"
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(255,200,80,0.10),transparent_65%)]" />
        <div
          ref={setSurface}
          className={`absolute inset-0 h-[86%] touch-none ${active ? "cursor-grab active:cursor-grabbing" : "cursor-pointer"}`}
        >
          {status === "failed" ? (
            <div className="flex h-full w-full items-center justify-center text-[11px] text-white/30">
              Model unavailable
            </div>
          ) : (
            <ModelView
              url={item.glb}
              dim={opacity}
              active={active}
              domElement={surface}
              onStatus={setStatus}
            />
          )}
          {status === "loading" && (
            <span className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 animate-pulse rounded-full bg-yellow-400/70" />
          )}
        </div>
        <span className="absolute inset-x-0 bottom-2 text-center text-[11px] font-medium tracking-wide text-white/85">
          {item.label}
        </span>
      </motion.div>
    </motion.button>
  );
}

function OrbitCarousel() {
  const { w, h } = useSize();
  const reduce = useReducedMotion();
  const rot = useMotionValue(0);
  const busy = useRef(false);
  const hovered = useRef(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const { rx, ry, base, orbitTop } = layout(w, h);

  // fetch + parse each GLB once, in the background; cards then read from drei's cache
  useEffect(() => {
    import("./ModelViewer").then((m) =>
      m.preloadModels(SHOWCASE.map((s) => s.glb)),
    );
  }, []);

  // slow continuous drift; paused while a click animation runs or a card is hovered
  useAnimationFrame((_, delta) => {
    if (reduce || busy.current || hovered.current) return;
    rot.set(rot.get() + delta * 0.004);
  });

  const select = (i: number) => {
    setActiveId(SHOWCASE[i].id);
    // shortest rotation that brings card i to the FRONT angle
    const current = rot.get();
    let target = FRONT - i * STEP;
    target += Math.round((current - target) / 360) * 360;
    busy.current = true;
    animate(rot, target, {
      duration: 1.1,
      ease: [0.65, 0, 0.35, 1],
      onComplete: () => (busy.current = false),
    });
  };

  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-0 z-0 overflow-hidden"
      style={{ top: orbitTop }}
      aria-label="3D model showcase"
    >
      {SHOWCASE.map((item, i) => (
        <OrbitCard
          key={item.id}
          item={item}
          index={i}
          rot={rot}
          rx={rx}
          ry={ry}
          base={base}
          active={activeId === item.id}
          onSelect={select}
          onHover={(v) => (hovered.current = v)}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Upload container                                                    */
/* ------------------------------------------------------------------ */
function UploadBox({
  onCreateFromScratch,
  onNavigate,
}: {
  onCreateFromScratch?: () => void;
  onNavigate?: (page: string) => void;
}) {
  const [preview, setPreview] = useState<{
    url: string;
    dataUrl: string;
    kind: "image" | "sketch";
  } | null>(null);
  const [drag, setDrag] = useState(false);
  const imageInput = useRef<HTMLInputElement>(null);
  const sketchInput = useRef<HTMLInputElement>(null);

  const load = (file: File | undefined, kind: "image" | "sketch") => {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      sessionStorage.setItem("sketch2shape_drawing", dataUrl);
      setPreview((p) => {
        if (p) URL.revokeObjectURL(p.url);
        return { url: URL.createObjectURL(file), dataUrl, kind };
      });
    };
    reader.readAsDataURL(file);
  };

  const handleGenerate = () => {
    if (preview) {
      sessionStorage.setItem("sketch2shape_drawing", preview.dataUrl);
      sessionStorage.setItem("sketch2shape_autogen", "true");
      sessionStorage.removeItem("sketch2shape_ask_prompt");
    }
    if (onNavigate) {
      onNavigate("final");
    } else {
      window.history.pushState({}, "", "/final");
      window.dispatchEvent(new PopStateEvent("popstate"));
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    load(e.dataTransfer.files[0], "image");
  };

  const btn =
    "h-11 rounded-full px-5 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-300";

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className="relative mx-auto w-full max-w-[766px] overflow-hidden rounded-[32px] p-px"
    >
      {/* travelling light on the border */}
      <motion.div
        aria-hidden
        className="absolute left-1/2 top-1/2 aspect-square w-[160%] -translate-x-1/2 -translate-y-1/2"
        style={{
          background:
            "conic-gradient(from 0deg, transparent 0deg, transparent 300deg, rgba(250,204,21,0.9) 340deg, transparent 360deg)",
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 7, ease: "linear", repeat: Infinity }}
      />
      <div className="absolute inset-0 rounded-[32px] border border-yellow-500/25" />

      <motion.div
        animate={{ backgroundColor: drag ? "#1a1406" : "#0c0a05" }}
        className="relative flex h-[170px] flex-col items-center justify-center rounded-[31px] sm:h-[190px]"
      >
        {preview ? (
          <div className="flex items-center gap-3 pb-10">
            <img
              src={preview.url}
              alt="Selected upload preview"
              className="h-20 w-20 rounded-xl border border-white/10 object-cover"
            />
            <div className="text-left text-sm">
              <p className="text-white/90">
                {preview.kind === "sketch" ? "Sketch ready" : "Image ready"}
              </p>
              <button
                className="text-white/50 underline hover:text-white cursor-pointer"
                onClick={() => {
                  setPreview(null);
                  sessionStorage.removeItem("sketch2shape_drawing");
                  sessionStorage.removeItem("sketch2shape_autogen");
                }}
              >
                Remove
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 pb-8 text-white/55">
            <svg
              width="30"
              height="30"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <rect x="3" y="5" width="15" height="15" rx="2.5" />
              <path d="M3 16l4.5-4.5 4 4 2.5-2.5L18 17" />
              <path d="M19 2v5M16.5 4.5h5" />
            </svg>
            <p className="text-[13px]">
              Upload an image, photo, or sketch here
            </p>
          </div>
        )}

        <div className="absolute bottom-4 right-4 flex items-center gap-2">
          <motion.button
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => {
              sessionStorage.removeItem("sketch2shape_drawing");
              sessionStorage.removeItem("sketch2shape_autogen");
              sessionStorage.setItem("sketch2shape_mode", "scratch");
              if (onCreateFromScratch) {
                onCreateFromScratch();
              } else {
                window.history.pushState({}, "", "/scribble");
                window.dispatchEvent(new PopStateEvent("popstate"));
              }
            }}
            className={`${btn} border border-yellow-400/50 bg-white/5 text-yellow-300 hover:bg-yellow-400/10 cursor-pointer`}
          >
            Create from Scratch
          </motion.button>
          {preview ? (
            <motion.button
              whileHover={{ y: -2, scale: 1.02 }}
              whileTap={{ scale: 0.96 }}
              onClick={handleGenerate}
              className={`${btn} bg-yellow-400 text-black hover:bg-yellow-300 font-bold shadow-lg shadow-yellow-400/20 cursor-pointer flex items-center gap-1.5`}
            >
              Generate
            </motion.button>
          ) : (
            <motion.button
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.96 }}
              onClick={() => imageInput.current?.click()}
              className={`${btn} bg-yellow-400 text-black hover:bg-yellow-300 cursor-pointer`}
            >
              Upload Image
            </motion.button>
          )}
        </div>

        <input
          ref={imageInput}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            load(e.target.files?.[0], "image");
            e.target.value = "";
          }}
        />
        <input
          ref={sketchInput}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            load(e.target.files?.[0], "sketch");
            e.target.value = "";
          }}
        />
      </motion.div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
function NavBar({ 
  onNavigate, 
  onOpenApiModal, 
  apiOnline 
}: { 
  onNavigate?: (page: string) => void;
  onOpenApiModal?: () => void;
  apiOnline?: boolean | null;
}) {
  return (
    <header className="absolute inset-x-3 top-3 z-20 mx-auto flex h-12 max-w-[1560px] items-center justify-between rounded-full border border-white/10 bg-black/70 px-5 backdrop-blur">
      <div 
        className="flex items-center gap-1.5 cursor-pointer"
        onClick={() => onNavigate?.("main")}
        title="Go to Hero / Main Menu"
      >
        <span className="text-lg font-bold tracking-tight text-white">
          <span className="mr-1.5 text-yellow-400">▼</span>Sketch2Shape
        </span>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenApiModal}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/5 border border-white/10 hover:border-yellow-400/50 cursor-pointer text-xs text-white/80 transition-colors"
          title="Click to configure Kaggle GPU API"
        >
          <span 
            className={`w-2 h-2 rounded-full ${
              apiOnline === true 
                ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" 
                : apiOnline === false 
                ? "bg-red-400 shadow-[0_0_8px_#f87171]" 
                : "bg-yellow-400 animate-pulse"
            }`} 
          />
          <span className="hidden sm:inline">
            {apiOnline === true ? "Tesla T4 Ready" : apiOnline === false ? "API Offline" : "Connecting..."}
          </span>
          <span className="sm:hidden">GPU</span>
        </button>

        <button
          onClick={() => onNavigate?.("gallery")}
          className="text-xs text-white/70 hover:text-white transition-colors cursor-pointer"
        >
          Gallery
        </button>
        <button
          className="flex items-center gap-1 text-xs text-white/70 hover:text-white"
          aria-label="Select language"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            aria-hidden
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18" />
          </svg>
          EN ▾
        </button>
      </div>
    </header>
  );
}

export interface HeroProps {
  onCreateFromScratch?: () => void;
  onNavigate?: (page: string) => void;
}

export default function Hero({ onCreateFromScratch, onNavigate }: HeroProps = {}) {
  const { w, h } = useSize();
  const { contentTop, minH } = layout(w, h);
  const [showApiModal, setShowApiModal] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  const checkConnection = async () => {
    const res = await checkApiHealth();
    setApiOnline(res.ok);
  };

  useEffect(() => {
    checkConnection();
  }, []);

  return (
    <main
      className="relative w-full overflow-hidden bg-black text-white"
      style={{ minHeight: minH }}
    >
      <div
        aria-hidden
        className="absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "radial-gradient(rgba(255,255,255,0.14) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
          maskImage:
            "radial-gradient(ellipse at center, black 40%, transparent 85%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 40%, transparent 85%)",
        }}
      />
      <NavBar 
        onNavigate={onNavigate} 
        onOpenApiModal={() => setShowApiModal(true)} 
        apiOnline={apiOnline} 
      />
      <OrbitCarousel />
      <ModelStage urls={MODEL_URLS} />

      <section
        className="pointer-events-none relative z-10 flex flex-col items-center justify-start px-4 pb-8 text-center"
        style={{ paddingTop: contentTop }}
      >
        <p className="mb-3 text-sm text-yellow-400/90">Industrial Design</p>
        <h1 className="max-w-[900px] text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
          Create 3D Models in Seconds
        </h1>
        <p className="mt-4 max-w-[480px] text-sm text-white/50 sm:text-base">
          Turn your text prompts, images or sketches into detailed 3D models
          with AI.
        </p>
        <div className="pointer-events-auto mt-8 w-full">
          <UploadBox onCreateFromScratch={onCreateFromScratch} onNavigate={onNavigate} />
        </div>
      </section>

      <ApiSettingsModal
        isOpen={showApiModal}
        onClose={() => setShowApiModal(false)}
        onApiUpdated={() => checkConnection()}
      />
    </main>
  );
}

