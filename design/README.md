# 🎨 Design Guide – For the Next Agent

**⚠️ READ THIS FIRST** if you are implementing the QueueVision web frontend.

---

## 📍 What Was Done

A complete UI/UX design for the **QueueVision** web application was created using **Pencil MCP** (`.pen` format). The design covers **7 pages** — from a public landing page to all admin screens needed for the queue monitoring system.

### Design File Location

- **File:** `QueueVision Design.pen` (inside `design/`)
- **Tool:** Pencil MCP — the file is encrypted and can ONLY be read using Pencil MCP tools (`batch_get`, `get_screenshot`, `snapshot_layout`, etc.)
- **DO NOT** try to read the `.pen` file with `read_file` or `grep_search` — it will return encrypted data

### Full Specification

- **Detailed spec:** [`design/DESIGN_SPEC.md`](../design/DESIGN_SPEC.md) — Contains complete documentation of every page, component, color, font, layout, and implementation guidance
- **Reading time:** 20–30 minutes

---

## 📐 The 7 Pages

| # | Page | Purpose | Route |
|---|------|---------|-------|
| 1 | **Landing Page** | Public marketing page | `/` |
| 2 | **Dashboard** | Real-time monitoring (cameras, alerts, metrics) | `/dashboard` |
| 3 | **Setup Wizard** | First-time onboarding (add cameras, step-by-step) | `/setup` |
| 4 | **Zone Editor** | Draw detection zones on camera feeds | `/setup/zones` |
| 5 | **Historical Analytics** | Charts, KPIs, trend analysis | `/analytics` |
| 6 | **Settings / Config** | Application configuration | `/settings` |
| 7 | **Heatmap Overlay** | Density/dwell time visualization | `/heatmap` |

---

## 🎨 Design System Summary

### Colors (Dark Theme – "Terminal Minimal")

| Token | Hex | Use |
|-------|-----|-----|
| Background | `#0A0F1C` | Page background |
| Card | `#1E293B` | Card/panel surfaces |
| Border | `#334155` | Borders, dividers |
| Cyan | `#22D3EE` | Primary accent, buttons, links |
| Amber | `#F59E0B` | Warnings, zone editor |
| Red | `#EF4444` | Critical alerts, errors |
| Purple | `#A78BFA` | Uncertainty, analytics |
| Green | `#10B981` | Success, online status |
| Text | `#F1F5F9` | Primary text |
| Secondary | `#94A3B8` | Body text, labels |
| Muted | `#64748B` | Placeholders, disabled |

### Fonts

- **Inter** – UI text, headings, labels (400–700 weight)
- **JetBrains Mono** – Data values, KPIs, metrics, code (400–700 weight)

---

## 🚀 What You Need To Do

### Step 1: Choose a Framework
The design was built for a modern web stack. Recommended:
- **Next.js 14+** (App Router) or **React + Vite**
- **Tailwind CSS** — color tokens map directly to design
- **Lucide React** — icons used throughout
- **Recharts** or **Chart.js** — for analytics charts

### Step 2: Read the Full Spec
Read [`design/DESIGN_SPEC.md`](../design/DESIGN_SPEC.md) for:
- Complete layout diagrams for each page
- Component breakdown with descriptions
- Tailwind config with exact color mapping
- TypeScript data models
- Suggested API endpoints
- Component hierarchy tree

### Step 3: Reference the Design Visually
Use Pencil MCP tools to see the designs:
```
get_screenshot(nodeId)    → See a page visually
batch_get(patterns)       → Read component structure
snapshot_layout()         → Get computed layout rectangles
```

Node IDs for screenshots:
- Landing: `tvmWe`
- Dashboard: `OPPgB`
- Setup Wizard: `8QJyT`
- Zone Editor: `y64OV`
- Analytics: `RraID`
- Settings: `XJlxs`
- Heatmap: `SU8Ec`

### Step 4: Connect to Backend
The existing Python backend (`backend/src/`) provides:
- YOLO26 detection + ByteTrack tracking
- M/M/1 queue analysis with Bayesian uncertainty
- Webhook client for n8n integration
- CSV logging

The web frontend should:
1. Use existing REST endpoints in `backend/src/api/app.py`
2. Consume websocket events from `/ws/metrics`
3. Implement zone drawing with HTML5 Canvas API
4. Build chart components from metrics data and live updates

---

## ⚠️ Important Notes

1. The design is **admin-focused** — all pages except landing require authentication
2. The Zone Editor is both a **wizard step** AND an **inline edit tool** (accessible from dashboard)
3. The heatmap uses **AI-generated images** in the design — implement with real computed heatmaps using canvas overlays
4. Charts in the design are **placeholders** — implement with real data from the queue metrics CSV files
5. The Settings page has a **sidebar navigation** — each nav item shows different form sections
6. Camera grid on dashboard shows **4 feeds max** in the design, but should support dynamic count

---

## 📁 Related Files

| File | Purpose |
|------|---------|
| `design/DESIGN_SPEC.md` | Complete technical design specification |
| `QueueVision Design.pen` | Pencil design file (use MCP tools to view) |
| `backend/src/config.py` | Backend configuration (maps to Settings page) |
| `backend/src/queue_analyzer.py` | Queue metrics (maps to Dashboard KPIs) |
| `backend/src/uncertainty.py` | Uncertainty calculations (maps to Analytics confidence intervals) |
| `backend/src/threshold_detector.py` | Alert logic (maps to Dashboard alert sidebar) |
| `backend/src/webhook_client.py` | n8n integration (maps to Settings webhook section) |
| `data/*.csv` | Historical metrics (maps to Analytics charts) |

---

*Last Updated: February 27, 2026*
