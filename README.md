# 🕐 Queue Wait-Time Estimation System

> **PFE – Conception et développement d'un système multi-agents pour l'estimation du temps d'attente aux caisses à partir de flux vidéo, avec quantification d'incertitude**

> ⚠️ **New to this project?** 
> 1. Start with [docs/agent-guide/INDEX.md](docs/agent-guide/INDEX.md) for the reading roadmap
> 2. Then read [docs/agent-guide/PROJECT_CONCEPT.md](docs/agent-guide/PROJECT_CONCEPT.md) to understand the **complete idea**
> 3. Then read [docs/agent-guide/AGENT_CONTEXT.md](docs/agent-guide/AGENT_CONTEXT.md) for **current status**
> 4. Finally, see [docs/tracking/PROGRESS.md](docs/tracking/PROGRESS.md) for **full details**

Real-time queue monitoring for supermarket / bank checkouts using a video feed.  
Detects people, tracks them across frames, counts how many stand inside a configurable queue zone, and estimates **arrival rate (λ)**, **service rate (μ)** and **expected waiting time (W)** – with **Bayesian uncertainty quantification** providing confidence intervals for all metrics.

---

## 📦 Tech Stack

| Component | Library |
|-----------|---------|
| Object detection | Ultralytics YOLO26 (nano / small) |
| Tracking | supervision ByteTrack |
| Video I/O | OpenCV |
| Zone logic | supervision PolygonZone |
| Queueing math | numpy / pandas |
| Uncertainty quantification | scipy.stats (Bayesian Gamma) |
| GUI | tkinter / customtkinter |
| Alerting | n8n webhook via `requests` |
| Logging | CSV files, JSON webhooks |

---

## 📹 IP Camera Discovery

**Automatically discover and configure IP cameras on your network!**

This feature works like network device discovery tools - it finds IP cameras without needing to know their addresses in advance.

### Key Capabilities

- **Broad Compatibility**: Works with cameras that expose ONVIF media service AND cameras that don't (via automatic fallback)
- **Dual Discovery Method**: 
  - Primary: ONVIF media service (standard method)
  - Fallback: Automatic testing of common RTSP paths (`/profile1`, `/live/main`, etc.) 
- **Credential Support**: Test streams with username/password authentication

### GUI Integration

The discovery feature is fully integrated into the GUI application:

1. **Launch the GUI**: `python -m backend.src.gui.app`
2. **Step 1**: Select "IP Camera Discovery" tab
3. **Discover**: Click "🔍 Discover Cameras" to scan your network
4. **Select & Test**: Choose cameras from the list and test connections with credentials
5. **Add to Analysis**: Add discovered cameras to your monitoring setup

### Programmatic Usage

```python
from backend.src.rtsp_camera import RTSPCamera

# Discover all IP cameras on your network
devices = RTSPCamera.discover_onvif_devices()

for device in devices:
    print(f"Found: {device['name']} ({device['manufacturer']} {device['model']})")
    print(f"IP: {device['ip']}")

    # Get RTSP stream URLs (works even without media service)
    rtsp_urls = RTSPCamera.get_rtsp_urls_from_onvif_device(
        device,
        username="admin",
        password="password123"
    )
    for url in rtsp_urls:
        print(f"Stream: {url}")
```

### Try it out

```bash
# Run the GUI with IP camera discovery
python -m backend.src.gui.app

# Or run the discovery example
python backend/scripts/discover_cameras.py

# Or run the basic test
python backend/scripts/test_ip_camera_discovery.py
```

### Documentation

📖 [Complete IP Camera Discovery Guide](docs/IP_CAMERA_DISCOVERY_README.md)

---

## 🚀 Installation

### 1. Create a Python virtual environment (venv)

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **GPU support (optional):**  
> If you have an NVIDIA GPU, install the CUDA-enabled PyTorch wheel *before* the other dependencies. Recommended build for this project: **CUDA 12.4**.
> ```bash
> pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
> ```
> Verify GPU availability:
> ```bash
> python -c "import torch; print('GPU available:', torch.cuda.is_available())"
> ```
> **Recommended Python:** 3.10 (best-tested). Python 3.13 may require manual wheel selection for some libraries.

---

## 🐳 N8n Workflow Automation

