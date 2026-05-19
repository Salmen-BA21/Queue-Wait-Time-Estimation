from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import supervision as sv
try:
    import pytest
except ImportError:  # pragma: no cover - unittest-only environments
    pytest = None

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.main import _dashboard_metrics_payload
from src.queue_analyzer import QueueAnalyzer
from src.tracker import ObjectTracker
from src.tracking_validation import DetectionRecord, evaluate_manifest, summarize_records

if pytest is not None:
    pytestmark = pytest.mark.tracking


class TestQueueAnalyzerIdBehavior(unittest.TestCase):
    def test_stable_ids_no_false_arrival_departure(self) -> None:
        analyzer = QueueAnalyzer(arrival_window=30.0, service_window=60.0, id_absence_grace_sec=1.0)

        with patch("src.queue_analyzer.time.monotonic", side_effect=[0.0, 0.5, 1.0]):
            analyzer.update(np.array([True]), np.array([101]))
            analyzer.update(np.array([True]), np.array([101]))
            analyzer.update(np.array([True]), np.array([101]))

        self.assertEqual(len(analyzer._arrivals), 1)
        self.assertEqual(len(analyzer._departures), 0)

    def test_temporary_missing_id_within_grace_does_not_double_count(self) -> None:
        analyzer = QueueAnalyzer(arrival_window=30.0, service_window=60.0, id_absence_grace_sec=1.0)

        with patch("src.queue_analyzer.time.monotonic", side_effect=[0.0, 0.4, 0.8]):
            analyzer.update(np.array([True]), np.array([5]))
            analyzer.update(np.array([], dtype=bool), np.array([]))
            analyzer.update(np.array([True]), np.array([5]))

        self.assertEqual(len(analyzer._arrivals), 1)
        self.assertEqual(len(analyzer._departures), 0)


class TestObjectTrackerBasicBehavior(unittest.TestCase):
    def test_tracker_keeps_id_on_smooth_motion(self) -> None:
        tracker = ObjectTracker(frame_rate=30)

        frames = [
            np.array([[10.0, 10.0, 50.0, 90.0]], dtype=np.float32),
            np.array([[14.0, 10.0, 54.0, 90.0]], dtype=np.float32),
            np.array([[18.0, 10.0, 58.0, 90.0]], dtype=np.float32),
        ]

        ids = []
        for xyxy in frames:
            det = sv.Detections(
                xyxy=xyxy,
                confidence=np.array([0.95], dtype=np.float32),
                class_id=np.array([0], dtype=np.int32),
            )
            tracked = tracker.update(det)
            self.assertIsNotNone(tracked.tracker_id)
            ids.append(int(tracked.tracker_id[0]))

        self.assertTrue(all(tid == ids[0] for tid in ids), f"tracker IDs changed unexpectedly: {ids}")


class TestDashboardPayloadContract(unittest.TestCase):
    def test_payload_includes_tracker_id_column(self) -> None:
        detections = sv.Detections(
            xyxy=np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32),
            confidence=np.array([0.77], dtype=np.float32),
            class_id=np.array([0], dtype=np.int32),
            tracker_id=np.array([12], dtype=np.int32),
        )

        payload = _dashboard_metrics_payload(
            type("M", (), {"people_in_zone": 1, "arrival_rate": 0.0, "service_rate": 0.0, "estimated_wait_sec": 0.0})(),
            timestamp=1.23,
            detections=detections,
        )

        self.assertIn("detections", payload)
        self.assertEqual(len(payload["detections"][0]), 7)
        self.assertEqual(payload["detections"][0][6], 12.0)


class TestTrackingSummaryAndManifest(unittest.TestCase):
    def test_intentional_id_switch_detected(self) -> None:
        records = [
            DetectionRecord(1, 0.03, "clip.mp4", 10, 10, 50, 80, 0.9, 0, 1, True),
            DetectionRecord(2, 0.06, "clip.mp4", 11, 10, 51, 80, 0.9, 0, 1, True),
            DetectionRecord(3, 0.09, "clip.mp4", 12, 10, 52, 80, 0.9, 0, 99, True),
        ]
        metrics = summarize_records(records, iou_match_threshold=0.3)
        self.assertGreaterEqual(metrics.id_switch_count, 1)

    def test_manifest_evaluation_returns_failure_when_clip_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = root / "manifest.json"
            output_dir = root / "out"

            manifest.write_text(
                json.dumps(
                    {
                        "defaults": {"model_path": "yolo26n.pt", "confidence": 0.3, "detector_imgsz": 512, "process_every_n_frames": 1, "track_buffer": 60},
                        "clips": [{"id": "missing", "path": "missing.mp4", "quick": True, "thresholds": {"max_id_switch_rate": 1.0, "max_fragmentation_rate": 1.0, "max_occupancy_drift": 10}}],
                    }
                ),
                encoding="utf-8",
            )

            summary = evaluate_manifest(manifest, mode="quick", output_dir=output_dir, compare_previous=False)
            self.assertEqual(summary["status"], "failed")
            self.assertTrue(any("missing clip file" in msg for msg in summary["failures"]))


if __name__ == "__main__":
    unittest.main()
