# Code Quality Report: Post-Refactor Follow-Up

**Review Scope:** Current working tree after the dashboard refactor on branch `frontend-backend-integration`

**Files Analyzed:**
- frontend/src/pages/Dashboard.tsx
- frontend/src/components/dashboard/FeedGrid.tsx
- frontend/src/components/dashboard/AttentionPanel.tsx
- frontend/src/components/dashboard/ActivityPanel.tsx
- frontend/src/components/dashboard/ZoneSelectionDialog.tsx
- frontend/src/hooks/use-dashboard-local-files.ts
- frontend/src/hooks/use-dashboard-setup-effects.ts
- frontend/src/hooks/use-dashboard-websocket.ts
- frontend/src/hooks/use-live-dashboard.ts
- frontend/src/lib/api.ts
- frontend/src/lib/api.test.ts
- frontend/src/pages/Dashboard.integration.test.tsx

## Resolved Since The Previous Report
- The repeated `localFile*` state maps were consolidated into `useDashboardLocalFiles`, reducing duplication and centralizing per-file metadata.
- Complex setup synchronization effects were moved out of `Dashboard.tsx` into `useDashboardSetupEffects`.
- The live surveillance wall, attention panel, and activity panel were extracted into separate components.
- `useLiveDashboard` no longer mixes WebSocket transport handling with query/mutation logic; socket handling now lives in `useDashboardWebsocket`.
- `api.ts` now distinguishes `NetworkError`, `ValidationError`, and `ApiError` instead of throwing only generic errors.
- `ZoneSelectionDialog.tsx` now handles preview setup more defensively, with explicit cleanup and better failure handling.
- Tests were strengthened with helper-based integration test cleanup and direct API client tests.

## 🔴 Critical Issues
- **Dashboard.tsx**: The main page is still a large orchestration component spanning a very large surface area (`Dashboard.tsx`, starting around line 272 and continuing through the main render flow). It still owns setup flow state, RTSP/ONVIF configuration, batch staging, edit-zone flows, mutation orchestration, and dialog wiring in one place. The original God component problem was reduced, but not resolved.

## 🟠 Major Issues
- **ZoneSelectionDialog.tsx**: The manual retry path in `reloadPreview` creates a local `AbortController`, but that retry request is not tied to component unmount or dialog close. The initial preview load is cleanup-safe; the retry path is not. This can still allow stale async completion after the dialog closes.
- **use-dashboard-websocket.ts**: WebSocket event parsing still uses raw `JSON.parse(message.data)` without a guarded parse path. A malformed or partial backend message can still throw and break the event handler.
- **Dashboard.tsx**: State sprawl remains high even after the local-file extraction. The page still carries many unrelated `useState` values and callbacks for batch setup, source testing, metadata, dialogs, and feed actions, which keeps the file hard to reason about and difficult to unit test.
- **Dashboard.tsx**: `handleFinalizeBatch` is documented now, but the batch submission path is still long and mixes validation, upload orchestration, payload construction, result recovery, UI state restoration, and toast handling in one function. This is still an extraction candidate.

## 🟡 Minor Issues
- **Dashboard.tsx / FeedGrid.tsx**: Feed action types are duplicated (`FeedAction` in `Dashboard.tsx` and `FeedGridAction` in `FeedGrid.tsx`). This is a small maintainability issue and should be unified under one shared type.
- **ActivityPanel.tsx**: `ActivityPanel` imports `ActivityItem` from `use-live-dashboard` even though the type now originates from the shared WebSocket layer. The dependency direction works, but it leaks orchestration concerns into a presentational component.
- **use-dashboard-websocket.ts**: Activity IDs still rely on `Date.now()` for several event types. That is acceptable for UI keys, but it makes deterministic testing and replay harder than necessary.

## ✅ What's Done Well
- **Structural Improvement**: The refactor produced real separation of concerns rather than cosmetic file splitting.
- **DRY Improvement**: The local-file reducer hook removes one of the most obvious duplication clusters from the previous report.
- **UI Readability**: Extracting `FeedGrid`, `AttentionPanel`, and `ActivityPanel` materially reduced JSX depth in the main page.
- **Error Handling**: API failures are now typed and easier for the UI layer to distinguish.
- **Defensive Async Logic**: The preview loading path in `ZoneSelectionDialog.tsx` is safer than before and better contained.
- **Test Coverage**: The API client now has focused tests, and the dashboard integration tests are easier to extend.

## 💡 Suggestions For The Next Agent
- Extract the batch setup flow from `Dashboard.tsx` into a dedicated hook or component boundary. That is now the highest-value structural change left.
- Refactor `handleFinalizeBatch` into smaller units such as validation, file upload preparation, payload mapping, and failed-draft recovery.
- Make `ZoneSelectionDialog` retry loading lifecycle-safe by reusing the same cancellation model as the initial load effect.
- Add guarded parsing and fallback handling in `useDashboardWebsocket` so malformed server messages do not break the live dashboard.
- Unify shared dashboard types so presentational components depend on shared contracts rather than page-level orchestration types.

## Recommended Priority Order
1. Extract remaining batch setup logic from `Dashboard.tsx`
2. Split `handleFinalizeBatch` into testable helpers
3. Fix `ZoneSelectionDialog` retry cancellation
4. Harden WebSocket event parsing
5. Clean up minor shared-type and dependency-direction issues