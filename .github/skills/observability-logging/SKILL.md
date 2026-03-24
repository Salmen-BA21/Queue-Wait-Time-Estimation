---
name: observability-logging
description: "Structured logging conventions for Python and n8n, Prometheus/Grafana metrics, SLO alerts for queue backlog, webhook retry logic, and dead-letter queue for failed payloads."
user-invocable: true
---

# 📊 Skill: observability-logging

> Structured logging conventions for Python and n8n, Prometheus/Grafana metrics, SLO alerts for queue backlog, webhook retry logic, and dead-letter queue for failed payloads.

---

## 🪵 Structured Logging — Python

### Logger Setup (JSON structured logs)
```python
# backend/src/utils/logger.py
import logging, json, time, os
from typing import Any

class JSONFormatter(logging.Formatter):
    """Emits one JSON line per log record — compatible with Grafana Loki, Datadog, etc."""
    def format(self, record: logging.LogRecord) -> str:
        base = {
            /* Lines 19-32 omitted */
        return json.dumps(base)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        /* Lines 38-40 omitted */
        logger.setLevel(logging.DEBUG if os.getenv("ENV") == "development" else logging.INFO)
    return logger
```

### Usage Convention
```python
log = get_logger("queue.analyzer")

# ✅ Structured — searchable fields
log.info("metrics_computed", extra={
    "ctx_zone_id":         "checkout_lane_3",
    "ctx_camera_id":       "cam_01",
    "ctx_people_in_zone":  7,
    "ctx_wait_time":       15.3,
    "ctx_lambda":          0.15,
    "ctx_mu":              0.16,
    "ctx_uncertainty":     "MEDIUM",
})

# ✅ Alert fired
log.warning("alert_fired", extra={
    "ctx_zone_id":    "checkout_lane_3",
    "ctx_alert_type": "WAIT_TIME_WARNING",
    "ctx_value":      72.3,
    "ctx_threshold":  60,
})

# ✅ Webhook outcome
log.info("n8n_webhook_sent", extra={
    "ctx_zone_id":     "checkout_lane_3",
    "ctx_status_code": 200,
    "ctx_latency_ms":  43,
})

# ❌ Avoid — unstructured, unsearchable
log.info(f"Zone checkout_lane_3 has 7 people, wait=15s")
```

---

## 📐 Log Levels Convention

| Level | When to use |
|-------|-------------|
| `DEBUG` | Per-frame detection counts, tracking ID assignments |
| `INFO`  | Metrics computed, alert fired/cleared, webhook sent, zone state changes |
| `WARNING` | Webhook failed (will retry), detection confidence low, ID swaps detected |
| `ERROR` | Webhook failed after all retries, video capture lost, unhandled exception |
| `CRITICAL` | System cannot continue (GPU OOM, database down) |

---

## 🔢 Prometheus Metrics

### Python – Metric Definitions
```python
# backend/src/observability/metrics.py
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ── Queue state metrics ──────────────────────────────────────────────────────
PEOPLE_IN_ZONE = Gauge(
    "queue_people_in_zone",
    "Current number of people in zone",
    labelnames=["zone_id", "camera_id"],
)
WAIT_TIME_SECONDS = Gauge(
    "queue_wait_time_seconds",
    "Estimated wait time in seconds",
    labelnames=["zone_id"],
)
ARRIVAL_RATE = Gauge(
    "queue_arrival_rate_per_sec",
    "Estimated arrival rate (lambda)",
    labelnames=["zone_id"],
)
SERVICE_RATE = Gauge(
    "queue_service_rate_per_sec",
    "Estimated service rate (mu)",
    labelnames=["zone_id"],
)
UNCERTAINTY_LEVEL = Gauge(
    "queue_uncertainty_level",
    "Uncertainty level: 0=LOW, 1=MEDIUM, 2=HIGH",
    labelnames=["zone_id"],
)

# ── Alert metrics ─────────────────────────────────────────────────────────────
ALERTS_FIRED = Counter(
    "queue_alerts_fired_total",
    "Total number of alerts fired",
    labelnames=["zone_id", "alert_type", "severity"],
)

# ── Webhook metrics ───────────────────────────────────────────────────────────
WEBHOOK_REQUESTS = Counter(
    "n8n_webhook_requests_total",
    "Total webhook POST attempts",
    labelnames=["zone_id", "status"],  # status: success|retry|dead_letter
)
WEBHOOK_LATENCY = Histogram(
    "n8n_webhook_latency_seconds",
    "Webhook POST latency",
    labelnames=["zone_id"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# ── Detection metrics ─────────────────────────────────────────────────────────
DETECTION_FPS = Gauge("queue_detection_fps", "Current frames per second", labelnames=["camera_id"])
DETECTION_CONFIDENCE = Histogram(
    "queue_yolo_confidence",
    "Distribution of YOLO detection confidence scores",
    labelnames=["camera_id"],
    buckets=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

UNCERTAINTY_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

def record_metrics(payload: dict) -> None:
    zone  = payload["zone_id"]
    cam   = payload["camera_id"]
    m     = payload["metrics"]
    u     = payload["uncertainty"]

    PEOPLE_IN_ZONE.labels(zone_id=zone, camera_id=cam).set(m["people_in_zone"])
    WAIT_TIME_SECONDS.labels(zone_id=zone).set(max(m["wait_time_seconds"], 0))
    ARRIVAL_RATE.labels(zone_id=zone).set(m["arrival_rate"])
    SERVICE_RATE.labels(zone_id=zone).set(m["service_rate"])
    UNCERTAINTY_LEVEL.labels(zone_id=zone).set(UNCERTAINTY_MAP[u["level"]])
    DETECTION_FPS.labels(camera_id=cam).set(payload["fps"])

    for alert in payload.get("alerts", []):
        ALERTS_FIRED.labels(
            /* Lines 172-175 omitted */
        ).inc()


def start_metrics_server(port: int = 9090) -> None:
    start_http_server(port)
```

