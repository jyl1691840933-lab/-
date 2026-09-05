from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable

Vec3 = tuple[float, float, float]

LOOP_SECONDS = 8.0
EVOLVE_SECONDS = 6.0


@dataclass(frozen=True)
class Scene:
    vertices: list[Vec3]
    nodes: list[Vec3]
    faces: list[tuple[int, int, int]]
    edges: list[tuple[int, int]]
    vertex_motion: list[tuple[Vec3, Vec3, Vec3]]
    node_motion: list[tuple[Vec3, Vec3, Vec3]]
    face_motion: list[tuple[Vec3, float, float]]


def motion_progress(seconds: float) -> float:
    seconds = max(0.0, min(LOOP_SECONDS, seconds))
    if seconds <= EVOLVE_SECONDS:
        return seconds / EVOLVE_SECONDS
    return 1.0 - ((seconds - EVOLVE_SECONDS) / (LOOP_SECONDS - EVOLVE_SECONDS))


def build_scene(seed: int = 683277) -> Scene:
    rng = random.Random(seed)
    vertices = _core_vertices()
    faces = _core_faces()
    edges = _unique_edges(faces)
    nodes = _network_nodes(rng)

    vertex_motion = [
        (_rand_vec(rng, 0.12, 0.42), _rand_vec(rng, 0.04, 0.16), _rand_vec(rng, 0.02, 0.11))
        for _ in vertices
    ]
    node_motion = [
        (_rand_vec(rng, 0.08, 0.36), _rand_vec(rng, 0.03, 0.20), _rand_vec(rng, 0.03, 0.16))
        for _ in nodes
    ]
    face_motion = [
        (_rand_vec(rng, 0.02, 0.12), rng.uniform(-0.22, 0.22), rng.uniform(-0.14, 0.14))
        for _ in faces
    ]
    return Scene(vertices, nodes, faces, edges, vertex_motion, node_motion, face_motion)


def frame_state(scene: Scene, frame_index: int, frame_count: int) -> dict[str, list]:
    if frame_count < 2:
        raise ValueError("frame_count must be at least 2")
    seconds = LOOP_SECONDS * (frame_index / (frame_count - 1))
    progress = motion_progress(seconds)
    vertices = [
        _move_point(point, motion, progress, i, 0.36)
        for i, (point, motion) in enumerate(zip(scene.vertices, scene.vertex_motion))
    ]
    nodes = [
        _move_point(point, motion, progress, i + 101, 0.28)
        for i, (point, motion) in enumerate(zip(scene.nodes, scene.node_motion))
    ]
    face_centers = [
        _face_center(vertices, face, scene.face_motion[i], progress, i)
        for i, face in enumerate(scene.faces)
    ]
    edge_lengths = [math.dist(vertices[a], vertices[b]) for a, b in scene.edges]
    return {
        "seconds": seconds,
        "progress": progress,
        "vertices": vertices,
        "nodes": nodes,
        "face_centers": face_centers,
        "edge_lengths": edge_lengths,
    }


def face_points(scene: Scene, state: dict[str, list], face_index: int) -> list[Vec3]:
    vertices = state["vertices"]
    face = scene.faces[face_index]
    points = [vertices[i] for i in face]
    progress = state["progress"]
    drift, twist, lift = scene.face_motion[face_index]
    center = _average(points)
    wave = _wave(progress, 0.38 + face_index * 0.071, 0.7 + face_index * 0.37)
    twist_amount = twist * wave
    lifted = _add(center, _mul(drift, wave))
    normal = _normal(points[0], points[1], points[2])
    lifted = _add(lifted, _mul(normal, lift * wave))
    return [_add(_rotate_around_z(_sub(point, center), twist_amount), lifted) for point in points]


