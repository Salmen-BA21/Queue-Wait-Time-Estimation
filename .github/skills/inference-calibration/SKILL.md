---
name: inference-calibration
description: "YOLO/ByteTrack false positive/negative mitigation, threshold tuning, peak smoothing, and inference-to-alert rules mapping for the queue system."
user-invocable: true
---

# 🎯 Skill: inference-calibration

> YOLO/ByteTrack false positive/negative mitigation, threshold tuning, peak smoothing, and inference-to-alert rules mapping for the queue system.

---

## 🧠 Root Causes of Bad Detections

| Source | Effect on Queue Metrics | Typical symptom |
|--------|------------------------|-----------------|
| YOLO false positive (ghost person) | `people_in_zone` inflated | W spikes without real crowd |
| YOLO false negative (missed person) | `people_in_zone` deflated | W underestimated |
| ByteTrack ID swap | Same person counted twice | λ double-counted on re-entry |
| Occlusion (people overlap) | Missed detections | `raw_detection_count` < true count |
| Low FPS | ID tracking breaks | ByteTrack loses continuity |
| Poor lighting | Low confidence scores | High uncertainty even when stable |

---

## ⚙️ YOLO Configuration Thresholds

### Recommended defaults for queue monitoring
```python
# backend/src/perception/detector.py

YOLO_CONFIG = {
    "conf_threshold":  0.45,    # Minimum confidence to accept a detection
                                # < 0.35 → too many ghosts
                                # > 0.65 → misses partially occluded people
    "iou_threshold":   0.50,    # NMS overlap threshold
                                # Lower = more boxes kept (noisier)
                                # Higher = aggressive suppression
    "model_size":      "small", # nano (speed) → small → medium → large → xlarge (accuracy)
                                # Use 'medium' if GPU available; 'small' for CPU
    "classes":         [0],     # Class 0 = person only (ignore bags, carts)
    "max_det":         50,      # Cap detections per frame (prevents runaway)
    "half_precision":  True,    # FP16 for GPU speedup (set False on CPU)
}
```

### Tuning Guide by Environment

| Environment | Recommended `conf_threshold` | Recommended model |
|-------------|------------------------------|-------------------|
| Bright retail / supermarket | 0.45 – 0.55 | small / medium |
| Dim lighting / evening | 0.35 – 0.45 | medium / large |
| Outdoor / variable light | 0.40 – 0.50 | medium |
| Dense crowds (>15 people) | 0.40 (lower) + higher `iou`) | large / xlarge |
| Low-end CPU only | 0.50 + nano model | nano |

---

## 🔁 ByteTrack Calibration

```python
# backend/src/perception/tracker.py

BYTETRACK_CONFIG = {
    "track_thresh":     0.55,   # Min detection conf to start a new track
                                # Lower → tracks uncertain detections (more ID swaps)
                                # Higher → misses briefly occluded people
    "track_buffer":     60,     # Frames to keep a lost track alive (@ 30fps = 2 seconds)
                                # Too low → exit events on every occlusion
                                # Too high → ghost tracks linger
    "match_thresh":     0.80,   # IoU threshold for matching detections to tracks
    "min_box_area":     100,    # Ignore very small boxes (noise / background)
    "frame_rate":       30,     # Must match actual capture FPS for correct buffer
}
```

### ID Swap Detection and Mitigation
```python
def detect_id_swap(track_history: dict, person_id: int, new_box: tuple) -> bool:
    """
    Heuristic: flag if a track jumps more than 30% of frame width in one frame.
    Indicates an ID swap rather than real movement.
    """
    if person_id not in track_history:
        return False
    prev_cx = (track_history[person_id]["box"][0] + track_history[person_id]["box"][2]) / 2
    new_cx  = (new_box[0] + new_box[2]) / 2
    frame_width = 1920  # or pull from video capture
    jump_ratio = abs(new_cx - prev_cx) / frame_width
    return jump_ratio > 0.30
```

---

## 📊 people_in_zone Threshold Tuning

### EMA Smoothing (recommended)
```python
class ZoneCounter:
    def __init__(self, alpha: float = 0.3):
        """
        alpha: EMA smoothing factor
          - 0.1 = heavy smoothing (slow to respond to real changes)
          /* Lines 98-99 omitted */
          - 0.9 = light smoothing (reacts fast, noisy)
        /* Lines 100-103 omitted */
        """
        self._ema = 0.0

    def update(self, raw_count: int) -> float:
        self._ema = self.alpha * raw_count + (1 - self.alpha) * self._ema
        return round(self._ema)
```

### Minimum Dwell Time Filter
```python
MIN_DWELL_SECONDS = 1.5  # Person must be in zone for at least N seconds
                          # before counting as "in queue"
                          # Prevents: walkers-by, brief overlaps at zone boundary
```

### Zone Boundary Buffer
```python
ZONE_BOUNDARY_BUFFER_PX = 15  # Shrink effective zone polygon by N pixels inward
                               # Prevents edge-clippers from triggering events
```

