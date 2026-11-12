import { Suspense, useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import { AnimatePresence, useScroll, useSpring } from "framer-motion";
import { PIECES, type Piece } from "./galleryData";
import { GalleryEnvironment } from "./GalleryEnvironment";
import { GalleryCamera } from "./GalleryCamera";
import { GalleryModel } from "./GalleryModel";
import { FinalDestination } from "./FinalDestination";
import { ExpandedViewer } from "./ExpandedViewer";
import { GalleryUI } from "./GalleryUI";

PIECES.forEach((p) => useGLTF.preload(p.url)); // each GLB is fetched once and reused

interface Selected {
  piece: Piece;
  origin: { x: number; y: number };
}

export default function GalleryPage({ onNavigateToMain }: { onNavigateToMain?: () => void } = {}) {
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 70, damping: 24, mass: 0.5 });
  const [sel, setSel] = useState<Selected | null>(null);
  const mobile = window.innerWidth < 768;

  // Lock page scroll while a model is expanded. Overflow only hides the scrollbar, so scrollY is preserved.
  useEffect(() => {
    if (!sel) return;
    const html = document.documentElement;
    const prev = html.style.overflow;
    html.style.overflow = "hidden";
    return () => {
      html.style.overflow = prev;
    };
  }, [sel]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setSel(null);
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  useEffect(() => () => PIECES.forEach((p) => useGLTF.clear(p.url)), []);

  return (
    <div className="relative w-full overflow-x-clip bg-[#050403]" style={{ height: "1150vh" }}>
      <div className="fixed inset-0">
        <Canvas shadows={!mobile} dpr={[1, mobile ? 1.25 : 1.5]} camera={{ fov: 50, near: 0.1, far: 140, position: [0, 1.7, 7] }}>
          <Suspense fallback={null}>
            <GalleryEnvironment />
            <GalleryCamera progress={progress} />
            {PIECES.map((p, i) => (
              <GalleryModel
                key={p.id}
                piece={p}
                index={i}
                hidden={sel?.piece.id === p.id}
                shadows={!mobile}
                onPick={(piece, origin) => setSel({ piece, origin })}
              />
            ))}
            <FinalDestination onNavigateToMain={onNavigateToMain} />
          </Suspense>
        </Canvas>
      </div>
      <GalleryUI progress={progress} onNavigateToMain={onNavigateToMain} />
      <AnimatePresence mode="wait">
        {sel && <ExpandedViewer key={sel.piece.id} piece={sel.piece} origin={sel.origin} onClose={() => setSel(null)} />}
      </AnimatePresence>
    </div>
  );
}
