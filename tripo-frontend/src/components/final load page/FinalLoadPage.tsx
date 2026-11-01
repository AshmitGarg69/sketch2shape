import { useEffect, useState } from "react";
import { getApiBaseUrl } from "../../services/apiConfig";

export interface FinalLoadPageProps {
  onNavigate?: (page: "gallery" | "main" | "scribble" | "final") => void;
}

export default function FinalLoadPage({ onNavigate }: FinalLoadPageProps = {}) {
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());

  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data && e.data.type === "navigate" && onNavigate) {
        onNavigate(e.data.page);
      }
      if (e.data && e.data.type === "api_url_changed" && e.data.url) {
        setApiUrl(e.data.url);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onNavigate]);

  return (
    <div className="relative w-full h-screen bg-[#0e0f12] overflow-hidden">
      <iframe
        src={`/final-load.html?api=${encodeURIComponent(apiUrl)}`}
        title="Sketch2Shape Studio"
        className="w-full h-full border-0 block"
      />
    </div>
  );
}


