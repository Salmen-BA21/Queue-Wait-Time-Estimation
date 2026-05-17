# Sprint Diagrams Specification (Revised)

> Revised after critique against actual chapter content.
> Removed: all 3 component diagrams (redundant), Sprint 3 transport state diagram (covered by activity), Sprint 4 evaluation activity (models a process, not system behavior).
> Each entry now includes a **Detail Level** field: High-Level or Detailed.

---

## Sprint 1 — Perception and Queue Analytics

Sprint 1 is a single Python process — one main loop, no service boundaries, no state machine.
The complexity lives entirely in the **runtime logic** of one pipeline.
Needed diagrams: two activity diagrams (pipeline + analytics) and one sequence diagram.

---

### Figure 3.1 — Activity Diagram: Pipeline Flow

**File:** `chapter3_activity.pdf`
**Type:** UML Activity Diagram
**Detail Level:** High-Level

**Purpose:** Show the frame-by-frame runtime flow from video source to metric output. This is the entry-point diagram for Sprint 1. The reader needs to see the pipeline stages and the one key decision (people detected or not) at a glance, without being overloaded by analytics logic.

**Nodes:**
1. Start
2. Capture frame
3. Decision: **People detected?**
   - No → loop back to Capture frame
   - Yes → continue
4. Run tracker
5. Filter by zone
6. Compute metrics (pass to analytics step)
7. Publish metrics
8. End (loop back to Capture frame)

**Keep simple:** Do not show the M/M/1 branching here — that belongs in the Analytics diagram below.

**Maps to:** US1.1, US1.2, US1.3, T1.4

---

### Figure 3.2 — Activity Diagram: Queue Analytics

**File:** `chapter3_activity_Analytics.pdf`
**Type:** UML Activity Diagram
**Detail Level:** Detailed

**Purpose:** Zoom into the single "Compute metrics" step from Figure 3.1 and show the full adaptive estimation logic. This diagram must be detailed because the branching conditions are the core intellectual contribution of Sprint 1 — they justify the choice of M/M/1 over alternatives and explain how the system stays safe when conditions are unstable.

**Nodes:**
1. Start (receives: current tracked IDs, previous window)
2. Diff current vs previous → identify arrivals and departures
3. Update arrival window (Na, Ta) and departure window (Nd, Td)
4. Decision: **Enough events observed?**
   - No → return λ=0, μ=0, W=0 → End
   - Yes → continue
5. Compute λ = Na/Ta, μ = Nd/Td
6. Decision: **μ > 0?**
   - No → return W = L/1 (bounded fallback) → End
   - Yes → continue
7. Decision: **λ < μ?**
   - Yes → W = 1/(μ − λ) [M/M/1 formula]
   - No → W = L/μ [occupancy-based fallback]
8. Publish {λ, μ, W, occupancy L}
9. End

**Label the two branches clearly:** "Stable queue (M/M/1)" and "Overloaded / fallback".

**Maps to:** US1.6, US1.7, T1.7, T1.8

---

### Figure 3.3 — Sequence Diagram: Per-Frame Pipeline

**File:** `chapter3_sequence.pdf`
**Type:** UML Sequence Diagram
**Detail Level:** Detailed (message names matter)

**Purpose:** Show exactly who calls whom during one frame cycle and name the metric contract published at the end. The detail level is needed here because the sequence diagram is the only diagram that makes the **interface** between components explicit — the activity diagram shows logic, not interfaces.

**Lifelines (left to right):**
1. Video Source
2. Detector
3. Tracker
4. Zone Filter
5. Queue Analyzer
6. Metric Publisher

**Messages:**

| # | From | To | Message | Arrow |
|---|------|----|---------|-------|
| 1 | Video Source | Detector | `capture_frame(frame)` | Solid |
| 2 | Detector | Tracker | `person_detections(boxes)` | Solid |
| 3 | Tracker | Zone Filter | `tracked_ids(persons)` | Solid |
| 4 | Zone Filter | Queue Analyzer | `zone_occupants(ids, entry_events)` | Solid |
| 5 | Queue Analyzer | Metric Publisher | `metrics(λ, μ, W, L)` | Solid |
| 6 | Metric Publisher | [External sink] | `publish_snapshot(payload)` | Solid |

