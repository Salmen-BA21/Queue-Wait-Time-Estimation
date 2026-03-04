"""
RTSP camera connection with authentication, connection testing, and
automatic reconnection on stream loss.

Typical usage
-------------
    # Test first, then stream
    ok, info = RTSPCamera.test_connection("rtsp://192.168.1.10/stream")
    if ok:
        with RTSPCamera("rtsp://192.168.1.10/stream") as cam:
            for frame in cam.frames():
                ...

    # With credentials embedded at runtime (URL kept clean in logs)
    with RTSPCamera(
        "rtsp://192.168.1.10/stream",
        username="admin",
        password="secret",
    ) as cam:
        ...
"""

from __future__ import annotations

import logging
import os
import time
from typing import Generator
from urllib.parse import urlparse, urlunparse

import cv2
import numpy as np

from src.config import (
    RTSP_CONNECTION_TIMEOUT_SEC,
    RTSP_RECONNECT_ATTEMPTS,
    RTSP_RECONNECT_DELAY_SEC,
    RTSP_TRANSPORT,
)

logger = logging.getLogger("queue_system.rtsp_camera")


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _build_rtsp_url(
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Embed *username* and *password* into an RTSP URL if provided.

    If the URL already contains credentials they are **replaced** by the
    supplied values so the caller doesn't have to strip them manually.
    """
    if not (username or password):
        return url

    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if username or password:
        user_part = username or ""
        pass_part = f":{password}" if password else ""
        netloc = f"{user_part}{pass_part}@{netloc}"

    return urlunparse(parsed._replace(netloc=netloc))


def _safe_url(url: str) -> str:
    """Return the URL with the password redacted for log messages."""
    parsed = urlparse(url)
    if parsed.password:
        masked = parsed._replace(
            netloc=parsed.netloc.replace(f":{parsed.password}", ":***")
        )
        return urlunparse(masked)
    return url


def _apply_rtsp_env(transport: str) -> None:
    """Set OpenCV / FFMPEG environment variables for RTSP transport."""
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", f"rtsp_transport;{transport}")


# ──────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────

class RTSPCamera:
    """Robust RTSP camera stream.

    Parameters
    ----------
    url : str
        RTSP URL, e.g. ``rtsp://192.168.1.10:554/live/main``.
    username : str | None
        Optional username (embedded into the URL at connect time).
    password : str | None
        Optional password (embedded into the URL at connect time).
    reconnect_attempts : int
        How many times to try reconnecting after a dropped stream.
        ``0`` means no retries (fail immediately).
    reconnect_delay : float
        Seconds to wait between reconnect attempts.
    transport : str
        RTSP transport protocol – ``"tcp"`` (default) or ``"udp"``.
    """

    def __init__(
        self,
        url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        reconnect_attempts: int = RTSP_RECONNECT_ATTEMPTS,
        reconnect_delay: float = RTSP_RECONNECT_DELAY_SEC,
        transport: str = RTSP_TRANSPORT,
    ) -> None:
        self._raw_url = url
        self._username = username
        self._password = password
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._transport = transport
        self._cap: cv2.VideoCapture | None = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def _auth_url(self) -> str:
        """RTSP URL with credentials embedded (never logged directly)."""
        return _build_rtsp_url(self._raw_url, self._username, self._password)

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
        raw = float(self._cap.get(cv2.CAP_PROP_FPS))
        return raw if raw > 0 else 30.0

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── Connection ───────────────────────────────────────────────────

    def open(self) -> "RTSPCamera":
        """Open the RTSP stream. Raises ``RuntimeError`` on failure."""
        _apply_rtsp_env(self._transport)
        safe = _safe_url(self._auth_url)
        logger.info("Connecting to RTSP stream: %s (transport=%s)", safe, self._transport)
        self._cap = cv2.VideoCapture(self._auth_url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_CONNECTION_TIMEOUT_SEC * 1000)
        self._cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_CONNECTION_TIMEOUT_SEC * 1000)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open RTSP stream: {safe}")
        logger.info(
            "Connected – %dx%d @ %.1f FPS", self.width, self.height, self.fps
        )
        return self

    def close(self) -> None:
        """Release the capture device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("RTSP stream released: %s", _safe_url(self._raw_url))

    def __enter__(self) -> "RTSPCamera":
        return self.open()

    def __exit__(self, *_exc) -> None:  # noqa: ANN001
        self.close()

    # ── Frame reading ────────────────────────────────────────────────

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read one frame. Returns ``(success, frame)``."""
        if self._cap is None:
            return False, None
        return self._cap.read()

    def frames(self) -> Generator[np.ndarray, None, None]:
        """Yield frames, automatically reconnecting on stream loss.

        Stops after exhausting all reconnect attempts.
        """
        consecutive_failures = 0

        while True:
            ok, frame = self.read()

            if ok and frame is not None:
                consecutive_failures = 0
                yield frame
                continue

            # ── Stream lost ──────────────────────────────────────────
            consecutive_failures += 1
            if consecutive_failures > self._reconnect_attempts:
                logger.error(
                    "RTSP stream lost after %d reconnect attempts. Stopping.",
                    self._reconnect_attempts,
                )
                break

            logger.warning(
                "RTSP frame read failed (attempt %d/%d). Reconnecting in %.1fs …",
                consecutive_failures,
                self._reconnect_attempts,
                self._reconnect_delay,
            )
            time.sleep(self._reconnect_delay)
            self.close()
            try:
                self.open()
            except RuntimeError as exc:
                logger.warning("Reconnect failed: %s", exc)

    # ── Static helpers ───────────────────────────────────────────────

    @staticmethod
    def test_connection(
        url: str,
        username: str | None = None,
        password: str | None = None,
        transport: str = RTSP_TRANSPORT,
        timeout: float = RTSP_CONNECTION_TIMEOUT_SEC,
    ) -> tuple[bool, dict]:
        """Probe an RTSP URL without starting the full pipeline.

        Returns
        -------
        tuple[bool, dict]
            ``(success, info)`` where *info* contains stream metadata on
            success or an ``"error"`` key on failure.

        Example
        -------
        ::

            ok, info = RTSPCamera.test_connection("rtsp://192.168.1.10/stream")
            if ok:
                print(info["width"], info["height"], info["fps"])
            else:
                print(info["error"])
        """
        _apply_rtsp_env(transport)
        auth_url = _build_rtsp_url(url, username, password)
        safe = _safe_url(auth_url)
        logger.info("Testing RTSP connection: %s", safe)

        cap = cv2.VideoCapture(auth_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)

        if not cap.isOpened():
            cap.release()
            msg = f"Could not open stream: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        # Try to grab one frame to confirm live data
        ok, _ = cap.read()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
        fps = raw_fps if raw_fps > 0 else 30.0
        cap.release()

        if not ok:
            msg = f"Stream opened but could not read a frame: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        info = {
            "url": url,
            "width": width,
            "height": height,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "transport": transport,
        }
        logger.info(
            "RTSP test OK – %dx%d @ %.1f FPS", width, height, fps
        )
        return True, info
