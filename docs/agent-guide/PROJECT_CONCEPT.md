# Queue Wait-Time Estimation System - Project Concept

Purpose: explain the current project scope, system pipeline, and operational roles.

## 1) Problem Statement

Service environments (supermarkets, banks, counters) often face the same issues:
- customers do not know expected waiting time,
- teams react late to congestion,
- staffing decisions are made with incomplete real-time indicators.

Common approaches are limited:
- manual observation is subjective and inconsistent,
- occupancy-only counters do not estimate wait time,
- disconnected alerting slows operational response.

## 2) Current Solution Scope

The system transforms camera streams into actionable queue telemetry:
1. detect people from video feeds,
2. track identities across frames,
3. filter detections by queue-zone polygon,
4. compute queue metrics (arrival rate, service rate, wait time),
5. classify queue stability (stable vs unstable),
6. trigger threshold-based alerts,
7. publish payloads to n8n/Telegram workflows,
8. persist data for operational review and trend analysis.

## 3) End-to-End Pipeline

### Step 1 - Video Input
Supported sources:
- webcam,
- RTSP streams,
- local MP4 files.

### Step 2 - Person Detection
YOLO-based inference detects person bounding boxes per frame.

### Step 3 - Multi-Object Tracking
ByteTrack maintains identity continuity so queue events are event-based, not frame-count based.

### Step 4 - Zone Filtering
Only detections inside configured queue polygons contribute to queue metrics.

### Step 5 - Queue Metric Computation
From arrival/departure events:
- arrival rate: $\lambda$,
- service rate: $\mu$,
- expected wait time: $W$.

### Step 6 - Stability Handling
Runtime flags queue stability from observed rates:
- stable branch for valid denominator behavior,
- fallback branch when the queue is unstable but service is observed.

### Step 7 - Alerting
Threshold rules generate warnings/critical alerts (wait time, backlog, spikes, degradations).

### Step 8 - Integration and Storage
- payload delivery to n8n webhook,
- optional Telegram notification routing,
- CSV/DB persistence for audit and analytics.

## 4) Core Queue Logic

The project uses an M/M/1-inspired operational model:
- $\lambda$: arrival rate,
- $\mu$: service rate,
- $W$: expected wait time.

Operational assumptions:
- arrivals and services are approximated from observed events,
- the stable condition is interpreted at runtime,
- fallback logic protects against invalid denominator scenarios.

## 5) Architecture Overview

### Video Acquisition Layer
- camera/file ingestion,
- reconnect and transport handling.

### Perception Layer
- person detection,
- identity tracking,
- zone-aware filtering.

### Analysis Layer
- event-window rate estimation,
- wait-time computation,
- queue-stability classification,
- threshold evaluation.

### Output and Integration Layer
- dashboard events,
- webhook dispatch,
- alert workflow routing,
- persistence.

## 6) Roles and Responsibilities

The system currently targets two platform roles plus end-user impact:

- Administrator:
  - create, update, and delete manager accounts,
  - enforce access governance.

- Manager:
  - configure feeds, zones, thresholds, and integration settings,
  - monitor live queue status,
  - react to alerts,
  - review trend indicators for operational decisions.

- End users:
  - benefit indirectly from reduced wait times and smoother service.

## 7) Why Each Component Exists

- Detector: convert raw frames into person observations.
- Tracker: preserve identity continuity across time.
- Zone manager: isolate queue-relevant activity.
- Queue analyzer: produce interpretable operational metrics.
- Threshold detector: turn metrics into actionable events.
- Webhook client: connect runtime to external automation.
- Persistence: keep historical evidence for analysis and diagnosis.

## 8) Practical Use Cases

For managers:
- monitor live queue pressure,
- react when alerts exceed thresholds,
- compare performance periods for staffing decisions.

For administrators:
- maintain role access and account governance.

## 9) Strengths and Limitations

Strengths:
- near-real-time operational visibility,
- modular architecture,
- automation-ready output contracts,
- scalable multi-feed runtime model.

Limitations:
- occlusion and lighting can impact detection quality,
- dense scenes may reduce tracking reliability,
- queueing assumptions are approximations of real-world behavior,
- long-duration validation remains important for production confidence.

## 10) Related Documents

- Sprint setup and integration details: [../sprints/SPRINT5_SETUP.md](../sprints/SPRINT5_SETUP.md)
- Full project progress: [../tracking/PROGRESS.md](../tracking/PROGRESS.md)
- Current status overview: [AGENT_CONTEXT.md](AGENT_CONTEXT.md)

Summary: this is an operational queue-monitoring platform that combines computer vision, queue analytics, live supervision, and automation.