**Fragment:** `loop` wrapping all messages — labeled "per frame".

**Maps to:** US1.3, US1.6, US1.9

---

### Sprint 1 — Additional Diagrams Recommendation

**Do you need more diagrams in Sprint 1?** No.

Reason: Sprint 1 is a single-process pipeline. The three diagrams already cover every unique concern:
- The **pipeline activity** gives the frame-loop overview.
- The **analytics activity** details the M/M/1 / fallback branching — the only complex logic in the sprint.
- The **sequence** documents the metric contract interface.

There is no state machine, no multi-party protocol, no structural complexity that would justify an additional diagram type. Adding one would repeat information already present.

---

## Sprint 2 — Backend Services and API Integration

Sprint 2 introduces real structural complexity: external actors (IP cameras, dashboard), a named feed lifecycle, state persistence across restarts, and layered transport. All three diagram types are justified here and all need to be detailed.

---

### Figure 4.1 — Sequence Diagram: Feed Orchestration

**File:** `chapter4_sequence.pdf`
**Type:** UML Sequence Diagram
**Detail Level:** Detailed

**Purpose:** Show the full orchestration chain when a dashboard action triggers a feed. This is the primary diagram for explaining how a frontend request becomes a running live stream, including the state persistence step that is Sprint 2's key reliability contribution.

**Lifelines (left to right):**
1. Dashboard
2. API Layer
3. Feed Manager
4. RTSP Handler
5. State Store

**Messages:**

| # | From | To | Message | Arrow |
|---|------|----|---------|-------|
| 1 | Dashboard | API Layer | `GET /feeds/{id}` | Solid |
| 2 | API Layer | Feed Manager | `get_feed_metadata(id)` | Solid |
| 3 | Feed Manager | API Layer | `feed metadata` | Dashed return |
| 4 | API Layer | Feed Manager | `start_feed(id)` | Solid |
| 5 | Feed Manager | RTSP Handler | `open_rtsp_connection(url, creds)` | Solid |
| 6 | RTSP Handler | Feed Manager | `stream frames` | Dashed return |
| 7 | Feed Manager | State Store | `persist_feed_state(id, ACTIVE)` | Solid |
| 8 | State Store | Feed Manager | `ack` | Dashed return |
| 9 | Feed Manager | API Layer | `feed_active` | Dashed return |
| 10 | API Layer | Dashboard | `live event / stream URL` | Solid |

**Fragment:** `opt` wrapping messages 9–10 — labeled "live delivery when transport ready".

**Maps to:** US2.3, US2.4, T2.3, T2.4

---

### Figure 4.2 — Activity Diagram: Camera Discovery and Onboarding

**File:** `chapter4_camera_discovery_activity.pdf`
**Type:** UML Activity Diagram
**Detail Level:** Detailed

**Purpose:** Show the ONVIF-based camera discovery and RTSP onboarding flow. This must be detailed because the steps are non-trivial and specific to the technology stack (WS-Discovery, ONVIF SOAP, RTSP validation with OpenCV). A high-level version would lose the key decisions that make the implementation reliable.

**Nodes:**
1. Start
2. Send WS-Discovery probe on local network
3. Decision: **Device responded?**
   - No → Log no cameras found → End
   - Yes → Extract device metadata from ONVIF response
4. Resolve media service and request RTSP URI via ONVIF SOAP
5. Decision: **RTSP URI resolved?**
   - No → Log resolution error → End
   - Yes → continue
6. Decision: **Credentials required?**
   - Yes → Accept credentials as runtime input (not logged)
   - No → continue
