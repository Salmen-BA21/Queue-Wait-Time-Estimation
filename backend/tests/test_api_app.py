"""Backend API tests for the first FastAPI integration slice."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import app
from src import database
from src.api.models import AlertModel, BatchFeedDraft, BatchFeedLaunchRequest, QueueMetricsModel, ZonePolygon
from src.api.runtime import RECOVERED_FEED_MESSAGE, FeedRegistry, FeedStartError, FeedWorkerHandle, WebSocketHub


class FakeWorkerRunner:
    """In-memory runner so feed control can be tested without launching OpenCV workers."""

    def __init__(self, *, fail_sources: set[str] | None = None) -> None:
        self.started: list[str] = []
        self.started_config: dict[str, dict[str, object | None]] = {}
        self.stopped: list[str] = []
        self._running: dict[str, bool] = {}
        self.handles: dict[str, FeedWorkerHandle] = {}
        self.fail_sources = fail_sources or set()

    def start(self, record) -> FeedWorkerHandle:  # noqa: ANN001
        if record.source in self.fail_sources:
            raise FeedStartError(f"Worker start rejected for source {record.source}")

        event_file = tempfile.NamedTemporaryFile(mode="a", suffix=".events.jsonl", delete=False)
        event_file.close()
        handle = FeedWorkerHandle(
            feed_id=record.feed_id,
            command=["fake-worker", record.source],
            event_path=Path(event_file.name),
        )
        self._running[record.feed_id] = True
        self.started.append(record.feed_id)
        self.handles[record.feed_id] = handle
        self.started_config[record.feed_id] = {
            "source": record.source,
            "rtsp_username": record.rtsp_username,
            "rtsp_password": record.rtsp_password,
            "rtsp_transport": record.rtsp_transport,
            "log_level": record.log_level,
            "webhook_enabled": record.webhook_enabled,
        }
        return handle

    def stop(self, handle: FeedWorkerHandle) -> None:
        self._running[handle.feed_id] = False
        self.stopped.append(handle.feed_id)

    def poll(self, handle: FeedWorkerHandle) -> int | None:
        if self._running.get(handle.feed_id, False):
            return None
        return 0

    def close(self, handle: FeedWorkerHandle) -> None:
        return None

    def exit_details(self, handle: FeedWorkerHandle, exit_code: int) -> str | None:
        return None

    def write_event(self, feed_id: str, event: str, payload: dict[str, object]) -> None:
        handle = self.handles[feed_id]
        if handle.event_path is None:
            raise AssertionError("Fake runner handle is missing an event path.")

        with handle.event_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": event, "payload": payload}) + "\n")


class CapturingWebSocket:
    """Minimal websocket stub for direct broadcast contract checks."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)


