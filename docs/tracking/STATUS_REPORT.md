# Queue Wait-Time Estimation System - Status Report

**Last Updated:** April 11, 2026

> Note: This file is a cumulative status log. Some older sections preserve historical context from before the `backend/` + `frontend/` restructure and may reference legacy paths. For the current runtime contract, use `../../README.md`, `../API_FOR_FRONTEND.md`, and `../WEBRTC_PREVIEW_SETUP.md`.

## ✅ FIXED: Signup/Signin + RBAC Integration (April 11, 2026)

### Overview
Implemented and validated end-to-end authentication and role-based access control for the web application.

### What Changed
- **Backend auth/session endpoints**
  - Added `POST /api/auth/register` for self-service account creation.
  - Added/validated cookie-session lifecycle endpoints:
    - `POST /api/auth/login`
    - `POST /api/auth/refresh`
    - `POST /api/auth/logout`
    - `GET /api/auth/me`
- **Role governance**
  - Added admin manager-account endpoints:
    - list/create manager
    - activate/deactivate manager
    - reset manager password
  - Added staged operational route protection via `QUEUEVISION_AUTH_ENFORCE_API`.
- **Frontend auth integration**
  - Added auth provider and protected-route enforcement by role.
  - Added signup page (`/signup`) and login-to-signup navigation.
  - Settings page now includes admin-only manager-account management UI.

### Validation
- Frontend test suite passed (`25 passed`).
- Backend API test suite passed (`86 passed`).
- Direct login verification against live backend returned HTTP 200 for bootstrap admin credentials.

### Runtime Compatibility Note
- Pinned `bcrypt<5` in `requirements.txt` to avoid passlib startup incompatibility on auth bootstrap paths.

## ✅ FIXED: WebRTC-First Live Transport Layer

### Overview
Implemented a WebRTC-first transport path for running RTSP feeds in the web dashboard while keeping MJPEG as the live fallback path.

### What Changed
- **Backend feed transport contract**
  - Added `GET /api/feeds/{feed_id}/transport`.
  - Added `POST /api/feeds/{feed_id}/webrtc/offer`.
  - Added explicit transport readiness and reason fields for frontend routing.
- **Frontend playback routing**
  - Running feed cards now attempt WebRTC first when capability is ready.
  - MJPEG remains the fallback transport when WebRTC is unsupported, unavailable, or fails.
  - Snapshot remains for zone/re-zoning and non-live preview workflows.
- **Media relay integration**
  - Added MediaMTX WHEP and Control API integration through backend env-configured endpoints.

### Files Updated
- `backend/src/api/app.py`
- `backend/src/api/models.py`
- `backend/src/api/runtime.py`
- `backend/src/config.py`
- `frontend/src/hooks/use-feed-webrtc.ts`
- `frontend/src/components/dashboard/FeedGrid.tsx`
- `frontend/src/lib/api.ts`
- `backend/tests/test_api_app.py`
- `frontend/src/hooks/use-feed-webrtc.test.tsx`
- `frontend/src/components/dashboard/FeedGrid.test.tsx`

### Verification
- Backend API transport tests passed for feed-state/source gating and error-path handling.
- Frontend tests passed for WebRTC hook behavior and playback fallback routing.
- API contract and transport docs updated in `../API_FOR_FRONTEND.md` and `../WEBRTC_PREVIEW_SETUP.md`.

## ✅ FIXED: Runtime Smoothness, GPU Selection, And Playback Pacing

### Overview
Implemented a focused runtime optimization pass to improve visual smoothness and remove playback timing artifacts while keeping queue metrics behavior unchanged.

### What Changed
- **GPU selection hardening**
  - Added explicit inference device control (`auto`, `cpu`, `cuda:0`, etc.).
  - Added startup diagnostics showing resolved device and CUDA runtime availability.
- **Detector performance controls**
  - Added configurable YOLO image size (`--detector-imgsz`).
  - Added frame processing stride (`--process-every-n-frames`).
- **Main loop responsiveness**
  - Webhook delivery moved to an async dispatcher thread to avoid blocking the hot path.
  - Rolling telemetry added to logs (`loop_fps`, `proc_fps`, detect/track/analyze stage timings).
- **Playback speed correction**
  - Added realtime file playback mode and made it default.
  - File sources are now paced to native source FPS (exact float), preventing fast-forward playback feel.

### Files Updated
- `backend/src/main.py`
- `backend/src/config.py`
- `backend/src/detector.py`
- `backend/src/api/runtime.py`
- `backend/src/gui/app.py`
- `frontend/src/hooks/use-dashboard-websocket.ts`
- `backend/tests/test_main_playback.py`
- `backend/tests/test_api_app.py`
- `test_gui_app.py`

### Verification
- Targeted unit tests for parser/defaults/playback flags and worker command construction.
- Runtime verification on local video source:
  - GPU resolved to `cuda:0` on RTX 4060.
  - Realtime playback run stabilized near source FPS.
  - Stage timings confirmed detection remains the dominant cost center.

## ✅ FIXED: IP Camera Discovery Implementation

### Overview
Implemented complete IP camera discovery system with GUI integration, allowing automatic detection and configuration of network cameras.

