"""
Zone manager – define and query polygon zones via **supervision**.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import supervision as sv

logger = logging.getLogger("queue_system.zone_manager")


class ZoneManager:
    """Manage one (or later several) polygon zones.

    Parameters
    ----------
    polygon_points : list[list[float]]
        Polygon vertices in either pixel coords or normalised coords
        ``[[x1,y1], [x2,y2], …]``. If the values look normalised (all ≤ 1), they are scaled to
        *frame_resolution* automatically.
    frame_resolution : tuple[int, int]
        ``(width, height)`` of the video frames.
    """

    def __init__(
        self,
        polygon_points: list[list[float]],
        frame_resolution: tuple[int, int],
    ) -> None:
        self._frame_w, self._frame_h = frame_resolution

        polygon_np = np.array(polygon_points, dtype=np.float64)

        # Auto-scale if the points look normalised (0-1 range)
        if polygon_np.max() <= 1.0:
            logger.info("Zone polygon appears normalised – scaling to frame size.")
            polygon_np[:, 0] *= self._frame_w
            polygon_np[:, 1] *= self._frame_h

        self._polygon = polygon_np.astype(np.int64)

        self._zone = sv.PolygonZone(
            polygon=self._polygon,
            triggering_anchors=[sv.Position.BOTTOM_CENTER],
        )

        self._zone_annotator = sv.PolygonZoneAnnotator(
            zone=self._zone,
            color=sv.Color(0, 255, 255),
            thickness=2,
            text_thickness=1,
            text_scale=0.5,
        )

        logger.info("Zone created with %d vertices.", len(self._polygon))

    # ── Public API ────────────────────────────────────────────

    @property
    def zone(self) -> sv.PolygonZone:
        """Return the underlying ``PolygonZone``."""
        return self._zone

    @property
    def zone_annotator(self) -> sv.PolygonZoneAnnotator:
        return self._zone_annotator

    @property
    def polygon(self) -> np.ndarray:
        return self._polygon

    def trigger(self, detections: sv.Detections) -> np.ndarray:
        """Check which detections fall inside the zone.

        Parameters
        ----------
        detections : sv.Detections
            Tracked detections for the current frame.

        Returns
        -------
        np.ndarray
            Boolean mask – ``True`` for detections inside the zone.
        """
        return self._zone.trigger(detections)

    @property
    def current_count(self) -> int:
        """Number of detections inside the zone after the last ``trigger()``."""
        return self._zone.current_count

    def annotate(self, frame: np.ndarray) -> np.ndarray:
        """Draw the zone polygon on *frame*.

        Parameters
        ----------
        frame : np.ndarray
            BGR image.

        Returns
        -------
        np.ndarray
            Annotated frame.
        """
        return self._zone_annotator.annotate(scene=frame)
