"""RTSP camera connection, testing, snapshot capture, and reconnect handling."""

from __future__ import annotations

import base64
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


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _build_rtsp_url(
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Embed username and password into an RTSP URL if provided."""
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
        masked = parsed._replace(netloc=parsed.netloc.replace(f":{parsed.password}", ":***"))
        return urlunparse(masked)
    return url


def _apply_rtsp_env(transport: str) -> None:
    """Set OpenCV / FFMPEG environment variables for RTSP transport."""
    normalized_transport = (transport or "tcp").strip().lower()

    # Hide low-level FFmpeg decoder noise (e.g. transient UDP macroblock errors)
    # unless the user explicitly overrides it.
    os.environ.setdefault(
        "OPENCV_FFMPEG_LOGLEVEL",
        os.getenv("QUEUE_RTSP_FFMPEG_LOGLEVEL", "8"),
    )

    # Always refresh capture options so transport changes (tcp/udp) take effect.
    # UDP can produce decoder errors when buffers are too aggressive, therefore use
    # a slightly safer profile for UDP and keep the ultra-low-latency profile for TCP.
    if normalized_transport == "udp":
        capture_options = (
            "rtsp_transport;udp"
            "|fflags;discardcorrupt"
            "|flags;low_delay"
            "|reorder_queue_size;32"
            "|max_delay;200000"
            "|overrun_nonfatal;1"
        )
    else:
        capture_options = (
            f"rtsp_transport;{normalized_transport}"
            "|fflags;nobuffer"
            "|flags;low_delay"
            "|reorder_queue_size;0"
            "|max_delay;0"
        )

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = capture_options


def _configure_low_latency_capture(cap: cv2.VideoCapture) -> None:
    """Best-effort low-latency capture tuning for RTSP streams."""
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)


def _open_capture_with_probe(
    *,
    auth_url: str,
    safe_url: str,
    transport: str,
    timeout: float,
) -> tuple[cv2.VideoCapture, np.ndarray, str]:
    """Open RTSP capture and ensure at least one frame is readable.

    If UDP is requested but no frame is received, automatically retry with TCP.
    """
    requested_transport = (transport or "tcp").strip().lower()
    transport_attempts = [requested_transport]
    if requested_transport == "udp":
        transport_attempts.append("tcp")

    last_error = f"Could not open stream: {safe_url}"

    for attempt_transport in transport_attempts:
        _apply_rtsp_env(attempt_transport)
        cap = cv2.VideoCapture(auth_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)
        _configure_low_latency_capture(cap)

        if not cap.isOpened():
            cap.release()
            last_error = f"Could not open stream: {safe_url}"
            continue

        ok, frame = cap.read()
        if ok and frame is not None:
            return cap, frame, attempt_transport

        cap.release()
        last_error = f"Stream opened but could not read a frame: {safe_url}"
        if attempt_transport == "udp" and "tcp" in transport_attempts:
            logger.warning(
                "RTSP UDP session opened but no frames arrived for %s. Retrying with TCP.",
                safe_url,
            )

    raise RuntimeError(last_error)


# ----------------------------------------------------------------------
# Main class
# ----------------------------------------------------------------------

class RTSPCamera:
    """Robust RTSP camera stream."""

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

    def open(self) -> "RTSPCamera":
        """Open the RTSP stream. Raises RuntimeError on failure."""
        safe = _safe_url(self._auth_url)
        logger.info("Connecting to RTSP stream: %s (transport=%s)", safe, self._transport)
        self._cap, _, active_transport = _open_capture_with_probe(
            auth_url=self._auth_url,
            safe_url=safe,
            transport=self._transport,
            timeout=RTSP_CONNECTION_TIMEOUT_SEC,
        )
        if active_transport != self._transport:
            logger.warning(
                "Falling back to RTSP transport=%s for %s (requested=%s).",
                active_transport,
                safe,
                self._transport,
            )
        logger.info(
            "Connected - %dx%d @ %.1f FPS (transport=%s)",
            self.width,
            self.height,
            self.fps,
            active_transport,
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

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read one frame. Returns (success, frame)."""
        if self._cap is None:
            return False, None
        return self._cap.read()

    def frames(self) -> Generator[np.ndarray, None, None]:
        """Yield frames, automatically reconnecting on stream loss."""
        consecutive_failures = 0

        while True:
            ok, frame = self.read()

            if ok and frame is not None:
                consecutive_failures = 0
                yield frame
                continue

            consecutive_failures += 1
            if consecutive_failures > self._reconnect_attempts:
                logger.error(
                    "RTSP stream lost after %d reconnect attempts. Stopping.",
                    self._reconnect_attempts,
                )
                break

            logger.warning(
                "RTSP frame read failed (attempt %d/%d). Reconnecting in %.1fs ...",
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

    @staticmethod
    def test_connection(
        url: str,
        username: str | None = None,
        password: str | None = None,
        transport: str = RTSP_TRANSPORT,
        timeout: float = RTSP_CONNECTION_TIMEOUT_SEC,
    ) -> tuple[bool, dict]:
        """Probe an RTSP URL without starting the full pipeline."""
        auth_url = _build_rtsp_url(url, username, password)
        safe = _safe_url(auth_url)
        logger.info("Testing RTSP connection: %s", safe)

        try:
            cap, _, active_transport = _open_capture_with_probe(
                auth_url=auth_url,
                safe_url=safe,
                transport=transport,
                timeout=timeout,
            )
        except RuntimeError as exc:
            msg = str(exc)
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
        fps = raw_fps if raw_fps > 0 else 30.0
        cap.release()

        info = {
            "url": url,
            "width": width,
            "height": height,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "transport": active_transport,
        }
        logger.info("RTSP test OK - %dx%d @ %.1f FPS", width, height, fps)
        return True, info

    @staticmethod
    def capture_snapshot(
        url: str,
        username: str | None = None,
        password: str | None = None,
        transport: str = RTSP_TRANSPORT,
        timeout: float = RTSP_CONNECTION_TIMEOUT_SEC,
        jpeg_quality: int = 90,
    ) -> tuple[bool, dict]:
        """Capture a single JPEG snapshot from an RTSP source."""
        auth_url = _build_rtsp_url(url, username, password)
        safe = _safe_url(auth_url)
        logger.info("Capturing RTSP snapshot: %s", safe)

        try:
            cap, frame, active_transport = _open_capture_with_probe(
                auth_url=auth_url,
                safe_url=safe,
                transport=transport,
                timeout=timeout,
            )
        except RuntimeError as exc:
            msg = str(exc)
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        encoded_ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )
        if not encoded_ok:
            msg = f"Could not encode snapshot frame: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        image_base64 = base64.b64encode(buffer.tobytes()).decode("ascii")
        info = {
            "url": url,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "transport": active_transport,
            "image_base64": image_base64,
            "mime_type": "image/jpeg",
        }
        logger.info("RTSP snapshot captured - %dx%d", width, height)
        return True, info