### Features Added
- **WS-Discovery Protocol**: Automatic camera discovery using standard protocols
- **Device Information Extraction**: Name, manufacturer, model, IP, serial, hardware
- **RTSP Stream Retrieval**: Automatic extraction of streaming URLs from camera media services
- **GUI Integration**: Dedicated "IP Camera Discovery" tab in video source selection
- **Connection Testing**: Validate camera connectivity before adding to monitoring
- **Multi-Camera Support**: Select and add multiple cameras simultaneously
- **Credential Management**: Secure credential entry for authenticated cameras

### Technical Implementation
- **XML Namespace Fixes**: Resolved SOAP parsing issues by registering proper namespaces
- **Error Handling**: Comprehensive error handling for network failures and authentication
- **Code Cleanup**: Removed duplicate files, fixed import paths
- **Documentation**: Updated README, created detailed ONVIF guide

### Files Created/Modified
- `backend/src/onvif_client.py`: Added ONVIF discovery and stream resolution helpers
- `backend/src/gui/app.py`: Added IP Camera Discovery tab and handlers
- `backend/scripts/discover_cameras.py`: Discovery example script
- `backend/scripts/test_ip_camera_discovery.py`: Basic discovery test
- `docs/IP_CAMERA_DISCOVERY_README.md`: Complete usage guide
- `README.md`: Updated with GUI integration instructions

### Testing
- ✅ Discovery functionality verified (0 devices found on test network)
- ✅ Import errors resolved
- ✅ GUI integration tested
- ✅ XML parsing with namespaces working correctly

## ✅ FIXED: Zone Selector GUI Image Display

### Problem
The zone selector window was failing to display video frames with the error:
```
_tkinter.TclError: image "pyimage1" doesn't exist
```

This happened because PIL `ImageTk.PhotoImage` objects were being garbage collected before the tkinter Canvas could use them.

### Root Cause
1. PhotoImage objects created in local variables (e.g., `photo = ImageTk.PhotoImage(...)`)
2. Variable scope ended before Canvas.create_image() could execute
3. Python's garbage collector destroyed the image object
4. Canvas tried to reference non-existent image by name

### Solution
Store **both** the PIL Image and PhotoImage objects as instance variables:
```python
self.pil_image = Image.fromarray(frame_rgb)
self.photo = ImageTk.PhotoImage(image=self.pil_image)
```

This prevents garbage collection by maintaining strong references throughout the lifetime of the Canvas.

### Files Changed
- `src/gui/app.py`: ZoneSelectorWindow class
  - Added `self.pil_image = None` and `self.photo = None` to __init__
  - Changed display_frame() to store images in instance variables
  - Fixed Unicode print statements (✓ → [OK])

## ✅ System Architecture (Legacy Snapshot)

### Core Pipeline
1. **Detection**: YOLO26 object detector (person class)
2. **Tracking**: ByteTrack persistent tracking
3. **Zone Analysis**: PolygonZone for queue area detection
4. **Queueing Model**: M/M/1 theory for wait time estimation
5. **Visualization**: Real-time metrics overlay

### GUI Workflow (3-Step Process)
**Step 1**: Video Selection
- Browse file dialog
- Select from videos/ directory
- Next button validates file exists

**Step 2**: Model Configuration & Zone Selection
- Model size selector (nano/small/medium)
- Confidence threshold slider
- **Zone Selector Dialog**
  - Displays video frame
  - Click to define polygon vertices (min 3 points)
  - Shows numbered points and connecting lines
  - Reset/Done buttons

**Step 3**: Analysis & Review
- Review selected settings
- Start analysis button
- Progress display
- Results summary

### Key Components
```
src/
├── main.py                 # CLI entry point
├── detector.py            # YOLOv11 detector
├── tracker.py             # ByteTrack wrapper
├── zone_manager.py        # PolygonZone management
├── queue_analyzer.py      # M/M/1 queueing analysis
├── config.py              # Constants & configuration
├── utils/
│   ├── drawing.py         # Visualization (metrics overlay)
│   └── zone_selector.py   # Interactive zone selection utility
├── gui/
│   ├── __init__.py
│   └── app.py             # MainWindow & ZoneSelectorWindow
└── models/
    └── metadata.yaml      # YOLOv11 metadata

gui.py                      # Convenient launcher
videos/                     # Test videos
tests/                      # Unit tests
```

## ✅ Verified Working
- [x] Zone selector displays video frames without image errors
- [x] Main GUI window initializes successfully
- [x] Step workflow navigation (Step 1 → Step 2 → Step 3)
- [x] CLI video processing works (tested with retail_store.mp4)
- [x] Metrics calculation (λ, μ, W) produces reasonable values
- [x] Drawing utilities work (annotation, overlay, polygon drawing)
- [x] File I/O for video loading and processing

## Testing
Test scripts created:
- `test_gui.py` - Validates zone selector frame display (PASSES)
- `test_main_gui.py` - Validates main window initialization (PASSES)

## Next Steps
1. **Consolidated System Evaluation**: Run full-stack integration tests (Backend + Frontend + n8n).
2. **Deployment Hardening**: Finalize Docker Compose and environment isolation.
3. **Report Finalization**: Package all 4 sprint chapters with final evaluation results.

## Running the System

### GUI (Recommended)
```bash
python gui.py
```
Or: `python src/gui/app.py` followed by clicking through the 3-step workflow

### CLI
```bash
python src/main.py --video videos/retail_store.mp4 --model-size n --zone-points "100,100 600,100 600,400 100,400"
```

### Environment
- Python 3.10+
- All dependencies installed in virtual environment
- OpenCV for video processing
- YOLOv11 nano/small models pre-downloaded
