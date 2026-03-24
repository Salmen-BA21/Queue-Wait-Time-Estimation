"""
Webhook payload structure and utilities for n8n integration.

This module defines the JSON payload format sent to n8n and includes
helper functions for payload creation and validation.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("queue_system.webhook")


@dataclass
class QueuePayload:
    """Webhook payload sent to n8n for queue metrics."""
    
    # Metadata
    timestamp: float  # Unix timestamp
    frame_id: int
    source: str  # e.g., "webcam", "retail_store.mp4"
    feed_id: str  # Unique source identifier (e.g., cashier_3, cam_02)
    
    # Core metrics
    people_in_zone: int
    arrival_rate: float  # λ – per second
    service_rate: float  # μ – per second
    estimated_wait_sec: float
    
    # Uncertainty bounds (95% credible/confidence intervals)
    arrival_rate_lower: float
    arrival_rate_upper: float
    service_rate_lower: float
    service_rate_upper: float
    wait_time_lower: float
    wait_time_upper: float
    
    # Classification
    uncertainty_level: str  # "Low", "Medium", "High"
    queue_stable: bool
    
    # Alerts and thresholds
    alert_triggered: bool = False
    alert_reason: str = ""  # e.g., "queue_exceeded_threshold"
    alert_severity: str = "info"  # "info", "warning", "critical"
    
    # Additional metadata
    system_uptime_sec: float = 0.0
    confidence_scores: list[float] = field(default_factory=list)  # YOLO scores
    establishment_name: str | None = None
    section_name: str | None = None
    employee_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_queue_metrics(
        cls,
        metrics,  # QueueMetrics object
        frame_id: int,
        source: str,
        feed_id: str | None = None,
        alert_triggered: bool = False,
        alert_reason: str = "",
        alert_severity: str = "info",
        confidence_scores: list[float] | None = None,
    ) -> QueuePayload:
        """Create payload from QueueMetrics object."""
        feed_identity = feed_id if feed_id is not None else source
        return cls(
            timestamp=time.time(),
            frame_id=frame_id,
            source=source,
            feed_id=feed_identity,
            people_in_zone=metrics.people_in_zone,
            arrival_rate=metrics.arrival_rate,
            service_rate=metrics.service_rate,
            estimated_wait_sec=metrics.estimated_wait_sec,
            arrival_rate_lower=metrics.arrival_rate_lower,
            arrival_rate_upper=metrics.arrival_rate_upper,
            service_rate_lower=metrics.service_rate_lower,
            service_rate_upper=metrics.service_rate_upper,
            wait_time_lower=metrics.wait_time_lower,
            wait_time_upper=metrics.wait_time_upper,
            uncertainty_level=metrics.uncertainty_level,
            queue_stable=metrics.queue_stable,
            alert_triggered=alert_triggered,
            alert_reason=alert_reason,
            alert_severity=alert_severity,
            confidence_scores=confidence_scores or [],
        )


# Example payload structure (for documentation)
EXAMPLE_PAYLOAD = {
    "timestamp": 1708294800.123,
    "frame_id": 1500,
    "source": "retail_store.mp4",
    "feed_id": "cashier_1",
    "people_in_zone": 4,
    "arrival_rate": 0.133,
    "service_rate": 0.050,
    "estimated_wait_sec": 5.2,
    "arrival_rate_lower": 0.089,
    "arrival_rate_upper": 0.177,
    "service_rate_lower": 0.020,
    "service_rate_upper": 0.080,
    "wait_time_lower": 4.1,
    "wait_time_upper": 6.3,
    "uncertainty_level": "Low",
    "queue_stable": True,
    "alert_triggered": False,
    "alert_reason": "",
    "alert_severity": "info",
    "system_uptime_sec": 3600.5,
    "confidence_scores": [0.95, 0.93, 0.96, 0.94],
    "establishment_name": "Downtown Store",
    "section_name": "Checkout Zone A",
    "employee_name": "John Doe",
}


def validate_payload(payload: dict) -> bool:
    """Validate payload structure before sending."""
    required_fields = {
        "timestamp", "frame_id", "source", "feed_id", "people_in_zone",
        "arrival_rate", "service_rate", "estimated_wait_sec",
        "uncertainty_level", "queue_stable", "alert_triggered"
    }
    
    if not all(field in payload for field in required_fields):
        missing = required_fields - set(payload.keys())
        logger.error("Invalid payload: missing fields %s", missing)
        return False
    
    return True


if __name__ == "__main__":
    # Test payload structure
    print("Example Payload:")
    print(json.dumps(EXAMPLE_PAYLOAD, indent=2))
    
    # Test validation
    is_valid = validate_payload(EXAMPLE_PAYLOAD)
    print(f"\nPayload valid: {is_valid}")
