"""
Video capture abstraction.

Wraps ``cv2.VideoCapture`` for webcam / file sources and delegates RTSP
URLs to :class:`~src.rtsp_camera.RTSPCamera` which adds authentication,
connection testing, and automatic reconnection.

Use :func:`open_video_source` as a factory instead of constructing
``VideoStream`` directly when the source type is determined at runtime.
"""

from __future__ import annotations

import logging
from typing import Generator, Union

import cv2
import numpy as np

logger = logging.getLogger("queue_system.video_capture")


def _is_rtsp(source: str | int) -> bool:
    """Return *True* when *source* looks like an RTSP URL."""
    return isinstance(source, str) and source.lower().startswith("rtsp://")


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


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────

def open_video_source(
    source: str | int,
    *,
    rtsp_username: str | None = None,
    rtsp_password: str | None = None,
    rtsp_reconnect: int | None = None,
    rtsp_transport: str | None = None,
) -> "Union[VideoStream, RTSPCamera]":  # noqa: F821  – RTSPCamera imported below
    """Return the appropriate stream object for *source*.

    * ``int`` or digit string  → webcam via :class:`VideoStream`
    * file path (mp4, avi, …)  → file via :class:`VideoStream`
    * ``rtsp://…`` URL         → :class:`~src.rtsp_camera.RTSPCamera`

    All RTSP keyword arguments are forwarded to ``RTSPCamera`` and
    silently ignored for non-RTSP sources.
    """
    if _is_rtsp(source):
        # Lazy import avoids a circular-import issue at module load time.
        from src.rtsp_camera import RTSPCamera  # noqa: PLC0415

        kwargs: dict = {}
        if rtsp_username is not None:
            kwargs["username"] = rtsp_username
        if rtsp_password is not None:
            kwargs["password"] = rtsp_password
        if rtsp_reconnect is not None:
            kwargs["reconnect_attempts"] = rtsp_reconnect
        if rtsp_transport is not None:
            kwargs["transport"] = rtsp_transport
        return RTSPCamera(source, **kwargs)

    return VideoStream(source)