7. Validate stream with OpenCV
8. Decision: **Stream valid?**
   - No → Decision: **Retry with alternate transport (TCP/UDP)?**
     - Yes → loop back to Validate stream
     - No → Log validation failure → End
   - Yes → continue
9. Register feed + persist state
10. Start live delivery
11. Decision: **Stream dropped?**
    - No → loop (continue streaming)
    - Yes → Attempt reconnection → loop back to Validate stream (dashed retry)

**Maps to:** US2.1, US2.2, T2.1, T2.2

---

### Figure 4.3 — State Diagram: Feed Lifecycle

**File:** `chapter4_feed_state.pdf`  *(to be added to .tex chapter)*
**Type:** UML State Diagram
**Detail Level:** Detailed

**Purpose:** Show the four named feed states and every transition, including the restart-recovery path where persisted state allows the system to resume without manual intervention. This is the only diagram in the project that captures the lifecycle of a feed object — no other diagram shows this.

**States:**

| State | Description |
|-------|-------------|
| Unregistered | Camera discovered or configured but feed not active |
| Active | RTSP stream running, metrics being published |
| Reconnecting | Stream dropped; retry in progress with fallback transport |
| Suspended | Max retries reached; state persisted in SQLite, feed paused |

**Transitions:**

| From | To | Guard |
|------|----|-------|
| [Start] | Unregistered | System starts / feed created |
| Unregistered | Active | Auth OK, RTSP validated, feed started |
| Active | Active | Stream healthy (self-loop) |
| Active | Reconnecting | Stream dropped unexpectedly |
| Active | Unregistered | `DELETE /feeds/{id}` or API stop command |
| Reconnecting | Active | Reconnect successful (dashed — recovery path) |
| Reconnecting | Suspended | Max retries reached |
| Suspended | Unregistered | Manual resume or backend restart (dashed) |
| Suspended | [End] | Feed permanently removed |

**Maps to:** US2.4, T2.4

---

### Sprint 2 — Additional Diagrams Recommendation

**Do you need more diagrams in Sprint 2?** No.

Reason: The class diagram (`optional_class_diagram.pdf`) already in the `.tex` chapter covers the static domain model (Manager, Feed, VideoSession, Alert, etc.). That accounts for the only structural gap. The three spec diagrams then cover:
- **Sequence** — the orchestration chain (the dynamic side of the same domain model).
- **Camera discovery activity** — the ONVIF/RTSP onboarding flow with its specific branching.
- **Feed state diagram** — the lifecycle of a feed object, which no other diagram captures.

Authenticated API access is described well enough in prose; a separate auth sequence diagram would not add new architectural information at this level.

---

## Sprint 3 — Web Dashboard and Live Monitoring

Sprint 3 has two distinct concerns that must not be collapsed: (1) the frontend architecture and integration flow, and (2) the real-time transport fallback behavior. These need two sequence diagrams (different scope) and one activity diagram. The transport state diagram from the original spec is removed — it is fully covered by the activity diagram.

---

### Figure 5.1 — Sequence Diagram: Feed Lifecycle and Alert Surfacing

**File:** `chapter5_sequence.pdf`
**Type:** UML Sequence Diagram
**Detail Level:** High-Level

**Purpose:** Show the three main event flows that the dashboard handles: feed lifecycle actions, live metric updates, and alert surfacing. This diagram answers "what kinds of events does the dashboard react to and in what order?" — it is intentionally high-level because the detailed transport logic is covered in Figure 5.2.

**Lifelines (left to right):**
1. Manager (Browser)
2. Dashboard UI
3. API Layer
4. Backend

**Three flows (use `alt` or separate sequences):**

- **Flow A — Feed action:** Manager clicks Start → Dashboard → `POST /feeds/{id}/start` → Backend → websocket event `feed_status: ACTIVE` → Dashboard updates card
- **Flow B — Metric update:** Backend emits websocket `metric_update(λ, μ, W, L)` → Dashboard receives → updates KPI widgets
- **Flow C — Alert:** Backend emits websocket `alert(severity, message)` → Dashboard → shows alert in activity panel

