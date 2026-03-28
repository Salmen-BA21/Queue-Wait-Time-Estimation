# API Summary for Frontend Developers

This document lists the primary backend BFF endpoints and websocket contract frontend should consume.

Base API: `/api/` (FastAPI app in `backend/src/api/app.py`)
WebSocket: `/ws/metrics`

## Key REST endpoints

- `GET /api/feeds`
  - Returns list of configured feeds (VideoFeed model).

- `POST /api/feeds`
  - Create/register a feed (body: `CreateFeedRequest`). Returns created `VideoFeed`.

- `POST /api/feeds/batch-launch`
  - Launch a batch of staged feeds. Body: `BatchFeedLaunchRequest`.

- `GET /api/feeds/{feed_id}/status`
  - Get status of a feed (VideoFeed).

- `POST /api/feeds/{feed_id}/start` — start a feed
- `POST /api/feeds/{feed_id}/stop` — stop a feed
- `POST /api/feeds/{feed_id}/restart` — restart a feed
- `DELETE /api/feeds/{feed_id}` — delete a feed
- `POST /api/feeds/{feed_id}/zone` — update feed zone
- `GET /api/feeds/{feed_id}/snapshot` — capture feed snapshot (returns `FeedSnapshotResult`)
- `GET /api/feeds/{feed_id}/stream` — MJPEG live stream (`multipart/x-mixed-replace; boundary=frame`) for running feeds

### MJPEG stream behavior

- Intended for live RTSP/webcam cards in the dashboard.
- Endpoint returns:
  - `404` when feed does not exist
  - `409` when feed exists but is not running/initializing
  - `200` streaming response when feed is active
- Client transport recommendation:
  - Use stream endpoint for steady-state live rendering.
  - Fall back to `GET /api/feeds/{feed_id}/snapshot` on transient stream error.
  - Keep snapshot endpoint for zone-editor workflows.

- `POST /api/upload` or `POST /api/uploads/video`
  - Upload video file (multipart). Returns `preview_path` usable by frontend for playback.

- RTSP / ONVIF helpers:
  - `POST /api/sources/rtsp/test` — test RTSP connection (body: `RTSPConnectionTestRequest`)
  - `POST /api/sources/rtsp/snapshot` — capture RTSP snapshot
  - `POST /api/sources/onvif/discover` — discover devices (ONVIF)
  - `POST /api/sources/onvif/streams` — resolve ONVIF streams
  - `POST /api/sources/onvif/test` — ONVIF camera test

- Metadata endpoints:
  - `GET /api/establishments`
  - `POST /api/establishments`
  - `GET /api/establishments/{id}/caisses`
  - `POST /api/establishments/{id}/caisses`

- System health:
  - `GET /api/system/health`

## WebSocket: `/ws/metrics`

- Connect to `/ws/metrics` to receive live events. On connect the server sends a `FeedSnapshotEvent` with current feeds.
- The pipeline writes newline-delimited JSON events to an events file when running in CLI; frontend will receive updates via broadcaster.

### Dashboard websocket payload (example fields)
- `timestamp` (float)
- `people_in_zone` (int)
- `arrival_rate` (float)
- `service_rate` (float)
- `wait_time_seconds` (float|null) — null when queue unstable
- `wait_time_ci` (list|null) — [lower, upper]
- `uncertainty_level` ("Low"|"Medium"|"High")
- `queue_stable` (bool)

Use these fields to update metrics, charts, and alert statuses in the dashboard.

## Webhook payload (n8n) — reference
See `backend/src/webhook.py` for `QueuePayload` and `EXAMPLE_PAYLOAD`.
Important fields sent to n8n include:
- `timestamp`, `frame_id`, `source`
- `people_in_zone`, `arrival_rate`, `service_rate`, `estimated_wait_sec`
- `arrival_rate_lower`, `arrival_rate_upper`, `service_rate_lower`, `service_rate_upper`, `wait_time_lower`, `wait_time_upper`
- `uncertainty_level`, `queue_stable`, `alert_triggered`, `alert_reason`, `alert_severity`

## Notes for Frontend Implementation
- The backend BFF is implemented (`backend/src/api/app.py`). The frontend should implement an API client to call the endpoints above and connect to `/ws/metrics` for live updates.
- Uploaded video `preview_path` values are served at `/api/uploads/files/{file_name}`.
- RTSP/ONVIF endpoints perform potentially blocking IO; use the provided async endpoints — they offload work to threads.

## Example: consume websocket (pseudo-code)

```js
const ws = new WebSocket('ws://localhost:8000/ws/metrics');
ws.onmessage = (ev) => {
  const data = JSON.parse(ev.data);
  // Handle FeedSnapshotEvent or other events
};
```

## Where to look in repo
- Backend API implementation: `backend/src/api/app.py`
- WebSocket hub & runtime: `backend/src/api/runtime.py`
- Payload model: `backend/src/webhook.py`
- Dashboard payload builder: `backend/src/main.py` (`_dashboard_metrics_payload`)

---

Last updated: automatic update by dev agent on request.
