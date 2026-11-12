# Sketch2Shape — Complete End-to-End Run Guide
### From Kaggle GPU Backend to API Connection to Running the Website

This guide walks you through starting the AI backend on Kaggle, connecting the Gradio API tunnel to the frontend, and launching the interactive 3D web studio.

---

## Architecture Overview

```
┌─────────────────────────────────┐          ┌──────────────────────────────────┐
│          Kaggle GPU             │          │       Your Local Machine         │
│  (Tesla T4 / Free Tier 30h/wk)  │          │                                  │
│                                 │          │  React 19 + Three.js + Vite UI   │
│  InstantMesh + TripoSR Pipeline │          │  (Port 5173 / Localhost)         │
│  Gradio SSE Server              │          │                                  │
└────────────────┬────────────────┘          └────────────────▲─────────────────┘
                 │                                            │
                 ▼                                            │
     https://xxxx.gradio.live (Live Tunnel) ──────────────────┘
```

1. **Backend**: Runs inside a Kaggle notebook with a GPU (Tesla T4). Generates 3D meshes (GLB/OBJ) from 2D sketches.
2. **Tunnel API**: Gradio exposes a public HTTPS endpoint (`https://xxxx.gradio.live`) connecting directly to the Kaggle session.
3. **Frontend**: Vite + React 19 web application where you draw sketches or upload drawings, view candidate images, inspect 3D models in real time, and explore the 3D gallery.

---

## Prerequisites

