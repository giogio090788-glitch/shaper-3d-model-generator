"""Cloud AI providers: real text-to-3D / image-to-3D via hosted APIs.

Supported:
- Meshy AI       (https://www.meshy.ai)          MESHY_API_KEY
- Tripo AI       (https://platform.tripo3d.ai)   TRIPO_API_KEY
- Stability AI   (https://platform.stability.ai) STABILITY_API_KEY  (image->3D only)

Returns raw GLB bytes.
"""
import os
import time
import base64
import requests

MESHY_BASE = "https://api.meshy.ai/openapi/v2"


class CloudError(Exception):
    pass


def _headers(api_key: str | None) -> dict:
    key = api_key or os.environ.get("MESHY_API_KEY")
    if not key:
        raise CloudError("No API key. Set MESHY_API_KEY or paste a key in the UI.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _wait_for_task(task_id: str, endpoint: str, api_key: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{MESHY_BASE}/{endpoint}/{task_id}",
                         headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status == "SUCCEEDED":
            return data
        if status in ("FAILED", "EXPIRED"):
            raise CloudError(f"Meshy task {status}: {data.get('task_error', {})}")
        time.sleep(5)
    raise CloudError("Cloud generation timed out.")


def _download_glb(task: dict) -> bytes:
    url = (task.get("model_urls") or {}).get("glb")
    if not url:
        raise CloudError("Task succeeded but no GLB URL returned.")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def meshy_text_to_3d(prompt: str, api_key: str | None = None,
                     art_style: str = "realistic", timeout: int = 600) -> bytes:
    payload = {"mode": "preview", "prompt": prompt, "art_style": art_style}
    r = requests.post(f"{MESHY_BASE}/text-to-3d", json=payload,
                      headers=_headers(api_key), timeout=30)
    r.raise_for_status()
    task_id = r.json()["result"]
    task = _wait_for_task(task_id, "text-to-3d", api_key, timeout)
    return _download_glb(task)


def meshy_image_to_3d(image_bytes: bytes, api_key: str | None = None,
                      timeout: int = 600) -> bytes:
    b64 = base64.b64encode(image_bytes).decode()
    payload = {"image_url": f"data:image/png;base64,{b64}", "enable_pbr": True}
    r = requests.post(f"{MESHY_BASE}/image-to-3d", json=payload,
                      headers=_headers(api_key), timeout=60)
    r.raise_for_status()
    task_id = r.json()["result"]
    task = _wait_for_task(task_id, "image-to-3d", api_key, timeout)
    return _download_glb(task)


# ---------- Tripo AI ----------

TRIPO_BASE = "https://api.tripo3d.ai/v2/openapi"


def _tripo_headers(api_key: str | None) -> dict:
    key = api_key or os.environ.get("TRIPO_API_KEY")
    if not key:
        raise CloudError("No Tripo API key. Set TRIPO_API_KEY or paste a key in the UI.")
    return {"Authorization": f"Bearer {key}"}


def _tripo_wait(task_id: str, api_key: str | None, timeout: int) -> bytes:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{TRIPO_BASE}/task/{task_id}",
                         headers=_tripo_headers(api_key), timeout=30)
        r.raise_for_status()
        data = r.json().get("data", {})
        status = data.get("status")
        if status == "success":
            out = data.get("output") or {}
            url = out.get("pbr_model") or out.get("model")
            if not url:
                raise CloudError("Tripo task succeeded but no model URL returned.")
            resp = requests.get(url, timeout=180)
            resp.raise_for_status()
            return resp.content
        if status in ("failed", "cancelled", "banned"):
            raise CloudError(f"Tripo task {status}.")
        time.sleep(4)
    raise CloudError("Tripo generation timed out.")


def tripo_text_to_3d(prompt: str, api_key: str | None = None,
                     timeout: int = 900) -> bytes:
    r = requests.post(f"{TRIPO_BASE}/task",
                      json={"type": "text_to_model", "prompt": prompt},
                      headers={**_tripo_headers(api_key),
                               "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    task_id = r.json()["data"]["task_id"]
    return _tripo_wait(task_id, api_key, timeout)


def tripo_image_to_3d(image_bytes: bytes, api_key: str | None = None,
                      timeout: int = 900) -> bytes:
    up = requests.post(f"{TRIPO_BASE}/upload",
                       files={"file": ("image.png", image_bytes, "image/png")},
                       headers=_tripo_headers(api_key), timeout=120)
    up.raise_for_status()
    data = up.json().get("data", {})
    token = data.get("image_token") or data.get("file_token")
    if not token:
        raise CloudError("Tripo image upload failed.")
    r = requests.post(f"{TRIPO_BASE}/task",
                      json={"type": "image_to_model",
                            "file": {"type": "png", "file_token": token}},
                      headers={**_tripo_headers(api_key),
                               "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    task_id = r.json()["data"]["task_id"]
    return _tripo_wait(task_id, api_key, timeout)


# ---------- Stability AI (image -> 3D) ----------

STABILITY_URLS = {
    "sf3d": "https://api.stability.ai/v2beta/3d/stable-fast-3d",
    "spar3d": "https://api.stability.ai/v2beta/3d/stable-point-aware-3d",
}


def stability_image_to_3d(image_bytes: bytes, api_key: str | None = None,
                          model: str = "sf3d", timeout: int = 600) -> bytes:
    key = api_key or os.environ.get("STABILITY_API_KEY")
    if not key:
        raise CloudError("No Stability API key. Set STABILITY_API_KEY or paste a key in the UI.")
    url = STABILITY_URLS.get(model, STABILITY_URLS["sf3d"])
    extra = {"foreground_ratio": "0.9"} if model == "sf3d" else {}
    r = requests.post(url,
                      headers={"Authorization": f"Bearer {key}"},
                      files={"image": ("image.png", image_bytes, "image/png")},
                      data=extra, timeout=timeout)
    if r.status_code != 200:
        raise CloudError(f"Stability error {r.status_code}: {r.text[:200]}")
    return r.content
