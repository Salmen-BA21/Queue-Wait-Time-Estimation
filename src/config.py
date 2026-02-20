"""
Global configuration & default constants.

All tuneable values live here so they are easy to find and override later
(e.g. from a YAML/JSON config file or from argparse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── YOLO ─────────────────────────────────────────────────────
YOLO_MODEL_MAP: dict[str, str] = {
    "n": "yolo26n.pt",
    "s": "yolo26s.pt",
    "m": "yolo26m.pt",
    "l": "yolo26l.pt",
    "x": "yolo26x.pt",
}

# COCO class id for "person"
PERSON_CLASS_ID: int = 0

# Minimum detection confidence to keep
DEFAULT_CONFIDENCE: float = 0.35


# ─── Tracker ──────────────────────────────────────────────────
DEFAULT_TRACKER_TYPE: str = "bytetrack"  # "bytetrack" or "botsort"
TRACK_THRESH: float = 0.25
TRACK_BUFFER: int = 60   # frames to keep lost tracks
MATCH_THRESH: float = 0.8


# ─── Zone ─────────────────────────────────────────────────────
# Fallback polygon: full frame (will be overridden by --zone-points)
DEFAULT_ZONE_POLYGON: list[list[int]] = [
    [0, 0],
    [1, 0],
    [1, 1],
    [0, 1],
]  # normalised – scaled to frame size at runtime


# ─── Queue analysis ──────────────────────────────────────────
ARRIVAL_WINDOW_SEC: float = 30.0   # sliding window for λ estimation
SERVICE_WINDOW_SEC: float = 60.0   # sliding window for μ estimation
MIN_EVENTS_FOR_RATE: int = 2       # min events to compute a rate


# ─── Display / Logging ───────────────────────────────────────
DEFAULT_OUTPUT_FPS: int = 0
DEFAULT_LOG_INTERVAL_SEC: float = 5.0
WINDOW_NAME: str = "Queue Estimation"


# ─── Webhook / n8n Integration ────────────────────────────────
# Local n8n webhook URL – change if n8n is on different host/port
N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/queue-metrics"
WEBHOOK_ENABLED: bool = True  # Set to False to disable webhook sending
WEBHOOK_TIMEOUT_SEC: float = 5.0
WEBHOOK_RETRY_COUNT: int = 3
WEBHOOK_SEND_INTERVAL_SEC: float = 5.0  # Send every N seconds (not every frame)

@dataclass
class AppConfig:
    """Runtime configuration assembled from CLI args + defaults."""

    source: str | int = 0
    model_size: str = "n"
    zone_points: Optional[list[list[int]]] = None
    output_fps: int = DEFAULT_OUTPUT_FPS
    log_interval_sec: float = DEFAULT_LOG_INTERVAL_SEC
    confidence: float = DEFAULT_CONFIDENCE
    tracker_type: str = DEFAULT_TRACKER_TYPE

    @property
    def model_path(self) -> str:
        """Return the YOLO weight filename for the chosen size."""
        return YOLO_MODEL_MAP.get(self.model_size, YOLO_MODEL_MAP["n"])

    @property
    def zone_polygon(self) -> list[list[int]]:
        """Return zone polygon – user-supplied or default."""
        return self.zone_points if self.zone_points else DEFAULT_ZONE_POLYGON
