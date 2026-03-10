# Web App GUI Parity Plan

**Created:** March 9, 2026  
**Last Updated:** March 10, 2026  
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
- Added multi-source staging in one setup session with staged-source edit, remove, and batch review support.
- Added global launch settings for webhook enable or disable and worker log level.
- Wired real `metrics_update`, `alert_fired`, and `system_warning` events from the analysis pipeline into the dashboard.
- Improved dashboard live monitoring, runtime warning surfacing, and recovered-feed handling.
- Added backend parity tests and frontend integration tests for the dashboard and live hook flows.

### Validated today

- Backend API suite passed: `45/45` tests.
- Frontend Vitest suite passed: `4/4` tests.
- Frontend production build passed.
- Diagnostics were clean for the edited backend and frontend files.

### Highest-priority work still open

- No blocking GUI-parity gaps remain for the current web replacement goal.
- Remaining work is optional polish such as bulk feed actions, dedicated metadata management screens, or broader frontend test coverage.

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

### Current parity status

The web app now covers the end-to-end operator workflow required to replace the desktop GUI for day-to-day use: multi-source staging, per-source configuration, batch review and launch, real worker lifecycle control, real live metrics and warning streaming, persistence, recovery, and frontend/backend test coverage.

## Gap Analysis

## 1. Source Onboarding Parity

**Status:** Implemented.

### Delivered in web app

- Multi-source setup flow in one session.
- Exact source-count validation before continuing.
- Add, remove, edit, and review multiple pending sources before submission.
- Add multiple discovered ONVIF cameras into one staged batch.

### Required backend work

- Completed with a batch launch contract handled by the backend-for-frontend layer.
- Persisted credentials remain backend-only; stronger protection is still a future hardening concern rather than a parity blocker.

### Required frontend work

- Completed.

## 2. Per-Source Configuration Parity

**Status:** Implemented.

### Delivered in web app

- Per-source switching while configuring multiple sources.
- Ability to revisit any staged source before launch.

### Required backend work

- No major new backend contract is required until batch staging is designed.

### Required frontend work

- Add source selector for staged feeds.
- Preserve staged zone and metadata state per source before launch.

## 3. Review And Launch Parity

**Status:** Implemented.

### Delivered in web app

- Final review screen showing every staged source in one batch.
- Global webhook enable or disable in the launch flow.
- Global log level in the launch flow.
- Batch launch for multiple staged sources.

### Required backend work

- Completed with a single batch launch contract carrying shared runtime settings.

### Required frontend work

- Completed for batch review and shared runtime settings.
- Per-feed batch progress remains lightweight and summary-based, which is sufficient for current parity.

## 4. Runtime Control Parity

**Status:** Implemented.

### Missing in web app

- Optional bulk operations when multi-source management is added.

### Delivered in web app

- Better surfacing of worker errors, persistent warnings, and recovery-required states in the dashboard.

### Required backend work

- Core parity work completed. More diagnostics depth is now a polish track.

### Required frontend work

- Completed.

## 5. Zone Workflow Parity

**Status:** Implemented.

### Missing in web app

- Optional dedicated zone page beyond the current dialog flow.

### Delivered in web app

- Revisiting staged feed zones before a batch launch through the staged workflow and review flow.

### Required backend work

- No new backend contract required for parity.

### Required frontend work

- Completed.

## 6. Metadata Management Parity

**Status:** Implemented for parity.

### Missing in web app

- Dedicated standalone metadata management screens outside the feed wizard.

### Delivered in web app

- Per-source metadata switching for the staged multi-source flow.

### Required backend work

- Optional future metadata edit and delete endpoints if dedicated management pages are added.

### Required frontend work

- Add a standalone management view only if operators need metadata maintenance outside the setup wizard.

## 7. Webhook And Settings Parity

**Status:** Implemented.

### Delivered in web app

- Webhook enable or disable as part of the actual launch request.
- Log level selection in the launch request.
- Clear indication of which runtime settings are global versus per-feed.

### Required backend work

- Completed.

### Required frontend work

- Completed.

## 8. WebSocket And Live Monitoring Parity

**Status:** Implemented.

### Delivered in web app

- Real metrics streaming from the actual analysis pipeline.
- Alert events.
- System warnings.
- Better synchronization between worker state and dashboard state.

### Required backend work

- Completed.

### Required frontend work

- Completed.

## 9. Persistence And Recovery

**Status:** Implemented for configured feeds.

### Missing in web app

- Optional policy for auto-resume if that ever becomes a product requirement.

### Delivered in web app

- Explicit UI treatment for recovered feeds via persistent warnings and recovery-required state instead of hard errors.

### Required backend work

- Current implementation persists feed configuration in SQLite and recovers stale `running` and `initializing` feeds as `stopped` after backend restart.

## 10. Testing Needed For Parity

**Status:** Implemented for the parity scope on this branch.

### Backend

- API tests for batch launch validation.
- WebSocket tests for metrics and alerts.
- Tests for webhook and log-level launch settings.

### Frontend

- Live dashboard hook integration coverage for websocket updates, activity feed, and runtime actions.
- Dashboard integration tests for batch launch, restart, edit-zone actions, and runtime error surfacing.
- Additional explicit zone-editor and RTSP-validation test files remain optional extensions, not blockers for current parity.

## Recommended Implementation Order

The planned implementation order for parity has been completed on this branch.

### Completed phases

- Phase 1: Worker orchestration, runtime controls, metadata APIs, RTSP and ONVIF onboarding, snapshot-based zone setup, and persistence.
- Phase 2: Multi-source staged workflow parity.
- Phase 3: Global runtime settings parity.
- Phase 4: Real live monitoring parity.
- Phase 5: Test coverage and runtime diagnostics polish.

## Suggested Definition Of Done

**Current assessment:** Satisfied for the intended web-app replacement scope.

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

If work continues beyond parity, the next slice should be optional operator-quality improvements rather than parity blockers:

1. Add bulk runtime operations for multiple feeds from the dashboard.
2. Add standalone metadata management screens if operators need maintenance outside the setup wizard.
3. Expand frontend coverage with dedicated zone-editor and RTSP-validation test cases.