**Maps to:** US3.4, US3.5, US3.6

---

### Figure 5.2 — Sequence Diagram: Full Dashboard Data Flow

**File:** `chapter5_dashboard_data_flow_sequence.pdf`
**Type:** UML Sequence Diagram
**Detail Level:** Detailed

**Purpose:** Show the complete session lifecycle from protected login through WebRTC negotiation, live metric synchronization, fallback polling, and stale guard. This diagram must be detailed because it is the only place that documents the full contract between the frontend and backend at the transport level.

**Lifelines (left to right):**
1. Manager (Browser)
2. React Dashboard
3. Auth Provider
4. API Layer
5. Backend / Runtime
6. WebSocket Channel
7. Media Transport

**Key message groups:**
1. Protected route check → redirect to login if unauthenticated
2. `GET /feeds` + `GET /health` on mount
3. Open metrics WebSocket → receive initial snapshot
4. WebSocket events: `feed_status`, `metric_update`, `alert`, `system_warning`
5. Feed action: `POST /feeds/{id}/start` → websocket `feed_status: ACTIVE`
6. **`alt`** — WebSocket stale: fallback `GET /feeds` polling
7. **`alt`** — WebRTC available: send browser offer → receive SDP answer → stream live; else use MJPEG fallback

**Maps to:** US3.6, US3.7, US3.8, T3.6, T3.7, T3.11

---

### Figure 5.3 — Activity Diagram: Live Dashboard Runtime

**File:** `chapter5_live_dashboard_activity.pdf`
**Type:** UML Activity Diagram
**Detail Level:** Detailed

**Purpose:** Show how the dashboard decides between WebSocket updates, fallback polling, feed control actions, and video transport modes at runtime. This must be detailed because the decisions (WebSocket stale check, transport negotiation) are the core reliability behavior of Sprint 3 and are not visible in any other single diagram.

**Nodes:**
1. Start — authenticated dashboard access
2. Load feed list + system health (REST)
3. Open metrics WebSocket
4. Receive event
5. Decision: **Event type?**
   - `feed_status` → update feed card state
   - `metric_update` → update KPI widgets
   - `alert` / `system_warning` → show in activity panel
6. Decision: **WebSocket stale / unavailable AND feeds running?**
   - Yes → poll `GET /feeds` at interval → rejoin at step 4
   - No → wait for next event
7. **In parallel — per feed card:**
   - Decision: **WebRTC ready?**
     - Yes → negotiate WebRTC (offer/answer) → show live stream
     - No → Decision: **MJPEG available?**
       - Yes → show MJPEG fallback stream
       - No → show stored preview snapshot
8. End (dashboard remains live until session ends)

**Maps to:** US3.6, US3.7, US3.8, T3.7, T3.8

---

### Figure 5.4 — Activity Diagram: Setup Wizard Onboarding Flow

**File:** `chapter5_setup_wizard_activity.pdf`
**Type:** UML Activity Diagram
**Detail Level:** High-Level

**Purpose:** Show the step-by-step onboarding path a manager follows inside the dashboard UI — from selecting a source type, through camera discovery, zone tracing, and model selection, to batch launch. This diagram covers the wizard workflow that no existing Sprint 3 diagram traces: the two sequence diagrams cover live transport; the live dashboard activity covers the runtime event loop. The wizard is a separate, linear user journey with its own decisions described across 5 UI screens in the chapter.

**Nodes:**
1. Start — manager opens feed setup screen
2. Decision: **Source type?**
   - Uploaded video → Skip to node 7
   - ONVIF camera → continue
3. Discover cameras on local network (WS-Discovery)
4. Decision: **Credentials required?**
   - Yes → Enter per-camera credentials
   - No → continue
5. Resolve RTSP stream URI via ONVIF
6. Test stream connection
7. Capture snapshot frame for zone tracing
8. Trace queue polygon on snapshot (zone editor screen)
9. Select YOLO model size (nano / small / medium)
10. Stage feed in review panel
11. Decision: **Add another feed?**
    - Yes → loop back to node 2
    - No → continue
