# RTSP / ONVIF Refactor Handoff

This brief is for the next agent, ideally `code-fixer.agent.md`, to continue the RTSP / ONVIF cleanup without breaking the current API contract.

## Context

The last 3 commits show a progression in ONVIF support:

1. `2747cfb` - broad ONVIF discovery and RTSP stream-resolution rewrite.
2. `daea365` - stricter ONVIF RTSP resolution plus tests.
3. `735f75a` - docs and agent-instruction cleanup only.

The current implementation in [backend/src/rtsp_camera.py](../../backend/src/rtsp_camera.py) is functional but too large and too custom. It manually implements:

- WS-Discovery device discovery
- ONVIF capability lookup
- ONVIF GetServices fallback
- ONVIF GetProfiles and GetStreamUri requests
- RTSP URL sanitation and testing
- OpenCV RTSP capture and reconnect logic

The user’s concern is that the ONVIF path is more complex than necessary and may be better handled with `onvif-zeep`.

## What to Preserve

Do not break these behaviors:

- `RTSPCamera.test_connection()` and `RTSPCamera.capture_snapshot()`
- Existing API response shapes in [backend/src/api/app.py](../../backend/src/api/app.py)
- Sanitized RTSP URLs in API outputs
- Backward-compatible discovery entry points:
  - `RTSPCamera.discover_ip_devices()`
  - `RTSPCamera.discover_onvif_devices()`
  - `RTSPCamera.get_rtsp_urls_from_onvif_device()`

## Recommended Refactor Order

### 1. Separate RTSP capture from ONVIF control-plane logic

Keep camera streaming and reconnect behavior in `backend/src/rtsp_camera.py`, but move ONVIF-specific logic into a smaller adapter or service module.

Suggested split:

- `backend/src/rtsp_camera.py` - RTSP connection, test, snapshot, reconnect
- `backend/src/onvif_client.py` or similar - discovery and stream resolution

### 2. Replace manual ONVIF SOAP code if feasible

The main candidate for simplification is replacing the hand-written SOAP/XML logic with `onvif-zeep`.

Use it for:

- `GetCapabilities`
- `GetProfiles`
- `GetStreamUri`

Be careful with:

- Windows compatibility
- WSDL path handling
- Authentication behavior
- Keeping fallback behavior for cameras that do not expose media directly

Do not hardcode a Linux-style WSDL path from examples.

### 3. Keep discovery separate from stream resolution

Discovery and stream resolution are different problems.

If `onvif-zeep` helps with stream resolution but not discovery, keep WS-Discovery as a separate, testable module.

### 4. Preserve and expand tests

Current tests already cover the main ONVIF behavior:

- [backend/tests/test_rtsp_camera_discovery.py](../../backend/tests/test_rtsp_camera_discovery.py)
- [backend/tests/test_rtsp_camera_onvif_resolution.py](../../backend/tests/test_rtsp_camera_onvif_resolution.py)
- [backend/tests/test_api_app.py](../../backend/tests/test_api_app.py)

Update or add tests before changing implementation so behavior stays stable.

## Good Target Shape

A safe end state would look like this:

- `rtsp_camera.py` remains the public entry point for RTSP operations
- ONVIF lookup is delegated to a dedicated helper module
- The public methods still return the same payloads and URL lists
- The backend API does not need to change

## Notes for the Next Agent

- Start from the current behavior, not from the ideal API.
- Prefer the smallest refactor that removes the custom ONVIF SOAP code.
- If `onvif-zeep` adds complexity or platform risk, keep the current logic but extract and simplify it.
- Avoid changing the frontend unless the backend contract changes, which should be avoided.

## Suggested Next Step

Have the next agent inspect the ONVIF-specific block in [backend/src/rtsp_camera.py](../../backend/src/rtsp_camera.py) and decide whether to:

1. Extract it into a dedicated module with the same behavior, or
2. Replace it with `onvif-zeep` while keeping the current API contract intact.

## How to Use

Give this file to the refactoring agent as the working brief. The agent should work directly on the files referenced here and preserve the existing tests and API behavior.
