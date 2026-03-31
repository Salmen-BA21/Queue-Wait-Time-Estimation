"""
Entry point – Queue Wait-Time Estimation System.

Run with::

    python -m src.main --source 0
    python -m src.main --source videos/test.mp4 --model-size s
    python -m src.main --source rtsp://192.168.1.10/stream --log-interval-sec 10
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread

import cv2
import numpy as np
import supervision as sv

from src.config import (
    AppConfig,
    DEFAULT_INFERENCE_DEVICE,
    DEFAULT_DETECTOR_IMAGE_SIZE,
    DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY,
    DEFAULT_LOG_INTERVAL_SEC,
    DEFAULT_OUTPUT_FPS,
    DEFAULT_PROCESS_EVERY_N_FRAMES,
    DEFAULT_REALTIME_FILE_PLAYBACK,
    DASHBOARD_EVENT_EMIT_INTERVAL_SEC,
    WINDOW_NAME,
    N8N_WEBHOOK_URL,
    N8N_WEBHOOK_SECRET,
    WEBHOOK_ENABLED,
    WEBHOOK_SEND_INTERVAL_SEC,
    ALERT_DEDUPE_WINDOW_SEC,
)
from src.detector import PersonDetector
from src.queue_analyzer import QueueAnalyzer, QueueMetrics
from src.threshold_detector import QueueThresholdDetector, ThresholdConfig
from src.tracker import ObjectTracker
from src.utils.drawing import create_annotators, draw_detections, draw_metrics_overlay
from src.utils.logging_setup import setup_logging
from src.video_capture import VideoStream, open_video_source
from src.webhook_client import WebhookClient
from src.zone_manager import ZoneManager

logger: logging.Logger  # assigned in main()


class DashboardEventWriter:
    """Writes line-delimited dashboard events for the API runtime to tail."""

    def __init__(self, path: str | None) -> None:
        self._stream = None
        if path:
            event_path = Path(path)
            event_path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = event_path.open("a", encoding="utf-8", buffering=1)

    def emit(self, event: str, payload: dict[str, object]) -> None:
        if self._stream is None:
            return

        record = {"event": event, "payload": payload}
        self._stream.write(json.dumps(record) + "\n")
        self._stream.flush()

    def close(self) -> None:
        if self._stream is not None and not self._stream.closed:
            self._stream.close()


@dataclass(frozen=True)
class WebhookJob:
    """Typed unit of webhook work consumed by the background dispatcher."""

    metrics: QueueMetrics
    frame_id: int
    source: str
    feed_id: str | None
    alert_triggered: bool = False
    alert_reason: str = ""
    alert_severity: str = "info"
    confidence_scores: list[float] | None = None


class AsyncWebhookDispatcher:
    """Send webhook payloads on a background thread to keep the loop responsive."""

    def __init__(self, webhook_client: WebhookClient, max_queue_size: int = 32) -> None:
        self._client = webhook_client
        self._queue: Queue[WebhookJob] = Queue(maxsize=max_queue_size)
        self._stop_event = Event()
        self._worker = Thread(
            target=self._run,
            name="queue-webhook-dispatcher",
            daemon=True,
        )
        self._worker.start()

    def enqueue(
        self,
        *,
        metrics: QueueMetrics,
        frame_id: int,
        source: str,
        feed_id: str | None,
        alert_triggered: bool = False,
        alert_reason: str = "",
        alert_severity: str = "info",
        confidence_scores: list[float] | None = None,
    ) -> None:
        payload = WebhookJob(
            metrics=metrics,
            frame_id=frame_id,
            source=source,
            feed_id=feed_id,
            alert_triggered=alert_triggered,
            alert_reason=alert_reason,
            alert_severity=alert_severity,
            confidence_scores=confidence_scores,
        )

        if self._stop_event.is_set():
            return

        try:
            self._queue.put_nowait(payload)
            return
        except Full:
            pass

        # Keep the latest payloads under sustained backpressure.
        try:
            self._queue.get_nowait()
            self._queue.task_done()
        except Empty:
            pass

        try:
            self._queue.put_nowait(payload)
        except Full:
            logger.debug("Dropping webhook payload: dispatcher queue is still full.")

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                payload = self._queue.get(timeout=0.2)
            except Empty:
                continue

            try:
                self._client.send_metrics(
                    metrics=payload.metrics,
                    frame_id=payload.frame_id,
                    source=payload.source,
                    feed_id=payload.feed_id,
                    alert_triggered=payload.alert_triggered,
                    alert_reason=payload.alert_reason,
                    alert_severity=payload.alert_severity,
                    confidence_scores=payload.confidence_scores,
                )
            except Exception as exc:
                logger.debug("Async webhook send failed: %s", exc)
            finally:
                self._queue.task_done()

    def stop(self, timeout_sec: float = 2.0) -> None:
        self._stop_event.set()
        self._worker.join(timeout=timeout_sec)


# ═══════════════════════════════════════════════════════════════
# Argument parser
# ═══════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="queue-estimator",
        description=(
            "Real-time queue wait-time estimation from video feed "
            "using YOLO26 + ByteTrack."
        ),
    )
    parser.add_argument(
        "--source",
        type=str,
        default="0",
        help=(
            "Video source: 0 for webcam, path to an mp4 file, "
            "or an RTSP URL. (default: 0)"
        ),
    )
    parser.add_argument(
        "--model-size",
        type=str,
        choices=["n", "s", "m", "l", "x"],
        default="n",
        help="YOLO model size – n(ano), s(mall), m(edium), l(arge), x(large). (default: n)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=DEFAULT_INFERENCE_DEVICE,
        help=(
            "Inference device: auto, cpu, cuda, cuda:0, ... "
            f"(default: {DEFAULT_INFERENCE_DEVICE})"
        ),
    )
    parser.add_argument(
        "--detector-imgsz",
        type=int,
        default=DEFAULT_DETECTOR_IMAGE_SIZE,
        help=(
            "Inference image size passed to YOLO. "
            f"Smaller values are faster. (default: {DEFAULT_DETECTOR_IMAGE_SIZE})"
        ),
    )
    parser.add_argument(
        "--process-every-n-frames",
        type=int,
        default=DEFAULT_PROCESS_EVERY_N_FRAMES,
        help=(
            "Run detection/tracking every N frames and reuse the latest result in-between. "
            f"(default: {DEFAULT_PROCESS_EVERY_N_FRAMES})"
        ),
    )
    parser.add_argument(
        "--zone-points",
        type=str,
        default=None,
        help=(
            "JSON list of [x,y] polygon points defining the queue zone. "
            'Example: \'[[100,200],[400,200],[400,600],[100,600]]\'. '
            "If omitted, the full frame is used."
        ),
    )
    parser.add_argument(
        "--output-fps",
        type=int,
        default=DEFAULT_OUTPUT_FPS,
        help=f"Display refresh rate in FPS. (default: {DEFAULT_OUTPUT_FPS})",
    )
    parser.set_defaults(realtime_file_playback=DEFAULT_REALTIME_FILE_PLAYBACK)
    file_playback_group = parser.add_mutually_exclusive_group()
    file_playback_group.add_argument(
        "--realtime-file-playback",
        dest="realtime_file_playback",
        action="store_true",
        help=(
            "Pace non-RTSP file sources to their native FPS for natural playback speed. "
            f"(default: {DEFAULT_REALTIME_FILE_PLAYBACK})"
        ),
    )
    file_playback_group.add_argument(
        "--no-realtime-file-playback",
        dest="realtime_file_playback",
        action="store_false",
        help="Process non-RTSP file sources as fast as possible.",
    )
    parser.add_argument(
        "--log-interval-sec",
        type=float,
        default=DEFAULT_LOG_INTERVAL_SEC,
        help=(
            f"How often (seconds) to log metrics to the console. "
            f"(default: {DEFAULT_LOG_INTERVAL_SEC})"
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level: DEBUG, INFO, WARNING, ERROR. (default: INFO)",
    )
    parser.add_argument(
        "--resize-scale",
        type=float,
        default=1.0,
        help="Scale factor to resize the frame (e.g., 0.5 for 50%%). (default: 1.0)",
    )
    parser.add_argument(
        "--queue-length-warning",
        type=int,
        default=8,
        help="Queue length warning threshold in people. (default: 8)",
    )
    # ── RTSP-specific ─────────────────────────────────────────────
    parser.add_argument(
        "--rtsp-user",
        type=str,
        default=None,
        help="Username for RTSP camera authentication (optional).",
    )
    parser.add_argument(
        "--rtsp-pass",
        type=str,
        default=None,
        help="Password for RTSP camera authentication (optional).",
    )
    parser.add_argument(
        "--rtsp-reconnect",
        type=int,
        default=None,
        help="Number of reconnect attempts on RTSP stream loss (default from config).",
    )
    parser.add_argument(
        "--rtsp-transport",
        type=str,
        choices=["tcp", "udp"],
        default=None,
        help="RTSP transport protocol: tcp (reliable) or udp (low-latency). (default: tcp)",
    )
    # ── Metadata tracking ──────────────────────────────────────────
    parser.add_argument(
        "--establishment-id",
        type=int,
        default=None,
        help="Database ID of the establishment (company/store) (optional).",
    )
    parser.add_argument(
        "--register-id",
        "--caisse-id",
        dest="caisse_id",
        type=int,
        default=None,
        help="Database ID of the checkout/register being monitored (optional).",
    )
    parser.add_argument(
        "--feed-id",
        type=str,
        default=None,
        help="Unique identifier for this source/feed (e.g., cashier_3).",
    )
    parser.add_argument(
        "--disable-webhook",
        action="store_true",
        help="Disable sending queue metrics to the configured webhook endpoint.",
    )
    parser.add_argument(
        "--events-file",
        type=str,
        default=None,
        help="Optional JSONL file used to stream structured dashboard events back to the API runtime.",
    )
    parser.add_argument(
        "--dashboard-render-frames",
        action="store_true",
        help=(
            "Include worker-rendered JPEG frames in dashboard metrics events "
            "so browser tracking boxes stay synchronized with detections."
        ),
    )
    parser.add_argument(
        "--dashboard-frame-jpeg-quality",
        type=int,
        default=DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY,
        help=(
            "JPEG quality (1-100) for dashboard-rendered frames when "
            "--dashboard-render-frames is enabled. (default: "
            f"{DEFAULT_DASHBOARD_FRAME_JPEG_QUALITY})"
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without opening any GUI windows (cv2.imshow). (default: False)",
    )
    return parser


def parse_zone_points(raw: str | None) -> list[list[float]] | None:
    """Parse the ``--zone-points`` JSON string into a list of [x, y] pairs."""
    if raw is None:
        return None
    try:
        points = json.loads(raw)
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("Need at least 3 points for a polygon.")

        parsed_points: list[list[float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise ValueError("Each zone point must be a [x, y] pair.")

            x = float(point[0])
            y = float(point[1])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("Zone point coordinates must be finite numbers.")

            parsed_points.append([x, y])

        return parsed_points
    except (json.JSONDecodeError, TypeError, IndexError, ValueError) as exc:
        logger.warning("Invalid --zone-points (%s). Using full-frame zone.", exc)
        return None


# ═══════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════

def run(cfg: AppConfig) -> None:
    """Run the main detection → tracking → analysis loop.

    Parameters
    ----------
    cfg : AppConfig
        Assembled runtime configuration.
    """
    # ── Initialise components ─────────────────────────────────
    detector = PersonDetector(
        model_path=cfg.model_path,
        confidence=cfg.confidence,
        device=cfg.inference_device,
        image_size=cfg.detector_imgsz if cfg.detector_imgsz > 0 else None,
    )

    stream = open_video_source(
        cfg.source,
        rtsp_username=cfg.rtsp_username,
        rtsp_password=cfg.rtsp_password,
        rtsp_reconnect=cfg.rtsp_reconnect if cfg.rtsp_reconnect is not None else None,
        rtsp_transport=cfg.rtsp_transport if cfg.rtsp_transport else None,
    )
    with stream:
        tracker = ObjectTracker(frame_rate=int(stream.fps))
        zone_mgr = ZoneManager(
            polygon_points=cfg.zone_polygon,
            frame_resolution=stream.resolution,
        )
        analyzer = QueueAnalyzer()
        threshold_detector = QueueThresholdDetector(
            ThresholdConfig(
                queue_length_warning=cfg.queue_length_warning,
            )
        )
        annotators = create_annotators()
        webhook_client = WebhookClient(N8N_WEBHOOK_URL, webhook_secret=N8N_WEBHOOK_SECRET) if cfg.webhook_enabled else None
        webhook_dispatcher = AsyncWebhookDispatcher(webhook_client) if webhook_client else None
        event_writer = DashboardEventWriter(cfg.events_file)

        # Multi-stream identity for webhook payloads; fallback to source string
        feed_identifier = (
            str(cfg.feed_id)
            if cfg.feed_id
            else (f"caisse_{cfg.caisse_id}" if cfg.caisse_id is not None else str(cfg.source))
        )

        source_is_file = _is_file_source(cfg.source)
        source_fps = max(float(stream.fps), 1.0)
        realtime_file_playback = bool(cfg.realtime_file_playback and source_is_file)

        display_target_fps = cfg.output_fps
        if realtime_file_playback and display_target_fps <= 0 and not cfg.headless:
            display_target_fps = max(1, int(round(source_fps)))

        frame_delay = int(1000 / display_target_fps) if display_target_fps > 0 else 1
        playback_target_fps = _compute_playback_target_fps(
            source_fps=source_fps,
            output_fps=display_target_fps,
            realtime_file_playback=realtime_file_playback,
        )
        process_stride = max(1, int(cfg.process_every_n_frames))
        last_log_time = time.monotonic()
        last_webhook_time = time.monotonic()
        last_dashboard_event_time = time.monotonic()
        last_warning_message: str | None = None
        last_warning_webhook_time = 0.0
        frame_count = 0
        dashboard_jpeg_quality = int(np.clip(cfg.dashboard_frame_jpeg_quality, 30, 95))

        last_detections: sv.Detections | None = None
        last_in_zone: np.ndarray | None = None
        last_labels: list[str] = []
        last_metrics: QueueMetrics | None = None

        # Real-time pacing for headless file playback (GUI path is paced by waitKey).
        playback_started_at = time.perf_counter()
        playback_frame_index = 0

        # Rolling performance counters (reset on each metrics log window)
        window_started_at = time.monotonic()
        last_logged_frame_count = 0
        processed_frames_window = 0
        detect_ms_window = 0.0
        track_ms_window = 0.0
        analyze_ms_window = 0.0

        logger.info(
            "Entering main loop. Press 'q' to quit. (process_every_n_frames=%d, detector_imgsz=%s, realtime_file_playback=%s)",
            process_stride,
            cfg.detector_imgsz if cfg.detector_imgsz > 0 else "auto",
            realtime_file_playback,
        )

        try:
            for frame in stream.frames():
                frame_count += 1
                playback_frame_index += 1
                event_timestamp = time.time()

                should_process_frame = (
                    last_detections is None
                    or last_metrics is None
                    or process_stride <= 1
                    or (frame_count % process_stride == 0)
                )

                alerts = []
                if should_process_frame:
                    stage_started = time.perf_counter()
                    detections = detector.detect(frame)
                    detect_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    stage_started = time.perf_counter()
                    detections = tracker.update(detections)
                    track_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    stage_started = time.perf_counter()
                    in_zone = zone_mgr.trigger(detections)
                    metrics = analyzer.update(
                        in_zone_mask=in_zone,
                        tracker_ids=detections.tracker_id,
                    )
                    analyze_ms_window += (time.perf_counter() - stage_started) * 1000.0

                    alerts = threshold_detector.check_metrics(
                        people_in_zone=metrics.people_in_zone,
                        estimated_wait_sec=metrics.estimated_wait_sec,
                        arrival_rate=metrics.arrival_rate,
                        service_rate=metrics.service_rate,
                        uncertainty_level=metrics.uncertainty_level,
                        queue_stable=metrics.queue_stable,
                        frame_id=frame_count,
                        timestamp=event_timestamp,
                    )
                    labels = _build_labels(detections, in_zone)

                    last_detections = detections
                    last_in_zone = in_zone
                    last_metrics = metrics
                    last_labels = labels
                    processed_frames_window += 1
                else:
                    detections = last_detections
                    in_zone = last_in_zone if last_in_zone is not None else np.array([], dtype=bool)
                    metrics = last_metrics
                    labels = last_labels

                if detections is None or metrics is None:
                    continue

                rendered_display_frame: np.ndarray | None = None

                # 5. Draw + 6. Show
                if not cfg.headless:
                    rendered_display_frame = draw_detections(frame.copy(), detections, annotators, labels)
                    rendered_display_frame = zone_mgr.annotate(rendered_display_frame)
                    rendered_display_frame = draw_metrics_overlay(rendered_display_frame, _metrics_dict(metrics))

                    # Resize frame if scale != 1.0
                    if cfg.resize_scale != 1.0:
                        rendered_display_frame = cv2.resize(
                            rendered_display_frame,
                            (0, 0),
                            fx=cfg.resize_scale,
                            fy=cfg.resize_scale,
                        )

                    cv2.imshow(WINDOW_NAME, rendered_display_frame)

                    wait_delay = frame_delay
                    if realtime_file_playback:
                        target_elapsed = playback_frame_index / playback_target_fps
                        elapsed = time.perf_counter() - playback_started_at
                        sleep_sec = target_elapsed - elapsed
                        wait_delay = max(1, int(sleep_sec * 1000)) if sleep_sec > 0 else 1

                    key = cv2.waitKey(wait_delay) & 0xFF
                    if key == ord("q"):
                        logger.info("Quit requested by user.")
                        break

                # 7. Periodic logging and event emission
                now = time.monotonic()
                if (now - last_dashboard_event_time) >= DASHBOARD_EVENT_EMIT_INTERVAL_SEC:
                    render_frame_jpeg_base64: str | None = None
                    if cfg.dashboard_render_frames:
                        if rendered_display_frame is not None:
                            render_frame = rendered_display_frame
                        else:
                            render_frame = frame.copy()
                            render_frame = draw_detections(render_frame, detections, annotators, labels)
                            render_frame = zone_mgr.annotate(render_frame)
                            render_frame = draw_metrics_overlay(render_frame, _metrics_dict(metrics))

                            if cfg.resize_scale != 1.0:
                                render_frame = cv2.resize(
                                    render_frame,
                                    (0, 0),
                                    fx=cfg.resize_scale,
                                    fy=cfg.resize_scale,
                                )

                        encoded_ok, encoded_frame = cv2.imencode(
                            ".jpg",
                            render_frame,
                            [int(cv2.IMWRITE_JPEG_QUALITY), dashboard_jpeg_quality],
                        )
                        if encoded_ok:
                            render_frame_jpeg_base64 = base64.b64encode(encoded_frame.tobytes()).decode("ascii")

                    event_writer.emit(
                        "metrics_update",
                        {
                            "metrics": _dashboard_metrics_payload(
                                metrics,
                                event_timestamp,
                                detections,
                                render_frame_jpeg_base64=render_frame_jpeg_base64,
                            )
                        },
                    )
                    last_dashboard_event_time = now

                for alert in alerts:
                    if alert.message == last_warning_message:
                        continue

                    event_writer.emit(
                        "alert_fired",
                        {"alert": _dashboard_alert_payload(alert)},
                    )
                    last_warning_message = alert.message

                    # Immediately forward the warning to webhook (if configured), respecting dedupe window.
                    if webhook_dispatcher:
                        now_ts = time.time()
                        if (now_ts - last_warning_webhook_time) >= ALERT_DEDUPE_WINDOW_SEC:
                            webhook_dispatcher.enqueue(
                                metrics=metrics,
                                frame_id=frame_count,
                                source=str(cfg.source),
                                feed_id=feed_identifier,
                                alert_triggered=True,
                                alert_reason=alert.message,
                                alert_severity=alert.severity.value,
                            )
                            last_warning_webhook_time = now_ts

                if (now - last_log_time) >= cfg.log_interval_sec:
                    elapsed = max(now - window_started_at, 1e-6)
                    loop_fps = (frame_count - last_logged_frame_count) / elapsed
                    processed_fps = processed_frames_window / elapsed
                    avg_detect_ms = detect_ms_window / processed_frames_window if processed_frames_window else 0.0
                    avg_track_ms = track_ms_window / processed_frames_window if processed_frames_window else 0.0
                    avg_analyze_ms = analyze_ms_window / processed_frames_window if processed_frames_window else 0.0

                    _log_metrics(
                        metrics,
                        frame_count,
                        loop_fps=loop_fps,
                        processed_fps=processed_fps,
                        process_stride=process_stride,
                        avg_detect_ms=avg_detect_ms,
                        avg_track_ms=avg_track_ms,
                        avg_analyze_ms=avg_analyze_ms,
                    )
                    last_log_time = now
                    window_started_at = now
                    last_logged_frame_count = frame_count
                    processed_frames_window = 0
                    detect_ms_window = 0.0
                    track_ms_window = 0.0
                    analyze_ms_window = 0.0

                # 8. Periodic webhook sending to n8n
                if webhook_dispatcher and (now - last_webhook_time) >= WEBHOOK_SEND_INTERVAL_SEC:
                    webhook_dispatcher.enqueue(
                        metrics=metrics,
                        frame_id=frame_count,
                        source=str(cfg.source),
                        feed_id=feed_identifier,
                    )
                    last_webhook_time = now

                if realtime_file_playback and cfg.headless:
                    target_elapsed = playback_frame_index / playback_target_fps
                    elapsed = time.perf_counter() - playback_started_at
                    sleep_sec = target_elapsed - elapsed
                    if sleep_sec > 0:
                        time.sleep(min(sleep_sec, 0.25))
        finally:
            if webhook_dispatcher:
                webhook_dispatcher.stop()
            if webhook_client:
                webhook_client.close()
            event_writer.close()

    cv2.destroyAllWindows()
    logger.info("Pipeline finished. Processed %d frames.", frame_count)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _build_labels(detections, in_zone: np.ndarray) -> list[str]:
    """Generate per-detection labels like ``#5 ✓`` or ``#5``."""
    labels: list[str] = []
    ids = detections.tracker_id
    if ids is None:
        return labels
    for tid, inside in zip(ids, in_zone):
        tag = f"#{int(tid)}"
        if inside:
            tag += " \u2713"  # ✓
        labels.append(tag)
    return labels


