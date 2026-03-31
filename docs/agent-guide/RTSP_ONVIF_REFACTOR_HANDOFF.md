# RTSP / ONVIF Refactor Handoff

This brief is for the next agent to continue ONVIF cleanup without breaking the current API contract.

## Context

ONVIF logic is now split by responsibility:

- [backend/src/onvif_client.py](../../backend/src/onvif_client.py): discovery + ONVIF stream resolution
- [backend/src/rtsp_camera.py](../../backend/src/rtsp_camera.py): RTSP connection testing, snapshot, capture/reconnect behavior

The current concern is maintainability and complexity in ONVIF SOAP handling. The split is correct, but internals can still be simplified.

## What to Preserve

Do not break these behaviors:

- `RTSPCamera.test_connection()` and `RTSPCamera.capture_snapshot()`
- Existing API response shapes in [backend/src/api/app.py](../../backend/src/api/app.py)
- Sanitized RTSP URLs in API outputs
- Backward-compatible discovery entry points:
  - `discover_ip_devices()`
  - `discover_onvif_devices()`
  - `get_rtsp_urls_from_onvif_device()`

## Recommended Refactor Order

### 1. Keep existing module split

The split between `rtsp_camera.py` and `onvif_client.py` is already in place. Do not re-merge them.

Focus on reducing complexity inside `onvif_client.py` while preserving function signatures.

### 2. Replace manual ONVIF SOAP code if feasible

The main candidate is replacing selected hand-written SOAP/XML blocks with `onvif-zeep`.

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
- `onvif_client.py` remains the dedicated ONVIF helper module
- The public methods still return the same payloads and URL lists
- The backend API does not need to change

## Notes for the Next Agent

- Start from the current behavior, not from the ideal API.
- Prefer the smallest refactor that simplifies custom ONVIF SOAP code.
- If `onvif-zeep` adds complexity or platform risk, keep the current logic but extract and simplify it.
- Avoid changing the frontend unless the backend contract changes, which should be avoided.

## Suggested Next Step

Have the next agent inspect ONVIF-specific blocks in [backend/src/onvif_client.py](../../backend/src/onvif_client.py) and decide whether to:

1. Extract it into a dedicated module with the same behavior, or
2. Replace it with `onvif-zeep` while keeping the current API contract intact.

## How to Use

Give this file to the refactoring agent as the working brief. The agent should work directly on the files referenced here and preserve the existing tests and API behavior.
