# MJPEG Streaming Migration (Snapshot Polling Replacement)

## Summary

This document records the first implementation slice that replaced per-feed snapshot polling with backend MJPEG streaming for live RTSP/webcam cards in the dashboard.

Goal:

- Reduce render latency and backend load caused by repeated `GET /api/feeds/{feed_id}/snapshot` calls every 800ms.
- Keep the existing zone-editor and setup flows working without contract breaks.

## Problem Before Migration

The original live transport used one snapshot request per feed on a fixed interval.

- Frontend loop: one request every 800ms for RTSP/webcam feeds.
- Backend snapshot path opened/decoded/captured/encoded a fresh frame for each request.
- Multiple feed cards multiplied request volume and CPU overhead.

Result: avoidable latency and unstable smoothness when multiple feeds were visible.

## What Was Implemented

### 1) Backend shared frame stream manager

File: `backend/src/api/runtime.py`

Added `FeedFrameStreamManager` and `FeedFrameStreamState`.

Key behavior:

- Maintains one capture loop per feed with a shared latest-frame buffer.
- Uses subscriber counting so multiple clients reuse the same capture loop.
- Supports RTSP credential embedding and transport selection (`tcp` / `udp`).
- Reconnect behavior:
  - RTSP: periodic reopen attempts after repeated read failures.
  - File/camera index source: rewinds to frame 0 when stream ends.
- JPEG quality set to 80 for lower transfer size in live view.

Registry integration (`FeedRegistry`):

- `subscribe_feed_stream(feed_id)`
- `next_feed_stream_frame(feed_id, after_frame_index, timeout_seconds)`
- `unsubscribe_feed_stream(feed_id)`

Lifecycle cleanup was added on:

- feed stop
- feed delete
- worker monitor exit (normal or error)
- registry clear

### 2) Backend MJPEG endpoint

File: `backend/src/api/app.py`

Added endpoint:

- `GET /api/feeds/{feed_id}/stream`

Contract:

- `404` when feed does not exist.
- `409` when feed is not running/initializing.
- Success returns `multipart/x-mixed-replace; boundary=frame`.

Response loop details:

- Pulls buffered frames from the stream manager.
- Emits MJPEG parts with `Content-Type: image/jpeg`.
- Breaks stream when feed stops.
- Always unsubscribes on disconnect/finalization.

### 3) Frontend transport switch

Files:

- `frontend/src/lib/api.ts`
- `frontend/src/components/dashboard/FeedGrid.tsx`

Added helper:

- `getFeedMjpegStreamUrl(feedId)`

Updated feed surface behavior:

- RTSP/webcam live cards now use MJPEG URL rendering instead of 800ms snapshot polling.
- Added reconnect attempts using an increasing delay.
- On stream error, performs one-shot snapshot fallback and renders that frame.
- Existing uploaded-video preview transport remains unchanged.

### 4) Documentation and tests

Files:

- `docs/API_FOR_FRONTEND.md`
- `backend/tests/test_api_app.py`
- `frontend/src/components/dashboard/FeedGrid.test.tsx`

Added backend tests for stream endpoint:

- missing feed returns 404
- non-running feed returns 409
- MJPEG chunk formatting/content type path

Added frontend tests for transport:

- RTSP card uses MJPEG endpoint
- fallback snapshot is used after stream error

## Compatibility Notes

The migration is additive and keeps existing flows intact.

- `GET /api/feeds/{feed_id}/snapshot` is still used for zone editing and fallback.
- `/ws/metrics` contract is unchanged.
- Existing feed CRUD/start/stop/restart APIs are unchanged.

## Throughput, Smoothness, And Playback Pacing (March 31, 2026)

The first low-latency tuning improved overlay freshness but increased pressure on slower machines. The runtime profile now prioritizes smoothness by default while keeping high-throughput toggles available.

- Backend event cadence defaults:
  - `DASHBOARD_EVENT_EMIT_INTERVAL_SEC`: `0.2`
  - `DASHBOARD_EVENT_POLL_INTERVAL_SEC`: `0.1`
- Dashboard client cadence defaults:
  - metrics flush interval: `250ms`
  - stale threshold: `3500ms`
  - fallback polling interval: `1500ms`
- Worker launch profile (API + GUI):
  - `--device auto` (resolves to CUDA automatically when available)
  - `--detector-imgsz 512`
  - `--process-every-n-frames 1` (visual smoothness default)
- File playback profile:
  - `--realtime-file-playback` enabled by default
  - file sources are paced to native source FPS (not rounded), preventing fast-forward playback feel
- Main loop integration path:
  - webhook delivery moved to an async dispatcher thread to prevent retry delays from blocking frame processing
  - rolling performance telemetry added to logs (`loop_fps`, `proc_fps`, stage timings)

Observed local behavior after pacing fix:

- File source at 13.1 FPS with realtime playback enabled: loop/proc stabilizes around source-rate (~13 FPS)
- Throughput mode remains available by disabling realtime playback (`--no-realtime-file-playback`) when benchmark speed is preferred over natural playback speed

Changed files for this tuning:

- `backend/src/config.py`
- `backend/src/main.py`
- `backend/src/detector.py`
- `backend/src/api/runtime.py`
- `backend/src/gui/app.py`
- `frontend/src/hooks/use-dashboard-websocket.ts`
- `backend/tests/test_main_playback.py`

## Validation Run

Validated during implementation:

- `python -m unittest backend.tests.test_api_app.TestQueueVisionApi.test_feed_stream_returns_not_found_for_missing_feed backend.tests.test_api_app.TestQueueVisionApi.test_feed_stream_requires_running_feed backend.tests.test_api_app.TestQueueVisionApi.test_feed_stream_yields_mjpeg_chunks`
- `npm --prefix frontend run test -- FeedGrid.test.tsx`
- `python -m py_compile backend/src/api/runtime.py backend/src/api/app.py backend/tests/test_api_app.py`
- `python -m unittest backend.tests.test_main_playback`
- `python -m unittest test_gui_app`

Note:

- `pytest` was not available in the local environment during this run, so `unittest` was used for targeted backend checks.
- Frontend repository lint currently has pre-existing unrelated violations outside this migration slice.

## Manual Verification Checklist

1. Start backend and frontend.
2. Open dashboard with one running RTSP feed.
3. Confirm live frame URL resolves against `/api/feeds/{feed_id}/stream`.
4. Verify repeated `/snapshot` polling is no longer used for steady-state live cards.
5. Stop feed and ensure stream closes cleanly.
6. Re-start feed and verify transport resumes.
7. Open zone editor and confirm snapshot capture still works.

## Known Limitations (Current Slice)

- Streamed frames are sourced directly from capture input, while overlays still come from latest metrics updates.
  - This can create slight timing drift between boxes/zone overlays and the underlying image.
- No dedicated stream auth token is added yet; endpoint relies on current API access model.
- This slice uses MJPEG, not WebRTC.

## Follow-up Path (Phase 2)

If stricter low-latency targets are required later:

- move to WebSocket binary frame transport with canvas rendering
- optionally emit annotated frames directly from worker pipeline
- add per-feed stream health metrics (frame age, subscribers, effective fps)