def _is_file_source(source: str | int) -> bool:
    """Return True when source is a local video file path."""
    if isinstance(source, int):
        return False

    source_text = str(source).strip()
    if not source_text or source_text.isdigit():
        return False

    return not source_text.lower().startswith("rtsp://")


def _compute_playback_target_fps(
    *,
    source_fps: float,
    output_fps: int,
    realtime_file_playback: bool,
) -> float:
    """Choose target FPS for playback pacing.

    Real-time file playback should follow the file's native FPS (float) for
    natural speed, while non-realtime mode can optionally use output_fps.
    """
    normalized_source_fps = max(float(source_fps), 1.0)
    if realtime_file_playback:
        return normalized_source_fps
    if output_fps > 0:
        return float(output_fps)
    return normalized_source_fps


def _metrics_dict(m: QueueMetrics) -> dict[str, str]:
    """Convert ``QueueMetrics`` to a display-friendly dict with uncertainty.
    
    Formats metrics with credible intervals for compact display.
    """
    return {
        "People": str(m.people_in_zone),
        "λ (arr)": f"{m.arrival_rate:.3f}±{(m.arrival_rate_upper - m.arrival_rate_lower)/2:.3f}",
        "μ (svc)": f"{m.service_rate:.3f}±{(m.service_rate_upper - m.service_rate_lower)/2:.3f}",
        "Wait": f"{m.estimated_wait_sec:.1f}s",
        "Unc.": m.uncertainty_level,
        "Stable": "✓" if m.queue_stable else "✗",
    }


