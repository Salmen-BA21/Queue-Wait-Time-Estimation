# 🤖 Agent Context – Current Project Status

**⚠️ START HERE** – Read this file first, then refer to [../tracking/PROGRESS.md](../tracking/PROGRESS.md) for full details.

---

## 📍 Current Phase

**Phase 5 – Send Data to n8n Integration**  
**Status:** IN PROGRESS (mostly complete)

- ✅ n8n webhook setup and deployment complete
- ✅ JSON payload structure designed (17 fields)
- ✅ Python webhook client created with retry logic
- ✅ Main.py integration complete (webhook sends every 5 seconds)
- ✅ End-to-end testing successful (HTTP 200 responses)
- ✅ CSV backup logging implemented
- ✅ Queue threshold detection logic implemented
- ⏳ **Telegram bot setup and integration PENDING**
- ⏳ **Persistence checking with n8n state PENDING**

---

## 🎯 Next Immediate Tasks

1. **Complete Phase 5:** Implement Telegram bot setup and integration with n8n
2. **Phase 6:** Define alert persistence rules and implement inline Telegram buttons
3. **Enhance Testing:** Run comprehensive end-to-end tests with multiple simultaneous video feeds
4. **Phase 8 Testing:** Evaluate system under various scenarios (normal, crowd, slow service)

---

## ✅ What's Already Done

- **Phases 0-4:** Core functionality with uncertainty quantification ✅
- **Phase 7:** Dashboard GUI implemented ✅
- **n8n integration:** Webhook + CSV logging ✅
- **Queue analysis:** YOLO26 + ByteTrack + zone detection ✅
- **Uncertainty quantification:** Bayesian Gamma distributions ✅
- **Multi-video support:** GUI with per-video zones ✅

---

## 📁 Project Structure

```
docs/
  ├── README.md              (📖 Documentation index)
  ├── agent-guide/           (Agent onboarding docs)
  ├── tracking/
  │   ├── PROGRESS.md        (📊 FULL PROJECT STATUS - READ THIS)
  │   ├── STATUS_REPORT.md   (🐛 Issue fixes and architecture)
  ├── phases/
  │   ├── PHASE4_SUMMARY.md  (Uncertainty implementation details)
  │   ├── PHASE5_SETUP.md    (n8n setup guide)
  └── daily-logs/            (Development logs by phase)

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

## 🔑 Key Files For This Phase

| File | Purpose |
|------|---------|
| [../../src/webhook_client.py](../../src/webhook_client.py) | Send metrics to n8n webhook with retry logic |
| [../../src/threshold_detector.py](../../src/threshold_detector.py) | Detect queue alerts (wait time, backlog, spikes, etc.) |
| [../../src/csv_logger.py](../../src/csv_logger.py) | Backup CSV logging for offline metrics |
| [../../src/main.py](../../src/main.py) | Main loop integrating webhook sends every 5 sec |
| [../phases/PHASE5_SETUP.md](../phases/PHASE5_SETUP.md) | n8n webhook setup instructions |

---

## 📈 Project Completion

- **Completed:** Phases 0, 1, 2, 3, 4 (5 phases = ~50%)
- **In Progress:** Phase 5 (~90% complete, missing Telegram)
- **Not Started:** Phases 6, 8, 9
- **Overall:** ~55% complete

---

## 🚀 Getting Started If You're New

1. **See the reading roadmap:** [INDEX.md](INDEX.md) ← **START HERE**
2. **Understand the big picture:** [PROJECT_CONCEPT.md](PROJECT_CONCEPT.md)
3. **Quick status reference:** [AGENT_CONTEXT.md](AGENT_CONTEXT.md) (this file)
4. **Read full status:** [../tracking/PROGRESS.md](../tracking/PROGRESS.md)
5. **Understand Phase 5:** [../phases/PHASE5_SETUP.md](../phases/PHASE5_SETUP.md)
6. **Check recent issues:** [../tracking/STATUS_REPORT.md](../tracking/STATUS_REPORT.md)
7. **See daily logs:** [../daily-logs/](../daily-logs/) (latest is Feb 18)

---

**Last Updated:** February 23, 2026

