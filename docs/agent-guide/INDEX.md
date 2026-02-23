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
- 📍 Current phase (Phase 5 – 90% complete)
- ✅ What's already implemented
- 🔄 Next immediate tasks (3-4 items)
- 📁 Project folder structure
- 🔑 Key files for the current phase
- 📈 Overall project completion percentage

**Reading time:** 5 minutes

---

### 3️⃣ **[../tracking/PROGRESS.md](../tracking/PROGRESS.md)** – Full Details
**Purpose:** Get comprehensive phase-by-phase breakdown with detailed completion status.

**Topics covered:**
- ✅ All completed phases with specific achievements
- 🔄 Partially completed phases with blockers
- ❌ Remaining phases and blockers
- 📊 Overall progress metrics
- 🎯 Next immediate tasks
- 📝 Project notes and context

**Reading time:** 10 minutes

---

### 4️⃣ **[../tracking/STATUS_REPORT.md](../tracking/STATUS_REPORT.md)** – Recent Fixes & Architecture
**Purpose:** Understand recent bug fixes and system architecture decisions.

**Reading time:** 5-10 minutes

---

### 5️⃣ **[../phases/](../phases/)** – Phase-Specific Details
Deep dives into specific phases:
- `PHASE4_SUMMARY.md` – Uncertainty quantification implementation
- `PHASE5_SETUP.md` – n8n webhook integration setup

---

### 6️⃣ **[../daily-logs/](../daily-logs/)** – Development History
Daily logs organized by phase and date. Useful for understanding design decisions.

---

## 🎯 Quick Navigation by Role

### **I just want to understand the project**
→ Start with **PROJECT_CONCEPT.md**

### **I need to know what we're doing now**
→ Read **AGENT_CONTEXT.md**

### **I need full details on everything**
→ Read in order: PROJECT_CONCEPT → AGENT_CONTEXT → PROGRESS.md → specific phase docs

### **I'm implementing Phase 5 (Telegram/n8n)**
1. **AGENT_CONTEXT.md** – Status
2. **PROGRESS.md** – Phase 5 section
3. **phases/PHASE5_SETUP.md** – Setup instructions
4. **Code**: `src/webhook_client.py`, `src/threshold_detector.py`, `src/main.py`

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

docs/tracking/             (project status)
├── PROGRESS.md            (phase-by-phase breakdown)
└── STATUS_REPORT.md       (recent fixes & architecture)

docs/phases/               (phase-specific deep dives)
├── PHASE4_SUMMARY.md      (uncertainty quantification)
└── PHASE5_SETUP.md        (n8n integration)

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

**Last Updated:** February 23, 2026

Welcome to the Queue Wait-Time Estimation System! 🚀

