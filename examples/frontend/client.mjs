// Minimal custom-frontend client for a running Sketch2Shape server (local, or the Kaggle *.gradio.live link).
//   npm install @gradio/client
//   node client.mjs http://localhost:7860/ path/to/sketch.png ["optional prompt"] [fast|balanced|best]
import { Client, handle_file } from "@gradio/client";
import { readFile, writeFile } from "node:fs/promises";

const [url = "http://localhost:7860/", sketch, prompt = "", preset = "balanced"] = process.argv.slice(2);
const app = await Client.connect(url);

console.log("capabilities:", (await app.predict("/capabilities", {})).data[0]);

const blob = new Blob([await readFile(sketch)], { type: "image/png" });      // in a browser: a File from <input> or canvas.toBlob()
const job = app.submit("/generate_api", { file: handle_file(blob), prompt_v: prompt, preset_v: preset, seed_v: "" });
for await (const ev of job) {
  if (ev.type === "status") console.log("status:", ev.stage, ev.queue ? `queue pos ${ev.position ?? "-"}` : "");
  if (ev.type === "data") {
    const [info, glb, obj] = ev.data;          // info = run summary JSON; glb/obj = { url, ... } downloadable files
    console.log("ok:", info.ok, info.message, info.badges);
    if (glb?.url) {
      console.log("GLB url:", glb.url);        // in a browser: <model-viewer src={glb.url}> or three.js GLTFLoader
      await writeFile("model.glb", Buffer.from(await (await fetch(glb.url)).arrayBuffer()));
      console.log("saved model.glb");
    }
    break;
  }
}
process.exit(0);
