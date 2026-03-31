# 📋 Documentation Structure

This directory contains all project documentation, now standardized around **Sprint** terminology.

## 📁 Folder Organization

### 🔹 `/design/` ⭐ NEW
Web application UI/UX design documentation:
- **[README.md](../design/README.md)** – Quick-start guide for implementing the frontend
- **[DESIGN_SPEC.md](../design/DESIGN_SPEC.md)** – Complete technical design specification (7 pages)
- **QueueVision Design.pen** – Pencil design file (use Pencil MCP tools to view)

### 🔹 `/sprints/` (primary)
Sprint-specific planning and execution documentation:
- **README.md** – Sprint model and usage notes
- **SPRINT_MAPPING.md** – Legacy phase-to-sprint mapping
- **SPRINT4_SUMMARY.md** – Uncertainty quantification completion summary
- **SPRINT5_SETUP.md** – n8n integration setup guide

### 🔹 `/tracking/`
Project progress and status tracking:
- **PROGRESS.md** – Overall project progress report with sprint completion status
- **STATUS_REPORT.md** – Status updates on specific issues/fixes
- **WEB_APP_GUI_PARITY_PLAN.md** – Remaining work to bring the web app to full desktop GUI feature parity
- **MJPEG_STREAMING_MIGRATION.md** – Snapshot polling to MJPEG streaming migration details
	- Includes March 31 updates for GPU device selection, source-FPS playback pacing, and smoothness tuning defaults.

### 🔹 `/daily-logs/`
Daily development logs (legacy filenames may still use "Phase"):
- `2026-02-12__Phase1__Core_Detection_and_Queue_Logic.md`
- `2026-02-16__Phase2__GUI_Stability_Fixes.md`
- `2026-02-16__Phase3__YOLO26_Migration.md`
- `2026-02-18__Phase4__Uncertainty_Quantification.md`
- `TEMPLATE.md` – Template for creating new daily logs (Sprint format)

### 🔹 `/archive/phases/` (legacy archive)
Legacy phase documents are archived to preserve history. New updates should be written in `/sprints/`.

## 🎯 Quick Navigation

- **Getting Started?** → Start with `agent-guide/INDEX.md`
- **Implementing the Web Frontend?** → See `design/README.md` then `design/DESIGN_SPEC.md`
- **Tracking Progress?** → See `tracking/PROGRESS.md`
- **Planning GUI-to-Web parity?** → See `tracking/WEB_APP_GUI_PARITY_PLAN.md`
- **Looking for live stream transport changes?** → See `tracking/MJPEG_STREAMING_MIGRATION.md`
- **Understanding a Sprint?** → Check `sprints/` or `daily-logs/`
- **Checking Recent Work?** → See `tracking/STATUS_REPORT.md` or latest in `daily-logs/`

- **Backend API:** The backend BFF REST API and websocket (`/ws/metrics`) are implemented in `backend/src/api/`, and the typed frontend client is implemented in `frontend/src/lib/api.ts`.

---

*Last organized: March 31, 2026*

## Development — Running locally

Follow these steps to launch the development backend and frontend on a developer machine.

- **Backend (Windows PowerShell)**:
	- Create a virtual environment (only once):
		- `python -m venv .venv`
	- Activate the environment:
		- PowerShell: `.venv\Scripts\Activate.ps1`
	- Install dependencies:
		- `pip install -r requirements.txt`
	- Start the FastAPI development server (auto-reload):
		- `uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000`
	- The backend API will be available at `http://127.0.0.1:8000` and the OpenAPI UI at `http://127.0.0.1:8000/docs`.

- **Frontend (Windows PowerShell / any shell)**:
	- Change into the frontend folder:
		- `cd frontend`
	- Install node dependencies (only once or after package changes):
		- `npm install`
	- Start the Vite dev server:
		- `npm run dev`
	- By default Vite serves the app on `http://localhost:5173`. The frontend is configured to allow CORS from common dev origins.

- **Notes**:
	- If you prefer a different frontend port, set the `PORT` environment variable before running `npm run dev`.
	- If running the backend on a remote machine, update the frontend API base URL to point to the backend host and ensure CORS and network access are permitted.
