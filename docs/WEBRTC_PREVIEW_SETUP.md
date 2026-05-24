# WebRTC Preview Setup and Operations

Canonical operations guide for WebRTC live preview in the web dashboard.

- Last validated against code: April 7, 2026
- Backend implementation: `backend/src/api/app.py`, `backend/src/api/runtime.py`, `backend/src/config.py`
- Frontend implementation: `frontend/src/hooks/use-feed-webrtc.ts`, `frontend/src/components/dashboard/FeedGrid.tsx`

## Architecture

The dashboard uses a WebRTC-first playback policy for running feeds.

1. Frontend checks feed capabilities using `GET /api/feeds/{feed_id}/transport`.
2. If WebRTC is ready, frontend builds an SDP offer with `RTCPeerConnection`.
3. Frontend posts offer to `POST /api/feeds/{feed_id}/webrtc/offer`.
4. Backend validates feed state/source, then proxies to MediaMTX WHEP.
5. Backend returns SDP answer, frontend sets remote description.
6. If WebRTC is unavailable or fails, frontend falls back to MJPEG stream.

## Requirements

- Feed source must currently be RTSP for WebRTC readiness.
- Feed status must be `running`.
- MediaMTX WHEP and Control API endpoints must be reachable from backend.
- Browser environment must support `RTCPeerConnection`.

## Environment Variables

These values are read by backend config:

- `MEDIAMTX_WEBRTC_PREVIEW_ENABLED` (default: `true`)
- `MEDIAMTX_WHEP_BASE_URL` (default: `http://127.0.0.1:8889`)
- `MEDIAMTX_CONTROL_API_BASE_URL` (default: `http://127.0.0.1:9997`)
- `MEDIAMTX_WEBRTC_TIMEOUT_SEC` (default: `8.0`)
- `QUEUEVISION_RTSP_WEBRTC_STRICT_MODE` (default: `false`)  
  When `true`, RTSP running feeds are WebRTC-only in transport capability (no MJPEG fallback selection).
- `QUEUEVISION_WEBRTC_SYNC_OVERLAY_ENABLED` (default: `false`)  
  Enables frame-sync metadata buffering for WebRTC overlay synchronization.

## MediaMTX Ports

Default ports in this repository setup:

- `8554` RTSP relay path
- `8889` WHEP/WebRTC endpoint
- `9997` MediaMTX Control API

## Feed Transport Capability Contract

`GET /api/feeds/{feed_id}/transport` returns:

```json
{
  "backend_annotations": true,
  "webrtc": {
    "enabled": true,
    "ready": true,
    "source_mode": "direct",
    "path_name": "feed_123",
    "reason": null
  },
  "mjpeg": {
    "enabled": true,
    "ready": true,
    "reason": null
  }
}
```

When `QUEUEVISION_RTSP_WEBRTC_STRICT_MODE=true`, running RTSP feeds return MJPEG capability with:

- `mjpeg.enabled = false`
- `mjpeg.reason = "strict_webrtc_rtsp_mode"`

`webrtc.source_mode` values:

- `direct`: direct RTSP relay path
- `annotated`: backend-annotated path expected
- `none`: no WebRTC route for this feed

Common unavailability reasons:

- `feed_not_running`
- `rtsp_source_required`
- `webrtc_not_ready`

## WebRTC Offer Endpoint

Endpoint: `POST /api/feeds/{feed_id}/webrtc/offer`

Request body:

```json
{
  "offer": {
    "type": "offer",
    "sdp": "v=0\r\no=- 123..."
  }
}
```

Response body:

```json
{
  "answer": {
    "type": "answer",
    "sdp": "v=0\r\no=- 456..."
  }
}
```

Expected status codes:

- `200` offer accepted, answer returned
- `404` feed not found
- `409` feed not running, unsupported source, or WebRTC not ready
- `422` invalid SDP payload
- `502` MediaMTX upstream error
- `503` preview disabled or MediaMTX unavailable

## Frontend Fallback Behavior

Current dashboard behavior:

- Try WebRTC first when capability is ready.
- Retry on recoverable failures with exponential delays.
- Do not retry on `404`, `409`, or `422` responses.
- Fall back to MJPEG live stream if WebRTC cannot be established.
- Keep snapshot for zone workflows and non-live preview only.

## Important SDP Handling Rule

Do not normalize or trim SDP before forwarding to upstream signaling.

- Validation can use `if not sdp.strip()`.
- Forward the original SDP string unchanged when proxying.

This avoids known upstream interoperability failures caused by removing trailing CRLF from browser-generated SDP.

## Quick Troubleshooting

If WebRTC is not used:

1. Check `GET /api/feeds/{feed_id}/transport` and inspect `webrtc.reason`.
2. Confirm feed source is RTSP and feed status is `running`.
3. Verify MediaMTX process and port reachability (`8889`, `9997`).
4. Confirm `MEDIAMTX_WEBRTC_PREVIEW_ENABLED=true`.

If dashboard falls back to MJPEG unexpectedly:

1. Inspect API response status from `/api/feeds/{feed_id}/webrtc/offer`.
2. Check browser support for `RTCPeerConnection`.
3. Review backend logs for upstream timeout or MediaMTX errors.

## Terminal-Only Launcher

If you want to stay in the terminal and avoid the GUI, use the backend helper script:

```powershell
Set-Location "C:\Users\Salmen Ben Ammar\Desktop\Stage_PFE\backend"
python -m scripts.launch_webrtc_preview --source "rtsp://admin:Datadoit_1234@192.168.1.23:554/profile2" --model-size s
```

To open the MediaMTX relay in a terminal player after the feed is ready:

```powershell
Set-Location "C:\Users\Salmen Ben Ammar\Desktop\Stage_PFE\backend"
python -m scripts.launch_webrtc_preview --source "rtsp://admin:Datadoit_1234@192.168.1.23:554/profile2" --model-size s --watch
```

The helper creates or reuses a feed through the backend, starts it, waits for WebRTC readiness, and prints the MediaMTX URLs. It also uses the project-local ffplay copy at `.venv\Scripts\ffplay.exe` when available, so you do not need a separate system FFmpeg install.

Known working playback commands:

```powershell
& "C:\Users\Salmen Ben Ammar\Desktop\Stage_PFE\.venv\Scripts\ffplay.exe" -fflags nobuffer -flags low_delay -framedrop -rtsp_transport tcp rtsp://127.0.0.1:8554/<feed_id>
```

Replace `<feed_id>` with the path name printed by the helper. It changes when the helper creates a new feed.

## Related Documents

- `API_FOR_FRONTEND.md`
- `tracking/MJPEG_STREAMING_MIGRATION.md`
- `../README.md`
- `../frontend/README.md`
