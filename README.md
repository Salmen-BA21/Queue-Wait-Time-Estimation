# Queue Wait-Time Estimation System

Real-time queue monitoring system for checkout lanes and service counters.

The project combines computer vision, queueing theory, uncertainty estimation, and alerting workflows:

- Person detection + tracking from video feeds
- Queue metrics estimation: arrival rate (lambda), service rate (mu), wait time (W)
- Bayesian uncertainty intervals and stability checks
- Desktop GUI workflow and web dashboard workflow
- n8n webhook integration for alert automation

## Start Here

1. Read [docs/agent-guide/INDEX.md](docs/agent-guide/INDEX.md) for the documentation map.
2. Read [docs/agent-guide/PROJECT_CONCEPT.md](docs/agent-guide/PROJECT_CONCEPT.md) for system concepts.
3. Read [docs/tracking/PROGRESS.md](docs/tracking/PROGRESS.md) for current delivery status.

## Tech Stack

| Layer | Stack |
|---|---|
| Vision pipeline | YOLO26 + ByteTrack + OpenCV |
| Queue analytics | numpy, pandas, scipy |
| Backend API | FastAPI + Pydantic v2 |
| Frontend | React + TypeScript + Vite + Tailwind |
| Automation | n8n webhook workflows |
| Persistence | CSV + SQLite metadata |

## Installation

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional GPU install (CUDA 12.4):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

## Run Modes

### 1. Desktop GUI mode

From repository root:

```bash
python gui.py
```

### 2. CLI analysis mode

Run from `backend/` so the `src` package resolves correctly:

```bash
cd backend
python -m src.main --source 0
```

Examples:

```bash
python -m src.main --source ../videos/test.mp4
python -m src.main --source rtsp://192.168.1.10:554/stream
python -m src.main --source ../videos/test.mp4 --zone-points '[[0.2,0.2],[0.8,0.2],[0.8,0.9],[0.2,0.9]]'
```

Show all CLI options:

```bash
python -m src.main --help
```

### 3. Web dashboard mode (API + frontend)

Backend API:

```bash
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

Optional WebRTC gateway for live preview (MediaMTX):

```bash
docker-compose up -d mediamtx
```

MediaMTX defaults used by the backend:

- WHEP/WebRTC: `http://127.0.0.1:8889`
- Control API: `http://127.0.0.1:9997`
- RTSP relay: `rtsp://127.0.0.1:8554/<stream_name>`

## IP Camera Discovery

The ONVIF discovery and stream-resolution helpers live in `backend/src/onvif_client.py`.

Programmatic example:

```python
from backend.src.onvif_client import discover_onvif_devices, get_rtsp_urls_from_onvif_device
from backend.src.rtsp_camera import RTSPCamera

devices = discover_onvif_devices(timeout=5.0)
for device in devices:
    urls = get_rtsp_urls_from_onvif_device(device, username="admin", password="password123")
    for url in urls:
        ok, info = RTSPCamera.test_connection(url, username="admin", password="password123")
        print(url, ok, info)
```

Useful scripts:

```bash
python backend/scripts/discover_cameras.py
python backend/scripts/test_ip_camera_discovery.py
python backend/scripts/test_ip_camera_gui_integration.py
```

Detailed guide: [docs/IP_CAMERA_DISCOVERY_README.md](docs/IP_CAMERA_DISCOVERY_README.md)

## n8n Integration

Start local support services (n8n + MediaMTX):

```bash
docker-compose up -d
```

Open `http://localhost:5678` and import workflow:

- Recommended: `n8n_workflow_with_telegram.json`
- Legacy minimal template: `n8n_workflow_template.json`

MediaMTX control and WebRTC endpoints (for debugging):

- Control API: `http://127.0.0.1:9997/v3/paths/list`
- WebRTC page: `http://127.0.0.1:8889/<path>`
- WHEP endpoint: `http://127.0.0.1:8889/<path>/whep`

Set secrets/variables in n8n:

- `WEBHOOK_SECRET`
- `TELEGRAM_CHAT_ID` (if Telegram node enabled)

Set backend environment variables:

- `N8N_WEBHOOK_URL` (default: `http://localhost:5678/webhook/queue-metrics`)
- `N8N_WEBHOOK_SECRET`
- `MEDIAMTX_WEBRTC_PREVIEW_ENABLED` (default: `true`)
- `MEDIAMTX_WHEP_BASE_URL` (default: `http://127.0.0.1:8889`)
- `MEDIAMTX_CONTROL_API_BASE_URL` (default: `http://127.0.0.1:9997`)
- `MEDIAMTX_WEBRTC_TIMEOUT_SEC` (default: `8.0`)

If go2rtc is still running locally, stop it before starting MediaMTX to avoid port conflicts.

Automated test runbook: [scripts/TEST_N8N.md](scripts/TEST_N8N.md)

## Repository Structure

```text
Queue-Wait-Time-Estimation/
├── backend/
│   ├── app.py
│   ├── src/
│   │   ├── api/
│   │   ├── gui/
│   │   ├── main.py
│   │   ├── onvif_client.py
│   │   ├── rtsp_camera.py
│   │   ├── queue_analyzer.py
│   │   ├── uncertainty.py
│   │   └── webhook_client.py
│   ├── tests/
│   └── scripts/
├── frontend/
├── docs/
├── scripts/
├── design/
├── report-latex/
├── gui.py
└── requirements.txt
```

## Documentation Index

- [docs/README.md](docs/README.md)
- [docs/API_FOR_FRONTEND.md](docs/API_FOR_FRONTEND.md)
- [docs/IP_CAMERA_DISCOVERY_README.md](docs/IP_CAMERA_DISCOVERY_README.md)
- [docs/tracking/MJPEG_STREAMING_MIGRATION.md](docs/tracking/MJPEG_STREAMING_MIGRATION.md)

## Author

Salmen Ben Ammar - PFE 2025-2026
