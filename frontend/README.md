# QueueVision Frontend

React + TypeScript + Vite frontend for the Queue Wait-Time Estimation dashboard.

## Tech Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Vitest

## Prerequisites

- Node.js 20+
- npm 10+

## Local Development

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Default URL: `http://localhost:5173`

## Environment Variables

The frontend API base URL is read from `VITE_API_BASE_URL`.

Example `.env.local` inside `frontend/`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

If not set, the client defaults to `http://localhost:8000`.

## Authentication (April 2026 update)

Implemented auth flows:

- `/login` for sign in
- `/signup` for self-service manager account registration

Session behavior:

- Cookie-based auth with access + refresh cookies
- Frontend requests include credentials by default in `frontend/src/lib/api.ts`
- Role-protected routes:
	- manager: `/dashboard`, `/analytics`
	- manager/admin: `/settings`

Bootstrap admin defaults (backend startup creates account if missing):

- email: `admin@queuevision.local`
- password: `ChangeMe123!`

Important: override bootstrap defaults via environment variables before production deployment.

## Scripts

```bash
npm run dev      # Start Vite dev server
npm run build    # Production build
npm run preview  # Preview production build locally
npm run lint     # ESLint
npm run test     # Vitest
```

## Backend Contract Used by the Frontend

- REST API base: `/api/*`
- WebSocket: `/ws/metrics`
- API client: `frontend/src/lib/api.ts`

The client includes support for:

- Authentication and session endpoints (`register`, `login`, `refresh`, `logout`, `me`)
- Admin manager-account operations (list/create/status/password reset)

- Feed lifecycle (`create`, `start`, `stop`, `restart`, `delete`)
- Feed zone and threshold updates
- RTSP/ONVIF source onboarding
- Feed transport capability discovery (`/api/feeds/{feed_id}/transport`)
- WebRTC offer/answer signaling (`/api/feeds/{feed_id}/webrtc/offer`)
- MJPEG fallback transport (`/api/feeds/{feed_id}/stream`)
- Webhook integration status and test endpoints

Playback policy in dashboard feed cards:

- WebRTC first when the backend reports ready capability.
- MJPEG fallback when WebRTC is unavailable, unsupported, or fails.
- Snapshot endpoints are used for zone/re-zoning and non-live preview workflows.

Canonical transport and API references:

- `../docs/API_FOR_FRONTEND.md`
- `../docs/WEBRTC_PREVIEW_SETUP.md`

## Key Files

- `frontend/src/lib/api.ts`: Typed API + websocket contract
- `frontend/src/hooks/use-dashboard-websocket.ts`: Live event handling
- `frontend/src/pages/Dashboard.tsx`: Main operations screen

## Troubleshooting

- If API calls fail, confirm backend is running on `http://localhost:8000` and CORS is enabled.
- If live updates fail, verify websocket connection to `/ws/metrics` from browser devtools.
- If WebRTC does not start, inspect `/api/feeds/{feed_id}/transport` and check `webrtc.ready` plus `webrtc.reason`.
- If cards fall back to MJPEG unexpectedly, check `/api/feeds/{feed_id}/webrtc/offer` response status and backend MediaMTX configuration.
