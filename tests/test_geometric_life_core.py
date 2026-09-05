import math
import unittest

from scripts.geometric_life_core import build_scene, frame_state, motion_progress
from scripts.render_geometric_life import validate_video_dimensions


class GeometricLifeCoreTests(unittest.TestCase):
    def test_video_dimensions_must_be_even_for_h264_output(self):
        self.assertEqual(validate_video_dimensions(720, 900), [])
        self.assertEqual(
            validate_video_dimensions(180, 225),
            ["height must be even for yuv420p H.264 output"],
        )

    def test_motion_progress_returns_to_start_for_eight_second_loop(self):
        self.assertAlmostEqual(motion_progress(0.0), 0.0)
        self.assertAlmostEqual(motion_progress(6.0), 1.0)
        self.assertAlmostEqual(motion_progress(8.0), 0.0)

    def test_first_and_last_frame_have_identical_geometry(self):
        scene = build_scene(seed=683277)
        first = frame_state(scene, frame_index=0, frame_count=240)
        last = frame_state(scene, frame_index=239, frame_count=240)

        for collection in ("vertices", "nodes", "face_centers"):
            self.assertEqual(len(first[collection]), len(last[collection]))
            for a, b in zip(first[collection], last[collection]):
                for av, bv in zip(a, b):
                    self.assertAlmostEqual(av, bv, places=9)

    def test_mid_animation_uses_independent_irregular_motion(self):
        scene = build_scene(seed=683277)
        first = frame_state(scene, frame_index=0, frame_count=240)
        middle = frame_state(scene, frame_index=120, frame_count=240)

        displacements = []
        for base, moved in zip(first["vertices"], middle["vertices"]):
            distance = math.dist(base, moved)
            displacements.append(round(distance, 4))

        self.assertGreater(max(displacements), 0.2)
        self.assertGreater(len(set(displacements)), 12)

        base_lengths = first["edge_lengths"]
        moved_lengths = middle["edge_lengths"]
        changed = [
            abs(a - b)
            for a, b in zip(base_lengths, moved_lengths)
            if abs(a - b) > 0.03
        ]
        self.assertGreater(len(changed), len(base_lengths) // 2)


if __name__ == "__main__":
    unittest.main()
