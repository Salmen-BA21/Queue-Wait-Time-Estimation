---
name: queue-system-dev
description: 'Use when working on the Queue Wait-Time Estimation System in this repo: YOLO detection, ByteTrack tracking, queue metrics, wait-time estimation, Bayesian uncertainty, threshold alerts, RTSP cameras, zone polygons, CSV logging, webhook delivery, database metadata, FastAPI/API planning, WebSocket streaming, or React dashboard integration. Trigger for requests like add an endpoint, fix the tracker, update the analyzer, debug uncertainty, wire frontend metrics, or write tests for this system.'
argument-hint: 'Describe the queue-system task, module, or contract you want changed.'
user-invocable: true
---

# Queue Wait-Time Estimation System Development

Use this skill for code changes and reviews that touch the queue-analysis pipeline, the frontend dashboard, or the planned API/BFF layer for this repository.

## Current Architecture

The current repo is not yet a full FastAPI service. Treat these as the active layers today:

| Layer | Current Stack | Primary Files |
|---|---|---|
| Video pipeline | Python, OpenCV, YOLO26, ByteTrack | `backend/src/main.py`, `backend/src/detector.py`, `backend/src/tracker.py`, `backend/src/video_capture.py` |
| Queue math | Sliding-window queue analysis, uncertainty estimation | `backend/src/queue_analyzer.py`, `backend/src/uncertainty.py` |
| Alerts and integrations | Threshold rules, webhooks, CSV, DB metadata | `backend/src/threshold_detector.py`, `backend/src/webhook_client.py`, `backend/src/csv_logger.py`, `backend/src/database.py` |
| Zone and camera setup | Polygon zones, RTSP config, GUI flows | `backend/src/zone_manager.py`, `backend/src/rtsp_camera.py`, `backend/src/gui/app.py`, `select_zone.py` |
| Frontend | React, TypeScript, Vite, shadcn/ui | `frontend/src/pages/`, `frontend/src/components/` |

If a task mentions FastAPI endpoints, WebSockets, or response wrappers, first verify whether the request is about implementing a new API layer or only designing one.

## When To Use

- Add or fix detector, tracker, queue, zone, RTSP, webhook, CSV, or metadata logic.
- Review or extend uncertainty estimation, confidence intervals, or alert thresholds.
- Implement frontend dashboard integration for queue metrics and system state.
- Design or implement a future API/BFF layer for the frontend.
- Add tests for queue math, GUI command generation, or integration behavior.

## Core Domain Rules

### Queue Stability

- Always treat the queue as unstable when `service_rate <= arrival_rate`.
- Never divide by zero or by `service_rate - arrival_rate` when the denominator is not positive.
- Surface unstable state explicitly instead of crashing.

### Current Wait-Time Logic

Match the current implementation in `backend/src/queue_analyzer.py` unless the task explicitly changes the model:

- Stable case: `wait_time = 1 / (service_rate - arrival_rate)`
- Unstable but `service_rate > 0`: fallback to `people_in_zone / service_rate`
- No service observed: return `0.0` today, but call out whether that should remain the contract

### Bayesian Rate Uncertainty

- Posterior currently uses Gamma with `alpha = event_count + 1` and `beta = window_seconds`.
- Credible intervals come from Gamma quantiles in `backend/src/uncertainty.py`.

### Wait-Time Uncertainty

- Use variance-based intervals when enough samples exist.
- Use a documented fallback when history is insufficient.
- Preserve non-negative bounds.

## Standard Workflow

1. Identify the affected layer and start from the real entry points in this repo.
2. Read the nearby implementation before changing anything. For backend work, start with the relevant file in `backend/src/`. For frontend work, start with the page or component in `frontend/src/`.
3. Confirm whether the task is about current behavior or planned architecture.
4. Check domain invariants before editing:
   - queue stability
   - empty detections and empty zones
   - RTSP reconnect behavior
   - webhook failure tolerance
   - metadata and logging consistency
5. Make the smallest complete change that preserves current contracts unless the task explicitly requests a contract change.
6. Add or update focused tests using the nearest existing pattern.
7. Run targeted verification and report what was verified versus what remains unverified.

## Decision Branches

### If the task touches queue math

1. Inspect `backend/src/queue_analyzer.py` and `backend/src/uncertainty.py` first.
2. Preserve explicit handling for low-event windows and unstable queues.
3. Check whether tests belong in `test_uncertainty.py` or a new nearby queue-analysis test.
4. Call out any contract change to `QueueMetrics` fields.

### If the task touches detection or tracking

1. Inspect `backend/src/detector.py`, `backend/src/tracker.py`, and the call path from `backend/src/main.py`.
2. Verify assumptions about tracker IDs, empty detections, and frame rate.
3. Make sure zone filtering and downstream queue metrics still receive consistent inputs.

### If the task touches RTSP, GUI, or zone selection

1. Inspect `backend/src/rtsp_camera.py`, `backend/src/gui/app.py`, `backend/src/zone_manager.py`, and `select_zone.py`.
2. Preserve the no-zone path as a valid state.
3. Prefer graceful degradation for connection failures and reconnect attempts.
4. Reuse the command-building and Tkinter testing pattern already present in `test_gui_app.py`.

### If the task touches alerts, logging, webhook, or metadata

1. Inspect `backend/src/threshold_detector.py`, `backend/src/webhook_client.py`, `backend/src/csv_logger.py`, `backend/src/database.py`, and `backend/src/config.py`.
2. Keep integrations non-fatal: logging and webhook failures should not take down the analysis loop.
3. Preserve current metadata terminology, including `caisse_id` and optional `establishment_id`.

### If the task touches the frontend

1. Inspect the relevant route in `frontend/src/pages/` and any shared components it uses.
2. Verify whether the UI is consuming mock data, static state, or a real backend contract.
3. If you introduce a new backend contract, document the payload shape and update the consuming UI code together.

### If the task asks for FastAPI or WebSocket work

1. First verify whether an API server already exists. Do not invent files or routes without checking.
2. If no API exists yet, decide whether the task is:
   - API design only
   - first implementation of a backend-for-frontend layer
   - frontend integration against a proposed contract
3. When implementing a new API layer, keep it explicit that this is new architecture, not a pre-existing subsystem.
4. Prefer typed request and response models, explicit error handling, and a stable event schema for live updates.

## Edge Cases To Check Every Time

- `service_rate <= arrival_rate`
- no detections or no tracker IDs
- empty zone or zone not yet drawn
- RTSP stream disconnects or reconnect exhaustion
- webhook send failures
- bootstrap periods with too little history for stable uncertainty estimates
- zero or invalid time windows in uncertainty calculations
- feed or camera references that may exist in the frontend language but not yet in the backend implementation

## Completion Checks

- The change is consistent with the actual current architecture.
- Queue invariants and uncertainty bounds still hold.
- New or changed behavior is covered by a targeted test where practical.
- Logging and error handling remain explicit and non-fatal where appropriate.
- Any planned API or WebSocket contract is clearly marked as new or proposed, not implied as already implemented.

## Output Expectations

When using this skill, report:

- what changed
- which layer was affected
- any domain or contract assumptions
- verification run
- gaps or follow-up work still needed
