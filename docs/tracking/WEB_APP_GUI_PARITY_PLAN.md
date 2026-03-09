# Web App GUI Parity Plan

**Created:** March 9, 2026  
**Last Updated:** March 9, 2026  
**Purpose:** Track what is still missing before the web application can replace the desktop GUI for day-to-day operation.

## Progress Update

### Completed today

- Added real feed worker orchestration in the backend with `start`, `stop`, and `restart` feed actions.
- Extended feed runtime state to support `created`, `initializing`, `running`, `stopped`, and `error`.
- Added metadata APIs and frontend setup support for establishments and caisses.
- Added manual RTSP onboarding with username, password, transport selection, and backend connection testing.
- Added ONVIF discovery, RTSP stream resolution, and backend camera testing.
- Added local video upload handling with backend-served preview paths.
- Added snapshot-based zone selection for RTSP and ONVIF feeds.
- Added review-and-launch flow with save-only versus create-and-start behavior.
- Added dashboard feed card controls for start, stop, restart, and edit zone.
- Added feed snapshot support for existing feeds so secured cameras can be re-zoned without re-entering credentials.
- Added SQLite persistence for configured feeds and recovery after backend restart.

### Validated today

- Backend API suite passed: `36/36` tests.
- Frontend production build passed.
- Diagnostics were clean for the edited backend and frontend files.

### Highest-priority work still open

- Multi-source staging in one setup session is still missing.
- Global webhook enable/disable and log-level controls are still missing from the web launch flow.
- Real queue metrics, alert events, and system warning events are not yet streamed from the analysis pipeline into the dashboard.
- Frontend integration tests for the new wizard flow and runtime controls are still missing.

## Goal

The target is not just visual parity. The web application must support the same operational workflow that the desktop GUI supports today:

1. Select one or more sources.
2. Configure each source.
3. Define queue zones.
4. Attach optional establishment and caisse metadata.
5. Review the full configuration.
6. Start analysis from the web app.
7. Monitor status and live metrics from the same interface.

## Current State

### Desktop GUI already supports

- Multi-source setup with exact source-count validation.
- Local video file selection.
- Manual RTSP source entry.
- RTSP credential capture.
- RTSP transport selection (`tcp` or `udp`).
- RTSP connection testing before adding a source.
- ONVIF camera discovery.
- Viewing discovered camera details.
- Testing discovered cameras with credentials.
- Adding multiple discovered cameras.
- Per-source zone selection.
- Per-source model selection.
- Global log-level configuration.
- Global webhook enable or disable.
- Optional establishment and caisse assignment.
- Creation of new establishments and caisses from the workflow.
- Final review screen before launch.
- Launching one worker process per source.

### Web app currently supports

- Listing configured feeds and reloading them after backend restart.
- Creating a single feed through a full web wizard: source, zone, model, review.
- Uploading local video files to the backend and serving browser preview paths.
- Manual RTSP onboarding with credentials, transport selection, and backend connection testing.
- ONVIF discovery, stream resolution, and backend camera testing.
- Establishment and caisse assignment during setup, including inline creation.
- Reusing saved caisse zones as defaults for new feeds.
- Snapshot-based zone selection for RTSP and ONVIF sources.
- Editing the zone of an existing feed from the dashboard.
- Review-and-launch with save-only or create-and-start behavior.
- Feed card actions for start, stop, and restart.
- Viewing feed cards, health summary, worker lifecycle state, and feed-status WebSocket updates.
- Persisting configured feeds in SQLite with restart recovery for stale running feeds.

### Critical limitation today

The current web app now covers a full **single-feed** operator workflow and can launch and control real workers, but it still does **not** match the desktop GUI in multi-source staging, global launch settings, or real live metrics and alert streaming.

## Gap Analysis

## 1. Source Onboarding Parity

### Missing in web app

- Multi-source setup flow in one session.
- Exact source-count validation before continuing.
- Add, remove, and review multiple pending sources before submission.
- Add multiple discovered ONVIF cameras into one staged batch.

### Required backend work

- Decide whether multi-source launch should be a batch API contract or a coordinated sequence of single-feed calls.
- Decide whether persisted camera credentials need stronger protection than the current backend-only storage model.

### Required frontend work

- Replace the single-feed wizard with a multi-source staging workflow.
- Add a staged-source list with edit and remove actions before final review.
- Support adding multiple discovered cameras from one ONVIF discovery pass.

## 2. Per-Source Configuration Parity

**Status:** Single-feed metadata assignment and RTSP/ONVIF zone configuration are implemented.

### Missing in web app

- Per-source switching while configuring multiple sources.
- Ability to revisit any staged source before launch.

### Required backend work

- No major new backend contract is required until batch staging is designed.

### Required frontend work

- Add source selector for staged feeds.
- Preserve staged zone and metadata state per source before launch.

## 3. Review And Launch Parity

**Status:** Single-feed review and create-and-start are implemented.

### Missing in web app

- Final review screen showing every staged source in one batch.
- Global webhook enable or disable in the launch flow.
- Global log level in the launch flow.
- Batch launch for multiple staged sources.

### Required backend work

- Add webhook and log-level settings to the launch contract.
- Decide whether one request should launch all staged feeds or whether the frontend should coordinate one launch per feed.

