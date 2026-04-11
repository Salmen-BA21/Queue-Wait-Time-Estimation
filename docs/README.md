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
- **SPRINT4_SUMMARY.md** – Historical summary of legacy uncertainty work
- **SPRINT5_SETUP.md** – n8n integration setup guide

### 🔹 `/tracking/`
Project progress and status tracking:
- **PROGRESS.md** – Overall project progress report with sprint completion status
- **STATUS_REPORT.md** – Status updates on specific issues/fixes
- **WEB_APP_GUI_PARITY_PLAN.md** – Remaining work to bring the web app to full desktop GUI feature parity
- **MJPEG_STREAMING_MIGRATION.md** – Snapshot polling to MJPEG streaming migration details
	- Includes March 31 updates for GPU device selection, source-FPS playback pacing, and smoothness tuning defaults.

### 🔹 Root docs in `/docs/`
Canonical cross-cutting references:
- **API_FOR_FRONTEND.md** – Canonical REST/WebSocket/frontend contract (includes auth/RBAC endpoints)
- **WEBRTC_PREVIEW_SETUP.md** – WebRTC signaling flow, MediaMTX setup, fallback policy, and troubleshooting

### 🔹 `/daily-logs/`
Daily development logs (legacy filenames may still use "Phase"):
- `2026-02-12__Phase1__Core_Detection_and_Queue_Logic.md`
- `2026-02-16__Phase2__GUI_Stability_Fixes.md`
- `2026-02-16__Phase3__YOLO26_Migration.md`
- `2026-02-18__Phase4__Uncertainty_Quantification.md` (historical record)
- `TEMPLATE.md` – Template for creating new daily logs (Sprint format)

### 🔹 `/archive/phases/` (legacy archive)
Legacy phase documents are archived to preserve history. New updates should be written in `/sprints/`.

## 🎯 Quick Navigation

- **Getting Started?** → Start with `agent-guide/INDEX.md`
- **Implementing the Web Frontend?** → See `design/README.md` then `design/DESIGN_SPEC.md`
- **Tracking Progress?** → See `tracking/PROGRESS.md`
- **Planning GUI-to-Web parity?** → See `tracking/WEB_APP_GUI_PARITY_PLAN.md`
- **Looking for current live transport behavior?** → See `WEBRTC_PREVIEW_SETUP.md`
- **Looking for historical snapshot-to-MJPEG migration details?** → See `tracking/MJPEG_STREAMING_MIGRATION.md`
- **Understanding a Sprint?** → Check `sprints/` or `daily-logs/`
- **Checking Recent Work?** → See `tracking/STATUS_REPORT.md` or latest in `daily-logs/`
- **Need full backend/frontend API contract?** → See `API_FOR_FRONTEND.md` (includes signup/signin and admin manager-account APIs)

- **Backend API:** The backend BFF REST API and websocket (`/ws/metrics`) are implemented in `backend/src/api/`, and the typed frontend client is implemented in `frontend/src/lib/api.ts`.

---

*Last organized: April 11, 2026*

## Development — Running locally

Use the root setup guide to avoid duplicated run instructions:

- Project installation and run modes: `../README.md`
- Frontend-specific local workflow: `../frontend/README.md`
