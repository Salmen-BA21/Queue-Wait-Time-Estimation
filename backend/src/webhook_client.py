"""
Webhook client for sending queue metrics to n8n.

Handles POST requests to n8n webhook endpoints with automatic
retry logic and error handling. Also logs metrics to CSV for backup persistence.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from src.csv_logger import CSVMetricsLogger
from src.queue_analyzer import QueueMetrics
from src.webhook import QueuePayload, validate_payload

logger = logging.getLogger("queue_system.webhook_client")


class WebhookClient:
    """Client for sending metrics to n8n webhook."""

    def __init__(
        self,
        webhook_url: str,
        webhook_secret: str | None = None,
        timeout: float = 5.0,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        csv_output_dir: str = "data",
    ):
        """Initialize webhook client.
        
        Parameters
        ----------
        webhook_url : str
            Full URL to n8n webhook endpoint.
            Example: "http://localhost:5678/webhook/queue-metrics"
        webhook_secret : str | None
            Optional shared secret sent as `X-Webhook-Secret`.
        timeout : float
            Request timeout in seconds.
        retry_count : int
            Number of retry attempts on failure.
        retry_delay : float
            Delay between retries in seconds.
        csv_output_dir : str
            Directory for CSV backup files (default: 'data').
        """
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret.strip() if isinstance(webhook_secret, str) and webhook_secret.strip() else None
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.session = requests.Session()
        
        # Initialize CSV logger for backup persistence
        self.csv_logger = CSVMetricsLogger(output_dir=csv_output_dir)
        
        # Statistics
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_error: Optional[str] = None
        
        logger.info("WebhookClient initialized: %s", webhook_url)
        logger.info("CSV logging enabled: %s", self.csv_logger.get_csv_path())

    def send_metrics(
        self,
        metrics: QueueMetrics,
        frame_id: int,
        source: str,
        feed_id: str | None = None,
        alert_triggered: bool = False,
        alert_reason: str = "",
        alert_severity: str = "info",
        confidence_scores: list[float] | None = None,
    ) -> bool:
        """Send queue metrics to n8n.
        
        Parameters
        ----------
        metrics : QueueMetrics
            The queue metrics to send.
        frame_id : int
            Current frame number for tracking.
        source : str
            Video source identifier.
        alert_triggered : bool
            Whether an alert condition is active.
        alert_reason : str
            Reason for alert (if triggered).
        alert_severity : str
            Alert severity: "info", "warning", "critical".
        confidence_scores : list[float] | None
            YOLO confidence scores from this frame.
        
        Returns
        -------
        bool
            True if sent successfully, False otherwise.
        """
        # Create payload
        payload = QueuePayload.from_queue_metrics(
            metrics=metrics,
            frame_id=frame_id,
            source=source,
            feed_id=feed_id,
            alert_triggered=alert_triggered,
            alert_reason=alert_reason,
            alert_severity=alert_severity,
            confidence_scores=confidence_scores,
        )
        
        # Validate
        if not validate_payload(payload.to_dict()):
            self.messages_failed += 1
            self.last_error = "Invalid payload structure"
            return False
        
        # Log to CSV (for backup persistence)
        payload_dict = payload.to_dict()
        self.csv_logger.log_metrics(payload_dict)
        
        # Send with retry
        for attempt in range(1, self.retry_count + 1):
            try:
                response = self.session.post(
                    self.webhook_url,
                    json=payload_dict,
                    timeout=self.timeout,
                    headers={
                        "Content-Type": "application/json",
                        **({"X-Webhook-Secret": self.webhook_secret} if self.webhook_secret else {}),
                    },
                )
                
                # Check response
                if response.status_code in (200, 201, 204):
                    self.messages_sent += 1
                    logger.debug(
                        "Webhook sent (frame %d): %s",
                        frame_id,
                        response.status_code,
                    )
                    return True
                else:
                    logger.warning(
                        "Webhook error (attempt %d/%d): status=%d, response=%s",
                        attempt,
                        self.retry_count,
                        response.status_code,
                        response.text[:200],
                    )
            
            except requests.exceptions.Timeout:
                logger.warning(
                    "Webhook timeout (attempt %d/%d): %s",
                    attempt,
                    self.retry_count,
                    self.webhook_url,
                )
            except requests.exceptions.ConnectionError:
                logger.warning(
                    "Webhook connection error (attempt %d/%d): %s",
                    attempt,
                    self.retry_count,
                    self.webhook_url,
                )
            except Exception as e:
                logger.error(
                    "Webhook unexpected error (attempt %d/%d): %s",
                    attempt,
                    self.retry_count,
                    e,
                )
            
            # Retry delay (except on last attempt)
            if attempt < self.retry_count:
                time.sleep(self.retry_delay)
        
        self.messages_failed += 1
        self.last_error = f"Failed after {self.retry_count} attempts"
        return False

    def get_stats(self) -> dict:
        """Get send statistics."""
        return {
            "messages_sent": self.messages_sent,
            "messages_failed": self.messages_failed,
            "last_error": self.last_error,
            "success_rate": (
                self.messages_sent / (self.messages_sent + self.messages_failed)
                if (self.messages_sent + self.messages_failed) > 0
                else 0.0
            ),
        }

    def close(self) -> None:
        """Close the session."""
        self.session.close()
        logger.info("WebhookClient closed")


if __name__ == "__main__":
    # Test webhook client with mock data
    import json
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Try local n8n (default: http://localhost:5678/webhook/...)
    client = WebhookClient(
        webhook_url="http://localhost:5678/webhook/queue-metrics",
        timeout=2.0,
    )
    
    # Create mock metrics
    from src.queue_analyzer import QueueMetrics
    
    mock_metrics = QueueMetrics(
        timestamp=time.time(),
        people_in_zone=3,
        arrival_rate=0.15,
        service_rate=0.08,
        estimated_wait_sec=4.5,
        arrival_rate_lower=0.10,
        arrival_rate_upper=0.20,
        service_rate_lower=0.05,
        service_rate_upper=0.11,
        wait_time_lower=3.5,
        wait_time_upper=5.5,
        uncertainty_level="Low",
        queue_stable=True,
    )
    
    print("Testing webhook client...")
    print(f"Webhook URL: {client.webhook_url}\n")
    
    success = client.send_metrics(
        metrics=mock_metrics,
        frame_id=100,
        source="test_video.mp4",
        alert_triggered=False,
    )
    
    print(f"\nSend result: {success}")
    print(f"Stats: {json.dumps(client.get_stats(), indent=2)}")
    
    client.close()
