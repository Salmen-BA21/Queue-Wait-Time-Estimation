---
name: queue-metrics-testdata
description: "Payload generators, fixture management, replay sequences, and test helpers for the queue wait-time system."
user-invocable: true
---

# 🧪 Skill: queue-metrics-testdata

> Payload generators, fixture management, replay sequences, and test helpers for the queue wait-time system.

---

## 📦 Canonical Payload Shapes

### 1. No-Alert (Stable Queue)
```json
{
  "timestamp": "2026-03-05T08:00:00.000Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 2,
    "arrival_rate": 0.033,
    "service_rate": 0.10,
    "wait_time_seconds": 3.8,
    "queue_stable": true
  },
  "uncertainty": {
    "lambda_ci": [0.01, 0.07],
    "mu_ci": [0.06, 0.15],
    "wait_time_ci": [2.0, 6.5],
    "level": "LOW"
  },
  "alerts": [],
  "raw_detection_count": 2,
  "fps": 24.9
}
```

### 2. Single Warning Alert
```json
{
  "timestamp": "2026-03-05T12:00:00.000Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 9,
    "arrival_rate": 0.15,
    "service_rate": 0.16,
    "wait_time_seconds": 72.3,
    "queue_stable": true
  },
  "uncertainty": {
    "lambda_ci": [0.10, 0.22],
    "mu_ci": [0.11, 0.23],
    "wait_time_ci": [50.0, 98.0],
    "level": "MEDIUM"
  },
  "alerts": [
    {
      "type": "WAIT_TIME_WARNING",
      "severity": "warning",
      "message": "Wait time exceeded 60s threshold",
      "value": 72.3,
      "threshold": 60
    }
  ],
  "raw_detection_count": 9,
  "fps": 24.1
}
```

### 3. Multi-Alert Critical
```json
{
  "timestamp": "2026-03-05T14:32:10.123Z",
  "camera_id": "cam_02",
  "zone_id": "checkout_lane_1",
  "metrics": {
    "people_in_zone": 18,
    "arrival_rate": 0.52,
    "service_rate": 0.12,
    "wait_time_seconds": 154.0,
    "queue_stable": false
  },
  "uncertainty": {
    "lambda_ci": [0.40, 0.65],
    "mu_ci": [0.07, 0.19],
    "wait_time_ci": [120.0, 200.0],
    "level": "HIGH"
  },
  "alerts": [
    {
      "type": "WAIT_TIME_CRITICAL",
      "severity": "critical",
      "message": "Wait time exceeded 120s threshold",
      "value": 154.0,
      "threshold": 120
    },
    {
      "type": "QUEUE_BACKLOG_CRITICAL",
      "severity": "critical",
      "message": "Queue backlog exceeded 15 people threshold",
      "value": 18,
      "threshold": 15
    },
    {
      "type": "ARRIVAL_SPIKE",
      "severity": "warning",
      "message": "Arrival rate spike detected",
      "value": 0.52,
      "threshold": 0.5
    },
    {
      "type": "HIGH_UNCERTAINTY",
      "severity": "warning",
      "message": "High uncertainty in estimates",
      "value": "HIGH",
      "threshold": "MEDIUM"
    }
  ],
  "raw_detection_count": 18,
  "fps": 21.3
}
```

### 4. Unstable Queue (λ ≈ μ, W → ∞)
```json
{
  "timestamp": "2026-03-05T11:00:00.000Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 11,
    "arrival_rate": 0.159,
    "service_rate": 0.160,
    "wait_time_seconds": 999.0,
    "queue_stable": false
  },
  "uncertainty": {
    "lambda_ci": [0.11, 0.21],
    "mu_ci": [0.10, 0.17],
    "wait_time_ci": [220.0, 1140.0],
    "level": "HIGH"
  },
  "alerts": [
    {
      "type": "QUEUE_UNSTABLE",
      "severity": "warning",
      "message": "Queue stability loss, λ ~ μ",
      "value": 0.159,
      "threshold": "SERVICE_RATE_LEQ_ARRIVAL_RATE"
    }
  ],
  "raw_detection_count": 11,
  "fps": 23.0
}
```