12. Review staged feeds (batch)
13. Launch batch → feeds created and started
14. End — dashboard shows active feeds

**Keep high-level:** Do not repeat ONVIF SOAP details — those belong in the Sprint 2 camera discovery activity. This diagram focuses on the **UI workflow** as experienced by the manager.

**Maps to:** US3.2, US3.4, US3.5, T3.10

---

### Sprint 3 — Additional Diagrams Recommendation

**Do you need more diagrams in Sprint 3?** Yes — one (Figure 5.4 above).

Reason: The chapter explicitly documents a multi-step onboarding wizard with 5 UI screenshots and detailed prose. The existing diagrams cover the live transport behavior and backend event handling, but none of them trace the **manager's workflow through the setup wizard**. A high-level activity diagram fills that gap without duplicating any existing diagram. No other additional diagram types are needed: the auth flow is a two-step redirect (covered in text), and the analytics/heatmap views are display-only with no non-trivial branching logic.

---

## Sprint 4 — Automation, Evaluation, and Optimization

Sprint 4 has two concerns: alert routing (backend → n8n → Telegram) and system evaluation. The n8n workflow screenshot (`n8n_workflow.png`) already documents the full automation chain visually. The UML diagrams here complement it — they do not duplicate it.

Removed: Evaluation activity diagram (models the testing process, not system behavior — handled by prose + bullet lists in the chapter).

---

### Figure 6.1 — Activity Diagram: Backend Alert Dispatch

**File:** `chapter6_evaluation_resilience_activity.pdf`
**Type:** UML Activity Diagram
**Detail Level:** Detailed

**Scope:** Backend-side only — from threshold detection to webhook delivery. Do NOT diagram the n8n internal routing or Telegram steps here; those are covered by the n8n screenshot and the sequence diagram.

**Purpose:** Show the retry logic, cooldown gate, payload validation, and async dispatch that happen inside the Python runtime before the HTTP call reaches n8n. This is the unique behavior that the n8n screenshot cannot show.

**Nodes:**
1. Start — metrics tick received
2. Decision: **Threshold breached? (λ > μ or queue > limit)**
   - No → End (no alert)
   - Yes → continue
3. Decision: **Within cooldown window?**
   - Yes → Suppress (deduplicate) → End
   - No → continue
4. Build `QueuePayload` (timestamp, frame, source, feed ID, λ, μ, W, severity)
5. Decision: **Payload valid?**
   - No → Log validation error → End
   - Yes → continue
6. Hand off to `AsyncWebhookDispatcher` (non-blocking — main loop continues)
7. `POST /webhook` to n8n with shared-secret header
8. Decision: **HTTP 200 received?**
   - Yes → Log success → End
   - No → Decision: **Retries remaining?**
     - Yes → Exponential backoff → loop back to POST
     - No → Log delivery failure (persisted in SQLite) → End

**Maps to:** US4.1, T4.1, T4.2

---

### Figure 6.2 — Sequence Diagram: Backend → n8n → Telegram

**File:** `chapter6_sequence.pdf`  *(to be added to .tex chapter)*
**Type:** UML Sequence Diagram
**Detail Level:** Detailed

**Purpose:** Show the cross-system message protocol across four lifelines. The sequence diagram is the only diagram that makes the **async boundaries** visible: the analytics engine fires and forgets; the alert dispatcher owns delivery; n8n handles routing and cooldown; Telegram is the terminal sink.

**Lifelines (left to right):**
1. Analytics Engine
2. Alert Dispatcher
3. n8n Workflow
4. Telegram Bot

**Messages:**

