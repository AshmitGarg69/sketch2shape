export interface ApiCapabilities {
  gpu: string;
  vram_gb: number;
  profile: string;
  backends: {
    triposr?: string;
    instantmesh?: string;
    [key: string]: string | undefined;
  };
}

export const DEFAULT_API_URL = "https://c390743a1c8023653b.gradio.live";

export function getApiBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_API_URL;
  const stored = localStorage.getItem("sketch2shape_api_url");
  if (stored && stored.trim()) {
    return stored.trim().replace(/\/+$/, "");
  }
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, "");
  }
  return DEFAULT_API_URL;
}

export function setApiBaseUrl(url: string): string {
  const clean = (url || DEFAULT_API_URL).trim().replace(/\/+$/, "");
  if (typeof window !== "undefined") {
    localStorage.setItem("sketch2shape_api_url", clean);
  }
  return clean;
}

export async function checkApiHealth(
  targetUrl?: string
): Promise<{ ok: boolean; data?: ApiCapabilities; error?: string }> {
  const baseUrl = (targetUrl || getApiBaseUrl()).replace(/\/+$/, "");
  try {
    const postRes = await fetch(`${baseUrl}/gradio_api/call/capabilities`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: [] }),
    });

    if (!postRes.ok) {
      throw new Error(`HTTP ${postRes.status} (${postRes.statusText})`);
    }

    const { event_id } = await postRes.json();
    if (!event_id) {
      throw new Error("No event_id returned by capabilities endpoint");
    }

    const streamRes = await fetch(`${baseUrl}/gradio_api/call/capabilities/${event_id}`);
    if (!streamRes.body) {
      throw new Error("ReadableStream not supported on this device/browser");
    }

    const reader = streamRes.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let eventType = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i: number;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:") && eventType === "complete") {
          const raw = JSON.parse(line.slice(5).trim());
          const caps = Array.isArray(raw) ? raw[0] : raw;
          return { ok: true, data: caps as ApiCapabilities };
        }
      }
    }
    throw new Error("Connection stream ended without complete event");
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message };
  }
}
