import { useEffect } from "react";

export interface FinalLoadPageProps {
  onNavigate?: (page: "gallery" | "main" | "scribble" | "final") => void;
}

export default function FinalLoadPage({ onNavigate }: FinalLoadPageProps = {}) {
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === "navigate" && onNavigate) {
        onNavigate(e.data.page);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onNavigate]);

  return (
    <div className="relative w-full h-screen bg-[#0e0f12] overflow-hidden">
      <iframe
        src="/final-load.html"
        title="Sketch2Shape Studio"
        className="w-full h-full border-0 block"
      />
    </div>
  );
}