### 5. Empty Queue (Zero State)
```json
{
  "timestamp": "2026-03-05T06:00:00.000Z",
  "camera_id": "cam_01",
  "zone_id": "checkout_lane_3",
  "metrics": {
    "people_in_zone": 0,
    "arrival_rate": 0.0,
    "service_rate": 0.0,
    "wait_time_seconds": 0.0,
    "queue_stable": true
  },
  "uncertainty": {
    "lambda_ci": [0.0, 0.0],
    "mu_ci": [0.0, 0.0],
    "wait_time_ci": [0.0, 0.0],
    "level": "LOW"
  },
  "alerts": [],
  "raw_detection_count": 0,
  "fps": 25.0
}
```

---

## 🐍 Python Payload Generator

```python
# test_data/generators.py
import json
import random
from datetime import datetime, timezone
from typing import Literal, Optional

AlertSeverity = Literal["warning", "critical"]

ALERT_CATALOG = {
    "WAIT_TIME_WARNING":     {"severity": "warning",  "threshold": 60},
    "WAIT_TIME_CRITICAL":    {"severity": "critical", "threshold": 120},
    "QUEUE_BACKLOG_WARNING":  {"severity": "warning",  "threshold": 8},
    "QUEUE_BACKLOG_CRITICAL": {"severity": "critical", "threshold": 15},
    "ARRIVAL_SPIKE":         {"severity": "warning",  "threshold": 0.5},
    "SERVICE_DEGRADATION":   {"severity": "warning",  "threshold": 0.05},
    "HIGH_UNCERTAINTY":      {"severity": "warning",  "threshold": "MEDIUM"},
    "QUEUE_UNSTABLE":        {"severity": "warning",  "threshold": None},
}


def make_payload(
    *,
    camera_id: str = "cam_01",
    zone_id: str = "checkout_lane_3",
    people: int = 3,
    arrival_rate: float = 0.05,
    service_rate: float = 0.10,
    wait_time: float = 5.0,
    stable: bool = True,
    uncertainty_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW",
    alert_types: Optional[list[str]] = None,
    fps: float = 24.0,
) -> dict:
    alerts = []
    for atype in (alert_types or []):
        cat = ALERT_CATALOG[atype]
        alerts.append({
            "type": atype,
            "severity": cat["severity"],
            "message": f"{atype} triggered",
            "value": {"WAIT_TIME_WARNING": 72.3, "WAIT_TIME_CRITICAL": 154.0}.get(atype, 0.0),
            "threshold": cat["threshold"],
        })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "camera_id": camera_id,
        "zone_id": zone_id,
        "metrics": {
            "people_in_zone": people,
            "arrival_rate": arrival_rate,
            "service_rate": service_rate,
            "wait_time_seconds": wait_time,
            "queue_stable": stable,
        },
        "uncertainty": {
            "lambda_ci": [max(0, arrival_rate - 0.05), arrival_rate + 0.05],
            "mu_ci": [max(0, service_rate - 0.05), service_rate + 0.05],
            "wait_time_ci": [max(0, wait_time - 15), wait_time + 15],
            "level": uncertainty_level,
        },
        "alerts": alerts,
        "raw_detection_count": people,
        "fps": fps,
    }

# ── Convenience presets ──────────────────────────────────────────────────────
def stable_payload(**kw) -> dict:
    return make_payload(**kw)

def warning_payload(**kw) -> dict:
    return make_payload(
        people=9, arrival_rate=0.15, service_rate=0.16,
        wait_time=72.3, stable=True, uncertainty_level="MEDIUM",
        alert_types=["WAIT_TIME_WARNING"], **kw
    )

def critical_payload(**kw) -> dict:
    return make_payload(
        people=18, arrival_rate=0.52, service_rate=0.12,
        wait_time=154.0, stable=False, uncertainty_level="HIGH",
        alert_types=["WAIT_TIME_CRITICAL", "QUEUE_BACKLOG_CRITICAL"], **kw
    )

def empty_queue_payload(**kw) -> dict:
    return make_payload(people=0, arrival_rate=0.0, service_rate=0.0, wait_time=0.0, **kw)
```

---

## 🔁 Replay Sequence Generator

