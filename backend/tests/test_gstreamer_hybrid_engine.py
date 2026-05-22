from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config import AppConfig
from src.main import DashboardEventWriter, PipelineEngineSelector, UnifiedPublishPipeline, GStreamerHybridEngine


class _NoopWriter(DashboardEventWriter):
    def __init__(self) -> None:
        self._emitted: list[tuple[str, dict[str, object]]] = []

    def emit(self, event: str, payload: dict[str, object]) -> None:
        self._emitted.append((event, payload))

    def close(self) -> None:
        return


class TestGStreamerHybridEngine(unittest.TestCase):
    def _cfg(self, source: str | int) -> AppConfig:
        return AppConfig(
            source=source,
            annotated_webrtc_enable=True,
            annotated_webrtc_path="ann-test",
            annotated_webrtc_rtsp_host="127.0.0.1",
            annotated_webrtc_rtsp_port=8554,
            pipeline_engine="gstreamer_hybrid",
            gstreamer_rtsp_latency_ms=120,
        )

    def test_rtsp_graph_contains_tee_analyzer_and_publish_branches(self) -> None:
        engine = GStreamerHybridEngine(self._cfg("rtsp://camera/live"))
        spec = engine.build_graph_spec(source="rtsp://camera/live", publish_path="ann-test")
        self.assertIn("rtspsrc", spec.pipeline)
        self.assertIn("latency=120", spec.pipeline)
        self.assertIn("tee name=t", spec.pipeline)
        self.assertIn("appsink name=analyzer_sink", spec.pipeline)
        self.assertIn("rtspclientsink", spec.pipeline)
        self.assertIn("profile=baseline", spec.pipeline)
        self.assertEqual(spec.command[0], "gst-launch-1.0")
        self.assertEqual(spec.command[1], "-e")

    def test_file_graph_contains_filesrc_decodebin(self) -> None:
        engine = GStreamerHybridEngine(self._cfg("videos/test.mp4"))
        spec = engine.build_graph_spec(source="videos/test.mp4", publish_path="ann-test")
        self.assertIn("filesrc location=\"videos/test.mp4\"", spec.pipeline)
        self.assertIn("decodebin", spec.pipeline)
        self.assertIn("tee name=t", spec.pipeline)

    def test_selector_falls_back_to_opencv_when_gstreamer_missing(self) -> None:
        writer = _NoopWriter()
        cfg = self._cfg("rtsp://camera/live")
        pipeline = UnifiedPublishPipeline(cfg, writer)
        selector = PipelineEngineSelector(cfg, writer, pipeline)
        with patch("src.main.GStreamerHybridEngine.is_available", return_value=False):
            selector.resolve()
        self.assertEqual(selector.selected_mode, "opencv")
        self.assertEqual(selector.compatibility_reason, "gstreamer_unavailable_fallback_opencv")

    def test_selector_uses_gstreamer_mode_when_available(self) -> None:
        writer = _NoopWriter()
        cfg = self._cfg("rtsp://camera/live")
        pipeline = UnifiedPublishPipeline(cfg, writer)
        selector = PipelineEngineSelector(cfg, writer, pipeline)
        with patch("src.main.GStreamerHybridEngine.is_available", return_value=True):
            selector.resolve()
        self.assertEqual(selector.selected_mode, "gstreamer_hybrid")
        self.assertEqual(selector.compatibility_reason, "gstreamer_authoritative_ingest")


if __name__ == "__main__":
    unittest.main()
