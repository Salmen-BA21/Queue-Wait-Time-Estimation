# 🤖 Agent Context – Current Project Status

**⚠️ START HERE** – Read this file first, then refer to [../tracking/PROGRESS.md](../tracking/PROGRESS.md) for full details.

---

## 📍 Current Sprint

**Sprint 11 – Web Application Integration & Stabilization**
**Status:** IN PROGRESS 🔄

- ✅ Design completed (Sprint 10)
- ✅ 7 pages implemented in React + TypeScript (Mar 4)
  - Landing Page, Dashboard, Login, Settings, Zone Editor, Analytics, NotFound
- ✅ 55+ shadcn/ui components scaffolded
- ✅ Layout system created (AppLayout, AppSidebar, TopBar)
- ✅ Tailwind CSS configured
- ✅ Routing structure in place with React Router
- ✅ Testing setup (Vitest)
- ✅ Typed frontend API client implemented (`frontend/src/lib/api.ts`)
- ✅ Backend REST + websocket BFF implemented (`backend/src/api/` + `/ws/metrics`)
- ⏳ Remaining frontend wiring polish and end-to-end validation

**Also Completed (Sprint 5 Enhancement):**
- ✅ RTSP camera support with authentication (Mar 5)
- ✅ IP camera connection testing and UI management
- ✅ Transport protocol options (TCP/UDP)

---

## 🎯 Next Immediate Tasks
1. **Complete Dashboard Runtime Wiring:** Continue UX/state polish for live metrics and feed-state transitions.
2. **Telegram Bot Setup:** Complete Sprint 5 by finishing Telegram credential/config onboarding in n8n.
3. **Frontend Testing:** Expand integration/E2E coverage for API and websocket flows.
4. **Deployment Setup:** Finalize Docker/full-stack deployment profile (frontend + backend + n8n).

---

## ✅ What's Already Done

- **Sprints 0-4:** Core functionality for detection, tracking, and queue analytics ✅
- **Sprint 7:** Dashboard GUI (Tkinter) implemented ✅
- **Sprint 10:** Complete web UI/UX design (7 pages in Pencil) ✅
- **Sprint 11:** Frontend pages & components implemented (React + TypeScript) ✅ ⭐ NEW
- **RTSP Support:** IP camera authentication and management ✅ ⭐ NEW
- **n8n integration:** Webhook + CSV logging ✅
- **Queue analysis:** YOLO26 + ByteTrack + zone detection ✅
- **Queue stability handling:** Stable/unstable runtime interpretation ✅
- **Multi-video support:** GUI with per-video zones ✅

---

## 📁 Project Structure

```
design/                    ⭐ WEB DESIGN
  ├── README.md              (Quick-start guide)
  ├── DESIGN_SPEC.md         (Full technical design spec – 7 pages)
  └── QueueVision Design.pen (Pencil MCP design file – DO NOT read with text tools)

backend/                   ⭐ PYTHON BACKEND
  ├── src/
  │   ├── main.py             (Entry point + analysis pipeline)
  │   ├── rtsp_camera.py      (IP camera support) ← NEW
  │   ├── queue_analyzer.py   (Core queue metrics)
  │   ├── detector.py         (YOLO26 detection)
  │   ├── tracker.py          (ByteTrack tracking)
  │   ├── webhook_client.py   (n8n integration)
  │   ├── threshold_detector.py (Alert logic)
  │   ├── video_capture.py    (Video source handling)
  │   ├── zone_manager.py     (Zone filtering)
  │   ├── config.py           (Configuration)
  │   ├── csv_logger.py       (CSV backup)
  │   ├── gui/app.py          (Tkinter GUI)
  │   └── utils/              (Drawing, logging, zone selector)
  ├── scripts/
  │   └── test_connection.py  (Test RTSP connections) ← NEW
  └── requirements.txt

frontend/                  ⭐ REACT FRONTEND
  ├── src/
  │   ├── pages/              (7 application pages)
  │   │   ├── LandingPage.tsx
  │   │   ├── Dashboard.tsx
  │   │   ├── Login.tsx
  │   │   ├── SettingsPage.tsx
  │   │   ├── ZoneEditor.tsx
  │   │   ├── Analytics.tsx
  │   │   └── NotFound.tsx    ← ALL NEW (Mar 4)
  │   ├── components/
  │   │   ├── ui/             (55+ shadcn/ui components)
  │   │   └── layout/         (AppLayout, AppSidebar, TopBar)
  │   ├── hooks/              (use-mobile, use-toast)
  │   ├── App.tsx
  │   └── main.tsx
  ├── package.json
  ├── vite.config.ts          (Build config)
  ├── tailwind.config.ts       (Tailwind setup)
  └── tsconfig.json

docs/
  ├── README.md               (Documentation index)
  ├── agent-guide/            (Agent onboarding docs)
  ├── tracking/
  │   ├── PROGRESS.md         (Sprint-by-sprint status)
  │   └── STATUS_REPORT.md    (Recent fixes & architecture)
  ├── sprints/                (Sprint-specific deep dives)
  └── daily-logs/             (Development history)
```

