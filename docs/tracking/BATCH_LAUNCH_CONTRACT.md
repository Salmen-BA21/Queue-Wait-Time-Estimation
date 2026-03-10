# Batch Launch Contract

## Decision

Multi-source launch should use a dedicated batch endpoint instead of having the frontend coordinate a sequence of single-feed create and start calls.

Planned endpoint:

- `POST /api/feeds/batch-launch`

## Why this shape

- The review step already represents one staged operator action, so one API request matches the UI and the desktop workflow more closely.
- Shared runtime settings like `webhook_enabled` and `log_level` are global for the launch session, not per feed.
- The dashboard needs per-feed progress and partial failure reporting, which is easier to express in one response payload with itemized results.
- Centralizing the orchestration in the backend keeps worker startup order, error handling, and future WebSocket progress events consistent.

## Request shape

```json
{
  "launch_mode": "create_and_start",
  "runtime": {
    "webhook_enabled": true,
    "log_level": "INFO"
  },
  "feeds": [
    {
      "client_id": "draft-1",
      "name": "Checkout North",
      "source": "rtsp://192.168.1.10/live/main",
      "model_size": "m",
      "establishment_id": 1,
      "caisse_id": 2,
      "rtsp_username": "operator",
      "rtsp_password": "secret",
      "rtsp_transport": "tcp",
      "zone": {
        "points": [
          { "x": 0.12, "y": 0.18 },
          { "x": 0.84, "y": 0.18 },
          { "x": 0.84, "y": 0.92 }
        ]
      }
    }
  ]
}
```

## Contract rules

- `launch_mode` supports `save_only` and `create_and_start`.
- `runtime` is shared by the full batch, not attached per feed.
- `feeds[*].client_id` is required and is echoed back so the frontend can reconcile staged rows with results.
- `feeds[*].zone` is optional, but when present it must contain at least 3 normalized points.
- The backend must not echo RTSP passwords back in response payloads.
- The endpoint should be best-effort, not atomic. One feed failure must not roll back successful feed creations that already completed.

## Response shape

```json
{
  "launch_mode": "create_and_start",
  "runtime": {
    "webhook_enabled": true,
    "log_level": "INFO"
  },
  "results": [
    {
      "client_id": "draft-1",
      "status": "started",
      "feed": {
        "feed_id": "9e2149c5-23e4-4cb1-a7a2-e5d0b419f137",
        "name": "Checkout North",
        "source": "rtsp://192.168.1.10/live/main",
        "preview_path": null,
        "model_size": "m",
        "status": "running",
        "created_at": "2026-03-10T12:00:00Z",
        "updated_at": "2026-03-10T12:00:02Z",
        "establishment_id": 1,
        "caisse_id": 2,
        "zone": {
          "points": [
            { "x": 0.12, "y": 0.18 },
            { "x": 0.84, "y": 0.18 },
            { "x": 0.84, "y": 0.92 }
          ]
        },
        "latest_metrics": null,
        "last_error": null
      },
      "error": null
    }
  ],
  "summary": {
    "total": 1,
    "created": 1,
    "started": 1,
    "failed": 0
  }
}
```

## Implementation notes for the next slice

- Reuse the existing single-feed create logic inside the registry so validation and persistence stay aligned.
- Apply the shared runtime settings when the batch endpoint starts workers.
- Return `status: created` for successful `save_only` items.
- Return `status: failed` with a clear `error` string when either creation or startup fails for that item.
- Keep feed creation, zone persistence, and worker start sequencing explicit so future WebSocket progress events can mirror the same phases.