# 📋 Documentation Structure

This directory contains all project documentation, now standardized around **Sprint** terminology.

## 📁 Folder Organization

### 🔹 `/design/` ⭐ NEW
Web application UI/UX design documentation:
- **[README.md](../design/README.md)** – Quick-start guide for implementing the frontend
- **[DESIGN_SPEC.md](../design/DESIGN_SPEC.md)** – Complete technical design specification (7 pages)
- **pencil-new.pen** – Pencil design file (use Pencil MCP tools to view)

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
- **Understanding a Sprint?** → Check `sprints/` or `daily-logs/`
- **Checking Recent Work?** → See `tracking/STATUS_REPORT.md` or latest in `daily-logs/`

---

*Last organized: February 27, 2026*
