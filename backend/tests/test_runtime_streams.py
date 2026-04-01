"""Unit tests for feed frame stream handoff continuity."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.api.runtime import FeedFrameStreamManager, FeedFrameStreamState


class TestFeedFrameStreamManager(unittest.IsolatedAsyncioTestCase):
    """Validate capture-to-worker handoff behavior for MJPEG stream state."""

    async def test_worker_handoff_preserves_frame_index_for_waiters(self) -> None:
        manager = FeedFrameStreamManager()
        feed_id = "handoff-feed-index"
        capture_state = FeedFrameStreamState(
            feed_id=feed_id,
            source="rtsp://camera.local/live",
            username=None,
            password=None,
            transport="tcp",
            mode="capture",
            subscribers=1,
            frame_index=250,
            latest_frame=b"capture-frame",
        )
        manager._states[feed_id] = capture_state

        await manager.push_worker_frame(
            feed_id=feed_id,
            source="rtsp://camera.local/live",
            username=None,
            password=None,
            transport="tcp",
            frame_bytes=b"worker-frame",
        )

        frame = await manager.wait_for_next_frame(
            feed_id,
            after_frame_index=250,
            timeout_seconds=0.05,
        )

        self.assertIsNotNone(frame)
        if frame is None:
            return
        frame_index, frame_bytes = frame

        self.assertEqual(frame_index, 251)
        self.assertEqual(frame_bytes, b"worker-frame")
        self.assertEqual(manager._states[feed_id].mode, "worker")

    async def test_worker_handoff_keeps_subscribers_through_unsubscribe(self) -> None:
        manager = FeedFrameStreamManager()
        feed_id = "handoff-feed-subscribers"
        capture_state = FeedFrameStreamState(
            feed_id=feed_id,
            source="0",
            username=None,
            password=None,
            transport="tcp",
            mode="capture",
            subscribers=2,
            frame_index=40,
            latest_frame=b"capture-frame",
        )
        manager._states[feed_id] = capture_state

        await manager.push_worker_frame(
            feed_id=feed_id,
            source="0",
            username=None,
            password=None,
            transport="tcp",
            frame_bytes=b"worker-frame-1",
        )

        await manager.unsubscribe(feed_id)
        self.assertIn(feed_id, manager._states)
        self.assertEqual(manager._states[feed_id].subscribers, 1)

        await manager.unsubscribe(feed_id)
        self.assertNotIn(feed_id, manager._states)

    async def test_worker_handoff_uses_final_capture_index_after_stop(self) -> None:
        manager = FeedFrameStreamManager()
        feed_id = "handoff-feed-final-index"
        capture_state = FeedFrameStreamState(
            feed_id=feed_id,
            source="0",
            username=None,
            password=None,
            transport="tcp",
            mode="capture",
            subscribers=1,
            frame_index=12,
            latest_frame=b"capture-frame",
        )
        manager._states[feed_id] = capture_state

        original_stop_state = manager._stop_state

        def stop_state_with_extra_capture_progress(state: FeedFrameStreamState) -> None:
            state.frame_index = 120
            original_stop_state(state)

        with patch.object(manager, "_stop_state", side_effect=stop_state_with_extra_capture_progress):
            await manager.push_worker_frame(
                feed_id=feed_id,
                source="0",
                username=None,
                password=None,
                transport="tcp",
                frame_bytes=b"worker-frame",
            )

        frame = await manager.wait_for_next_frame(
            feed_id,
            after_frame_index=120,
            timeout_seconds=0.05,
        )

        self.assertIsNotNone(frame)
        if frame is None:
            return
        frame_index, frame_bytes = frame

        self.assertEqual(frame_index, 121)
        self.assertEqual(frame_bytes, b"worker-frame")

    async def test_wait_for_next_frame_recovers_from_index_regression(self) -> None:
        manager = FeedFrameStreamManager()
        feed_id = "handoff-feed-index-regression"
        state = FeedFrameStreamState(
            feed_id=feed_id,
            source="0",
            username=None,
            password=None,
            transport="tcp",
            mode="worker",
            subscribers=1,
            frame_index=7,
            latest_frame=b"worker-frame",
        )
        manager._states[feed_id] = state

        frame = await manager.wait_for_next_frame(
            feed_id,
            after_frame_index=42,
            timeout_seconds=0.02,
        )

        self.assertIsNotNone(frame)
        if frame is None:
            return
        frame_index, frame_bytes = frame

        self.assertEqual(frame_index, 7)
        self.assertEqual(frame_bytes, b"worker-frame")


if __name__ == "__main__":
    unittest.main()
