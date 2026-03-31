"""Tests for file playback pacing and parser defaults in src.main."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config import DEFAULT_PROCESS_EVERY_N_FRAMES, DEFAULT_REALTIME_FILE_PLAYBACK
from src.main import _compute_playback_target_fps, _is_file_source, build_parser


class TestMainPlaybackFlags(unittest.TestCase):
    """Validate CLI flags and source classification for playback pacing."""

    def test_parser_defaults_use_config_values(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])

        self.assertEqual(args.process_every_n_frames, DEFAULT_PROCESS_EVERY_N_FRAMES)
        self.assertEqual(args.realtime_file_playback, DEFAULT_REALTIME_FILE_PLAYBACK)

    def test_parser_accepts_realtime_toggle_flags(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["--no-realtime-file-playback"])
        self.assertFalse(args.realtime_file_playback)

        args = parser.parse_args(["--realtime-file-playback"])
        self.assertTrue(args.realtime_file_playback)

    def test_is_file_source_detects_local_video_sources(self) -> None:
        self.assertTrue(_is_file_source("videos/sample.mp4"))
        self.assertFalse(_is_file_source("rtsp://192.168.1.50/live"))
        self.assertFalse(_is_file_source("0"))
        self.assertFalse(_is_file_source(0))

    def test_realtime_playback_targets_exact_source_fps(self) -> None:
        self.assertAlmostEqual(
            _compute_playback_target_fps(
                source_fps=13.1,
                output_fps=13,
                realtime_file_playback=True,
            ),
            13.1,
        )

        self.assertEqual(
            _compute_playback_target_fps(
                source_fps=13.1,
                output_fps=24,
                realtime_file_playback=False,
            ),
            24.0,
        )


if __name__ == "__main__":
    unittest.main()
