# Shaper — AI 3D Model Studio

Generate 3D models from text prompts or images, preview them in a slick
glassmorphism web UI, and export straight to Blender (GLB/OBJ/STL/PLY).

## Features

- **Text to 3D**
  - *Local procedural* — offline keyword-driven generator (rocks, trees,
    crystals, castles, vases, gears…) with complexity + seed control
  - *Shap-E (OpenAI)* — real neural text-to-3D running locally (optional,
    needs torch + shap-e, see below)
  - *Meshy / Tripo AI cloud* — full generative text-to-3D
- **Image to 3D**
  - *Relief heightmap* — luminance becomes sculpted terrain-like relief
  - *Silhouette extrude* — dark shapes become solid extruded geometry
  - *Meshy / Tripo / Stability (Stable Fast 3D, SPAR3D)* — cloud image-to-3D
- **Prompt enhancer (LLM)** — GPT, Claude, Kimi K3, Qwen, Llama (OpenRouter)
  or a local Ollama model expands your short idea into a detailed 3D prompt.
  (LLMs can't emit meshes themselves — they write better prompts for the
  engines that do.)
- **Live 3D preview** (Three.js) — orbit controls, auto-rotate, wireframe
  toggle, background presets, soft shadows
- **Export** GLB / OBJ / STL / PLY — all import natively into Blender
- **Blender integration** — downloadable per-model import script, plus a
  one-click importer addon (`blender/shaper_importer.py`)
- **Model library** — saved models with auto-captured preview thumbnails

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000

## Cloud / API keys (all optional)

Paste keys into the UI (never stored) or export env vars:

```bash
export MESHY_API_KEY=msy-...          # Meshy text/image-to-3D
export TRIPO_API_KEY=...              # Tripo text/image-to-3D
export STABILITY_API_KEY=sk-...       # Stable Fast 3D / SPAR3D image-to-3D
export OPENAI_API_KEY=sk-...          # GPT prompt enhancer
export ANTHROPIC_API_KEY=sk-ant-...   # Claude prompt enhancer
export MOONSHOT_API_KEY=sk-...        # Kimi K3 prompt enhancer
export DASHSCOPE_API_KEY=sk-...       # Qwen prompt enhancer
export OPENROUTER_API_KEY=sk-or-...   # Llama prompt enhancer
# Ollama enhancer needs no key — just run: ollama pull llama3.1
```

## Optional: OpenAI Shap-E (local neural text-to-3D)

```bash
cd backend && source .venv/bin/activate
pip install torch
pip install git+https://github.com/openai/shap-e
```

First generation downloads ~1 GB of weights. GPU strongly recommended —
CPU works but takes minutes per model.

## Blender export

1. Quick way: in the app, click **Blender import script** — run the downloaded
   `.py` inside Blender's Scripting workspace.
2. Nicer way: install `blender/shaper_importer.py` as an addon, then import
   the latest model with one click from the 3D viewport sidebar.
3. Manual way: download GLB/OBJ/STL/PLY and use File → Import in Blender.

## Project layout

```
backend/
  main.py                  FastAPI app (generation, download, export routes)
  generators/procedural.py local text-to-3D engine
  generators/image_to_3d.py local image converters (relief / extrude)
  generators/cloud.py      Meshy API client
frontend/
  index.html / style.css / app.js   glassmorphism UI + Three.js viewer
blender/shaper_importer.py          Blender addon
output/                             generated models + library index
```