---

## 📊 Grafana Dashboard Panels

### Key Panels to Configure

| Panel | Query | Alert threshold |
|-------|-------|----------------|
| Wait Time (per zone) | `queue_wait_time_seconds` | > 60s → yellow; > 120s → red |
| People in Zone | `queue_people_in_zone` | > 8 → yellow; > 15 → red |
| Arrival Rate | `queue_arrival_rate_per_sec` | > 0.5/s → yellow |
| Webhook Success Rate | `rate(n8n_webhook_requests_total{status="success"}[5m])` | < 95% → alert |
| Alert Rate | `rate(queue_alerts_fired_total[10m])` | spike detection |
| FPS Health | `queue_detection_fps` | < 15 → warning |
| Uncertainty Distribution | `queue_uncertainty_level` | avg > 1.5 → warning |

### SLO: Queue Backlog Alert (Grafana)
```yaml
# grafana/alerts/queue_backlog_slo.yaml
apiVersion: 1
groups:
  - name: queue_slo
    rules:
```

---

## 🔁 Webhook Retry Logic

```python
# backend/src/integrations/n8n_client.py
import time, requests, logging
from utils.logger import get_logger
from observability.metrics import WEBHOOK_REQUESTS, WEBHOOK_LATENCY

log = get_logger("n8n.client")

RETRY_DELAYS = [1, 5, 15]   # seconds between retries (3 attempts total)
TIMEOUT_SEC  = 5


def post_with_retry(url: str, payload: dict, headers: dict) -> bool:
    """
    Returns True on success, False if all retries exhausted (→ dead letter).
    """
    zone = payload.get("zone_id", "unknown")

    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:

    # All retries failed
    WEBHOOK_REQUESTS.labels(zone_id=zone, status="dead_letter").inc()
    dead_letter(payload)
    return False
```

---

## 📬 Dead-Letter Queue

```python
# backend/src/integrations/dead_letter.py
"""
Persists failed webhook payloads to disk for manual replay or investigation.
"""
import json, pathlib, time
from utils.logger import get_logger

log = get_logger("n8n.dead_letter")

DEAD_LETTER_DIR = pathlib.Path("data/dead_letter")
DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES = 500   # Rolling cap — delete oldest when exceeded


def dead_letter(payload: dict) -> None:
    """Write failed payload to disk with timestamp."""
    fname = DEAD_LETTER_DIR / f"{int(time.time())}_{payload.get('zone_id', 'unknown')}.json"
    fname.write_text(json.dumps(payload, indent=2))

    log.error("payload_dead_lettered", extra={
        "ctx_zone_id": payload.get("zone_id"),
        "ctx_file":    str(fname),
    })

    # Purge oldest if over cap
    files = sorted(DEAD_LETTER_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    for old in files[:-MAX_FILES]:
        old.unlink()


def replay_dead_letters(n8n_url: str, headers: dict, limit: int = 50) -> tuple[int, int]:
    """
    Replay dead-letter files. Returns (sent_count, failed_count).
    Call manually or via a scheduled task after n8n recovers.
    """
    import requests
    sent = failed = 0
    for path in sorted(DEAD_LETTER_DIR.glob("*.json"))[:limit]:
        payload = json.loads(path.read_text())

    log.info("dead_letter_replay_complete", extra={
        /* Lines 348-350 omitted */
    return sent, failed
```

---

## 🔁 n8n Workflow Execution Logging

Add a **Code node** at the end of every n8n workflow to log execution details:

```javascript
// "Log Execution" — Code node at end of workflow
const execution = {
  workflow_name:  $workflow.name,
  /* Lines 363-367 omitted */
  ts:             new Date().toISOString(),
};

// n8n stores this in its own DB — visible in execution history
console.log(JSON.stringify(execution));
return [{ json: { ...execution, success: true } }];
```

---

## ✅ Observability Checklist

- [ ] Python logger outputs JSON (one line per record)
- [ ] All `extra={}` fields use `ctx_` prefix convention
- [ ] Prometheus `/metrics` endpoint live on port 9090
- [ ] `queue_people_in_zone`, `queue_wait_time_seconds` gauges updated each cycle
- [ ] `queue_alerts_fired_total` counter incremented on every alert
- [ ] `n8n_webhook_requests_total` labelled with `status: success|retry|dead_letter`
- [ ] Grafana dashboard imported with all 7 key panels
- [ ] SLO alert rules configured for backlog and webhook failure
- [ ] Webhook retry logic: 3 attempts with 1s/5s/15s delays
- [ ] Dead-letter directory created and writable
- [ ] Dead-letter replay script tested after simulated n8n outage
- [ ] n8n workflow includes a "Log Execution" Code node at end

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*