def _log_metrics(
    m: QueueMetrics,
    frame_count: int,
    *,
    loop_fps: float,
    processed_fps: float,
    process_stride: int,
    avg_detect_ms: float,
    avg_track_ms: float,
    avg_analyze_ms: float,
) -> None:
    """Write queue metrics and rolling loop performance diagnostics."""
    logger.info(
        "[frame %d] zone=%d | λ=%.4f [%.4f,%.4f] | μ=%.4f [%.4f,%.4f] | W=%.1fs [%.1f,%.1f] | unc=%s | stable=%s | loop_fps=%.2f | proc_fps=%.2f | stride=%d | detect=%.1fms | track=%.1fms | analyze=%.1fms",
        frame_count,
        m.people_in_zone,
        m.arrival_rate,
        m.arrival_rate_lower,
        m.arrival_rate_upper,
        m.service_rate,
        m.service_rate_lower,
        m.service_rate_upper,
        m.estimated_wait_sec,
        m.wait_time_lower,
        m.wait_time_upper,
        m.uncertainty_level,
        m.queue_stable,
        loop_fps,
        processed_fps,
        process_stride,
        avg_detect_ms,
        avg_track_ms,
        avg_analyze_ms,
    )


def _dashboard_metrics_payload(
    m: QueueMetrics,
    timestamp: float,
    detections: sv.Detections | None = None,
    render_frame_jpeg_base64: str | None = None,
) -> dict[str, object]:
    """Convert runtime metrics into the frontend websocket contract."""
    wait_time_seconds: float | None = m.estimated_wait_sec if m.queue_stable else None
    wait_time_ci: list[float] | None = [m.wait_time_lower, m.wait_time_upper] if m.queue_stable else None

    # Convert supervision detections (xyxy) to nested list for JSON
    # Each detection is [x1, y1, x2, y2, confidence, class_id, tracker_id]
    det_list: list[list[float]] | None = None
    if detections is not None:
        det_list = []
        for i, box in enumerate(detections.xyxy):
            row = [
                float(box[0]), float(box[1]), float(box[2]), float(box[3]),
                float(detections.confidence[i]) if detections.confidence is not None else 1.0,
                float(detections.class_id[i]) if detections.class_id is not None else 0.0,
                float(detections.tracker_id[i]) if detections.tracker_id is not None else -1.0,
            ]
            det_list.append(row)

    return {
        "timestamp": timestamp,
        "people_in_zone": m.people_in_zone,
        "arrival_rate": m.arrival_rate,
        "service_rate": m.service_rate,
        "wait_time_seconds": wait_time_seconds,
        "wait_time_ci": wait_time_ci,
        "uncertainty_level": m.uncertainty_level,
        "queue_stable": m.queue_stable,
        "detections": det_list,
        "render_frame_jpeg_base64": render_frame_jpeg_base64,
    }


