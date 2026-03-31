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

- Feed lifecycle (`create`, `start`, `stop`, `restart`, `delete`)
- Feed zone and threshold updates
- RTSP/ONVIF source onboarding
- MJPEG stream transport (`/api/feeds/{feed_id}/stream`)
- Webhook integration status and test endpoints

## Key Files

- `frontend/src/lib/api.ts`: Typed API + websocket contract
- `frontend/src/hooks/use-dashboard-websocket.ts`: Live event handling
- `frontend/src/pages/Dashboard.tsx`: Main operations screen

## Troubleshooting

- If API calls fail, confirm backend is running on `http://localhost:8000` and CORS is enabled.
- If live updates fail, verify websocket connection to `/ws/metrics` from browser devtools.
- If MJPEG cards are blank, check feed status and test `/api/feeds/{feed_id}/snapshot` as fallback.