| # | From | To | Message | Arrow |
|---|------|----|---------|-------|
| 1 | Analytics Engine | Alert Dispatcher | `threshold_breached(λ > μ)` | Solid |
| 2 | Alert Dispatcher | Alert Dispatcher | `validate_payload()` | Solid (self-call) |
| 3 | Alert Dispatcher | n8n Workflow | `POST /webhook {payload, X-Secret}` | Solid |
| 4 | n8n Workflow | n8n Workflow | `check_secret() + apply_cooldown()` | Solid (self-call) |
| 5 | n8n Workflow | n8n Workflow | `format_telegram_message()` | Solid (self-call) |
| 6 | n8n Workflow | Telegram Bot | `sendMessage(chat_id, text)` | Solid |
| 7 | Telegram Bot | n8n Workflow | `200 OK` | Dashed return |
| 8 | n8n Workflow | Alert Dispatcher | `delivery_confirmed` | Dashed return |
| 9 | Alert Dispatcher | Alert Dispatcher | `log_success()` | Solid (self-call) |

**Fragment:** `alt` wrapping messages 3–8 — labeled "retry on failure (exponential backoff, max N attempts)".

**Maps to:** US4.1, US4.3, T4.3

---

## Summary Table

| Figure | File | Sprint | Type | Detail Level | Status |
|--------|------|--------|------|--------------|--------|
| 3.1 | chapter3_activity.pdf | Sprint 1 | Activity (pipeline) | High-Level | In .tex ✅ |
| 3.2 | chapter3_activity_Analytics.pdf | Sprint 1 | Activity (analytics) | Detailed | In .tex ✅ |
| 3.3 | chapter3_sequence.pdf | Sprint 1 | Sequence | Detailed | In .tex ✅ |
| 4.1 | chapter4_sequence.pdf | Sprint 2 | Sequence | Detailed | In .tex ✅ |
| 4.2 | chapter4_camera_discovery_activity.pdf | Sprint 2 | Activity | Detailed | In .tex ✅ |
| 4.3 | chapter4_feed_state.pdf | Sprint 2 | State | Detailed | **Add to .tex** ⚠️ |
| 5.1 | chapter5_sequence.pdf | Sprint 3 | Sequence (high-level) | High-Level | In .tex ✅ |
| 5.2 | chapter5_dashboard_data_flow_sequence.pdf | Sprint 3 | Sequence (detailed) | Detailed | In .tex ✅ |
| 5.3 | chapter5_live_dashboard_activity.pdf | Sprint 3 | Activity | Detailed | In .tex ✅ |
| 5.4 | chapter5_setup_wizard_activity.pdf | Sprint 3 | Activity (wizard) | High-Level | **Add to .tex** ⚠️ |
| 6.1 | chapter6_evaluation_resilience_activity.pdf | Sprint 4 | Activity (dispatch) | Detailed | In .tex ✅ |
| 6.2 | chapter6_sequence.pdf | Sprint 4 | Sequence | Detailed | **Add to .tex** ⚠️ |

### Sprint 4 — Additional Diagrams Recommendation

**Do you need more diagrams in Sprint 4?** No.

Reason: Sprint 4's deliverables split cleanly across three artifacts:
- The **n8n workflow screenshot** (`n8n_workflow.png`) documents the automation chain authentically.
- The **alert dispatch activity** covers the backend-side retry/cooldown/validation logic.
- The **cross-system sequence** documents the message protocol across the four lifelines.

The fault-tolerance improvements (FeedRegistry supervision, WebSocket reconnect) and runtime tuning are implementation details better described in text — they do not have enough structural uniqueness to justify a separate diagram without overlapping with Sprint 2's feed state diagram or Sprint 3's activity diagram.

### Removed from original spec

| Original Figure | Reason |
|-----------------|--------|
| 3.1 Component Diagram | Redundant — pipeline already shown by activity + sequence |
| 4.1 Component Diagram | Redundant — static structure covered by class diagram |
| 5.1 Component Diagram | Redundant — React app structure, no analytical value |
| 5.4 State Diagram (transport) | Covered by Sprint 3 activity diagram (WebSocket/polling/stale decisions) |
| 6.3 Activity Diagram (evaluation) | Models testing process, not system behavior |