class TestQueueVisionApi(unittest.TestCase):
    """Validate feed CRUD, zone validation, and websocket snapshots."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls._original_db_path = database.DB_PATH
        database.DB_PATH = Path(cls._temp_dir.name) / "queue_metrics_test.db"
        database.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        database.DB_PATH = cls._original_db_path
        cls._temp_dir.cleanup()

    def setUp(self) -> None:
        database.init_db()
        conn = database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM video_sessions")
            cursor.execute("DELETE FROM feed_configs")
            cursor.execute("DELETE FROM caisses")
            cursor.execute("DELETE FROM establishments")
            conn.commit()
        finally:
            conn.close()

        self.runner = FakeWorkerRunner()
        broadcaster = WebSocketHub()
        app.state.broadcaster = broadcaster
        app.state.registry = FeedRegistry(broadcaster=broadcaster, runner=self.runner)

    def dispatch_worker_event(self, feed_id: str, event: str, payload: dict[str, object]) -> None:
        asyncio.run(app.state.registry._dispatch_worker_event(feed_id, {"event": event, "payload": payload}))

    def test_create_and_list_establishments(self) -> None:
        create_response = self.client.post(
            "/api/establishments",
            json={"name": "Store Alpha"},
        )
        self.assertEqual(create_response.status_code, 201)
        payload = create_response.json()["data"]
        self.assertEqual(payload["name"], "Store Alpha")

        list_response = self.client.get("/api/establishments")
        self.assertEqual(list_response.status_code, 200)
        establishments = list_response.json()["data"]
        self.assertEqual(len(establishments), 1)
        self.assertEqual(establishments[0]["name"], "Store Alpha")

    def test_duplicate_establishment_returns_conflict(self) -> None:
        first_response = self.client.post(
            "/api/establishments",
            json={"name": "Store Beta"},
        )
        self.assertEqual(first_response.status_code, 201)

        duplicate_response = self.client.post(
            "/api/establishments",
            json={"name": "Store Beta"},
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.json()["detail"], "Establishment already exists.")

    def test_create_and_list_caisses_for_establishment(self) -> None:
        establishment = self.client.post(
            "/api/establishments",
            json={"name": "Store Gamma"},
        ).json()["data"]

        create_response = self.client.post(
            f"/api/establishments/{establishment['id']}/caisses",
            json={
                "name": "Register 1",
                "zone": {
                    "points": [
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.8, "y": 0.2},
                        {"x": 0.8, "y": 0.9},
                    ]
                },
            },
        )
        self.assertEqual(create_response.status_code, 201)
        payload = create_response.json()["data"]
        self.assertEqual(payload["name"], "Register 1")
        self.assertEqual(payload["establishment_id"], establishment["id"])
        self.assertEqual(len(payload["zone"]["points"]), 3)

        list_response = self.client.get(f"/api/establishments/{establishment['id']}/caisses")
        self.assertEqual(list_response.status_code, 200)
        caisses = list_response.json()["data"]
        self.assertEqual(len(caisses), 1)
        self.assertEqual(caisses[0]["name"], "Register 1")

    def test_create_caisse_requires_existing_establishment(self) -> None:
        response = self.client.post(
            "/api/establishments/999/caisses",
            json={"name": "Register Missing"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Establishment not found.")

    def test_feed_creation_can_reuse_saved_caisse_zone(self) -> None:
        establishment = self.client.post(
            "/api/establishments",
            json={"name": "Store Delta"},
        ).json()["data"]
        caisse = self.client.post(
            f"/api/establishments/{establishment['id']}/caisses",
            json={
                "name": "Register 2",
                "zone": {
                    "points": [
                        {"x": 0.15, "y": 0.25},
                        {"x": 0.65, "y": 0.25},
                        {"x": 0.65, "y": 0.75},
                    ]
                },
            },
        ).json()["data"]

        feed_response = self.client.post(
            "/api/feeds",
            json={
                "name": "Checkout Metadata",
                "source": "rtsp://camera-metadata",
                "establishment_id": establishment["id"],
                "caisse_id": caisse["id"],
            },
        )
        self.assertEqual(feed_response.status_code, 201)
        feed = feed_response.json()["data"]
        self.assertEqual(feed["establishment_id"], establishment["id"])
        self.assertEqual(feed["caisse_id"], caisse["id"])
        self.assertIsNotNone(feed["zone"])
        self.assertEqual(len(feed["zone"]["points"]), 3)

    def test_feed_creation_hides_embedded_rtsp_credentials(self) -> None:
        response = self.client.post(
            "/api/feeds",
            json={
                "name": "Secure Camera",
                "source": "rtsp://admin:secret@192.168.1.90/live/main",
            },
        )

        self.assertEqual(response.status_code, 201)
        feed = response.json()["data"]
        self.assertEqual(feed["source"], "rtsp://192.168.1.90/live/main")

    def test_batch_launch_request_supports_shared_runtime_settings(self) -> None:
        request = BatchFeedLaunchRequest.model_validate(
            {
                "launch_mode": "create_and_start",
                "runtime": {
                    "webhook_enabled": False,
                    "log_level": "DEBUG",
                },
                "feeds": [
                    {
                        "client_id": "draft-1",
                        "name": "Front Door Camera",
                        "source": "rtsp://camera-front-door",
                        "model_size": "m",
                        "zone": {
                            "points": [
                                {"x": 0.1, "y": 0.2},
                                {"x": 0.8, "y": 0.2},
                                {"x": 0.8, "y": 0.9},
                            ]
                        },
                    }
                ],
            }
        )

        self.assertEqual(request.launch_mode, "create_and_start")
        self.assertFalse(request.runtime.webhook_enabled)
        self.assertEqual(request.runtime.log_level, "DEBUG")
        self.assertEqual(len(request.feeds), 1)
        feed_draft = cast(BatchFeedDraft, request.feeds[0])
        self.assertEqual(feed_draft.client_id, "draft-1")
        zone = cast(ZonePolygon, feed_draft.zone)
        self.assertEqual(len(zone.points), 3)

    def test_batch_launch_request_requires_at_least_one_feed(self) -> None:
        with self.assertRaises(ValidationError):
            BatchFeedLaunchRequest.model_validate(
                {
                    "launch_mode": "save_only",
                    "feeds": [],
                }
            )

    def test_batch_launch_save_only_creates_multiple_feeds(self) -> None:
        response = self.client.post(
            "/api/feeds/batch-launch",
            json={
                "launch_mode": "save_only",
                "runtime": {
                    "webhook_enabled": True,
                    "log_level": "INFO",
                },
                "feeds": [
                    {
                        "client_id": "draft-file",
                        "name": "Uploaded Queue",
                        "source": "C:/videos/queue.mp4",
                        "model_size": "n",
                        "zone": {
                            "points": [
                                {"x": 0.1, "y": 0.2},
                                {"x": 0.7, "y": 0.2},
                                {"x": 0.7, "y": 0.8},
                            ]
                        },
                    },
                    {
                        "client_id": "draft-rtsp",
                        "name": "Back Register",
                        "source": "rtsp://192.168.1.120/live/main",
                        "model_size": "m",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["summary"], {"total": 2, "created": 2, "started": 0, "failed": 0})
        self.assertEqual([item["status"] for item in payload["results"]], ["created", "created"])
        self.assertEqual(len(self.runner.started), 0)
        self.assertEqual(len(payload["results"][0]["feed"]["zone"]["points"]), 3)

    def test_batch_launch_create_and_start_uses_shared_runtime_settings(self) -> None:
        response = self.client.post(
            "/api/feeds/batch-launch",
            json={
                "launch_mode": "create_and_start",
                "runtime": {
                    "webhook_enabled": False,
                    "log_level": "ERROR",
                },
                "feeds": [
                    {
                        "client_id": "draft-1",
                        "name": "Register One",
                        "source": "rtsp://192.168.1.121/live/main",
                        "model_size": "s",
                    },
                    {
                        "client_id": "draft-2",
                        "name": "Register Two",
                        "source": "rtsp://192.168.1.122/live/main",
                        "model_size": "l",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["summary"], {"total": 2, "created": 2, "started": 2, "failed": 0})
        self.assertEqual([item["status"] for item in payload["results"]], ["started", "started"])
        self.assertEqual(len(self.runner.started), 2)
        for feed_id in self.runner.started:
            self.assertEqual(self.runner.started_config[feed_id]["log_level"], "ERROR")
            self.assertFalse(self.runner.started_config[feed_id]["webhook_enabled"])

    def test_batch_launch_returns_partial_failure_without_rollback(self) -> None:
        self.runner = FakeWorkerRunner(fail_sources={"rtsp://192.168.1.124/live/main"})
        broadcaster = WebSocketHub()
        app.state.broadcaster = broadcaster
        app.state.registry = FeedRegistry(broadcaster=broadcaster, runner=self.runner)

        response = self.client.post(
            "/api/feeds/batch-launch",
            json={
                "launch_mode": "create_and_start",
                "feeds": [
                    {
                        "client_id": "ok-feed",
                        "name": "Healthy Feed",
                        "source": "rtsp://192.168.1.123/live/main",
                    },
                    {
                        "client_id": "bad-feed",
                        "name": "Broken Feed",
                        "source": "rtsp://192.168.1.124/live/main",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["summary"], {"total": 2, "created": 2, "started": 1, "failed": 1})

        results = {item["client_id"]: item for item in payload["results"]}
        self.assertEqual(results["ok-feed"]["status"], "started")
        self.assertEqual(results["bad-feed"]["status"], "failed")
        self.assertIn("Worker start rejected", results["bad-feed"]["error"])
        self.assertEqual(results["bad-feed"]["feed"]["status"], "error")

        list_response = self.client.get("/api/feeds")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 2)

    def test_start_feed_preserves_rtsp_runtime_options(self) -> None:
        response = self.client.post(
            "/api/feeds",
            json={
                "name": "Secure Runtime Camera",
                "source": "rtsp://192.168.1.91/live/main",
                "rtsp_username": "operator",
                "rtsp_password": "topsecret",
                "rtsp_transport": "udp",
            },
        )
        self.assertEqual(response.status_code, 201)
        feed = response.json()["data"]

        start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)

        started = self.runner.started_config[feed["feed_id"]]
        self.assertEqual(started["source"], "rtsp://192.168.1.91/live/main")
        self.assertEqual(started["rtsp_username"], "operator")
        self.assertEqual(started["rtsp_password"], "topsecret")
        self.assertEqual(started["rtsp_transport"], "udp")

    def test_feed_snapshot_uses_saved_rtsp_credentials(self) -> None:
        response = self.client.post(
            "/api/feeds",
            json={
                "name": "Zone Edit Camera",
                "source": "rtsp://192.168.1.92/live/main",
                "rtsp_username": "operator",
                "rtsp_password": "hidden",
                "rtsp_transport": "udp",
            },
        )
        self.assertEqual(response.status_code, 201)
        feed = response.json()["data"]

        with patch(
            "src.api.runtime._capture_rtsp_source_snapshot",
            return_value=(
                True,
                {
                    "width": 960,
                    "height": 540,
                    "resolution": "960x540",
                    "mime_type": "image/jpeg",
                    "image_base64": "ZmFrZS1mZWVkLXNuYXBzaG90",
                },
            ),
        ) as mocked_snapshot:
            snapshot_response = self.client.get(f"/api/feeds/{feed['feed_id']}/snapshot")

        self.assertEqual(snapshot_response.status_code, 200)
        payload = snapshot_response.json()["data"]
        self.assertTrue(payload["captured"])
        self.assertEqual(payload["feed_id"], feed["feed_id"])
        self.assertEqual(payload["source"], "rtsp://192.168.1.92/live/main")
        self.assertEqual(payload["image_data_url"], "data:image/jpeg;base64,ZmFrZS1mZWVkLXNuYXBzaG90")
        mocked_snapshot.assert_called_once_with(
            source="rtsp://192.168.1.92/live/main",
            username="operator",
            password="hidden",
            transport="udp",
        )

    def test_feed_snapshot_returns_not_found_for_missing_feed(self) -> None:
        response = self.client.get("/api/feeds/missing-feed/snapshot")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Feed not found.")

    def test_feed_config_persists_across_registry_restart(self) -> None:
        created_response = self.client.post(
            "/api/feeds",
            json={
                "name": "Persistent Feed",
                "source": "rtsp://192.168.1.93/live/main",
                "model_size": "l",
                "rtsp_username": "viewer",
                "rtsp_password": "secret",
                "rtsp_transport": "tcp",
            },
        )
        self.assertEqual(created_response.status_code, 201)
        feed = created_response.json()["data"]

        zone_response = self.client.post(
            f"/api/feeds/{feed['feed_id']}/zone",
            json={
                "zone": {
                    "points": [
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.8, "y": 0.25},
                        {"x": 0.78, "y": 0.88},
                    ]
                }
            },
        )
        self.assertEqual(zone_response.status_code, 200)

        replacement_broadcaster = WebSocketHub()
        app.state.broadcaster = replacement_broadcaster
        app.state.registry = FeedRegistry(broadcaster=replacement_broadcaster, runner=FakeWorkerRunner())

        list_response = self.client.get("/api/feeds")
        self.assertEqual(list_response.status_code, 200)
        feeds = list_response.json()["data"]
        self.assertEqual(len(feeds), 1)
        restored = feeds[0]
        self.assertEqual(restored["feed_id"], feed["feed_id"])
        self.assertEqual(restored["name"], "Persistent Feed")
        self.assertEqual(restored["model_size"], "l")
        self.assertEqual(restored["status"], "created")
        self.assertEqual(restored["source"], "rtsp://192.168.1.93/live/main")
        self.assertEqual(len(restored["zone"]["points"]), 3)

    def test_registry_restart_recovers_running_feed_to_stopped(self) -> None:
        created_response = self.client.post(
            "/api/feeds",
            json={
                "name": "Recovered Feed",
                "source": "rtsp://192.168.1.94/live/main",
            },
        )
        self.assertEqual(created_response.status_code, 201)
        feed = created_response.json()["data"]

        start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.json()["data"]["status"], "running")

        replacement_runner = FakeWorkerRunner()
        replacement_broadcaster = WebSocketHub()
        app.state.broadcaster = replacement_broadcaster
        app.state.registry = FeedRegistry(broadcaster=replacement_broadcaster, runner=replacement_runner)

        restored_response = self.client.get(f"/api/feeds/{feed['feed_id']}/status")
        self.assertEqual(restored_response.status_code, 200)
        restored = restored_response.json()["data"]
        self.assertEqual(restored["status"], "stopped")
        self.assertIsNone(restored["last_error"])
        self.assertEqual(restored["last_warning"], RECOVERED_FEED_MESSAGE)
        self.assertEqual(restored["last_warning_code"], "recovery_required")

        conn = database.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM video_sessions WHERE end_time IS NULL")
            open_sessions = cursor.fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(open_sessions, 0)

        restarted_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(restarted_response.status_code, 200)
        restarted = restarted_response.json()["data"]
        self.assertEqual(restarted["status"], "running")
        self.assertIsNone(restarted["last_error"])
        self.assertIsNone(restarted["last_warning"])
        self.assertIsNone(restarted["last_warning_code"])

    def test_rtsp_connection_test_success(self) -> None:
        with patch(
            "src.api.app.run_rtsp_connection_test",
            return_value=(
                True,
                {
                    "width": 1920,
                    "height": 1080,
                    "fps": 25.0,
                    "resolution": "1920x1080",
                    "transport": "udp",
                },
            ),
        ) as mocked_test:
            response = self.client.post(
                "/api/sources/rtsp/test",
                json={
                    "url": "rtsp://192.168.1.10/live/main",
                    "username": "admin",
                    "password": "secret",
                    "transport": "udp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["resolution"], "1920x1080")
        self.assertEqual(payload["fps"], 25.0)
        self.assertEqual(payload["transport"], "udp")
        self.assertIsNone(payload["error"])
        mocked_test.assert_called_once_with(
            url="rtsp://192.168.1.10/live/main",
            username="admin",
            password="secret",
            transport="udp",
        )

    def test_rtsp_connection_test_failure_returns_structured_result(self) -> None:
        with patch(
            "src.api.app.run_rtsp_connection_test",
            return_value=(False, {"error": "Could not open stream", "transport": "tcp"}),
        ):
            response = self.client.post(
                "/api/sources/rtsp/test",
                json={
                    "url": "rtsp://192.168.1.20/live/main",
                    "transport": "tcp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertFalse(payload["connected"])
        self.assertEqual(payload["transport"], "tcp")
        self.assertEqual(payload["error"], "Could not open stream")
        self.assertIsNone(payload["resolution"])

    def test_rtsp_connection_test_rejects_invalid_url(self) -> None:
        response = self.client.post(
            "/api/sources/rtsp/test",
            json={"url": "http://example.com/stream"},
        )

        self.assertEqual(response.status_code, 422)

    def test_rtsp_snapshot_capture_success(self) -> None:
        with patch(
            "src.api.app.run_rtsp_snapshot_capture",
            return_value=(
                True,
                {
                    "width": 1280,
                    "height": 720,
                    "resolution": "1280x720",
                    "transport": "tcp",
                    "mime_type": "image/jpeg",
                    "image_base64": "ZmFrZS1zbmFwc2hvdA==",
                },
            ),
        ) as mocked_snapshot:
            response = self.client.post(
                "/api/sources/rtsp/snapshot",
                json={
                    "url": "rtsp://192.168.1.30/live/main",
                    "username": "admin",
                    "password": "secret",
                    "transport": "tcp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertTrue(payload["captured"])
        self.assertEqual(payload["transport"], "tcp")
        self.assertEqual(payload["resolution"], "1280x720")
        self.assertEqual(payload["image_data_url"], "data:image/jpeg;base64,ZmFrZS1zbmFwc2hvdA==")
        mocked_snapshot.assert_called_once_with(
            url="rtsp://192.168.1.30/live/main",
            username="admin",
            password="secret",
            transport="tcp",
        )

    def test_rtsp_snapshot_capture_failure_returns_structured_result(self) -> None:
        with patch(
            "src.api.app.run_rtsp_snapshot_capture",
            return_value=(False, {"error": "Could not open stream", "transport": "udp"}),
        ):
            response = self.client.post(
                "/api/sources/rtsp/snapshot",
                json={
                    "url": "rtsp://192.168.1.31/live/main",
                    "transport": "udp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertFalse(payload["captured"])
        self.assertEqual(payload["transport"], "udp")
        self.assertEqual(payload["error"], "Could not open stream")
        self.assertIsNone(payload["image_data_url"])

    def test_onvif_discovery_returns_devices(self) -> None:
        with patch(
            "src.api.app.run_onvif_discovery",
            return_value=[
                {
                    "ip": "192.168.1.50",
                    "name": "Front Door Camera",
                    "manufacturer": "Hikvision",
                    "model": "DS-2CD2043G0-I",
                    "serial": "SN123456",
                    "hardware": "HW-1",
                    "location": "Entrance",
                    "services": {
                        "device": "http://192.168.1.50/onvif/device_service",
                        "media": "http://192.168.1.50/onvif/media",
                    },
                    "xaddrs": "http://192.168.1.50/onvif/device_service",
                }
            ],
        ) as mocked_discovery:
            response = self.client.post(
                "/api/sources/onvif/discover",
                json={"timeout_seconds": 3.5},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["ip"], "192.168.1.50")
        self.assertEqual(payload[0]["name"], "Front Door Camera")
        self.assertIn("media", payload[0]["services"])
        mocked_discovery.assert_called_once_with(timeout_seconds=3.5)

    def test_onvif_discovery_returns_empty_list_when_no_devices_found(self) -> None:
        with patch(
            "src.api.app.run_onvif_discovery",
            return_value=[],
        ):
            response = self.client.post(
                "/api/sources/onvif/discover",
                json={"timeout_seconds": 2.0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertEqual(response.json()["message"], "No ONVIF devices found.")

    def test_onvif_discovery_rejects_invalid_timeout(self) -> None:
        response = self.client.post(
            "/api/sources/onvif/discover",
            json={"timeout_seconds": 0},
        )

        self.assertEqual(response.status_code, 422)

    def test_onvif_stream_resolution_returns_sanitized_urls(self) -> None:
        device = {
            "ip": "192.168.1.60",
            "name": "Checkout Camera",
            "manufacturer": "Axis",
            "model": "P3245",
            "serial": "AXIS-123",
            "hardware": "HW-2",
            "location": "Checkout",
            "services": {
                "media": "http://192.168.1.60/onvif/media"
            },
            "xaddrs": "http://192.168.1.60/onvif/device_service",
        }

        with patch(
            "src.api.app.run_onvif_stream_resolution",
            return_value=[
                "rtsp://admin:secret@192.168.1.60:554/stream1",
                "rtsp://admin:secret@192.168.1.60:554/stream1",
                "rtsp://192.168.1.60:554/stream2",
            ],
        ) as mocked_resolution:
            response = self.client.post(
                "/api/sources/onvif/streams",
                json={
                    "device": device,
                    "username": "admin",
                    "password": "secret",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload, [
            {"url": "rtsp://192.168.1.60:554/stream1"},
            {"url": "rtsp://192.168.1.60:554/stream2"},
        ])
        mocked_resolution.assert_called_once_with(
            device=device,
            username="admin",
            password="secret",
        )

    def test_onvif_stream_resolution_returns_empty_list(self) -> None:
        device = {
            "ip": "192.168.1.61",
            "name": "Back Door Camera",
            "manufacturer": "Dahua",
            "model": "IPC-HDW",
            "serial": "DH-456",
            "hardware": "HW-3",
            "location": "Back Door",
            "services": {
                "media": "http://192.168.1.61/onvif/media"
            },
            "xaddrs": "http://192.168.1.61/onvif/device_service",
        }

        with patch(
            "src.api.app.run_onvif_stream_resolution",
            return_value=[],
        ):
            response = self.client.post(
                "/api/sources/onvif/streams",
                json={"device": device},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertEqual(response.json()["message"], "No RTSP streams found for this device.")

    def test_onvif_stream_resolution_requires_valid_device_payload(self) -> None:
        response = self.client.post(
            "/api/sources/onvif/streams",
            json={
                "device": {
                    "ip": "192.168.1.62",
                    "name": "Incomplete Device"
                }
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_onvif_camera_test_success(self) -> None:
        device = {
            "ip": "192.168.1.70",
            "name": "Lane Camera",
            "manufacturer": "Axis",
            "model": "P3245",
            "serial": "AXIS-777",
            "hardware": "HW-4",
            "location": "Lane 1",
            "services": {
                "media": "http://192.168.1.70/onvif/media"
            },
            "xaddrs": "http://192.168.1.70/onvif/device_service",
        }

        with patch(
            "src.api.app.run_onvif_stream_resolution",
            return_value=[
                "rtsp://admin:secret@192.168.1.70:554/main",
                "rtsp://192.168.1.70:554/sub",
            ],
        ) as mocked_resolution, patch(
            "src.api.app.run_rtsp_connection_test",
            return_value=(
                True,
                {
                    "width": 1280,
                    "height": 720,
                    "fps": 20.0,
                    "resolution": "1280x720",
                    "transport": "tcp",
                },
            ),
        ) as mocked_test:
            response = self.client.post(
                "/api/sources/onvif/test",
                json={
                    "device": device,
                    "username": "admin",
                    "password": "secret",
                    "transport": "tcp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertTrue(payload["connected"])
        self.assertEqual(payload["stream_count"], 2)
        self.assertEqual(payload["tested_stream"], {"url": "rtsp://192.168.1.70:554/main"})
        self.assertEqual(payload["streams"], [
            {"url": "rtsp://192.168.1.70:554/main"},
            {"url": "rtsp://192.168.1.70:554/sub"},
        ])
        self.assertEqual(payload["resolution"], "1280x720")
        self.assertEqual(payload["fps"], 20.0)
        mocked_resolution.assert_called_once_with(
            device=device,
            username="admin",
            password="secret",
        )
        mocked_test.assert_called_once_with(
            url="rtsp://admin:secret@192.168.1.70:554/main",
            username="admin",
            password="secret",
            transport="tcp",
        )

    def test_onvif_camera_test_returns_no_streams_failure(self) -> None:
        device = {
            "ip": "192.168.1.71",
            "name": "Lane Camera 2",
            "manufacturer": "Dahua",
            "model": "IPC-Lane",
            "serial": "DH-888",
            "hardware": "HW-5",
            "location": "Lane 2",
            "services": {
                "media": "http://192.168.1.71/onvif/media"
            },
            "xaddrs": "http://192.168.1.71/onvif/device_service",
        }

        with patch(
            "src.api.app.run_onvif_stream_resolution",
            return_value=[],
        ) as mocked_resolution, patch(
            "src.api.app.run_rtsp_connection_test",
        ) as mocked_test:
            response = self.client.post(
                "/api/sources/onvif/test",
                json={"device": device},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertFalse(payload["connected"])
        self.assertEqual(payload["stream_count"], 0)
        self.assertIsNone(payload["tested_stream"])
        self.assertEqual(payload["streams"], [])
        self.assertEqual(payload["error"], "No RTSP streams found")
        mocked_resolution.assert_called_once_with(
            device=device,
            username=None,
            password=None,
        )
        mocked_test.assert_not_called()

    def test_onvif_camera_test_returns_rtsp_failure_details(self) -> None:
        device = {
            "ip": "192.168.1.72",
            "name": "Lane Camera 3",
            "manufacturer": "Hikvision",
            "model": "DS-Test",
            "serial": "HK-999",
            "hardware": "HW-6",
            "location": "Lane 3",
            "services": {
                "media": "http://192.168.1.72/onvif/media"
            },
            "xaddrs": "http://192.168.1.72/onvif/device_service",
        }

        with patch(
            "src.api.app.run_onvif_stream_resolution",
            return_value=["rtsp://192.168.1.72:554/main"],
        ), patch(
            "src.api.app.run_rtsp_connection_test",
            return_value=(False, {"error": "Could not open stream", "transport": "udp"}),
        ):
            response = self.client.post(
                "/api/sources/onvif/test",
                json={
                    "device": device,
                    "transport": "udp",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertFalse(payload["connected"])
        self.assertEqual(payload["stream_count"], 1)
        self.assertEqual(payload["tested_stream"], {"url": "rtsp://192.168.1.72:554/main"})
        self.assertEqual(payload["error"], "Could not open stream")
        self.assertEqual(payload["transport"], "udp")

    def test_create_feed_and_fetch_status(self) -> None:
        response = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 1", "source": "rtsp://192.168.1.10/stream", "model_size": "m"},
        )
        self.assertEqual(response.status_code, 201)

        payload = response.json()["data"]
        self.assertEqual(payload["name"], "Checkout 1")
        self.assertEqual(payload["model_size"], "m")
        self.assertEqual(payload["status"], "created")

        status_response = self.client.get(f"/api/feeds/{payload['feed_id']}/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["data"]["source"], "rtsp://192.168.1.10/stream")

    def test_upload_video_returns_backend_readable_path(self) -> None:
        response = self.client.post(
            "/api/uploads/video",
            files={"file": ("queue-demo.mp4", b"fake-video-bytes", "video/mp4")},
        )
        self.assertEqual(response.status_code, 201)

        payload = response.json()["data"]
        uploaded_path = Path(payload["file_path"])
        self.assertEqual(payload["file_name"], "queue-demo.mp4")
        self.assertTrue(uploaded_path.exists())
        self.assertEqual(uploaded_path.suffix.lower(), ".mp4")
        self.assertEqual(payload["preview_path"], f"/api/uploads/files/{uploaded_path.name}")

        preview_response = self.client.get(payload["preview_path"])
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.content, b"fake-video-bytes")

        uploaded_path.unlink(missing_ok=True)

    def test_uploaded_feed_exposes_preview_path(self) -> None:
        uploaded_path = Path("backend/data/uploads/demo-preview.mp4")
        uploaded_path.parent.mkdir(parents=True, exist_ok=True)
        uploaded_path.write_bytes(b"demo-preview")

        try:
            response = self.client.post(
                "/api/feeds",
                json={"name": "Uploaded Preview", "source": str(uploaded_path.resolve())},
            )
            self.assertEqual(response.status_code, 201)

            payload = response.json()["data"]
            self.assertEqual(payload["preview_path"], f"/api/uploads/files/{uploaded_path.name}")
        finally:
            uploaded_path.unlink(missing_ok=True)

    def test_zone_requires_at_least_three_points(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Entrance A", "source": "0"},
        ).json()["data"]

        response = self.client.post(
            f"/api/feeds/{feed['feed_id']}/zone",
            json={
                "zone": {
                    "points": [
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.8, "y": 0.2},
                    ]
                }
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_start_and_stop_feed_update_status(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 3", "source": "rtsp://camera-3"},
        ).json()["data"]

        start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.json()["data"]["status"], "running")
        self.assertIn(feed["feed_id"], self.runner.started)

        status_response = self.client.get(f"/api/feeds/{feed['feed_id']}/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["data"]["status"], "running")

        stop_response = self.client.post(f"/api/feeds/{feed['feed_id']}/stop")
        self.assertEqual(stop_response.status_code, 200)
        self.assertEqual(stop_response.json()["data"]["status"], "stopped")
        self.assertIn(feed["feed_id"], self.runner.stopped)

    def test_start_feed_rejects_duplicate_start(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 4", "source": "rtsp://camera-4"},
        ).json()["data"]

        first_start = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(first_start.status_code, 200)

        duplicate_start = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(duplicate_start.status_code, 409)
        self.assertEqual(duplicate_start.json()["detail"], "Feed is already running.")

        self.client.post(f"/api/feeds/{feed['feed_id']}/stop")

    def test_stop_feed_requires_running_worker(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 5", "source": "rtsp://camera-5"},
        ).json()["data"]

        response = self.client.post(f"/api/feeds/{feed['feed_id']}/stop")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Feed is not running.")

    def test_restart_feed_relaunches_running_worker(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout Restart", "source": "rtsp://camera-restart"},
        ).json()["data"]

        first_start = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(first_start.status_code, 200)

        restart_response = self.client.post(f"/api/feeds/{feed['feed_id']}/restart")
        self.assertEqual(restart_response.status_code, 200)
        self.assertEqual(restart_response.json()["data"]["status"], "running")
        self.assertEqual(self.runner.started.count(feed["feed_id"]), 2)
        self.assertEqual(self.runner.stopped.count(feed["feed_id"]), 1)

    def test_restart_feed_starts_stopped_feed(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout Restart 2", "source": "rtsp://camera-restart-2"},
        ).json()["data"]

        restart_response = self.client.post(f"/api/feeds/{feed['feed_id']}/restart")
        self.assertEqual(restart_response.status_code, 200)
        self.assertEqual(restart_response.json()["data"]["status"], "running")
        self.assertEqual(self.runner.started.count(feed["feed_id"]), 1)

    def test_websocket_receives_snapshot_and_feed_events(self) -> None:
        with self.client.websocket_connect("/ws/metrics") as websocket:
            snapshot = websocket.receive_json()
            self.assertEqual(snapshot["event"], "snapshot")
            self.assertEqual(snapshot["payload"]["feeds"], [])

            response = self.client.post(
                "/api/feeds",
                json={"name": "Checkout 2", "source": "rtsp://camera-2"},
            )
            self.assertEqual(response.status_code, 201)

            event = websocket.receive_json()
            self.assertEqual(event["event"], "feed_status")
            self.assertEqual(event["payload"]["action"], "created")
            self.assertEqual(event["payload"]["feed"]["name"], "Checkout 2")

    def test_websocket_receives_start_and_stop_updates(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 6", "source": "rtsp://camera-6"},
        ).json()["data"]

        with self.client.websocket_connect("/ws/metrics") as websocket:
            snapshot = websocket.receive_json()
            self.assertEqual(snapshot["event"], "snapshot")
            self.assertEqual(len(snapshot["payload"]["feeds"]), 1)

            start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
            self.assertEqual(start_response.status_code, 200)

            initializing_event = websocket.receive_json()
            self.assertEqual(initializing_event["event"], "feed_status")
            self.assertEqual(initializing_event["payload"]["action"], "updated")
            self.assertEqual(initializing_event["payload"]["feed"]["status"], "initializing")

            running_event = websocket.receive_json()
            self.assertEqual(running_event["event"], "feed_status")
            self.assertEqual(running_event["payload"]["action"], "updated")
            self.assertEqual(running_event["payload"]["feed"]["status"], "running")

            stop_response = self.client.post(f"/api/feeds/{feed['feed_id']}/stop")
            self.assertEqual(stop_response.status_code, 200)

            stopped_event = websocket.receive_json()
            self.assertEqual(stopped_event["event"], "feed_status")
            self.assertEqual(stopped_event["payload"]["action"], "updated")
            self.assertEqual(stopped_event["payload"]["feed"]["status"], "stopped")

    def test_websocket_hub_broadcasts_metrics_alert_and_warning_events(self) -> None:
        hub = WebSocketHub()
        websocket = CapturingWebSocket()

        metrics = QueueMetricsModel(
            timestamp=1710000000.0,
            people_in_zone=4,
            arrival_rate=0.2,
            service_rate=0.4,
            wait_time_seconds=5.0,
            wait_time_ci=[3.5, 6.5],
            uncertainty_level="Low",
            queue_stable=True,
        )
        alert = AlertModel(
            alert_type="queue_backlog",
            severity="warning",
            message="High queue length: 4 people",
            threshold_name="queue_length_warning",
            current_value=4.0,
            threshold_value=3.0,
            frame_id=12,
            timestamp=datetime.fromisoformat("2026-03-10T12:00:00+00:00"),
        )

        async def exercise() -> None:
            hub._clients.add(cast(Any, websocket))
            await hub.broadcast_metrics_event(feed_id="feed-live", metrics=metrics)
            await hub.broadcast_alert_event(feed_id="feed-live", alert=alert)
            await hub.broadcast_system_warning(
                feed_id="feed-live",
                code="queue_unstable",
                message="Queue entered an unstable state.",
                timestamp=datetime.fromisoformat("2026-03-10T12:00:01+00:00"),
            )

        asyncio.run(exercise())

        self.assertEqual(
            [payload["event"] for payload in websocket.payloads],
            ["metrics_update", "alert_fired", "system_warning"],
        )
        self.assertEqual(websocket.payloads[0]["payload"]["feed_id"], "feed-live")
        self.assertEqual(websocket.payloads[0]["payload"]["metrics"]["people_in_zone"], 4)
        self.assertEqual(websocket.payloads[1]["payload"]["alert"]["alert_type"], "queue_backlog")
        self.assertEqual(websocket.payloads[2]["payload"]["code"], "queue_unstable")

    def test_websocket_warning_persists_on_feed_status(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout Warning", "source": "rtsp://camera-warning"},
        ).json()["data"]

        start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)

        self.dispatch_worker_event(
            feed["feed_id"],
            "system_warning",
            {
                "code": "webhook_delivery_failed",
                "message": "Webhook delivery failed: timeout.",
                "timestamp": "2026-03-10T12:00:05+00:00",
            },
        )

        feed_status = self.client.get(f"/api/feeds/{feed['feed_id']}/status")
        self.assertEqual(feed_status.status_code, 200)
        self.assertEqual(feed_status.json()["data"]["last_warning"], "Webhook delivery failed: timeout.")
        self.assertEqual(feed_status.json()["data"]["last_warning_code"], "webhook_delivery_failed")

    def test_websocket_snapshot_includes_latest_metrics_and_warning_state(self) -> None:
        feed = self.client.post(
            "/api/feeds",
            json={"name": "Checkout Reconnect", "source": "rtsp://camera-reconnect"},
        ).json()["data"]

        start_response = self.client.post(f"/api/feeds/{feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)

        self.dispatch_worker_event(
            feed["feed_id"],
            "metrics_update",
            {
                "metrics": {
                    "timestamp": 1710000100.0,
                    "people_in_zone": 6,
                    "arrival_rate": 0.3,
                    "service_rate": 0.5,
                    "wait_time_seconds": 9.0,
                    "wait_time_ci": [7.0, 11.0],
                    "uncertainty_level": "Medium",
                    "queue_stable": True,
                }
            },
        )
        self.dispatch_worker_event(
            feed["feed_id"],
            "system_warning",
            {
                "code": "webhook_delivery_failed",
                "message": "Webhook delivery failed: timeout.",
                "timestamp": "2026-03-10T12:05:00+00:00",
            },
        )

        with self.client.websocket_connect("/ws/metrics") as reconnect_socket:
            reconnect_snapshot = reconnect_socket.receive_json()
            self.assertEqual(reconnect_snapshot["event"], "snapshot")

        feeds = reconnect_snapshot["payload"]["feeds"]
        reconnect_feed = next(item for item in feeds if item["feed_id"] == feed["feed_id"])
        self.assertEqual(reconnect_feed["latest_metrics"]["people_in_zone"], 6)
        self.assertEqual(reconnect_feed["last_warning"], "Webhook delivery failed: timeout.")
        self.assertEqual(reconnect_feed["last_warning_code"], "webhook_delivery_failed")

    def test_recovered_feed_surfaces_warning_instead_of_error(self) -> None:
        created_feed = self.client.post(
            "/api/feeds",
            json={"name": "Recovered Feed", "source": "rtsp://camera-recovery"},
        ).json()["data"]

        start_response = self.client.post(f"/api/feeds/{created_feed['feed_id']}/start")
        self.assertEqual(start_response.status_code, 200)

        broadcaster = WebSocketHub()
        app.state.broadcaster = broadcaster
        app.state.registry = FeedRegistry(broadcaster=broadcaster, runner=self.runner)

        recovered_feed = self.client.get(f"/api/feeds/{created_feed['feed_id']}/status")
        self.assertEqual(recovered_feed.status_code, 200)
        payload = recovered_feed.json()["data"]
        self.assertEqual(payload["status"], "stopped")
        self.assertIsNone(payload["last_error"])
        self.assertEqual(payload["last_warning"], RECOVERED_FEED_MESSAGE)
        self.assertEqual(payload["last_warning_code"], "recovery_required")


if __name__ == "__main__":
    unittest.main()