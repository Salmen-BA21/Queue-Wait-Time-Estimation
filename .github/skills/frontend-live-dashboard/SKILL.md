---
name: frontend-live-dashboard
description: "WebSocket + REST contract, chart updates, state transitions, offline/reconnect patterns, throttling, and alert card design for the queue system live dashboard."
user-invocable: true
---

# 🖥️ Skill: frontend-live-dashboard

> WebSocket + REST contract, chart updates, state transitions, offline/reconnect patterns, throttling, and alert card design for the queue system live dashboard.

---

## 📡 Data Contract: Backend → Frontend

### REST Endpoint (polling fallback / initial load)
```
GET /api/metrics/latest
GET /api/metrics/history?zone_id=checkout_lane_3&limit=100
GET /api/alerts/recent?limit=20
```

**Response shape for `/api/metrics/latest`:**
```json
{
  "snapshot_at": "2026-03-05T14:32:10.123Z",
  "zones": [
    {
      "camera_id": "cam_01",
      "zone_id": "checkout_lane_3",
      "metrics": {
        "people_in_zone": 7,
        "arrival_rate": 0.15,
        "service_rate": 0.16,
        "wait_time_seconds": 15.0,
        "queue_stable": true
      },
      "uncertainty": {
        "lambda_ci": [0.10, 0.22],
        "mu_ci": [0.11, 0.23],
        "wait_time_ci": [9.5, 24.3],
        "level": "MEDIUM"
      },
      "active_alerts": ["WAIT_TIME_WARNING"],
      "fps": 24.5
    }
  ]
}
```

### WebSocket Event Shape
```typescript
// All WS messages share this envelope
type WSMessage =
  | { event: "metrics_update"; data: ZoneMetrics }
  | { event: "alert_fired";    data: Alert }
  | { event: "alert_cleared";  data: { alert_type: string; zone_id: string } }
  | { event: "zone_offline";   data: { zone_id: string; reason: string } }
  | { event: "zone_online";    data: { zone_id: string } }
  | { event: "ping" }
```

---

## 🔌 WebSocket Connection Management

```typescript
// hooks/useQueueSocket.ts
import { useEffect, useRef, useCallback, useState } from "react";

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000]; // exponential backoff

export function useQueueSocket(url: string, onMessage: (msg: WSMessage) => void) {
  const wsRef     = useRef<WebSocket | null>(null);
  const retryRef  = useRef(0);
  const [status, setStatus] = useState<"connecting" | "connected" | "offline">("connecting");

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("connected");
      retryRef.current = 0;     // Reset backoff on success
    };

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      if (msg.event === "ping") {
        ws.send(JSON.stringify({ event: "pong" }));
        return;
      }
      onMessage(msg);
    };

    ws.onclose = () => {
      setStatus("offline");
      const delay = RECONNECT_DELAYS[
        Math.min(retryRef.current, RECONNECT_DELAYS.length - 1)
      ];
      retryRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();   // Triggers onclose → reconnect loop
  }, [url, onMessage]);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); };
  }, [connect]);

  return { status };
}
```

---

## 📊 Chart Update Strategy

### Throttle Incoming Updates (max 1 chart redraw per 500ms)
```typescript
// hooks/useThrottledMetrics.ts
import { useRef, useState } from "react";

export function useThrottledMetrics(throttleMs = 500) {
  const [metrics, setMetrics] = useState<ZoneMetrics[]>([]);
  const pendingRef = useRef<ZoneMetrics | null>(null);
  const timerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);

  const push = (m: ZoneMetrics) => {
    pendingRef.current = m;
    if (!timerRef.current) {
      timerRef.current = setTimeout(() => {
        if (pendingRef.current) {
          setMetrics(prev => {
            const next = [...prev, pendingRef.current!];
            return next.slice(-100);
          });
        }
        timerRef.current = null;
      }, throttleMs);
    }
  };

  return { metrics, push };
}
```

### Wait Time Line Chart (Recharts example)
```tsx
// components/WaitTimeChart.tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceArea, ReferenceLine } from "recharts";

interface DataPoint {
  time: string;          // HH:MM:SS
  wait: number;          // seconds
  ci_lower: number;
  ci_upper: number;
}

export function WaitTimeChart({ data }: { data: DataPoint[] }) {
  return (
    <LineChart width={600} height={200} data={data}>
      <XAxis dataKey="time" />
      <YAxis unit="s" />
      <Tooltip formatter={(v: number) => `${v.toFixed(1)}s`} />

      {/* CI shaded area */}
      <ReferenceArea
        y1={data.at(-1)?.ci_lower}
        y2={data.at(-1)?.ci_upper}
        strokeOpacity={0}
        fill="#93c5fd"
        fillOpacity={0.25}
      />

      {/* Warning threshold line */}
      <ReferenceLine y={60}  stroke="#f59e0b" strokeDasharray="4 2" label="60s" />
      <ReferenceLine y={120} stroke="#ef4444" strokeDasharray="4 2" label="120s" />

      <Line
        type="monotone"
        dataKey="wait"
        stroke="#3b82f6"
        dot={false}
        strokeWidth={2}
        isAnimationActive={false}    // MUST disable for real-time; animation lags
      />
    </LineChart>
  );
}
```