def _dashboard_alert_payload(alert) -> dict[str, object]:  # noqa: ANN001
    """Convert threshold alerts into the frontend websocket contract."""
    return {
        "alert_type": alert.alert_type.value,
        "severity": alert.severity.value,
        "message": alert.message,
        "threshold_name": alert.threshold_name,
        "current_value": alert.current_value,
        "threshold_value": alert.threshold_value,
        "frame_id": alert.frame_id,
        "timestamp": datetime.fromtimestamp(alert.timestamp, tz=timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    """Parse CLI args and launch the pipeline."""
    global logger

    parser = build_parser()
    args = parser.parse_args()

    logger = setup_logging(level=args.log_level)

    zone_pts = parse_zone_points(args.zone_points)

    cfg = AppConfig(
        source=args.source,
        model_size=args.model_size,
        inference_device=(args.device or "auto").strip() or "auto",
        zone_points=zone_pts,
        output_fps=args.output_fps,
        log_interval_sec=args.log_interval_sec,
        resize_scale=args.resize_scale,
        detector_imgsz=max(0, int(args.detector_imgsz)),
        process_every_n_frames=max(1, int(args.process_every_n_frames)),
        realtime_file_playback=bool(args.realtime_file_playback),
        queue_length_warning=args.queue_length_warning,
        rtsp_username=args.rtsp_user,
        rtsp_password=args.rtsp_pass,
        rtsp_reconnect=args.rtsp_reconnect,
        rtsp_transport=args.rtsp_transport or "tcp",
        establishment_id=args.establishment_id,
        caisse_id=args.caisse_id,
        webhook_enabled=WEBHOOK_ENABLED and not args.disable_webhook,
        events_file=args.events_file,
        dashboard_render_frames=args.dashboard_render_frames,
        dashboard_frame_jpeg_quality=args.dashboard_frame_jpeg_quality,
        headless=args.headless,
    )

    logger.info("Configuration: %s", cfg)
    run(cfg)


if __name__ == "__main__":
    main()
