# Diagram Mappings & Merge Actions

This file lists the canonical diagrams for Sprints 1–4, highlights overlaps, and prescribes actions: keep, merge (and how), or remove. Use these mappings when exporting figures into the report.

## Naming conventions
- Keep diagram filenames and top captions in this repo consistent: `figure_<chapter>_<shortname>.<ext>`.

## Sprint 1 — Perception and Queue Analytics

- Figure 3.1 — Component Diagram: KEEP
  - Purpose: architecture overview of perception → analytics pipeline
  - Action: keep as canonical component diagram; add cross-ref to 4.1 for RTSP details

- Figure 3.2 — Activity Diagram: KEEP (canonical per-frame control flow)
  - Purpose: per-frame decision/control flow (capture → detect → track → compute → publish)
  - Action: make it the single authoritative activity for per-frame logic

- Figure 3.3 — Sequence Diagram: REMOVE or CONVERT
  - Reason: duplicates 3.2 at message level
  - Action: either remove from report or convert to a tiny inset fragment labelled "message-level example" showing 3–5 messages. If retained, rename `Figure 3.3 (inset)` and reference from 3.2.

## Sprint 2 — Backend Services and API Integration

- Figure 4.1 — Component Diagram: KEEP
  - Purpose: backend service layer and data flows (RTSP → feed manager → API → dashboard)
  - Action: keep; add note that `Video input` in 3.1 maps to `RTSP handler` here

- Figure 4.2 — Activity Diagram (onboarding): KEEP (canonical onboarding flow)
  - Action: merge any overlapping content from 4.3 into 4.2 as a swimlane fragment

- Figure 4.3 — Sequence Diagram: CONVERT to fragment
  - Purpose: illustrate dashboard GET → feed start → RTSP open
  - Action: convert to a small sequence fragment (single page) or embed as an "opt" fragment inside 4.2 and remove duplicate explanatory text

- Figure 4.4 — State Diagram: KEEP
  - Purpose: feed lifecycle and restart/recovery guards

## Sprint 3 — Web Dashboard and Live Monitoring

- Figure 5.1 — Component Diagram: KEEP
  - Purpose: show frontend layers and backend contracts

- Figure 5.2 — Activity Diagram: KEEP (two-phase build + live integration)

- Figure 5.3 — Sequence Diagram: OPTIONAL
  - Purpose: event propagation for live updates
  - Action: Keep only if you need to demonstrate alternative transport handling (WS vs poll). Otherwise convert to a short fragment.

- Figure 5.4 — State Diagram: KEEP
  - Purpose: transport states for the dashboard

## Sprint 4 — Automation, Evaluation, and Optimization

- Figure 6.1 — Activity Diagram (Alert Dispatch): KEEP (canonical alert flow)

- Figure 6.2 — Sequence Diagram (Backend → n8n → Telegram): MERGE
  - Action: merge this sequence into 6.1 as a swimlane or embedded sequence fragment; keep a small sequence block within 6.1 that lists the 4 lifelines and primary messages

- Figure 6.3 — Activity Diagram (Evaluation Pass): KEEP
  - Purpose: testing & validation flow — separate concern from alert dispatch

## Summary table (actionable)

| Figure | Action | Note |
|--------|--------|------|
| 3.1 | Keep | Component for perception
| 3.2 | Keep | Activity (canonical per-frame)
| 3.3 | Remove/Fragment | Duplicate — convert to inset if desired
| 4.1 | Keep | Backend components
| 4.2 | Keep | Onboarding activity (canonical)
| 4.3 | Fragment | Embed into 4.2 or keep as short sequence
| 4.4 | Keep | Feed state lifecycle
| 5.1 | Keep | Frontend components
| 5.2 | Keep | Two-phase build activity
| 5.3 | Optional | Fragment only if needed
| 5.4 | Keep | Transport state
| 6.1 | Keep | Alert dispatch activity
| 6.2 | Merge | Embed into 6.1 as swimlane/fragment
| 6.3 | Keep | Evaluation pass

## How to implement merges (editor-agnostic)

1. Open the primary diagram in your preferred editor.
2. Create a small UML frame or labeled rectangle for the fragment (e.g., "Dashboard request flow").
3. Inside the frame, add 4–6 lifelines/messages from the sequence diagram — keep text short.
4. Add a caption line under the frame: "Fragment: detailed message flow — see original sequence for full scenario".
5. Remove the separate sequence file or set its visibility to archived in the repo.

## Notes about report inclusion

- When exporting figures to `report-latex`, include the figure caption, the purpose line, and the primary user stories. Use the canonical diagram name and the summary table entry as metadata.

---

End of `diagram_mappings.md`.
