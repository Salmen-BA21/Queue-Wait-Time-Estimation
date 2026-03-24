import time

from src.queue_analyzer import QueueMetrics
from src.webhook import QueuePayload, validate_payload


def test_queue_payload_includes_feed_id_and_validates():
    metrics = QueueMetrics(
        timestamp=time.time(),
        people_in_zone=5,
        arrival_rate=0.12,
        service_rate=0.15,
        estimated_wait_sec=12.3,
        arrival_rate_lower=0.1,
        arrival_rate_upper=0.14,
        service_rate_lower=0.13,
        service_rate_upper=0.17,
        wait_time_lower=10.0,
        wait_time_upper=14.0,
        uncertainty_level="Low",
        queue_stable=True,
    )

    payload = QueuePayload.from_queue_metrics(
        metrics=metrics,
        frame_id=1,
        source="rtsp://example/stream",
        feed_id="cashier_1",
        alert_triggered=True,
        alert_reason="TEST_ALERT",
        alert_severity="critical",
        confidence_scores=[0.92, 0.95],
    )

    assert payload.feed_id == "cashier_1"
    assert payload.source == "rtsp://example/stream"
    assert payload.alert_triggered is True
    assert payload.alert_reason == "TEST_ALERT"
    assert validate_payload(payload.to_dict())
