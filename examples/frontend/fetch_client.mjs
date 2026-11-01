// Plain fetch() client for the Sketch2Shape API — no libraries. Works in a browser (use a File/Blob from <input>
// or canvas.toBlob) and in Node 18+.   node fetch_client.mjs https://xxxx.gradio.live path/to/sketch.png [prompt] [preset]
import { readFile } from "node:fs/promises";

export async function generate3D(baseUrl, sketchBlob, { prompt = "", preset = "balanced", seed = "" } = {}, onStatus = () => {}) {
  const base = baseUrl.replace(/\/$/, "");
  // 1) upload the sketch
  const form = new FormData();
  form.append("files", sketchBlob, "sketch.png");
  const [path] = await (await fetch(`${base}/gradio_api/upload`, { method: "POST", body: form })).json();
  // 2) start the job
  const { event_id } = await (await fetch(`${base}/gradio_api/call/generate_api`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: [{ path, meta: { _type: "gradio.FileData" } }, prompt, preset, String(seed)] }),
  })).json();
  // 3) read the result stream (Server-Sent Events): heartbeats while working, then "complete" (or "error")
  const res = await fetch(`${base}/gradio_api/call/generate_api/${event_id}`);
  const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = "", event = "";
  for (;;) {
    const { value, done } = await reader.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
      if (line.startsWith("event:")) { event = line.slice(6).trim(); onStatus(event); }
      else if (line.startsWith("data:") && event === "complete") {
        const [info, glb, obj] = JSON.parse(line.slice(5));
        return { info, glbUrl: glb?.url ?? null, objUrl: obj?.url ?? null };   // show glbUrl in <model-viewer>
      } else if (line.startsWith("data:") && event === "error") {
        throw new Error("server error: " + line.slice(5));
      }
    }
  }
  throw new Error("stream ended without a result");
}

if (process.argv[1]?.endsWith("fetch_client.mjs")) {
  const [url, sketch, prompt = "", preset = "balanced"] = process.argv.slice(2);
  const blob = new Blob([await readFile(sketch)], { type: "image/png" });
  const t = Date.now();
  const r = await generate3D(url, blob, { prompt, preset }, (e) => process.stdout.write(e === "heartbeat" ? "." : ` [${e}] `));
  console.log(`\nok=${r.info.ok} object=${r.info.badges?.object} time=${((Date.now() - t) / 1000).toFixed(0)}s\nGLB: ${r.glbUrl}`);
  const glb = await fetch(r.glbUrl); console.log("GLB download:", glb.status, (await glb.arrayBuffer()).byteLength, "bytes");
}