---

## 🔑 Key Files For Current Sprint (Frontend-Backend Integration)

| File | Purpose |
|------|---------|
| [../../frontend/src/pages/Dashboard.tsx](../../frontend/src/pages/Dashboard.tsx) | Main dashboard page (needs backend API integration) |
| [../../frontend/src/pages/SettingsPage.tsx](../../frontend/src/pages/SettingsPage.tsx) | Settings UI (maps to `backend/src/config.py`) |
| [../../frontend/src/pages/ZoneEditor.tsx](../../frontend/src/pages/ZoneEditor.tsx) | Zone polygon editor (maps to zone management) |
| [../../frontend/src/pages/Analytics.tsx](../../frontend/src/pages/Analytics.tsx) | Historical analytics (maps to queue metrics and trends) |
| [../../backend/src/config.py](../../backend/src/config.py) | Configuration management |
| [../../backend/src/queue_analyzer.py](../../backend/src/queue_analyzer.py) | Core metrics calculation |
| [../../backend/src/rtsp_camera.py](../../backend/src/rtsp_camera.py) | RTSP camera support (NEW) |
| [../../backend/src/threshold_detector.py](../../backend/src/threshold_detector.py) | Alert threshold and severity logic |
| [../../docker-compose.yml](../../docker-compose.yml) | Multi-service orchestration (Python + Frontend + n8n) |

---

## 📈 Project Completion

- **Completed:** Sprints 0, 1, 2, 3, 4, 10, 11 (7 sprints = ~65%)
- **In Progress:** Sprint 5 (~95% complete, missing Telegram bot), Sprint 7 (mostly complete), Sprint 8 (partially complete)
- **Not Started:** Sprints 6 and 9
- **Overall:** ~68% complete

---

## 🚀 Getting Started If You're New

1. **See the reading roadmap:** [INDEX.md](INDEX.md) ← **START HERE**
2. **Understand the big picture:** [PROJECT_CONCEPT.md](PROJECT_CONCEPT.md)
3. **Quick status reference:** [AGENT_CONTEXT.md](AGENT_CONTEXT.md) (this file)
4. **Read full status:** [../tracking/PROGRESS.md](../tracking/PROGRESS.md)
5. **Understand backend modules:** Check [../sprints/SPRINT4_SUMMARY.md](../sprints/SPRINT4_SUMMARY.md) and [../sprints/SPRINT5_SETUP.md](../sprints/SPRINT5_SETUP.md)
6. **Check recent issues & architecture:** [../tracking/STATUS_REPORT.md](../tracking/STATUS_REPORT.md)
7. **See daily logs:** [../daily-logs/](../daily-logs/)
8. **Frontend setup:** Read `frontend/README.md` for development environment

---

**Last Updated:** March 31, 2026

