"""
Drawing utilities – overlay bounding boxes, zone polygons, and text on frames.
"""

from __future__ import annotations

import cv2
import numpy as np
import supervision as sv
from typing import Any


# ─── Colour palette ──────────────────────────────────────────
COLOUR_GREEN = sv.Color(0, 200, 0)
COLOUR_RED = sv.Color(200, 0, 0)
COLOUR_YELLOW = sv.Color(0, 200, 200)
COLOUR_WHITE = sv.Color(255, 255, 255)


def create_annotators() -> dict[str, sv.annotators.BaseAnnotator]:  # type: ignore
    """Return a reusable set of supervision annotators.

    Returns
    -------
    dict
        Keys: ``box``, ``label``, ``trace``.
    """
    box_annotator = sv.BoxAnnotator(
        thickness=2,
        color=COLOUR_GREEN,
    )
    label_annotator = sv.LabelAnnotator(
        text_scale=0.4,
        text_thickness=1,
        text_padding=4,
        color=COLOUR_GREEN,
    )
    trace_annotator = sv.TraceAnnotator(
        thickness=1,
        trace_length=60,
        color=COLOUR_YELLOW,
    )
    return {
        "box": box_annotator,
        "label": label_annotator,
        "trace": trace_annotator,
    }


def draw_detections(
    frame: np.ndarray,
    detections: sv.Detections,
    annotators: dict[str, sv.annotators.BaseAnnotator],  # type: ignore
    labels: list[str] | None = None,
) -> np.ndarray:
    """Draw bounding boxes, labels and traces on *frame*.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    detections : sv.Detections
        Current detections (after tracking).
    annotators : dict
        Output of :func:`create_annotators`.
    labels : list[str] | None
        Optional label per detection.

    Returns
    -------
    np.ndarray
        Annotated frame (same object, modified in-place).
    """
    frame = annotators["box"].annotate(scene=frame, detections=detections)
    if labels is not None:
        det_count = len(detections.xyxy)
        if len(labels) < det_count:
            labels = labels + (["No ID"] * (det_count - len(labels)))
        elif len(labels) > det_count:
            labels = labels[:det_count]

        # Draw labels manually to avoid implicit placeholder text (e.g. "???")
        # from the upstream annotator implementation when lengths drift.
        for idx, box in enumerate(detections.xyxy):
            text = labels[idx]
            x1, y1 = int(box[0]), int(box[1])
            y_text = max(16, y1 - 8)
            cv2.putText(
                frame,
                text,
                (x1, y_text),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
    frame = annotators["trace"].annotate(scene=frame, detections=detections)
    return frame


def draw_zone(
    frame: np.ndarray,
    zone: sv.PolygonZone,
    zone_annotator: sv.PolygonZoneAnnotator,
) -> np.ndarray:
    """Draw a polygon zone overlay on *frame*.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    zone : sv.PolygonZone
        The polygon zone to visualise.
    zone_annotator : sv.PolygonZoneAnnotator
        Matching annotator.

    Returns
    -------
    np.ndarray
        Annotated frame.
    """
    return zone_annotator.annotate(scene=frame)


def draw_metrics_overlay(
    frame: np.ndarray,
    metrics: dict[str, Any],
    origin: tuple[int, int] | str = "top-right",
    font_scale: float = 0.45,
    colour: tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
    line_gap: int = 22,
    bg_colour: tuple[int, int, int] = (0, 0, 0),
    bg_alpha: float = 0.7,
) -> np.ndarray:
    """Print key-value metrics with semi-transparent dark background.

    Parameters
    ----------
    frame : np.ndarray
        BGR image.
    metrics : dict
        Metric name → value.
    origin : tuple[int, int] | str
        Position: "top-left", "top-right", or (x, y) coordinates.
        Default: "top-right".
    font_scale : float
        OpenCV font scale (default: 0.45 for smaller size).
    colour : tuple[int, int, int]
        BGR text colour (default: white).
    thickness : int
        Text thickness.
    line_gap : int
        Pixel gap between lines.
    bg_colour : tuple[int, int, int]
        BGR background colour (default: black).
    bg_alpha : float
        Background opacity (0-1).

    Returns
    -------
    np.ndarray
        Frame with overlay text and background.
    """
    if not metrics:
        return frame
    
    frame_h, frame_w = frame.shape[:2]
    padding = 6
    
    # Calculate background rectangle dimensions
    text_width = max(
        cv2.getTextSize(f"{k}: {v}", cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0][0]
        for k, v in metrics.items()
    )
    text_height = len(metrics) * line_gap
    
    # Determine position
    if isinstance(origin, str):
        if origin == "top-right":
            x = frame_w - text_width - padding * 2 - 10
            y = 25
        elif origin == "top-left":
            x = 10
            y = 25
        else:
            x, y = 10, 25
    else:
        x, y = origin
    
    # Draw semi-transparent background
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (x - padding, y - padding - 12),
        (x + text_width + padding, y + text_height + padding),
        bg_colour,
        -1,
    )
    cv2.addWeighted(overlay, bg_alpha, frame, 1 - bg_alpha, 0, frame)
    
    # Draw text with outline for better visibility
    y_pos = y
    for key, value in metrics.items():
        text = f"{key}: {value}"
        
        # Draw outline (black)
        for adj_x in [-1, 0, 1]:
            for adj_y in [-1, 0, 1]:
                if adj_x != 0 or adj_y != 0:
                    cv2.putText(
                        frame,
                        text,
                        (x + adj_x, y_pos + adj_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        font_scale,
                        (0, 0, 0),
                        thickness,
                        cv2.LINE_AA,
                    )
        
        # Draw text (white)
        cv2.putText(
            frame,
            text,
            (x, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            colour,
            thickness,
            cv2.LINE_AA,
        )
        y_pos += line_gap
    
    return frame