> **Rule:** Always set `isAnimationActive={false}` on Recharts components fed by live data. Animation queuing causes visual stutter on rapid updates.

---

## 🃏 Alert Card Design

### Alert Severity → Visual System
```typescript
const ALERT_STYLES = {
  critical: {
    bg:      "bg-red-50 border-red-400",
    icon:    "🚨",
    title:   "text-red-700 font-bold",
    badge:   "bg-red-500 text-white",
    pulse:   true,
  },
  warning: {
    bg:      "bg-amber-50 border-amber-400",
    icon:    "⚠️",
    title:   "text-amber-700 font-semibold",
    badge:   "bg-amber-400 text-white",
    pulse:   false,
  },
} as const;
```

### Alert Card Component
```tsx
// components/AlertCard.tsx
interface Alert {
  type: string;
  severity: "warning" | "critical";
  message: string;
  value: number | string;
  threshold: number | string;
  fired_at: string;
  zone_id: string;
}

export function AlertCard({ alert }: { alert: Alert }) {
  const style = ALERT_STYLES[alert.severity];

  return (
    <div className={`border-l-4 rounded p-3 mb-2 ${style.bg} ${style.pulse ? "animate-pulse" : ""}`}>
      <div className="flex items-center justify-between">
        <span className={style.title}>
          {style.icon} {alert.type.replace(/_/g, " ")}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${style.badge}`}>
          {alert.severity.toUpperCase()}
        </span>
      </div>
      <p className="text-sm text-gray-600 mt-1">{alert.message}</p>
      <div className="text-xs text-gray-400 mt-1 flex gap-4">
        <span>Zone: {alert.zone_id}</span>
        <span>Value: {alert.value}</span>
        <span>Threshold: {alert.threshold}</span>
        <span>{new Date(alert.fired_at).toLocaleTimeString()}</span>
      </div>
    </div>
  );
}
```

---

## 📴 Offline / Reconnect Data Patterns

### State Machine
```
  ┌──────────────┐  WS opens   ┌───────────────┐
  │  CONNECTING  │ ──────────► │   LIVE        │ ◄─── normal operation
  └──────────────┘             └───────────────┘
         ▲                           │ WS closes
         │ reconnect timer           ▼
         │                   ┌───────────────┐
         └─────────────────── │   OFFLINE     │ → show stale banner, retry
                              └───────────────┘
```

### Stale Data Banner
```tsx
// Show when last_update is older than 30 seconds
function StaleBanner({ lastUpdated }: { lastUpdated: Date | null }) {
  const secondsAgo = lastUpdated
    ? Math.floor((Date.now() - lastUpdated.getTime()) / 1000)
    : null;

  if (!secondsAgo || secondsAgo < 30) return null;

  return (
    <div className="bg-yellow-100 border border-yellow-400 text-yellow-800 px-4 py-2 rounded text-sm flex items-center gap-2">
      ⚡ Live data paused — last update {secondsAgo}s ago. Reconnecting...
    </div>
  );
}
```

### Offline Fallback: REST Polling
```typescript
// When WS is offline, fall back to polling every 10s
useEffect(() => {
  if (wsStatus !== "offline") return;

  const poll = async () => {
    const res = await fetch("/api/metrics/latest");
    const data = await res.json();
    data.zones.forEach((z: ZoneMetrics) => pushMetrics(z));
  };

  poll();  // immediate call
  const id = setInterval(poll, 10_000);
  return () => clearInterval(id);
}, [wsStatus]);
```

---

## ⚡ Rate Limiting Incoming Data

### Problem
Backend sends 24 fps of tracking data. Dashboard only needs 1 update/sec.

### Solution: Server-side decimation (preferred)
```python
# backend: emit WS update at most every N seconds per zone
DASHBOARD_EMIT_INTERVAL = 1.0   # seconds

last_emitted: dict[str, float] = {}

def maybe_emit(zone_id: str, payload: dict):
    now = time.time()
    if now - last_emitted.get(zone_id, 0) >= DASHBOARD_EMIT_INTERVAL:
        websocket_broadcast(payload)
        last_emitted[zone_id] = now
```

---

## 🔢 Dashboard Ingestion Readiness Checklist

- [ ] WS message parsed and typed against `WSMessage` union
- [ ] `isAnimationActive={false}` on all live charts
- [ ] Throttle hook applied (max 1 state update / 500ms per zone)
- [ ] Stale data banner shown when last update > 30s
- [ ] Offline fallback polls REST every 10s
- [ ] Alert card distinguishes `critical` (pulsing) vs `warning` visually
- [ ] `wait_time_seconds == -1` rendered as "Insufficient data" (not "-1s")
- [ ] `queue_stable == false` shown with visual warning (orange background)
- [ ] Confidence interval shaded on wait time chart
- [ ] Multi-zone support: one chart/card section per `zone_id`

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*