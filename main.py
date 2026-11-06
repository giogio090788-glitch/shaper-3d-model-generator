"""Shaper — AI 3D model generator API.

Endpoints:
  POST /api/generate/text    text prompt  -> model (local procedural or Meshy cloud)
  POST /api/generate/image   image upload -> model (relief / extrude / Meshy cloud)
  GET  /api/models           list generated models
  GET  /api/download/{id}?format=glb|obj|stl|ply
  GET  /api/export/blender/{id}   download a Blender import script for the model
  GET  /                     serves the frontend
"""
import io
import json
import time
import uuid
from pathlib import Path

import trimesh
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from generators import procedural, image_to_3d, cloud, llm_prompts, shape_local

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)
INDEX_FILE = OUT_DIR / "index.json"

app = FastAPI(title="Shaper 3D")


# ---------- model registry ----------

def _load_index() -> list:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return []


def _save_index(items: list):
    INDEX_FILE.write_text(json.dumps(items, indent=2))


def _register(mesh: trimesh.Trimesh | trimesh.Scene, name: str, meta: dict) -> dict:
    model_id = uuid.uuid4().hex[:12]
    glb_path = OUT_DIR / f"{model_id}.glb"
    mesh.export(glb_path)
    entry = {
        "id": model_id,
        "name": name,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "vertices": int(sum(len(g.vertices) for g in
                            (mesh.geometry.values() if isinstance(mesh, trimesh.Scene) else [mesh]))),
        **meta,
    }
    items = _load_index()
    items.insert(0, entry)
    _save_index(items[:200])
    return entry


def _load_mesh(model_id: str) -> trimesh.Scene | trimesh.Trimesh:
    path = OUT_DIR / f"{model_id}.glb"
    if not path.exists():
        raise HTTPException(404, "Model not found")
    return trimesh.load(path)


# ---------- generation ----------

@app.post("/api/generate/text")
async def generate_text(
    prompt: str = Form(...),
    provider: str = Form("local"),          # local | shape | meshy | tripo
    complexity: int = Form(3),
    seed: int | None = Form(None),
    api_key: str = Form(""),
    art_style: str = Form("realistic"),
):
    if not prompt.strip():
        raise HTTPException(400, "Prompt is empty")
    try:
        if provider == "meshy":
            glb = cloud.meshy_text_to_3d(prompt, api_key or None, art_style)
            mesh = trimesh.load(io.BytesIO(glb), file_type="glb")
        elif provider == "tripo":
            glb = cloud.tripo_text_to_3d(prompt, api_key or None)
            mesh = trimesh.load(io.BytesIO(glb), file_type="glb")
        elif provider == "shape":
            mesh = shape_local.text_to_3d(prompt)
        else:
            mesh = procedural.generate_from_text(prompt, complexity=complexity, seed=seed)
    except cloud.CloudError as e:
        raise HTTPException(502, str(e))
    except shape_local.ShapEMissing as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")
    entry = _register(mesh, prompt[:60], {"source": f"text/{provider}", "prompt": prompt})
    return {"model": entry, "glb_url": f"/api/download/{entry['id']}?format=glb"}


@app.post("/api/generate/image")
async def generate_image(
    file: UploadFile = File(...),
    mode: str = Form("relief"),              # relief | extrude
    provider: str = Form("local"),           # local | meshy
    depth: float = Form(0.5),
    threshold: int = Form(128),
    smooth: int = Form(1),
    api_key: str = Form(""),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty upload")
    try:
        if provider == "meshy":
            glb = cloud.meshy_image_to_3d(data, api_key or None)
            mesh = trimesh.load(io.BytesIO(glb), file_type="glb")
        elif provider == "tripo":
            glb = cloud.tripo_image_to_3d(data, api_key or None)
            mesh = trimesh.load(io.BytesIO(glb), file_type="glb")
        elif provider in ("sf3d", "spar3d"):
            glb = cloud.stability_image_to_3d(data, api_key or None, model=provider)
            mesh = trimesh.load(io.BytesIO(glb), file_type="glb")
        elif mode == "extrude":
            mesh = image_to_3d.extrude(data, depth=depth, threshold=threshold)
        else:
            mesh = image_to_3d.relief(data, depth=depth, smooth=smooth)
    except cloud.CloudError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")
    entry = _register(mesh, f"image:{file.filename}",
                      {"source": f"image/{provider}/{mode}"})
    return {"model": entry, "glb_url": f"/api/download/{entry['id']}?format=glb"}


@app.post("/api/enhance")
def enhance_prompt(
    prompt: str = Form(...),
    provider: str = Form("openai"),          # openai | claude | kimi | qwen | llama | ollama
    api_key: str = Form(""),
    model: str = Form(""),
):
    if not prompt.strip():
        raise HTTPException(400, "Prompt is empty")
    try:
        enhanced = llm_prompts.enhance(prompt, provider, api_key or None, model or None)
    except llm_prompts.LLMError as e:
        raise HTTPException(502, str(e))
    return {"enhanced": enhanced}


# ---------- library / export ----------

@app.get("/api/models")
def list_models():
    return _load_index()


@app.delete("/api/models/{model_id}")
def delete_model(model_id: str):
    items = [m for m in _load_index() if m["id"] != model_id]
    _save_index(items)
    for p in OUT_DIR.glob(f"{model_id}.*"):
        if p.name != "index.json":
            p.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/download/{model_id}")
def download(model_id: str, format: str = "glb"):
    if format not in ("glb", "obj", "stl", "ply"):
        raise HTTPException(400, "Unsupported format")
    src = OUT_DIR / f"{model_id}.glb"
    if not src.exists():
        raise HTTPException(404, "Model not found")
    if format == "glb":
        return FileResponse(src, media_type="model/gltf-binary",
                            filename=f"shaper_{model_id}.glb")
    mesh = trimesh.load(src)
    data = mesh.export(file_type=format)
    if isinstance(data, str):
        data = data.encode("utf-8")
    media = {"obj": "text/plain", "stl": "model/stl", "ply": "application/octet-stream"}[format]
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="shaper_{model_id}.{format}"'})


BLENDER_SCRIPT = '''\
"""Shaper export — run inside Blender: Scripting workspace -> Open -> Run Script.
Imports the generated model and applies a clean material setup."""
import bpy

MODEL_PATH = r"{path}"

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = MODEL_PATH.rsplit(".", 1)[-1].lower()
if ext == "glb":
    bpy.ops.import_scene.gltf(filepath=MODEL_PATH)
elif ext == "obj":
    bpy.ops.wm.obj_import(filepath=MODEL_PATH)
elif ext == "stl":
    bpy.ops.wm.stl_import(filepath=MODEL_PATH)
elif ext == "ply":
    bpy.ops.wm.ply_import(filepath=MODEL_PATH)

for obj in bpy.context.selected_objects:
    obj.select_set(True)
bpy.ops.object.shade_smooth()
print("Shaper model imported:", MODEL_PATH)
'''


@app.get("/api/export/blender/{model_id}")
def export_blender(model_id: str):
    src = OUT_DIR / f"{model_id}.glb"
    if not src.exists():
        raise HTTPException(404, "Model not found")
    script = BLENDER_SCRIPT.format(path=src.resolve())
    return Response(script, media_type="text/x-python", headers={
        "Content-Disposition": f'attachment; filename="shaper_import_{model_id}.py"'})


@app.exception_handler(Exception)
async def unhandled(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# frontend last so /api routes win
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