### Required frontend work

- Extend the current review step to multi-source batch review.
- Add global runtime settings to the review step.
- Show per-feed launch progress in batch mode.

## 4. Runtime Control Parity

**Status:** Core per-feed runtime control is implemented.

### Missing in web app

- Better surfacing of worker errors.
- Optional bulk operations when multi-source management is added.

### Required backend work

- Keep improving worker failure diagnostics and event detail.

### Required frontend work

- Improve how long worker errors and restart-recovery messages are surfaced in the dashboard.

## 5. Zone Workflow Parity

**Status:** Zone workflow parity is implemented for single-feed setup and edit flows.

### Missing in web app

- Revisiting multiple staged feed zones before a batch launch.
- Optional dedicated zone page beyond the current dialog flow.

### Required backend work

- No major new backend zone contract is required for the current single-feed flow.

### Required frontend work

- Reuse the current zone editor inside a future multi-source staged workflow.

## 6. Metadata Management Parity

**Status:** Core metadata parity is implemented in the setup flow.

### Missing in web app

- Dedicated standalone metadata management screens outside the feed wizard.
- Per-source metadata switching for a future multi-source staging flow.

### Required backend work

- Optional future metadata edit and delete endpoints if dedicated management pages are added.

### Required frontend work

- Add a standalone management view only if operators need metadata maintenance outside the setup wizard.

## 7. Webhook And Settings Parity

### Missing in web app

- Webhook enable or disable as part of the actual launch request.
- Log level selection in the launch request.
- Clear indication of which runtime settings are global versus per-feed.

### Required backend work

- Add settings fields to the launch contract.
- Map those settings into the worker startup command.

### Required frontend work

- Add these controls to the review or settings step.
- Persist the selected values across a multi-source setup session.

## 8. WebSocket And Live Monitoring Parity

**Status:** Feed lifecycle WebSocket updates are implemented.

### Missing in web app

- Real metrics streaming from the actual analysis pipeline.
- Alert events.
- System warnings.
- Better synchronization between worker state and dashboard state.

### Required backend work

- Broadcast `metrics_update`, `alert_fired`, and `system_warning` events.
- Wire the real analysis loop into the WebSocket hub.
- Keep feed status updates consistent when workers fail or exit.

### Required frontend work

- Consume richer event types.
- Show alerts and worker warnings in the dashboard activity stream.

## 9. Persistence And Recovery

**Status:** Implemented for configured feeds.

### Missing in web app

- Optional explicit UI treatment for recovered feeds beyond the current `last_error` recovery message.
- Optional policy for auto-resume if that ever becomes a product requirement.

### Required backend work

- Current implementation persists feed configuration in SQLite and recovers stale `running` and `initializing` feeds as `stopped` after backend restart.

## 10. Testing Needed For Parity

### Backend

- API tests for batch launch validation.
- WebSocket tests for metrics and alerts.
- Tests for webhook and log-level launch settings when those contracts are added.

### Frontend

- Wizard tests for multi-source staging and validation.
- Zone editor tests for uploaded files and RTSP snapshots.
- Dashboard integration tests for launch, restart, and edit-zone actions.
- Error-state tests for failed RTSP validation and failed worker startup.

## Recommended Implementation Order

This is the best path now that single-feed launch, zone editing, and persistence are already in place.

### Phase 1: Completed today

- Implement worker orchestration behind the existing feed model.
- Add start, stop, restart, and runtime status updates.
- Add metadata list and create endpoints.
- Add RTSP and ONVIF onboarding APIs.
- Add snapshot-based zone setup and edit flows.
- Persist configured feeds and recover them after backend restart.

### Phase 2: Add multi-source workflow parity

- Update the dashboard wizard to stage multiple sources before launch.
- Add staged-source edit and remove actions.
- Add multi-camera staging from ONVIF discovery.

### Phase 3: Add global runtime settings parity

- Add global launch settings: webhook and log level.
- Persist those settings through the review and launch flow.

### Phase 4: Wire real live monitoring

- Broadcast real `metrics_update`, alert, and warning events from the analysis pipeline.
- Update the dashboard to consume and display them.

### Phase 5: Add tests and polish

- Add frontend integration coverage for the wizard and wall controls.
- Improve worker error surfacing and recovered-feed UX.

## Suggested Definition Of Done

The web app can be considered functionally equivalent to the GUI when all of the following are true:

- A user can stage multiple local videos and RTSP cameras in one setup flow.
- A user can discover ONVIF cameras from the web app.
- A user can test RTSP connectivity before launch.
- A user can define or edit a zone for every source.
- A user can assign establishment and caisse metadata for each source.
- A user can review the complete batch before launch.
- Launching from the web app starts the actual analysis workers.
- The dashboard shows real worker status and live queue metrics.
- A user can stop and restart feeds from the web app.
- Errors are exposed as structured API responses and clear dashboard states.

## Recommended Next Slice

If only one slice is implemented next, it should be:

1. Multi-source web wizard with staged sources and batch review.
2. Global webhook and log-level settings in the review-and-launch flow.
3. Real `metrics_update`, alert, and warning events from the analysis pipeline.

That sequence closes the biggest remaining gap between the current single-feed web workflow and the desktop GUI's real multi-source operator flow.