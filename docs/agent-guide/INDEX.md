# 🤖 Agent Onboarding Guide

**Welcome!** This folder contains everything a new agent needs to understand and work on this project.

## 📖 Reading Order

### 1️⃣ **[PROJECT_CONCEPT.md](PROJECT_CONCEPT.md)** – Start Here
**Purpose:** Understand the complete project idea, architecture, and why each component exists.

**Topics covered:**
- 🎯 Problem statement (real-world queue issues)
- 🔄 Complete system pipeline (detection → tracking → analysis → alerts)
- 📐 Mathematics (M/M/1 queuing theory, Bayesian uncertainty)
- 🏗️ System architecture diagram
- 💾 Real-world data flow example
- 🔌 Why each component exists
- 🎯 Use cases (for customers, staff, managers)
- ⚠️ Limitations and honest assessment

**Reading time:** 15-20 minutes

---

### 2️⃣ **[AGENT_CONTEXT.md](AGENT_CONTEXT.md)** – Current Status
**Purpose:** Know where the project stands right now and what needs to be done.

**Topics covered:**
- 📍 Current sprint (Sprint 11 – Web Frontend Implementation, in progress)
- ✅ What's already implemented
- 🔄 Next immediate tasks (frontend-backend integration)
- 📁 Project folder structure (backend/ and frontend/)
- 🔑 Key files for the current sprint
- 📈 Overall project completion percentage

**Reading time:** 5 minutes

---

### 3️⃣ **[../tracking/PROGRESS.md](../tracking/PROGRESS.md)** – Full Details
**Purpose:** Get comprehensive sprint-by-sprint breakdown with detailed completion status.

**Topics covered:**
- ✅ All completed sprints with specific achievements
- 🔄 Partially completed sprints with blockers
- ❌ Remaining sprints and blockers
- 📊 Overall progress metrics
- 🎯 Next immediate tasks
- 📝 Project notes and context

**Reading time:** 10 minutes

---

### 4️⃣ **[../tracking/STATUS_REPORT.md](../tracking/STATUS_REPORT.md)** – Recent Fixes & Architecture
**Purpose:** Understand recent bug fixes and system architecture decisions.

**Reading time:** 5-10 minutes

---

### 5️⃣ **[../../design/README.md](../../design/README.md)** – Web Design Guide ⭐ NEW
**Purpose:** Understand the complete web frontend design — 7 pages designed in Pencil MCP.

**Topics covered:**
- 🎨 Design system (colors, fonts, spacing)
- 📐 All 7 page layouts with component breakdowns
- 🚀 Implementation roadmap for the next agent
- 📁 File references and Pencil MCP node IDs

**Reading time:** 5 minutes (then read `design/DESIGN_SPEC.md` for full 20-minute deep dive)

---

### 6️⃣ **[../sprints/](../sprints/)** – Sprint-Specific Details
Deep dives into specific sprints:
- `SPRINT4_SUMMARY.md` – Uncertainty quantification implementation
- `SPRINT5_SETUP.md` – n8n webhook integration setup

---

### 7️⃣ **[../daily-logs/](../daily-logs/)** – Development History
Daily logs organized by date and sprint activity. Useful for understanding design decisions.

---

## 🎯 Quick Navigation by Role

### **I just want to understand the project**
→ Start with **PROJECT_CONCEPT.md**

### **I need to know what we're doing now**
→ Read **AGENT_CONTEXT.md**

### **I need full details on everything**
→ Read in order: PROJECT_CONCEPT → AGENT_CONTEXT → PROGRESS.md → specific sprint docs

### **I'm implementing the web frontend (HTML/CSS/React/TypeScript)** ⭐ NEW
1. **frontend/README.md** – Development environment setup
2. **design/DESIGN_SPEC.md** – Full technical design spec (colors, layouts, components)
3. **frontend/src/pages/** – All 7 page implementations
4. **frontend/src/components/** – UI components library (55+ shadcn/ui components)
5. **Backend reference**: `backend/src/config.py`, `backend/src/queue_analyzer.py`, `backend/src/uncertainty.py`

### **I'm implementing Sprint 5 (Telegram/n8n)**
1. **AGENT_CONTEXT.md** – Status
2. **PROGRESS.md** – Sprint 5 section
3. **sprints/SPRINT5_SETUP.md** – Setup instructions
4. **Code**: `backend/src/webhook_client.py`, `backend/src/threshold_detector.py`, `backend/src/main.py`, `backend/src/rtsp_camera.py` (RTSP support added)

### **I'm fixing a bug**
→ Check **STATUS_REPORT.md** for recent fixes, then dive into relevant code

### **I want to understand design decisions**
→ Browse **daily-logs/** for development history

---

## 📁 Document Organization

```
docs/agent-guide/          ← YOU ARE HERE
├── INDEX.md               (this file)
├── PROJECT_CONCEPT.md     (what is this project?)
└── AGENT_CONTEXT.md       (where are we now?)

backend/                   ⭐ PYTHON BACKEND
├── src/                   (core analysis pipeline)
├── scripts/               (testing utilities)
└── gui/                   (Tkinter GUI)

frontend/                  ⭐ REACT FRONTEND (NEW)
├── src/
│   ├── pages/             (7 application pages)
│   ├── components/        (UI components & layouts)
│   └── hooks/             (custom React hooks)
└── package.json           (dependencies)

design/                    ⭐ WEB DESIGN
├── README.md              (quick-start for frontend implementation)
├── DESIGN_SPEC.md         (full technical design specification)
└── pencil-new.pen         (Pencil MCP design file – 7 pages)

docs/tracking/             (project status)
├── PROGRESS.md            (sprint-by-sprint breakdown)
└── STATUS_REPORT.md       (recent fixes & architecture)

docs/sprints/              (sprint-specific deep dives)
├── SPRINT4_SUMMARY.md     (uncertainty quantification)
├── SPRINT5_SETUP.md       (n8n integration)
└── SPRINT_MAPPING.md      (legacy mapping)

docs/daily-logs/           (development history)
├── 2026-02-12__Phase1__...
├── 2026-02-16__Phase2__...
├── 2026-02-16__Phase3__...
├── 2026-02-18__Phase4__...
└── TEMPLATE.md            (template for new logs)
```

---

## ✨ Tips for Agents

1. **Don't skip PROJECT_CONCEPT.md** – Even if you're always coding, understanding the "why" helps you make better decisions
2. **Use AGENT_CONTEXT.md as a reference** – Add it to your browser bookmarks/favorites
3. **Check daily-logs for context** – Before making big changes, see what decisions were made before
4. **Update PROGRESS.md after you work** – Keep the project status current for the next agent
5. **Ask questions** – If something in the docs is unclear, improve the docs!

---

**Last Updated:** March 5, 2026

Welcome to the Queue Wait-Time Estimation System! 🚀