def _core_vertices() -> list[Vec3]:
    return [
        (-0.86, -0.58, -0.22),
        (0.74, -0.62, -0.18),
        (0.90, 0.42, -0.10),
        (-0.70, 0.56, -0.16),
        (-0.12, -0.02, 0.78),
        (0.10, -0.08, -0.82),
        (-1.72, -0.14, 0.12),
        (1.78, -0.06, 0.08),
        (-0.22, 1.60, 0.04),
        (0.04, -1.66, 0.05),
        (-1.36, -1.16, 0.22),
        (1.44, 1.10, 0.18),
        (-1.24, 1.16, -0.08),
        (1.26, -1.18, -0.06),
        (-0.38, 0.22, 1.12),
        (0.48, -0.10, 1.00),
        (-0.42, -0.28, -1.04),
        (0.54, 0.24, -0.96),
    ]


def _core_faces() -> list[tuple[int, int, int]]:
    return [
        (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
        (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5),
        (6, 0, 3), (6, 3, 12), (6, 10, 0),
        (7, 2, 1), (7, 11, 2), (7, 1, 13),
        (8, 3, 2), (8, 12, 3), (8, 2, 11),
        (9, 1, 0), (9, 13, 1), (9, 0, 10),
        (14, 3, 4), (14, 4, 15), (15, 4, 1),
        (16, 0, 5), (16, 5, 17), (17, 5, 2),
        (10, 16, 0), (11, 17, 2), (12, 14, 3), (13, 15, 1),
    ]


def _network_nodes(rng: random.Random) -> list[Vec3]:
    nodes: list[Vec3] = []
    for i in range(34):
        angle = (i / 34.0) * math.tau + rng.uniform(-0.26, 0.26)
        radius = rng.uniform(1.45, 2.55)
        z = rng.uniform(-0.88, 0.92)
        y_scale = rng.uniform(0.72, 1.16)
        nodes.append((math.cos(angle) * radius, math.sin(angle) * radius * y_scale, z))
    return nodes


def _unique_edges(faces: Iterable[tuple[int, int, int]]) -> list[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for a, b, c in faces:
        for edge in ((a, b), (b, c), (c, a)):
            edges.add(tuple(sorted(edge)))
    return sorted(edges)


def _move_point(point: Vec3, motion: tuple[Vec3, Vec3, Vec3], progress: float, index: int, gain: float) -> Vec3:
    a, b, c = motion
    w1 = _wave(progress, 0.42 + (index % 5) * 0.17, index * 0.61)
    w2 = _wave(progress, 0.77 + (index % 7) * 0.13, index * 0.43 + 1.8)
    w3 = _wave(progress, 1.18 + (index % 4) * 0.19, index * 0.31 + 3.1)
    return _add(point, _mul(_add(_add(_mul(a, w1), _mul(b, w2)), _mul(c, w3)), gain))


def _wave(progress: float, frequency: float, phase: float) -> float:
    return math.sin((math.tau * frequency * progress) + phase) - math.sin(phase)


def _face_center(vertices: list[Vec3], face: tuple[int, int, int], motion: tuple[Vec3, float, float], progress: float, index: int) -> Vec3:
    center = _average([vertices[i] for i in face])
    drift, _, lift = motion
    wave = _wave(progress, 0.51 + index * 0.041, index * 0.29 + 0.6)
    return _add(center, _mul(drift, wave + lift * 0.35))


def _rand_vec(rng: random.Random, low: float, high: float) -> Vec3:
    scale = rng.uniform(low, high)
    theta = rng.uniform(0.0, math.tau)
    z = rng.uniform(-1.0, 1.0)
    radial = math.sqrt(max(0.0, 1.0 - z * z))
    return (math.cos(theta) * radial * scale, math.sin(theta) * radial * scale, z * scale)


def _average(points: list[Vec3]) -> Vec3:
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    u = _sub(b, a)
    v = _sub(c, a)
    normal = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = math.sqrt(sum(value * value for value in normal)) or 1.0
    return (normal[0] / length, normal[1] / length, normal[2] / length)


def _rotate_around_z(point: Vec3, angle: float) -> Vec3:
    c = math.cos(angle)
    s = math.sin(angle)
    return (point[0] * c - point[1] * s, point[0] * s + point[1] * c, point[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Vec3, value: float) -> Vec3:
    return (a[0] * value, a[1] * value, a[2] * value)
