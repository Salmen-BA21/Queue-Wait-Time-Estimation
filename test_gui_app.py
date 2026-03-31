"""Unit tests for MainWindow.get_analysis_commands()."""

from __future__ import annotations

import json
import sys
import tkinter as tk
import unittest


class TestGetAnalysisCommands(unittest.TestCase):
    """Verify that get_analysis_commands() builds correct arg-lists."""

    @classmethod
    def setUpClass(cls):
        # A single hidden Tk root keeps tkinter happy across all tests
        cls._root = tk.Tk()
        cls._root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls._root.destroy()

    def _make_window(self):
        """Create a MainWindow without showing it."""
        from backend.src.gui.app import MainWindow

        win = MainWindow()
        win.root.withdraw()
        return win

    # ── single video, no zone ─────────────────────────────────

    def test_single_video_no_zone(self):
        from backend.src.gui.app import DEFAULT_GUI_PROCESS_EVERY_N_FRAMES

        win = self._make_window()
        win.video_paths = [r"C:\videos\cam1.mp4"]
        win.model_size.set("n")
        win.log_level.set("INFO")
        win.queue_length_warning.set(8)
        win.zone_points_map.clear()

        cmds = win.get_analysis_commands()
        self.assertEqual(len(cmds), 1)

        cmd = cmds[0]
        self.assertIn("--source", cmd)
        self.assertEqual(cmd[cmd.index("--source") + 1], r"C:\videos\cam1.mp4")
        self.assertIn("--model-size", cmd)
        self.assertEqual(cmd[cmd.index("--model-size") + 1], "n")
        self.assertIn("--device", cmd)
        self.assertIn("--detector-imgsz", cmd)
        self.assertEqual(cmd[cmd.index("--detector-imgsz") + 1], "512")
        self.assertIn("--process-every-n-frames", cmd)
        self.assertEqual(
            cmd[cmd.index("--process-every-n-frames") + 1],
            str(DEFAULT_GUI_PROCESS_EVERY_N_FRAMES),
        )
        self.assertIn("--queue-length-warning", cmd)
        self.assertEqual(cmd[cmd.index("--queue-length-warning") + 1], "8")
        self.assertNotIn("--zone-points", cmd)
        win.root.destroy()

    # ── single video, with zone ───────────────────────────────

    def test_single_video_with_zone(self):
        win = self._make_window()
        path = r"C:\videos\cam1.mp4"
        zone = [[10, 20], [30, 40], [50, 60]]
        win.video_paths = [path]
        win.model_size.set("m")
        win.log_level.set("DEBUG")
        win.queue_length_warning.set(6)
        win.zone_points_map = {path: zone}

        cmds = win.get_analysis_commands()
        self.assertEqual(len(cmds), 1)

        cmd = cmds[0]
        self.assertIn("--zone-points", cmd)
        raw = cmd[cmd.index("--zone-points") + 1]
        self.assertEqual(json.loads(raw), zone)
        self.assertEqual(cmd[cmd.index("--model-size") + 1], "m")
        self.assertEqual(cmd[cmd.index("--queue-length-warning") + 1], "6")
        win.root.destroy()

    # ── multiple videos, mixed zones ──────────────────────────

    def test_multiple_videos_mixed_zones(self):
        win = self._make_window()
        p1 = r"C:\videos\cam1.mp4"
        p2 = r"C:\videos\cam2.mp4"
        p3 = r"C:\videos\cam3.mp4"
        zone1 = [[0, 0], [100, 0], [100, 100]]
        win.video_paths = [p1, p2, p3]
        win.model_size.set("x (x-large)")
        win.log_level.set("WARNING")
        win.queue_length_warning.set(4)
        win.zone_points_map = {p1: zone1}  # only first has a zone

        cmds = win.get_analysis_commands()
        self.assertEqual(len(cmds), 3)

        # First video has zone
        self.assertIn("--zone-points", cmds[0])
        # Second and third do not
        self.assertNotIn("--zone-points", cmds[1])
        self.assertNotIn("--zone-points", cmds[2])

        # Model size extracted correctly ("x" from "x (x-large)")
        self.assertEqual(cmds[0][cmds[0].index("--model-size") + 1], "x")
        self.assertEqual(cmds[0][cmds[0].index("--queue-length-warning") + 1], "4")
        win.root.destroy()

    # ── no videos ─────────────────────────────────────────────

    def test_no_videos_returns_empty(self):
        win = self._make_window()
        win.video_paths = []
        cmds = win.get_analysis_commands()
        self.assertEqual(cmds, [])
        win.root.destroy()


if __name__ == "__main__":
    unittest.main()
