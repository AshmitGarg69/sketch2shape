import { motion, useTransform, type MotionValue } from "framer-motion";
import { useProgress } from "@react-three/drei";

const serif = { fontFamily: '"Cormorant Garamond", Georgia, serif' };

export function GalleryUI({
  progress,
  onNavigateToMain,
}: {
  progress: MotionValue<number>;
  onNavigateToMain?: () => void;
}) {
  const { active, progress: loaded } = useProgress();
  const hintOpacity = useTransform(progress, [0, 0.03], [1, 0]);
  return (
    <>
      <div
        onClick={onNavigateToMain}
        className="fixed left-5 top-4 z-20 text-[11px] tracking-[0.3em] text-[#e9dcc0] cursor-pointer hover:text-white transition-colors"
        style={serif}
        title="Go to Hero / Main Menu"
      >
        THE BOOK LANTERN <span className="mx-2 text-[#8a6234]">|</span>
        <span className="font-semibold">GALLERY</span>
      </div>

      <motion.div style={{ opacity: hintOpacity, ...serif }} className="pointer-events-none fixed inset-x-0 bottom-8 z-20 text-center text-[11px] tracking-[0.35em] text-[#d9c9a3]">
        SCROLL TO ENTER
        <div className="mx-auto mt-3 h-8 w-px animate-pulse bg-[#8a6234]" />
      </motion.div>

      <div className="pointer-events-none fixed right-5 top-1/2 z-20 h-32 w-px -translate-y-1/2 bg-white/10">
        <motion.div style={{ scaleY: progress }} className="h-full w-px origin-top bg-[#c9a24f]" />
      </div>

      {active && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#050403] text-[11px] tracking-[0.35em] text-[#d9c9a3]" style={serif}>
          ENTERING THE GALLERY · {Math.round(loaded)}%
        </div>
      )}
    </>
  );
}
