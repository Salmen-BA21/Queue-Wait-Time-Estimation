# 🤖 Agent Context – Current Project Status

**⚠️ START HERE** – Read this file first, then refer to [../tracking/PROGRESS.md](../tracking/PROGRESS.md) for full details.

---

## 📍 Current Sprint

**Sprint 10 – Web Application UI/UX Design**  
**Status:** COMPLETED ✅

- ✅ Complete design system created ("Terminal Minimal" dark theme)
- ✅ 7 pages designed in Pencil MCP (1440×900px each)
- ✅ Landing Page, Dashboard, Setup Wizard, Zone Editor, Analytics, Settings, Heatmap
- ✅ Design specification written (`design/DESIGN_SPEC.md`)
- ✅ Agent handoff guide written (`design/README.md`)
- ✅ All pages verified with screenshots

**Next Up: Implement Web Frontend from Design Specs**

---

## 🎯 Next Immediate Tasks

1. **Implement Web Frontend:** Build React/Next.js app from `design/DESIGN_SPEC.md` — see `design/README.md` for full guide
2. **Create REST API:** Wrap existing Python backend in API endpoints for the web app
3. **Complete Sprint 5:** Implement Telegram bot setup and integration with n8n
4. **Sprint 6:** Define alert persistence rules and implement inline Telegram buttons

---

## ✅ What's Already Done

- **Sprints 0-4:** Core functionality with uncertainty quantification ✅
- **Sprint 7:** Dashboard GUI implemented ✅
- **Sprint 10:** Complete web UI/UX design (7 pages) ✅ ⭐ NEW
- **n8n integration:** Webhook + CSV logging ✅
- **Queue analysis:** YOLO26 + ByteTrack + zone detection ✅
- **Uncertainty quantification:** Bayesian Gamma distributions ✅
- **Multi-video support:** GUI with per-video zones ✅

---

## 📁 Project Structure

```
design/                    ⭐ WEB DESIGN (NEW)
  ├── README.md              (Quick-start guide for frontend implementation)
  ├── DESIGN_SPEC.md         (Full technical design spec – 7 pages)
  └── pencil-new.pen         (Pencil MCP design file – DO NOT read with text tools)

docs/
  ├── README.md              (📖 Documentation index)
  ├── agent-guide/           (Agent onboarding docs)
  ├── tracking/
  │   ├── PROGRESS.md        (📊 FULL PROJECT STATUS - READ THIS)
  │   ├── STATUS_REPORT.md   (🐛 Issue fixes and architecture)
  ├── sprints/
  │   ├── SPRINT4_SUMMARY.md (Uncertainty implementation details)
  │   ├── SPRINT5_SETUP.md   (n8n setup guide)
  │   └── SPRINT_MAPPING.md  (legacy phase mapping)
  └── daily-logs/            (Development logs)

src/
  ├── main.py                (Entry point)
  ├── queue_analyzer.py      (Core queue metrics)
  ├── detector.py            (YOLO26 detection)
  ├── tracker.py             (ByteTrack tracking)
  ├── uncertainty.py         (Bayesian calculations)
  ├── webhook_client.py      (n8n integration)
  ├── threshold_detector.py  (Alert logic)
  ├── csv_logger.py          (CSV backup)
  └── gui/app.py             (Multi-video GUI)
```

---

## 🔑 Key Files For Next Sprint (Web Frontend Implementation)

| File | Purpose |
|------|---------|
| [../../design/DESIGN_SPEC.md](../../design/DESIGN_SPEC.md) | Complete design specification with layouts, colors, components, TypeScript models |
| [../../design/README.md](../../design/README.md) | Quick-start guide for frontend implementation |
| [../../pencil-new.pen](../../pencil-new.pen) | Pencil design file (use Pencil MCP tools to view) |
| [../../src/config.py](../../src/config.py) | Backend configuration (maps to Settings page) |
| [../../src/queue_analyzer.py](../../src/queue_analyzer.py) | Queue metrics logic (maps to Dashboard KPIs) |
| [../../src/uncertainty.py](../../src/uncertainty.py) | Uncertainty calculations (maps to Analytics CI bands) |
| [../../src/threshold_detector.py](../../src/threshold_detector.py) | Alert logic (maps to Dashboard alert sidebar) |

---

## 📈 Project Completion

- **Completed:** Sprints 0, 1, 2, 3, 4, 10 (6 sprints = ~55%)
- **In Progress:** Sprint 5 (~90% complete, missing Telegram), Sprint 7 (mostly complete), Sprint 8 (partially complete)
- **Not Started:** Sprints 6 and 9
- **Overall:** ~60% complete

---

## 🚀 Getting Started If You're New

1. **See the reading roadmap:** [INDEX.md](INDEX.md) ← **START HERE**
2. **Understand the big picture:** [PROJECT_CONCEPT.md](PROJECT_CONCEPT.md)
3. **Quick status reference:** [AGENT_CONTEXT.md](AGENT_CONTEXT.md) (this file)
4. **Read full status:** [../tracking/PROGRESS.md](../tracking/PROGRESS.md)
5. **Understand Sprint 5:** [../sprints/SPRINT5_SETUP.md](../sprints/SPRINT5_SETUP.md)
6. **Check recent issues:** [../tracking/STATUS_REPORT.md](../tracking/STATUS_REPORT.md)
7. **See daily logs:** [../daily-logs/](../daily-logs/) (latest is Feb 18)

---

**Last Updated:** February 27, 2026

