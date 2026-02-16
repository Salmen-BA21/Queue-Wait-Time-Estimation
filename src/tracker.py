"""
Object tracker wrapper.

Wraps **supervision**'s ByteTrack (default) to assign persistent IDs to
detections across frames.
"""

from __future__ import annotations

import logging

import supervision as sv

from src.config import MATCH_THRESH, TRACK_BUFFER, TRACK_THRESH

logger = logging.getLogger("queue_system.tracker")


class ObjectTracker:
    """Maintain a ByteTrack tracker and update detections with track IDs.

    Parameters
    ----------
    track_thresh : float
        Detection confidence threshold for initialising new tracks.
    track_buffer : int
        Number of frames to keep a lost track alive.
    match_thresh : float
        IoU threshold for matching detections to existing tracks.
    frame_rate : int
        Expected FPS – used internally by ByteTrack.
    """

    def __init__(
        self,
        track_thresh: float = TRACK_THRESH,
        track_buffer: int = TRACK_BUFFER,
        match_thresh: float = MATCH_THRESH,
        frame_rate: int = 30,
    ) -> None:
        logger.info(
            "Initialising ByteTrack tracker (thresh=%.2f, buffer=%d, match=%.2f)",
            track_thresh,
            track_buffer,
            match_thresh,
        )
        self._tracker = sv.ByteTrack(
            track_activation_threshold=track_thresh,
            lost_track_buffer=track_buffer,
            minimum_matching_threshold=match_thresh,
            frame_rate=frame_rate,
        )

    def update(self, detections: sv.Detections) -> sv.Detections:
        """Run tracker step and return detections enriched with ``tracker_id``.

        Parameters
        ----------
        detections : sv.Detections
            Raw detections from the detector (current frame).

        Returns
        -------
        sv.Detections
            Same detections with ``tracker_id`` populated.
        """
        tracked = self._tracker.update_with_detections(detections)
        return tracked

    def reset(self) -> None:
        """Reset internal tracker state."""
        self._tracker.reset()
        logger.info("Tracker state reset.")
