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
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts that can be triggered."""
    WAIT_TIME_EXCESSIVE = "wait_time_excessive"
    QUEUE_BACKLOG = "queue_backlog"
    ARRIVAL_SPIKE = "arrival_spike"
    SERVICE_DEGRADATION = "service_degradation"
    UNCERTAINTY_HIGH = "uncertainty_high"
    QUEUE_UNSTABLE = "queue_unstable"


@dataclass
class ThresholdConfig:
    """Configuration for alert thresholds."""
    
    # Wait time thresholds (in seconds)
    wait_time_warning: float = 60.0  # Alert if wait > 60s
    wait_time_critical: float = 120.0  # Critical alert if wait > 120s
    
    # Queue length thresholds (people)
    queue_length_warning: int = 8  # Alert if people_in_zone > 8
    queue_length_critical: int = 15  # Critical if > 15
    
    # Arrival rate thresholds (people/sec)
    arrival_rate_spike: float = 0.5  # Alert if arrival_rate > 0.5/sec (30/min)
    
    # Service rate thresholds (people/sec) - degradation if drops below this
    service_rate_min: float = 0.04  # Alert if service_rate < 0.04/sec (2.4/min)
    
    # Uncertainty thresholds
    uncertainty_critical_level: str = "High"  # Alert if uncertainty is "High"
    
    # Stability threshold - alert if not stable for N consecutive frames
    stability_check_frames: int = 5  # Must be unstable for 5+ frames to trigger


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
        
        # Tracking for persistence checks
        self.consecutive_unstable_frames = 0
        self.last_alert_by_type: dict[AlertType, QueueAlert] = {}
    
    def check_metrics(
        self,
        people_in_zone: int,
        estimated_wait_sec: float,
        arrival_rate: float,
        service_rate: float,
        uncertainty_level: str,
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
        uncertainty_level : str
            Uncertainty classification ("Low", "Medium", "High").
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
        
        # Check wait time
        alerts.extend(self._check_wait_time(estimated_wait_sec, frame_id, timestamp))
        
        # Check queue length
        alerts.extend(self._check_queue_length(people_in_zone, frame_id, timestamp))
        
        # Check arrival rate spike
        alerts.extend(self._check_arrival_spike(arrival_rate, frame_id, timestamp))
        
        # Check service degradation
        alerts.extend(self._check_service_rate(service_rate, frame_id, timestamp))
        
        # Check uncertainty
        alerts.extend(self._check_uncertainty(uncertainty_level, frame_id, timestamp))
        
        # Check queue stability
        alerts.extend(self._check_queue_stability(queue_stable, frame_id, timestamp))
        
        # Store alerts for persistence tracking
        for alert in alerts:
            self.last_alert_by_type[alert.alert_type] = alert
        
        return alerts
    
    def _check_wait_time(
        self, wait_time: float, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check if wait time exceeds thresholds."""
        alerts = []
        
        if wait_time > self.config.wait_time_critical:
            alerts.append(QueueAlert(
                alert_type=AlertType.WAIT_TIME_EXCESSIVE,
                severity=AlertSeverity.CRITICAL,
                message=f"Excessive wait time: {wait_time:.1f}s (critical: {self.config.wait_time_critical}s)",
                threshold_name="wait_time_critical",
                current_value=wait_time,
                threshold_value=self.config.wait_time_critical,
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        elif wait_time > self.config.wait_time_warning:
            alerts.append(QueueAlert(
                alert_type=AlertType.WAIT_TIME_EXCESSIVE,
                severity=AlertSeverity.WARNING,
                message=f"High wait time: {wait_time:.1f}s (warning: {self.config.wait_time_warning}s)",
                threshold_name="wait_time_warning",
                current_value=wait_time,
                threshold_value=self.config.wait_time_warning,
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_queue_length(
        self, people_count: int, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check if queue length exceeds thresholds."""
        alerts = []
        
        if people_count > self.config.queue_length_critical:
            alerts.append(QueueAlert(
                alert_type=AlertType.QUEUE_BACKLOG,
                severity=AlertSeverity.CRITICAL,
                message=f"Critical queue backlog: {people_count} people (critical: {self.config.queue_length_critical})",
                threshold_name="queue_length_critical",
                current_value=float(people_count),
                threshold_value=float(self.config.queue_length_critical),
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        elif people_count > self.config.queue_length_warning:
            alerts.append(QueueAlert(
                alert_type=AlertType.QUEUE_BACKLOG,
                severity=AlertSeverity.WARNING,
                message=f"High queue length: {people_count} people (warning: {self.config.queue_length_warning})",
                threshold_name="queue_length_warning",
                current_value=float(people_count),
                threshold_value=float(self.config.queue_length_warning),
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_arrival_spike(
        self, arrival_rate: float, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check for arrival rate spikes."""
        alerts = []
        
        if arrival_rate > self.config.arrival_rate_spike:
            alerts.append(QueueAlert(
                alert_type=AlertType.ARRIVAL_SPIKE,
                severity=AlertSeverity.WARNING,
                message=f"Arrival spike detected: {arrival_rate:.3f}/s ({arrival_rate*60:.1f}/min)",
                threshold_name="arrival_rate_spike",
                current_value=arrival_rate,
                threshold_value=self.config.arrival_rate_spike,
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_service_rate(
        self, service_rate: float, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check for service rate degradation."""
        alerts = []
        
        if service_rate < self.config.service_rate_min:
            alerts.append(QueueAlert(
                alert_type=AlertType.SERVICE_DEGRADATION,
                severity=AlertSeverity.WARNING,
                message=f"Service degradation: {service_rate:.3f}/s ({service_rate*60:.1f}/min)",
                threshold_name="service_rate_min",
                current_value=service_rate,
                threshold_value=self.config.service_rate_min,
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_uncertainty(
        self, uncertainty_level: str, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check for high uncertainty."""
        alerts = []
        
        if uncertainty_level == self.config.uncertainty_critical_level:
            alerts.append(QueueAlert(
                alert_type=AlertType.UNCERTAINTY_HIGH,
                severity=AlertSeverity.INFO,
                message=f"High uncertainty in estimates: {uncertainty_level}",
                threshold_name="uncertainty_critical",
                current_value=1.0,
                threshold_value=1.0,
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_queue_stability(
        self, queue_stable: bool, frame_id: int, timestamp: float
    ) -> list[QueueAlert]:
        """Check for queue instability."""
        alerts = []
        
        if not queue_stable:
            self.consecutive_unstable_frames += 1
        else:
            self.consecutive_unstable_frames = 0
        
        # Alert only after sustained instability
        if self.consecutive_unstable_frames >= self.config.stability_check_frames:
            alerts.append(QueueAlert(
                alert_type=AlertType.QUEUE_UNSTABLE,
                severity=AlertSeverity.WARNING,
                message=f"Queue unstable for {self.consecutive_unstable_frames} frames",
                threshold_name="queue_stability",
                current_value=float(self.consecutive_unstable_frames),
                threshold_value=float(self.config.stability_check_frames),
                frame_id=frame_id,
                timestamp=timestamp,
            ))
        
        return alerts
    
    def reset_statistics(self) -> None:
        """Reset tracking statistics."""
        self.consecutive_unstable_frames = 0
        self.last_alert_by_type.clear()
    
    def get_last_alert(self, alert_type: AlertType) -> Optional[QueueAlert]:
        """Get the last alert of a specific type."""
        return self.last_alert_by_type.get(alert_type)
