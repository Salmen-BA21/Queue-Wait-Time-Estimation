"""Backend API tests for the first FastAPI integration slice."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.app import app


class TestQueueVisionApi(unittest.TestCase):
    """Validate feed CRUD, zone validation, and websocket snapshots."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        feeds = self.client.get("/api/feeds").json()["data"]
        for feed in feeds:
            self.client.delete(f"/api/feeds/{feed['feed_id']}")

    def test_create_feed_and_fetch_status(self) -> None:
        response = self.client.post(
            "/api/feeds",
            json={"name": "Checkout 1", "source": "rtsp://192.168.1.10/stream"},
        )
        self.assertEqual(response.status_code, 201)

        payload = response.json()["data"]
        self.assertEqual(payload["name"], "Checkout 1")
        self.assertEqual(payload["status"], "created")

        status_response = self.client.get(f"/api/feeds/{payload['feed_id']}/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["data"]["source"], "rtsp://192.168.1.10/stream")

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


if __name__ == "__main__":
    unittest.main()