---

## 📈 Peak Smoothing (Arrival/Service Rate)

### Exponential Moving Average for λ and μ
```python
RATE_WINDOW_SECONDS = 60   # Rolling window for rate calculation
                            # Shorter (30s) → reactive but noisy on small counts
                            # Longer (120s) → stable but slow to detect spikes

RATE_EMA_ALPHA = 0.2        # Heavy smoothing on rates (they're noisy by nature)
```

### Spike Detection
```python
def is_arrival_spike(current_lambda: float, ema_lambda: float,
                     multiplier: float = 2.5) -> bool:
    """
    Arrival spike = current rate is 2.5× the recent EMA.
    Avoids false spikes from single-frame bursts.
    """
    return current_lambda > (ema_lambda * multiplier) and current_lambda > 0.1
```

---

## 🗺️ Inference-to-Alert Rules Mapping

### Decision Table
```
people_in_zone (smoothed)  |  wait_time_seconds  |  uncertainty.level  →  Alert
────────────────────────────────────────────────────────────────────────────────────
0                           |  any                |  any                →  No alert (empty queue)
1–7                         |  ≤60                |  LOW/MEDIUM         →  No alert
1–7                         |  61–120             |  any                →  WAIT_TIME_WARNING
1–7                         |  >120               |  any                →  WAIT_TIME_CRITICAL
8–14                        |  any                |  any                →  QUEUE_BACKLOG_WARNING
≥15                         |  any                |  any                →  QUEUE_BACKLOG_CRITICAL
any                         |  any                |  HIGH               →  HIGH_UNCERTAINTY (do not suppress others)
any, λ > 0.5               |  any                |  any                →  ARRIVAL_SPIKE
queue_stable = false        |  any                |  any                →  QUEUE_UNSTABLE
```

### When to Suppress an Alert
```python
def should_suppress_alert(alert_type: str, recent_alerts: list, window_sec: int = 120) -> bool:
    """
    Suppress if same alert fired in the last `window_sec` seconds.
    Prevents Telegram spam when condition persists.
    """
    now = time.time()
    return any(
        a["type"] == alert_type and (now - a["fired_at"]) < window_sec
        for a in recent_alerts
    )

SUPPRESSION_WINDOWS = {
    "WAIT_TIME_WARNING":     120,  # 2 min
    "WAIT_TIME_CRITICAL":    60,   # 1 min (urgent, less suppression)
    "QUEUE_BACKLOG_WARNING":  180,  # 3 min
    "QUEUE_BACKLOG_CRITICAL": 60,
    "ARRIVAL_SPIKE":         90,
    "HIGH_UNCERTAINTY":      300,  # 5 min (low urgency)
    "QUEUE_UNSTABLE":        60,
}
```

---

## 🏋️ Retraining Triggers

Indicators that YOLO fine-tuning is needed for your specific environment:

| Symptom | Metric | Action |
|---------|--------|--------|
| `raw_detection_count` consistently differs from manual count by >20% | Count accuracy < 80% | Collect and annotate 200+ frames from this camera, fine-tune |
| Alerts fire at empty queues | False positive rate > 5% | Raise `conf_threshold` by 0.05; if persists, retrain |
| Alerts missed during obvious rushes | False negative rate > 10% | Lower `conf_threshold` by 0.05; check lighting |
| FPS drops below 15 | Tracking continuity breaks | Switch to `nano` model or reduce resolution |
| `uncertainty.level` stuck on HIGH despite stable conditions | Calibration drift | Re-annotate a calibration sequence with ground-truth counts |

### Minimum Fine-Tune Dataset for Queue Monitoring
```
200 frames minimum:
  - 40 frames: empty queue
  - 60 frames: 1–5 people (normal)
  - 60 frames: 6–15 people (busy)
  - 40 frames: dense crowd / occlusion
  - All annotated with bounding boxes + person class only
```

---

## 🧪 Calibration Sanity Tests

```python
# tests/test_inference_calibration.py
import pytest
from perception.detector import detect_people
from perception.tracker import ZoneCounter

def test_empty_frame_no_detections(empty_frame):
    dets = detect_people(empty_frame)
    assert len(dets) == 0, "Ghost detections on empty frame"

def test_single_person_detected(single_person_frame):
    dets = detect_people(single_person_frame)
    assert len(dets) == 1

def test_ema_smoothing_dampens_spike():
    counter = ZoneCounter(alpha=0.3)
    counts = [3, 3, 3, 20, 3, 3]   # spike at position 3
    smoothed = [counter.update(c) for c in counts]
    assert smoothed[3] < 15, "EMA should dampen spike below raw value"

def test_suppression_window_blocks_duplicate():
    recent = [{"type": "WAIT_TIME_WARNING", "fired_at": time.time() - 60}]
    assert should_suppress_alert("WAIT_TIME_WARNING", recent, window_sec=120)
    assert not should_suppress_alert("WAIT_TIME_WARNING", recent, window_sec=30)
```

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*