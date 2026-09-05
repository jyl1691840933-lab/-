from __future__ import annotations

import argparse
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

try:
    from .geometric_life_core import build_scene, face_points, frame_state
except ImportError:
    from geometric_life_core import build_scene, face_points, frame_state


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "public" / "videos" / "geometric-life-loop.mp4"
DEFAULT_FFMPEG = ROOT / "node_modules" / "ffmpeg-static" / "ffmpeg.exe"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffmpeg", type=Path, default=DEFAULT_FFMPEG)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=683277)
    parser.add_argument("--first-frame", type=Path, default=ROOT / "public" / "videos" / "geometric-life-loop-first.png")
    parser.add_argument("--last-frame", type=Path, default=ROOT / "public" / "videos" / "geometric-life-loop-last.png")
    args = parser.parse_args()

    dimension_errors = validate_video_dimensions(args.width, args.height)
    if dimension_errors:
        for error in dimension_errors:
            print(error, file=sys.stderr)
        return 2

    if not args.ffmpeg.exists():
        print(f"ffmpeg executable not found: {args.ffmpeg}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene(seed=args.seed)
    frame_count = args.fps * args.seconds

    command = [
        str(args.ffmpeg),
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{args.width}x{args.height}",
        "-r",
        str(args.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(args.output),
    ]

    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:
        raise RuntimeError("ffmpeg stdin was not opened")

    first = None
    last = None
    try:
        for frame_index in range(frame_count):
            image = render_frame(scene, frame_index, frame_count, args.width, args.height)
            if frame_index == 0:
                first = image.copy()
            if frame_index == frame_count - 1:
                last = image.copy()
            process.stdin.write(image.tobytes())
    finally:
        process.stdin.close()

    exit_code = process.wait()
    if exit_code != 0:
        return exit_code

    if first is not None:
        first.save(args.first_frame)
    if last is not None:
        last.save(args.last_frame)
    return 0


def validate_video_dimensions(width: int, height: int) -> list[str]:
    errors = []
    if width % 2:
        errors.append("width must be even for yuv420p H.264 output")
    if height % 2:
        errors.append("height must be even for yuv420p H.264 output")
    return errors


def render_frame(scene, frame_index: int, frame_count: int, width: int, height: int) -> Image.Image:
    scale = 2
    canvas_size = (width * scale, height * scale)
    image = Image.new("RGB", canvas_size, (244, 244, 242))
    draw = ImageDraw.Draw(image, "RGBA")
    state = frame_state(scene, frame_index, frame_count)

    projected_vertices = [_project(point, canvas_size) for point in state["vertices"]]
    projected_nodes = [_project(point, canvas_size) for point in state["nodes"]]

    _draw_background_shadow(image, scene, state, canvas_size)
    _draw_network(draw, scene, state, projected_vertices, projected_nodes, scale)
    _draw_faces(draw, scene, state, canvas_size)
    _draw_core_lines(draw, scene, state, projected_vertices, scale)
    _draw_nodes(draw, state, projected_vertices, projected_nodes, scale)

    return image.resize((width, height), Image.Resampling.LANCZOS)


def _draw_background_shadow(image: Image.Image, scene, state, canvas_size: tuple[int, int]) -> None:
    overlay = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    shadow = ImageDraw.Draw(overlay, "RGBA")
    for face_index in range(len(scene.faces)):
        points = [_project(point, canvas_size, y_offset=34, flatten=0.88) for point in face_points(scene, state, face_index)]
        shadow.polygon(points, fill=(0, 0, 0, 13))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=14))
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def _draw_network(draw: ImageDraw.ImageDraw, scene, state, projected_vertices, projected_nodes, scale: int) -> None:
    progress = state["progress"]
    node_links = _node_links(scene)
    all_points = state["nodes"] + state["vertices"]
    projected_all = projected_nodes + projected_vertices
    node_count = len(state["nodes"])

    for link_index, (a, b) in enumerate(node_links):
        pa = projected_all[a]
        pb = projected_all[b]
        length_wave = _wave(progress, 0.31 + (link_index % 6) * 0.11, link_index * 0.47)
        slack = 1.0 + 0.08 * length_wave
        center = ((pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5)
        pa = (center[0] + (pa[0] - center[0]) * slack, center[1] + (pa[1] - center[1]) * slack)
        pb = (center[0] + (pb[0] - center[0]) * slack, center[1] + (pb[1] - center[1]) * slack)
        alpha = int(38 + 40 * abs(_wave(progress, 0.23 + (link_index % 4) * 0.09, link_index * 0.39)))
        width = max(1, int(scale * (0.46 + 0.16 * (link_index % 3))))
        draw.line([pa, pb], fill=(34, 34, 34, alpha), width=width)

        if link_index % 5 == 0 and a < node_count:
            target = node_count + ((b + link_index * 3) % len(scene.vertices))
            alt = projected_all[target]
            blend = 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, progress)))
            end = (pb[0] * (1 - blend) + alt[0] * blend, pb[1] * (1 - blend) + alt[1] * blend)
            draw.line([pa, end], fill=(10, 10, 10, int(alpha * 0.38)), width=1)


