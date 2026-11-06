"""Local procedural mesh generator.

Turns a text prompt into a composed 3D scene using keyword-driven
parametric primitives. Works fully offline — no GPU or API key needed.
"""
import random
import math
import numpy as np
import trimesh


# keyword -> builder(seed) -> trimesh.Trimesh
def _rock(seed):
    rng = np.random.default_rng(seed)
    m = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    noise = rng.normal(1.0, 0.22, size=(len(m.vertices), 1))
    m.vertices = m.vertices * noise
    return m


def _tree(seed):
    rng = random.Random(seed)
    parts = [trimesh.creation.cylinder(radius=0.12, height=1.2, sections=10)]
    parts[0].apply_translation([0, 0, 0.6])
    for i in range(rng.randint(2, 4)):
        r = 0.8 - i * 0.2
        cone = trimesh.creation.cone(radius=max(r, 0.25), height=0.9, sections=12)
        cone.apply_translation([0, 0, 1.1 + i * 0.55])
        parts.append(cone)
    return trimesh.util.concatenate(parts)


def _crystal(seed):
    rng = np.random.default_rng(seed)
    parts = []
    for i in range(6):
        h = float(rng.uniform(0.6, 2.0))
        r = float(rng.uniform(0.1, 0.3))
        c = trimesh.creation.cone(radius=r, height=h, sections=6)
        angle = float(rng.uniform(0, 2 * math.pi))
        dist = float(rng.uniform(0, 0.5))
        c.apply_transform(trimesh.transformations.rotation_matrix(
            rng.uniform(-0.4, 0.4), [1, 0, 0]))
        c.apply_translation([math.cos(angle) * dist, math.sin(angle) * dist, h / 2])
        parts.append(c)
    return trimesh.util.concatenate(parts)


def _castle(seed):
    rng = random.Random(seed)
    parts = [trimesh.creation.box(extents=[2.2, 2.2, 1.0])]
    parts[0].apply_translation([0, 0, 0.5])
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            t = trimesh.creation.cylinder(radius=0.35, height=1.8, sections=10)
            t.apply_translation([x, y, 0.9])
            top = trimesh.creation.cone(radius=0.45, height=0.6, sections=10)
            top.apply_translation([x, y, 2.1])
            parts += [t, top]
    keep = trimesh.creation.box(extents=[1.0, 1.0, 1.6])
    keep.apply_translation([0, 0, 0.8])
    parts.append(keep)
    return trimesh.util.concatenate(parts)


def _vase(seed):
    rng = np.random.default_rng(seed)
    n = 40
    profile = []
    for i in range(n + 1):
        t = i / n
        r = 0.25 + 0.55 * math.sin(t * math.pi) ** 1.2 + 0.05 * math.sin(t * 9)
        profile.append([max(r, 0.05), t * 1.8])
    return trimesh.creation.revolve(np.array(profile), sections=48)


def _gear(seed):
    rng = random.Random(seed)
    teeth = rng.randint(8, 14)
    outer, inner, depth = 1.0, 0.75, 0.25
    pts = []
    for i in range(teeth * 4):
        ang = i / (teeth * 4) * 2 * math.pi
        r = outer if i % 4 in (1, 2) else inner
        pts.append([math.cos(ang) * r, math.sin(ang) * r])
    from shapely.geometry import Polygon as SP
    hole = [(0.4 * math.cos(a), 0.4 * math.sin(a))
            for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
    return trimesh.creation.extrude_polygon(SP(pts, holes=[hole]), height=depth)


def _abstract(seed):
    rng = np.random.default_rng(seed)
    parts = []
    builders = [lambda: trimesh.creation.icosphere(subdivisions=2, radius=float(rng.uniform(0.3, 0.8))),
                lambda: trimesh.creation.box(extents=rng.uniform(0.3, 1.0, 3).tolist()),
                lambda: trimesh.creation.capsule(radius=float(rng.uniform(0.2, 0.4)), height=float(rng.uniform(0.5, 1.2))),
                lambda: trimesh.creation.cone(radius=float(rng.uniform(0.3, 0.6)), height=float(rng.uniform(0.5, 1.4)))]
    for _ in range(int(rng.integers(4, 8))):
        m = builders[int(rng.integers(0, len(builders)))]()
        m.apply_transform(trimesh.transformations.rotation_matrix(
            float(rng.uniform(0, math.pi)), rng.normal(size=3)))
        m.apply_translation(rng.uniform(-1, 1, 3).tolist())
        parts.append(m)
    return trimesh.util.concatenate(parts)


KEYWORDS = {
    "rock": _rock, "stone": _rock, "boulder": _rock, "asteroid": _rock,
    "tree": _tree, "pine": _tree, "forest": _tree,
    "crystal": _crystal, "gem": _crystal, "shard": _crystal,
    "castle": _castle, "fortress": _castle, "tower": _castle,
    "vase": _vase, "pot": _vase, "bottle": _vase, "cup": _vase,
    "gear": _gear, "cog": _gear, "machine": _gear,
}


def generate_from_text(prompt: str, complexity: int = 3, seed: int | None = None) -> trimesh.Trimesh:
    """Build a mesh from a text prompt using keyword matching + composition."""
    if seed is None:
        seed = abs(hash(prompt)) % (2**31)
    words = prompt.lower().split()
    builders = [KEYWORDS[w] for w in words if w in KEYWORDS]
    if not builders:
        builders = [_abstract]

    rng = np.random.default_rng(seed)
    parts = []
    count = min(len(builders) * max(complexity - 1, 1), 12)
    builders_cycle = (builders * ((count // len(builders)) + 1))[:max(count, 1)]
    for i, b in enumerate(builders_cycle):
        m = b(seed + i)
        if len(builders_cycle) > 1:
            m.apply_translation(rng.uniform(-1.5, 1.5, 3).tolist())
        parts.append(m)
    mesh = trimesh.util.concatenate(parts)
    _apply_color(mesh, prompt, seed)
    return mesh


PALETTES = {
    "lava": [(220, 60, 20), (255, 140, 0), (60, 20, 10)],
    "ice": [(150, 220, 255), (220, 245, 255), (90, 160, 220)],
    "gold": [(212, 175, 55), (255, 215, 0), (160, 120, 20)],
    "forest": [(34, 139, 34), (85, 170, 60), (20, 90, 40)],
    "crystal": [(170, 120, 255), (120, 200, 255), (230, 210, 255)],
}


def _apply_color(mesh: trimesh.Trimesh, prompt: str, seed: int):
    rng = np.random.default_rng(seed)
    base = None
    for key, pal in PALETTES.items():
        if key in prompt.lower():
            base = pal
            break
    if base is None:
        base = [(129, 182, 76), (120, 130, 140), (180, 170, 150)]
    colors = np.array([base[int(rng.integers(0, len(base)))] + (255,)
                       for _ in range(len(mesh.faces))], dtype=np.uint8)
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, face_colors=colors)
