# 🕐 Queue Wait-Time Estimation System

> **PFE – Conception et développement d'un système multi-agents pour l'estimation du temps d'attente aux caisses à partir de flux vidéo, avec quantification d'incertitude**

Real-time queue monitoring for supermarket / bank checkouts using a video feed.  
Detects people, tracks them across frames, counts how many stand inside a configurable queue zone, and estimates **arrival rate (λ)**, **service rate (μ)** and **expected waiting time (W)** – with uncertainty quantification coming soon.

---

## 📦 Tech Stack

| Component | Library |
|-----------|---------|
| Object detection | Ultralytics YOLO26 (nano / small) |
| Tracking | supervision ByteTrack |
| Video I/O | OpenCV |
| Zone logic | supervision PolygonZone |
| Queueing math | numpy / pandas |
| Alerting (future) | n8n webhook via `requests` |

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

- Quick flow: `Select Video` → `Select Zone from Video` (draw polygon) → `Run Analysis`.
- The GUI spawns the processing backend in a separate console window so the interface remains responsive.

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

---

## 🏗️ Project Structure

```
Stage_PFE/
├── src/
│   ├── __init__.py
│   ├── main.py               # entry point + argparse
│   ├── config.py              # constants & AppConfig dataclass
│   ├── video_capture.py       # VideoStream wrapper
│   ├── detector.py            # YOLO26 person detector
│   ├── tracker.py             # ByteTrack wrapper
│   ├── zone_manager.py        # PolygonZone management
│   ├── queue_analyzer.py      # λ, μ, W estimation
│   ├── uncertainty.py         # (placeholder) uncertainty quantification
│   └── utils/
│       ├── drawing.py         # annotators & overlay helpers
│       └── logging_setup.py   # logging configuration
├── videos/                    # test videos (git-ignored)
├── data/                      # CSV logs (git-ignored)
├── notebooks/                 # Jupyter experiments
├── requirements.txt
├── README.md
├── .gitignore
└── run_dev.sh
```

---

## 🗺️ Roadmap

- [x] YOLO26 person detection + ByteTrack tracking
- [x] Configurable polygon queue zone
- [x] Real-time λ / μ / W estimation (M/M/1 model)
- [ ] **Uncertainty quantification** – Bayesian rate estimation, bootstrap CI
- [ ] **Multi-zone** support (several queues at once)
- [ ] **n8n webhook integration** – send JSON alerts in real time
- [ ] **Dashboard** – Streamlit / Grafana visualisation
- [ ] **CSV logging** – persist metrics to `data/`
- [ ] **Multi-camera** support
- [ ] **Edge deployment** – ONNX / TensorRT export

---

## 📝 License

Academic project – Université Sesame, Tunisia.

---

## 👤 Author

**Salmen Ben Ammar** – PFE 2025-2026
