"""Local image -> 3D converters (no API key needed).

Two modes:
- relief: image luminance becomes a displaced heightmap surface
- extrude: image silhouette becomes an extruded solid
"""
import io
import numpy as np
import trimesh
from PIL import Image, ImageFilter, ImageOps


def _load(image_bytes: bytes, max_res: int = 128) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img.thumbnail((max_res, max_res))
    return img


def relief(image_bytes: bytes, depth: float = 0.5, smooth: int = 1) -> trimesh.Trimesh:
    """Luminance heightmap: bright pixels rise, dark pixels sink."""
    img = _load(image_bytes)
    if smooth:
        img = img.filter(ImageFilter.GaussianBlur(radius=smooth))
    h = np.asarray(img, dtype=np.float64) / 255.0 * depth
    rows, cols = h.shape

    xs = np.linspace(-1, 1, cols)
    ys = np.linspace(-1, 1, rows)
    xv, yv = np.meshgrid(xs, ys)

    verts = np.column_stack([xv.ravel(), yv.ravel(), h.ravel()])
    faces = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            i = r * cols + c
            faces.append([i, i + 1, i + cols])
            faces.append([i + 1, i + cols + 1, i + cols])
    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    _color_by_height(mesh)
    return mesh


def extrude(image_bytes: bytes, depth: float = 0.3, threshold: int = 128) -> trimesh.Trimesh:
    """Silhouette extrusion: dark regions of the image become a solid shape."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    img = _load(image_bytes, max_res=96)
    mask = np.asarray(img) < threshold
    rows, cols = mask.shape

    # Precompute grid lines so adjacent cells share EXACT float coordinates
    # (computing edges per-cell via different expressions leaves 1-ulp gaps
    # that shatter unary_union into fragments).
    sx, sy = 2.0 / cols, 2.0 / rows
    xs = -1.0 + np.arange(cols + 1) * sx
    ys = 1.0 - np.arange(rows + 1) * sy

    cells = []
    for r in range(rows):
        for c in range(cols):
            if mask[r, c]:
                cells.append(Polygon([(xs[c], ys[r + 1]), (xs[c + 1], ys[r + 1]),
                                      (xs[c + 1], ys[r]), (xs[c], ys[r])]))
    if not cells:
        raise ValueError("No silhouette found — try lowering the threshold.")
    shape = unary_union(cells)
    geoms = list(shape.geoms) if hasattr(shape, "geoms") else [shape]

    # keep all significant silhouette islands, not just the biggest
    biggest = max(g.area for g in geoms)
    keep = [g for g in geoms if g.area >= biggest * 0.02]
    tol = min(sx, sy) * 0.5

    meshes = []
    for g in keep:
        g = g.simplify(tolerance=tol)
        if g.is_empty or g.area <= 0:
            continue
        meshes.append(trimesh.creation.extrude_polygon(g, height=depth))
    if not meshes:
        raise ValueError("Silhouette too fragmented — try a cleaner image.")
    mesh = trimesh.util.concatenate(meshes)
    mesh.apply_translation([0, 0, -depth / 2])
    _color_by_height(mesh)
    return mesh


def _color_by_height(mesh: trimesh.Trimesh):
    z = mesh.vertices[:, 2]
    t = (z - z.min()) / (np.ptp(z) + 1e-9)
    # chess-green -> cream ramp (matches the UI theme)
    lo = np.array([115, 149, 82])
    hi = np.array([235, 236, 208])
    colors = (lo + (hi - lo) * t[:, None]).astype(np.uint8)
    face_colors = colors[mesh.faces].mean(axis=1).astype(np.uint8)
    face_colors = np.hstack([face_colors, np.full((len(face_colors), 1), 255, np.uint8)])
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, face_colors=face_colors)