def _draw_faces(draw: ImageDraw.ImageDraw, scene, state, canvas_size: tuple[int, int]) -> None:
    ordered = []
    for face_index in range(len(scene.faces)):
        points = face_points(scene, state, face_index)
        depth = sum(_rotate_static(point)[2] for point in points) / 3.0
        ordered.append((depth, face_index, points))

    light = _normalize((-0.42, -0.58, 1.0))
    for _, face_index, points in sorted(ordered):
        normal = _normal(points[0], points[1], points[2])
        lambert = max(0.0, _dot(normal, light))
        shade = int(58 + lambert * 148 + (face_index % 4) * 7)
        fill = (shade, shade, shade, 238)
        outline = (18, 18, 18, 70)
        polygon = [_project(point, canvas_size) for point in points]
        draw.polygon(polygon, fill=fill)
        draw.line(polygon + [polygon[0]], fill=outline, width=1)


def _draw_core_lines(draw: ImageDraw.ImageDraw, scene, state, projected_vertices, scale: int) -> None:
    progress = state["progress"]
    for edge_index, (a, b) in enumerate(scene.edges):
        pa = projected_vertices[a]
        pb = projected_vertices[b]
        alpha = int(78 + 76 * abs(_wave(progress, 0.33 + (edge_index % 5) * 0.08, edge_index * 0.52)))
        draw.line([pa, pb], fill=(9, 9, 9, alpha), width=max(1, int(0.78 * scale)))


def _draw_nodes(draw: ImageDraw.ImageDraw, state, projected_vertices, projected_nodes, scale: int) -> None:
    progress = state["progress"]
    for i, point in enumerate(projected_nodes):
        radius = scale * (2.0 + 1.0 * abs(_wave(progress, 0.35 + (i % 6) * 0.07, i * 0.51)))
        _ellipse(draw, point, radius, (4, 4, 4, 220))
    for i, point in enumerate(projected_vertices):
        radius = scale * (2.2 + 1.4 * abs(_wave(progress, 0.41 + (i % 4) * 0.09, i * 0.62)))
        _ellipse(draw, point, radius, (0, 0, 0, 230))


def _node_links(scene) -> list[tuple[int, int]]:
    points = scene.nodes + scene.vertices
    node_count = len(scene.nodes)
    links: set[tuple[int, int]] = set()
    for i, point in enumerate(scene.nodes):
        distances = sorted((math.dist(point, other), j) for j, other in enumerate(scene.nodes) if j != i)
        for _, j in distances[:2]:
            links.add(tuple(sorted((i, j))))
        vertex = min(range(len(scene.vertices)), key=lambda j: math.dist(point, scene.vertices[j]))
        links.add(tuple(sorted((i, node_count + vertex))))

    for vertex_index in range(len(scene.vertices)):
        node_index = min(range(node_count), key=lambda j: math.dist(scene.vertices[vertex_index], scene.nodes[j]))
        links.add(tuple(sorted((node_index, node_count + vertex_index))))
    return sorted(links)


def _project(point, canvas_size: tuple[int, int], y_offset: float = 0.0, flatten: float = 1.0) -> tuple[float, float]:
    width, height = canvas_size
    x, y, z = _rotate_static(point)
    z += 4.2
    perspective = 4.9 / z
    scale = min(width, height) * 0.205
    return (
        width * 0.5 + x * perspective * scale,
        height * 0.505 - y * perspective * scale * flatten + y_offset,
    )


def _rotate_static(point) -> tuple[float, float, float]:
    x, y, z = point
    cy, sy = math.cos(-0.22), math.sin(-0.22)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cx, sx = math.cos(0.20), math.sin(0.20)
    y, z = y * cx - z * sx, y * sx + z * cx
    return x, y, z


def _ellipse(draw: ImageDraw.ImageDraw, center, radius: float, fill) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _wave(progress: float, frequency: float, phase: float) -> float:
    return math.sin((math.tau * frequency * progress) + phase) - math.sin(phase)


def _normal(a, b, c):
    u = np.subtract(b, a)
    v = np.subtract(c, a)
    normal = np.cross(u, v)
    return _normalize(normal)


def _normalize(values):
    vector = np.array(values, dtype=float)
    length = np.linalg.norm(vector)
    if length == 0:
        return vector
    return vector / length


def _dot(a, b) -> float:
    return float(np.dot(a, b))


if __name__ == "__main__":
    raise SystemExit(main())
