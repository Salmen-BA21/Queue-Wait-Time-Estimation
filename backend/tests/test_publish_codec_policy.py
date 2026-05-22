from __future__ import annotations

import unittest
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config import AppConfig
from src.main import PublishedWebRtcPublisher


class _DummyEventWriter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, event: str, payload: dict[str, object]) -> None:
        self.events.append((event, payload))


class TestPublishCodecPolicy(unittest.TestCase):
    def _build_publisher(self) -> PublishedWebRtcPublisher:
        cfg = AppConfig(
            annotated_webrtc_enable=True,
            annotated_webrtc_path="ann-test",
            annotated_webrtc_rtsp_host="127.0.0.1",
            annotated_webrtc_rtsp_port=8554,
            annotated_webrtc_fps=15,
            annotated_webrtc_ffmpeg_binary="ffmpeg",
        )
        return PublishedWebRtcPublisher(cfg, _DummyEventWriter())  # type: ignore[arg-type]

    def test_build_command_enforces_baseline_compatible_output(self) -> None:
        publisher = self._build_publisher()
        command, compatibility_reason = publisher._build_command(width=1280, height=720)

        self.assertIn("-c:v", command)
        self.assertIn("libx264", command)
        self.assertIn("-profile:v", command)
        self.assertIn("baseline", command)
        self.assertIn("-level:v", command)
        self.assertIn("3.1", command)
        self.assertIn("-pix_fmt", command)
        self.assertIn("yuv420p", command)
        self.assertIsNone(compatibility_reason)

    def test_odd_dimensions_activate_padding_fallback(self) -> None:
        publisher = self._build_publisher()
        command, compatibility_reason = publisher._build_command(width=641, height=481)

        self.assertIn("-vf", command)
        self.assertIn("pad=ceil(iw/2)*2:ceil(ih/2)*2", command)
        self.assertEqual(compatibility_reason, "codec_fallback_dimension_alignment")


if __name__ == "__main__":
    unittest.main()
