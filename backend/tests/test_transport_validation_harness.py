from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.scripts import run_transport_validation


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestTransportValidationHarness(unittest.TestCase):
    def test_harness_produces_deterministic_json_and_pass_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            events_file = tmpdir / "sample.events.jsonl"
            report_file = tmpdir / "report.json"

            rows = []
            for idx in range(20):
                rows.append(
                    {
                        "event": "metrics_update",
                        "payload": {
                            "metrics": {
                                "pts_ms": 1000.0 + idx,
                                "server_emitted_at_ms": 1000.0 + idx + 50.0,
                            },
                            "performance": {
                                "dashboard_emit_fps": 15.0,
                                "dashboard_jpeg_encode_ms": 3.0,
                                "queue_age_ms": 10.0,
                                "end_to_end_frame_age_ms": 40.0,
                            },
                        },
                    }
                )
            rows.append(
                {
                    "event": "transport_status",
                    "payload": {
                        "published_webrtc_ready": True,
                        "published_webrtc_path": "ann-test",
                        "reason": None,
                        "compatibility_reason": "codec_fallback_dimension_alignment",
                        "pipeline_mode": "opencv",
                        "performance": {
                            "dashboard_emit_fps": 15.0,
                            "dashboard_jpeg_encode_ms": 3.0,
                            "queue_age_ms": 10.0,
                            "end_to_end_frame_age_ms": 40.0,
                        },
                    },
                }
            )
            rows.append(
                {
                    "event": "transport_status",
                    "payload": {
                        "published_webrtc_ready": False,
                        "published_webrtc_path": "ann-test",
                        "reason": "publisher_not_ready",
                        "compatibility_reason": "gstreamer_launch_failed_fallback_ffmpeg",
                        "pipeline_mode": "opencv",
                    },
                }
            )
            events_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            fake_ok = _FakeCompletedProcess(returncode=0, stdout="ok", stderr="")
            with patch("backend.scripts.run_transport_validation.subprocess.run", return_value=fake_ok):
                with patch(
                    "sys.argv",
                    [
                        "run_transport_validation",
                        "--scenario",
                        "ip_cam_like",
                        "--venv-python",
                        str(Path("C:/fake/python.exe")),
                        "--events-file",
                        str(events_file),
                        "--events-dir",
                        str(tmpdir / "none"),
                        "--output-json",
                        str(report_file),
                    ],
                ):
                    run_transport_validation.main()

            self.assertTrue(report_file.exists())
            payload = json.loads(report_file.read_text(encoding="utf-8"))

            self.assertEqual(payload["scenario"], "ip_cam_like")
            self.assertTrue(payload["evaluation"]["checks"]["required_tests_passed"])
            self.assertTrue(payload["evaluation"]["checks"]["skew_p95_within_threshold"])
            self.assertTrue(payload["evaluation"]["checks"]["no_drift_check"])
            self.assertTrue(payload["evaluation"]["overall_pass"])
            self.assertEqual(payload["event_summary"]["transport_metrics"]["metadata_video_skew_ms_p95"], 50.0)
            self.assertTrue(payload["event_summary"]["transport_metrics"]["codec_fallback_active"])
            self.assertEqual(
                payload["event_summary"]["transport_metrics"]["codec_compatibility_reason_counts"][
                    "codec_fallback_dimension_alignment"
                ],
                1,
            )
            self.assertEqual(
                payload["event_summary"]["transport_metrics"]["codec_compatibility_reason_counts"][
                    "gstreamer_launch_failed_fallback_ffmpeg"
                ],
                1,
            )
            self.assertEqual(
                payload["event_summary"]["transport_metrics"]["pipeline_mode_counts"]["opencv"],
                2,
            )
            self.assertEqual(len(payload["tests"]), 3)


if __name__ == "__main__":
    unittest.main()
