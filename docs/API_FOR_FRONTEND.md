# API Contract for Frontend

Canonical contract for the web dashboard frontend.

- Backend REST base: `/api`
- WebSocket endpoint: `/ws/metrics`
- Source of truth: `backend/src/api/app.py`, `backend/src/api/models.py`, `frontend/src/lib/api.ts`

## Response Envelope

Most REST endpoints return:

```json
{
  "success": true,
  "data": {},
  "message": "optional"
}
```

Streaming endpoint `/api/feeds/{feed_id}/stream` returns MJPEG bytes and does not use the envelope.

## Feed Endpoints

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| GET | `/api/feeds` | None | `VideoFeed[]` |
| POST | `/api/feeds` | `CreateFeedRequest` | `VideoFeed` |
| POST | `/api/feeds/batch-launch` | `BatchFeedLaunchRequest` | `BatchFeedLaunchResponse` |
| GET | `/api/feeds/{feed_id}/status` | None | `VideoFeed` |
| POST | `/api/feeds/{feed_id}/start` | None | `VideoFeed` |
| POST | `/api/feeds/{feed_id}/stop` | None | `VideoFeed` |
| POST | `/api/feeds/{feed_id}/restart` | None | `VideoFeed` |
| DELETE | `/api/feeds/{feed_id}` | None | `{ "feed_id": string }` |
| GET | `/api/feeds/{feed_id}/snapshot` | None | `FeedSnapshotResult` |
| GET | `/api/feeds/{feed_id}/stream` | None | `multipart/x-mixed-replace` |
| POST | `/api/feeds/{feed_id}/zone` | `ZoneUpdateRequest` | `VideoFeed` |
| POST | `/api/feeds/{feed_id}/thresholds` | `QueueThresholdUpdateRequest` | `VideoFeed` |

### MJPEG Stream Status Codes

- `200`: feed streaming
- `404`: feed id not found
- `409`: feed exists but is not running/initializing

Recommended frontend strategy:

1. Use `/api/feeds/{feed_id}/stream` for live cards.
2. Fallback to `/api/feeds/{feed_id}/snapshot` on transient stream failures.
3. Keep snapshot endpoint for zone editor and re-zoning workflows.

## Video Upload Endpoints

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| POST | `/api/upload` | multipart form `file` | `UploadVideoResponse` |
| POST | `/api/uploads/video` | multipart form `file` | `UploadVideoResponse` |
| GET | `/api/uploads/files/{file_name}` | None | file bytes |

`UploadVideoResponse.preview_path` is browser-facing and should be used by the frontend for preview playback.

## Source Onboarding Endpoints

### RTSP

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| POST | `/api/sources/rtsp/test` | `RTSPConnectionTestRequest` | `RTSPConnectionTestResult` |
| POST | `/api/sources/rtsp/snapshot` | `RTSPSnapshotRequest` | `RTSPSnapshotResult` |

### ONVIF

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| POST | `/api/sources/onvif/discover` | `ONVIFDiscoveryRequest` | `ONVIFDevice[]` |
| POST | `/api/sources/onvif/streams` | `ONVIFStreamResolutionRequest` | `ONVIFStream[]` |
| POST | `/api/sources/onvif/test` | `ONVIFCameraTestRequest` | `ONVIFCameraTestResult` |

## Metadata Endpoints

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| GET | `/api/establishments` | None | `Establishment[]` |
| POST | `/api/establishments` | `CreateEstablishmentRequest` | `Establishment` |
| GET | `/api/establishments/{establishment_id}/caisses` | None | `Caisse[]` |
| POST | `/api/establishments/{establishment_id}/caisses` | `CreateCaisseRequest` | `Caisse` |

## System and Integration Endpoints

| Method | Path | Request Body | Response `data` |
|---|---|---|---|
| GET | `/api/system/health` | None | `SystemHealth` |
| GET | `/api/system/webhook` | None | `WebhookIntegrationStatus` |
| POST | `/api/system/webhook/test` | None | `WebhookIntegrationTestResult` |
| POST | `/api/alerts/archive` | `QueueAlertArchiveRequest` | `QueueAlertArchiveResponse` |

## Core Request/Response Shapes

### CreateFeedRequest

```json
{
  "name": "Lane 3",
  "source": "rtsp://camera.local:554/stream1",
  "model_size": "n",
  "establishment_id": 1,
  "caisse_id": 2,
  "rtsp_username": "admin",
  "rtsp_password": "secret",
  "rtsp_transport": "tcp"
}
```

### ZoneUpdateRequest

```json
{
  "zone": {
    "points": [
      { "x": 0.2, "y": 0.25 },
      { "x": 0.8, "y": 0.25 },
      { "x": 0.8, "y": 0.95 },
      { "x": 0.2, "y": 0.95 }
    ]
  }
}
```

### QueueThresholdUpdateRequest

```json
{
  "queue_length_warning": 10
}
```

### QueueMetrics (from websocket `metrics_update`)

```json
{
  "timestamp": 1711898585.12,
  "people_in_zone": 7,
  "arrival_rate": 0.14,
  "service_rate": 0.18,
  "wait_time_seconds": 22.7,
  "wait_time_ci": [14.3, 33.8],
  "uncertainty_level": "Low",
  "queue_stable": true,
  "detections": [[12, 44, 130, 312, 0.94, 0, 53]],
  "render_frame_jpeg_base64": null
}
```

`detections` and `render_frame_jpeg_base64` are optional fields.

## WebSocket Contract: `/ws/metrics`

On connect, server emits snapshot first, then incremental events.

### Event Types

1. `snapshot`
2. `feed_status`
3. `metrics_update`
4. `alert_fired`
5. `system_warning`

### Event Schemas

```json
{
  "event": "snapshot",
  "payload": { "feeds": [] }
}
```

```json
{
  "event": "feed_status",
  "payload": {
    "action": "created",
    "feed": {},
    "feed_id": "feed_123"
  }
}
```

```json
{
  "event": "metrics_update",
  "payload": {
    "feed_id": "feed_123",
    "metrics": {}
  }
}
```

```json
{
  "event": "alert_fired",
  "payload": {
    "feed_id": "feed_123",
    "alert": {
      "alert_type": "QUEUE_BACKLOG_WARNING",
      "severity": "warning",
      "message": "Queue length exceeded",
      "threshold_name": "queue_length_warning",
      "current_value": 12,
      "threshold_value": 8,
      "frame_id": 455,
      "timestamp": "2026-03-31T10:15:20.000Z"
    }
  }
}
```

```json
{
  "event": "system_warning",
  "payload": {
    "feed_id": "feed_123",
    "code": "SOURCE_UNREACHABLE",
    "message": "RTSP reconnect attempts exhausted",
    "timestamp": "2026-03-31T10:16:02.000Z"
  }
}
```

## Webhook Payload Note

There are two related but different payloads in this repository:

1. Backend runtime webhook payload (`backend/src/webhook.py`) used by `WebhookClient`:
   - Flat fields such as `alert_triggered`, `alert_reason`, `alert_severity`
2. Alert archive payload (`POST /api/alerts/archive`) used for structured alert storage:
   - Includes nested `metrics`, optional `uncertainty`, and `alerts[]`

When integrating n8n, use the runtime webhook payload as the incoming contract unless your workflow explicitly transforms and archives to `/api/alerts/archive`.

## Frontend Client Mapping

The frontend already maps these routes in `frontend/src/lib/api.ts`, including:

- `updateFeedThresholds()`
- `getWebhookIntegrationStatus()`
- `testWebhookIntegration()`
- `getFeedMjpegStreamUrl()`
- websocket types for all five event families