- **Kaggle Account**: Must be **phone-verified** (required by Kaggle to enable GPU and Internet access).
- **Node.js**: v18.0 or higher ([Download Node.js](https://nodejs.org/)).
- **Package Manager**: `npm` (comes with Node.js).
- **Modern Web Browser**: Chrome, Edge, Brave, Firefox, or Safari (WebGL enabled).

---

## Step 1: Start the Kaggle GPU Backend

1. **Sign in to Kaggle**: Go to [kaggle.com](https://www.kaggle.com/) and log in.
2. **Upload or Open the Notebook**:
   - In Kaggle, click **+ Create** → **New Notebook** (or go to **Code** → **New Notebook**).
   - Click **File** → **Import Notebook** → upload [`kaggle/Sketch2Shape_Kaggle_demo.ipynb`](file:///home/ashmit/Code/new/sketch2shape-frontend-code/kaggle/Sketch2Shape_Kaggle_demo.ipynb) from this repository.
3. **Configure Notebook Settings** (In the right-hand panel):
   - **Accelerator**: Select **GPU T4 x 1** (under *Session options*).
   - **Internet**: Toggle **Internet ON** (critical: necessary to fetch model weights and establish the Gradio live tunnel).
4. **Run the Notebook**:
   - Click **Run All** (or run cells sequentially from top to bottom).
   - **First Run Setup Time**: Takes approximately 10–12 minutes on the first run (downloads pinned weights for SDXL, InstantMesh, and TripoSR).
5. **Copy the Gradio API URL**:
   - Scroll down to the output of the final cell.
   - Look for the printed output line:
     ```text
     ============================================================
     >>> API base URL:     https://xxxxxxxxxxxxxxxxxx.gradio.live
     ============================================================
     ```
   - Copy this URL (e.g. `https://c390743a1c8023653b.gradio.live`).

> [!IMPORTANT]
> - **Keep the Kaggle tab open and active.** If the notebook is closed or left idle, Kaggle may shut down the session.
> - Gradio live links remain active for **up to 72 hours** while the Kaggle session is running (standard Kaggle interactive sessions have a 12-hour maximum runtime).

---

## Step 2: Store / Configure the API URL in the Frontend

You can configure the API URL either dynamically in the browser UI or permanently in your environment file.

### Method A: Directly in the Web UI (Instant — Recommended)
You do not need to restart the development server or rebuild the app:
1. Launch the website (see [Step 3](#step-3-start-the-frontend-website)).
2. Look at the top-right header: click the status badge (**"Tesla T4 Ready"** or **"API Offline"** with the server icon).
3. The **Kaggle GPU Engine / Sketch2Shape API** modal will open.
4. Paste your `https://xxxx.gradio.live` URL into the **API Base URL** input field.
5. Click the **Test** button. The app will ping the `/gradio_api/call/capabilities` endpoint and display live telemetry (e.g., `GPU: Tesla T4`, `VRAM: 15 GB`, `Profile: balanced`).
6. Click **Save & Apply**. The URL is immediately saved to your browser's `localStorage` and takes effect across all pages.

### Method B: In the `.env` Configuration File
If you want the API URL pre-loaded automatically for everyone opening the dev server:
1. Open [`tripo-frontend/.env`](file:///home/ashmit/Code/new/sketch2shape-frontend-code/tripo-frontend/.env):
   ```env
   VITE_API_BASE_URL=https://xxxxxxxxxxxxxxxxxx.gradio.live
   ```
2. Save the file. Vite automatically picks up changes during development.

---

## Step 3: Start the Frontend Website

### 1. Open your terminal and enter the frontend directory:
```bash
cd tripo-frontend
```

### 2. Install dependencies (first time only):
```bash
npm install
```

### 3. Start the local development server:
```bash
npm run dev
```

The terminal will display:
```text
  VITE v8.3.5  ready in 280 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

### 4. Open in Browser:
Visit **`http://localhost:5173`** in your browser.

---

## Step 4: Using the Application

### 1. 2D Drawing & Upload Studio
- **Draw**: Use the interactive drawing canvas to sketch your object (black strokes on white canvas work best). Tools include Brush, Eraser, Undo, Redo, and Clear.
- **Upload**: Alternatively, drag and drop an existing drawing or photograph of a sketch.
- **Prompt**: Add an optional descriptive prompt (e.g., `"vintage leather armchair"`, `"ceramic coffee mug"`).
- **Preset**: Choose between `Fast` (~1.8 min), `Balanced` (~3.3 min, recommended), or `Best`.

### 2. Live Generation Pipeline
- Click **Generate 3D Shape**.
- The frontend connects to your Kaggle Gradio backend via Server-Sent Events (SSE).
- The pipeline executes:
  1. Sketch silhouette extraction & normalization
  2. Multi-view 2D candidate synthesis via diffusion
  3. CLIP-based candidate ranking
  4. 3D reconstruction & texture generation via InstantMesh / TripoSR
- Watch real-time heartbeat and status updates in the UI.

### 3. 3D Model Inspection & Export
- **Inspect**: Rotate, pan, and zoom around your generated 3D asset using Three.js OrbitControls.
- **View Options**: Toggle wireframe mode, lighting settings, and background environment.
- **Export**: Download the final **`.glb`** file or zipped **`.obj`** bundle with materials and textures.

### 4. 3D Virtual Gallery
- Navigate to the **Gallery** tab to explore a 3D virtual showroom exhibiting generated models on pedestals with dynamic lighting and camera transitions.

---

## Production Build (Optional)

To create an optimized production build:

```bash
cd tripo-frontend
npm run build
npm run preview
```

The compiled assets will be in `tripo-frontend/dist/` ready to deploy to Vercel, Netlify, Cloudflare Pages, or GitHub Pages.

---

## Troubleshooting & FAQ

| Problem | Cause | Solution |
|---|---|---|
| **API Status shows "API Offline"** | Kaggle cell stopped, URL mistyped, or tunnel expired | Check the Kaggle notebook cell; ensure it is still running. Re-copy the `https://xxxx.gradio.live` link and update it in the UI or `.env`. |
| **First request takes ~7 minutes** | Cold start model loading | Normal behavior on first request: PyTorch loads model weights into GPU VRAM. Subsequent requests take ~3 minutes (`balanced`) or ~1.8 minutes (`fast`). |
| **Kaggle Notebook Disconnected** | 12-hour session limit or browser sleep | Re-open the notebook, verify GPU is on, and click **Run All**. Copy the new Gradio URL and paste it into the frontend's API settings modal. |
| **CORS Error in Browser** | Calling `localhost:7860` instead of Gradio link | Use the public `https://xxxx.gradio.live` URL. The Gradio live tunnel automatically configures CORS headers for browser frontends. |
| **"Queue position: 1"** | Another generation is processing | The Kaggle GPU processes one 3D generation at a time. Requests queue automatically and start as soon as the previous generation completes. |