```python
# test_data/replay.py
"""Generates a time-series sequence simulating a realistic queue day."""
import time
from generators import make_payload, warning_payload, critical_payload, stable_payload

MORNING_QUIET   = dict(people=2,  arrival_rate=0.03, service_rate=0.10, wait_time=3.5)
LUNCH_RUSH      = dict(people=14, arrival_rate=0.42, service_rate=0.15, wait_time=130.0,
                       stable=False, uncertainty_level="HIGH",
                       alert_types=["WAIT_TIME_CRITICAL", "QUEUE_BACKLOG_CRITICAL"])
AFTERNOON_NORM  = dict(people=5,  arrival_rate=0.08, service_rate=0.12, wait_time=9.0,
                       uncertainty_level="MEDIUM")
EVENING_SPIKE   = dict(people=11, arrival_rate=0.51, service_rate=0.13, wait_time=88.0,
                       alert_types=["ARRIVAL_SPIKE", "WAIT_TIME_WARNING"],
                       uncertainty_level="MEDIUM")
CLOSING_EMPTY   = dict(people=0,  arrival_rate=0.0,  service_rate=0.0,  wait_time=0.0)

DAY_SEQUENCE = [
    (MORNING_QUIET,  "08:00 – Quiet morning"),
    (LUNCH_RUSH,     "12:30 – Lunch rush"),
    (AFTERNOON_NORM, "14:00 – Post-lunch normal"),
    (EVENING_SPIKE,  "17:45 – Evening spike"),
    (CLOSING_EMPTY,  "21:00 – Closing"),
]

def replay(delay_seconds: float = 0.0) -> list[dict]:
    """Return all payloads in sequence; optionally sleep between them."""
    payloads = []
    for scenario, label in DAY_SEQUENCE:
        p = make_payload(**scenario)
        payloads.append(p)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return payloads
```

---

## ✅ 1-Line Assertion Helpers (pytest)

```python
# tests/helpers/payload_assertions.py

def assert_valid_payload(p: dict) -> None:
    """Smoke-test a payload against the required schema."""
    assert "timestamp" in p
    assert "camera_id" in p
    assert "zone_id" in p

    m = p["metrics"]
    assert isinstance(m["people_in_zone"], int)
    assert m["arrival_rate"] >= 0
    assert m["service_rate"] >= 0
    assert m["wait_time_seconds"] >= 0
    assert isinstance(m["queue_stable"], bool)

    u = p["uncertainty"]
    assert u["level"] in {"LOW", "MEDIUM", "HIGH"}
    assert len(u["lambda_ci"]) == 2
    assert u["lambda_ci"][0] <= u["lambda_ci"][1]

    assert isinstance(p["alerts"], list)
    for a in p["alerts"]:
        assert a["severity"] in {"warning", "critical"}
        assert "type" in a and "message" in a

def assert_no_alerts(p: dict) -> None:
    assert p["alerts"] == [], f"Expected no alerts, got: {p['alerts']}"

def assert_has_alert(p: dict, alert_type: str) -> None:
    types = [a["type"] for a in p["alerts"]]
    assert alert_type in types, f"Expected alert '{alert_type}', found: {types}"

def assert_critical(p: dict) -> None:
    severities = {a["severity"] for a in p["alerts"]}
    assert "critical" in severities, "Expected at least one critical alert"
```

---

## 🗂️ Fixture File Conventions

```
test_data/
├── fixtures/
│   ├── stable.json              ← No-alert baseline
│   ├── warning_single.json      ← One warning alert
│   ├── critical_multi.json      ← 2+ critical alerts
│   ├── empty_queue.json         ← Zero state
│   └── unstable_near_sat.json   ← λ ≈ μ edge case
├── sequences/
│   └── full_day_replay.json     ← Array of payloads in time order
├── generators.py
├── replay.py
└── README.md
```

### Loading Fixtures in Tests
```python
import json, pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())
```

---

## 🔢 Boundary / Edge Case Checklist

| Scenario | `people_in_zone` | `arrival_rate` | `service_rate` | Expected behavior |
|----------|-----------------|----------------|----------------|-------------------|
| Empty queue | 0 | 0.0 | 0.0 | No alerts, W=0 |
| Near saturation | any | 0.159 | 0.160 | QUEUE_UNSTABLE |
| Overflow (λ > μ) | high | 0.20 | 0.10 | W=negative → clamp to 999 |
| High uncertainty | any | any | any | `level="HIGH"`, alert sent |
| Single person | 1 | low | any | No backlog alert |
| Max backlog | 16+ | high | low | QUEUE_BACKLOG_CRITICAL |
| Arrival spike | any | >0.5 | any | ARRIVAL_SPIKE alert |

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*