"""
Entry point – Queue Wait-Time Estimation System.

Run with::

    python -m src.main --source 0
    python -m src.main --source videos/test.mp4 --model-size s
    python -m src.main --source rtsp://192.168.1.10/stream --log-interval-sec 10
"""

from __future__ import annotations

import argparse
import json
import logging
import time

import cv2
import numpy as np

from src.config import (
    AppConfig,
    DEFAULT_LOG_INTERVAL_SEC,
    DEFAULT_OUTPUT_FPS,
    WINDOW_NAME,
)
from src.detector import PersonDetector
from src.queue_analyzer import QueueAnalyzer, QueueMetrics
from src.tracker import ObjectTracker
from src.utils.drawing import create_annotators, draw_detections, draw_metrics_overlay
from src.utils.logging_setup import setup_logging
from src.video_capture import VideoStream
from src.zone_manager import ZoneManager

logger: logging.Logger  # assigned in main()


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
    return parser


def parse_zone_points(raw: str | None) -> list[list[int]] | None:
    """Parse the ``--zone-points`` JSON string into a list of [x, y] pairs."""
    if raw is None:
        return None
    try:
        points = json.loads(raw)
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError("Need at least 3 points for a polygon.")
        return [[int(p[0]), int(p[1])] for p in points]
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
    detector = PersonDetector(model_path=cfg.model_path, confidence=cfg.confidence)

    with VideoStream(cfg.source) as stream:
        tracker = ObjectTracker(frame_rate=int(stream.fps))
        zone_mgr = ZoneManager(
            polygon_points=cfg.zone_polygon,
            frame_resolution=stream.resolution,
        )
        analyzer = QueueAnalyzer()
        annotators = create_annotators()

        frame_delay = int(1000 / cfg.output_fps) if cfg.output_fps > 0 else 1
        last_log_time = time.monotonic()
        frame_count = 0

        logger.info("Entering main loop. Press 'q' to quit.")

        for frame in stream.frames():
            frame_count += 1

            # 1. Detect
            detections = detector.detect(frame)

            # 2. Track
            detections = tracker.update(detections)

            # 3. Zone trigger
            in_zone = zone_mgr.trigger(detections)

            # 4. Queue metrics
            metrics: QueueMetrics = analyzer.update(
                in_zone_mask=in_zone,
                tracker_ids=detections.tracker_id,
            )

            # 5. Draw
            labels = _build_labels(detections, in_zone)
            frame = draw_detections(frame, detections, annotators, labels)
            frame = zone_mgr.annotate(frame)
            frame = draw_metrics_overlay(frame, _metrics_dict(metrics))

            # 6. Show
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(frame_delay) & 0xFF
            if key == ord("q"):
                logger.info("Quit requested by user.")
                break

            # 7. Periodic logging
            now = time.monotonic()
            if (now - last_log_time) >= cfg.log_interval_sec:
                _log_metrics(metrics, frame_count)
                last_log_time = now

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


def _metrics_dict(m: QueueMetrics) -> dict[str, str]:
    """Convert ``QueueMetrics`` to a display-friendly dict."""
    return {
        "In zone": str(m.people_in_zone),
        "Arrival (lam)": f"{m.arrival_rate:.3f} /s",
        "Service (mu)": f"{m.service_rate:.3f} /s",
        "Est. wait": f"{m.estimated_wait_sec:.1f} s",
        "Stable": "yes" if m.queue_stable else "NO",
    }


def _log_metrics(m: QueueMetrics, frame_count: int) -> None:
    """Write metrics to the logger."""
    logger.info(
        "[frame %d] zone=%d | λ=%.4f | μ=%.4f | W=%.1fs | stable=%s",
        frame_count,
        m.people_in_zone,
        m.arrival_rate,
        m.service_rate,
        m.estimated_wait_sec,
        m.queue_stable,
    )


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
        zone_points=zone_pts,
        output_fps=args.output_fps,
        log_interval_sec=args.log_interval_sec,
    )

    logger.info("Configuration: %s", cfg)
    run(cfg)


if __name__ == "__main__":
    main()
