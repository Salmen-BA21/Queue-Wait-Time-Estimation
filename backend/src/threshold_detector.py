"""
Queue threshold detection and alert logic.
Monitors queue metrics against configurable thresholds and generates alerts.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AlertSeverity(Enum):
    """Alert severity levels."""
    WARNING = "warning"


class AlertType(Enum):
    """Types of alerts that can be triggered."""
    QUEUE_BACKLOG = "queue_backlog"


@dataclass
class ThresholdConfig:
    """Configuration for alert thresholds."""
    # Queue length thresholds (people)
    queue_length_warning: int = 8  # Alert if people_in_zone > 8


@dataclass
class QueueAlert:
    """Represents a generated alert."""
    
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    threshold_name: str
    current_value: float
    threshold_value: float
    frame_id: int
    timestamp: float


class QueueThresholdDetector:
    """Detects queue threshold violations and generates alerts."""
    
    def __init__(self, config: Optional[ThresholdConfig] = None):
        """
        Initialize threshold detector.
        
        Parameters
        ----------
        config : ThresholdConfig, optional
            Threshold configuration. Uses defaults if not provided.
        """
        self.config = config or ThresholdConfig()
    
    def check_metrics(
        self,
        people_in_zone: int,
        estimated_wait_sec: float,
        arrival_rate: float,
        service_rate: float,
        queue_stable: bool,
        frame_id: int,
        timestamp: float,
    ) -> list[QueueAlert]:
        """
        Check queue metrics against thresholds.
        
        Parameters
        ----------
        people_in_zone : int
            Current number of people in the queue zone.
        estimated_wait_sec : float
            Estimated wait time in seconds.
        arrival_rate : float
            Arrival rate (people/second).
        service_rate : float
            Service rate (people/second).
        queue_stable : bool
            Whether queue is in stable state.
        frame_id : int
            Current frame ID for tracking.
        timestamp : float
            Frame timestamp (seconds).
        
        Returns
        -------
        list[QueueAlert]
            List of alerts generated in this check.
        """
        alerts: list[QueueAlert] = []

        if people_in_zone > self.config.queue_length_warning:
            alerts.append(QueueAlert(
                alert_type=AlertType.QUEUE_BACKLOG,
                severity=AlertSeverity.WARNING,
                message=f"High queue length: {people_in_zone} people (warning: {self.config.queue_length_warning})",
                threshold_name="queue_length_warning",
                current_value=float(people_in_zone),
                threshold_value=float(self.config.queue_length_warning),
                frame_id=frame_id,
                timestamp=timestamp,
            ))

        return alerts
    
    def reset_statistics(self) -> None:
        """Reset tracking statistics."""
        return None
    
    def get_last_alert(self, alert_type: AlertType) -> Optional[QueueAlert]:
        """Get the last alert of a specific type."""
        return None if alert_type != AlertType.QUEUE_BACKLOG else None