This project integrates with [n8n](https://n8n.io/) for workflow automation and alerting. The system sends webhook data every 5 seconds with queue metrics.

### Running n8n with Docker

1. **Install Docker** (if not already installed)

2. **Start n8n container:**
   ```bash
   docker-compose up -d
   ```

3. **Access n8n web interface:**
   - Open http://localhost:5678
   - Login with: `admin` / `password`

4. **Import the workflow template:**
   - In n8n, click "Import" → "Upload" → select `n8n_workflow_template.json`
   - Configure webhook URL in the workflow to match your setup

5. **Stop the container:**
   ```bash
   docker-compose down
   ```

The Docker setup includes persistent data storage and mounts the workflow template for easy import.

---

## ▶️ Quick Start

### Webcam (default)

```bash
python -m src.main
```

### Video file

```bash
python -m src.main --source videos/test.mp4
```

### RTSP stream

```bash
python -m src.main --source rtsp://192.168.1.10:554/stream
```

### Custom zone polygon

```bash
python -m src.main --source videos/test.mp4 \
    --zone-points '[[100,200],[400,200],[400,600],[100,600]]'
```

### GUI (Graphical interface)

```bash
# Activate the project's virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Start the GUI launcher
python gui.py
```

- **Multi-video support**: choose how many camera feeds to analyse, pick that many files, and define a separate cashier zone for each.
- Quick flow: `Set video count` → `Browse files` → `Configure model & zones (per video)` → `Run Analysis`.
- Each video launches in its **own console window**, so all feeds are processed simultaneously without interference.
- Real-time dashboard showing queue length, wait time, uncertainty levels, and confidence intervals.

### All options

```
python -m src.main --help
```

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `0` | Webcam index, file path, or RTSP URL |
| `--model-size` | `n` | YOLO model: `n`, `s`, `m`, `l`, `x` |
| `--zone-points` | full frame | JSON `[[x,y], …]` polygon |
| `--output-fps` | `30` | Display refresh rate |
| `--log-interval-sec` | `5` | Console log frequency (seconds) |
| `--log-level` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

Press **`q`** in the OpenCV window to quit.

**Display includes:** bounding boxes, track IDs, zone polygon, queue count, arrival/service rates, wait time with confidence intervals, uncertainty level (Low/Medium/High), and stability indicator.

---

## 🏗️ Project Structure

```
Queue-Wait-Time-Estimation/
├── src/
│   ├── __init__.py
│   ├── main.py               # entry point + argparse
│   ├── config.py              # constants & AppConfig dataclass
│   ├── video_capture.py       # VideoStream wrapper
│   ├── detector.py            # YOLO26 person detector
│   ├── tracker.py             # ByteTrack wrapper
│   ├── zone_manager.py        # PolygonZone management
│   ├── queue_analyzer.py      # λ, μ, W estimation + uncertainty
│   ├── uncertainty.py         # Bayesian uncertainty quantification
│   ├── webhook_client.py      # n8n webhook sender
│   ├── csv_logger.py          # CSV backup logging
│   ├── threshold_detector.py  # Queue threshold detection
│   └── utils/
│       ├── drawing.py         # annotators & overlay helpers
│       ├── logging_setup.py   # logging configuration
│       └── zone_selector.py   # GUI zone selection tool
│   └── gui/
│       └── app.py             # GUI dashboard & multi-video launcher
├── docs/
│   └── daily-logs/            # development logs
├── scripts/
│   ├── test_n8n_webhook.py    # webhook testing
│   └── ...
├── n8n_workflow_template.json # sample n8n workflow
├── requirements.txt
├── README.md
├── PHASE_TRACKING.md
├── PROGRESS.md
├── STATUS_REPORT.md
├── gui.py                     # GUI launcher script
├── test_gui_app.py            # GUI unit tests
├── test_uncertainty.py        # uncertainty unit tests
├── yolo26l.pt                 # YOLO model weights
├── yolo26x.pt
└── run_dev.sh
```

---

## 🗺️ Roadmap

- [x] YOLO26 person detection + ByteTrack tracking
- [x] Configurable polygon queue zone
- [x] Real-time λ / μ / W estimation (M/M/1 model)
- [x] **Uncertainty quantification** – Bayesian rate estimation, confidence intervals
- [x] **GUI dashboard** – Multi-video support, zone configuration
- [x] **CSV logging** – Persist metrics to local files
- [x] **n8n webhook integration** – Send JSON data every 5 seconds
- [ ] **Multi-zone** support (several queues at once)
- [ ] **Telegram alerts** – n8n integration for notifications
- [ ] **Streamlit dashboard** – Advanced visualization with time series
- [ ] **Edge deployment** – ONNX / TensorRT export
- [ ] **Comprehensive testing** – Various scenarios and evaluation

---

## 📝 License

Academic project – Université Sesame, Tunisia.

---

## 👤 Author

**Salmen Ben Ammar** – PFE 2025-2026
