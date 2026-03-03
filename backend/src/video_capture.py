"""
Video capture abstraction.

Wraps ``cv2.VideoCapture`` to support webcam index, file path, or RTSP URL.
"""

from __future__ import annotations

import logging
from typing import Generator

import cv2
import numpy as np

logger = logging.getLogger("queue_system.video_capture")


class VideoStream:
    """Thin wrapper around :class:`cv2.VideoCapture`.

    Parameters
    ----------
    source : str | int
        ``0`` for the default webcam, a file path, or an RTSP URL.
    """

    def __init__(self, source: str | int = 0) -> None:
        self._raw_source = source
        self._source: int | str = int(source) if str(source).isdigit() else source
        self._cap: cv2.VideoCapture | None = None

    # ── Context-manager interface ─────────────────────────────
    def open(self) -> "VideoStream":
        """Open the video source. Returns *self* for chaining."""
        logger.info("Opening video source: %s", self._source)
        self._cap = cv2.VideoCapture(self._source)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {self._source}")
        logger.info(
            "Opened – resolution %dx%d @ %.1f FPS",
            self.width,
            self.height,
            self.fps,
        )
        return self

    def close(self) -> None:
        """Release the underlying capture device."""
        if self._cap is not None:
            self._cap.release()
            logger.info("Video source released.")

    def __enter__(self) -> "VideoStream":
        return self.open()

    def __exit__(self, *_exc) -> None:  # noqa: ANN001
        self.close()

    # ── Properties ────────────────────────────────────────────
    @property
    def width(self) -> int:
        assert self._cap is not None
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        assert self._cap is not None
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def fps(self) -> float:
        assert self._cap is not None
        return float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)

    # ── Frame reading ─────────────────────────────────────────
    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read a single frame.

        Returns
        -------
        tuple[bool, np.ndarray | None]
            ``(success, frame)`` – frame is BGR ``np.ndarray`` or *None*.
        """
        if self._cap is None:
            return False, None
        return self._cap.read()

    def frames(self) -> Generator[np.ndarray, None, None]:
        """Yield frames until the source is exhausted or the capture closes."""
        while True:
            ok, frame = self.read()
            if not ok or frame is None:
                break
            yield frame
