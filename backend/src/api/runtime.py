"""In-memory runtime services for the FastAPI backend-for-frontend layer."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, TextIO, TypedDict, cast
from urllib.parse import quote, urlparse, urlunparse
from uuid import uuid4

import requests
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from src.api.models import (
    AlertFiredEvent,
    AlertFiredEventPayload,
    AlertModel,
    BatchFeedDraft,
    BatchFeedLaunchItemResult,
    BatchFeedLaunchResponse,
    BatchFeedLaunchSummary,
    BatchRuntimeSettings,
    BatchLaunchMode,
    FeedStatusEvent,
    FeedStatusEventPayload,
    FeedSnapshotResult,
    LogLevel,
    ModelSize,
    MetricsUpdateEvent,
    MetricsUpdateEventPayload,
    FeedTransportCapabilities,
    QueueMetricsModel,
    SystemWarningEvent,
    SystemWarningEventPayload,
    VideoFeed,
    ZonePolygon,
    coerce_zone_polygon,
)
from src.database import (
    create_video_session,
    delete_feed_config,
    end_open_video_sessions,
    end_video_session,
    get_caisse_by_id,
    get_feed_configs,
    upsert_feed_config,
    update_caisse_zone_points,
)
from src.config import (
    DASHBOARD_EVENT_POLL_INTERVAL_SEC,
    DEFAULT_CONFIDENCE,
    DEFAULT_DETECTOR_IMAGE_SIZE,
    MEDIAMTX_CONTROL_API_BASE_URL,
    MEDIAMTX_WEBRTC_TIMEOUT_SEC,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = (BACKEND_DIR / "data" / "uploads").resolve()
RUNTIME_LOG_DIR = (BACKEND_DIR / "data" / "runtime").resolve()
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_RESIZE_SCALE = 1.0
_raw_worker_process_stride = os.getenv("QUEUE_WORKER_PROCESS_EVERY_N_FRAMES", "2").strip()
try:
    _parsed_worker_process_stride = int(_raw_worker_process_stride)
except ValueError:
    _parsed_worker_process_stride = 2
DEFAULT_WORKER_PROCESS_EVERY_N_FRAMES = max(
    1,
    _parsed_worker_process_stride,
)
_raw_worker_dashboard_jpeg_quality = os.getenv("QUEUE_WORKER_DASHBOARD_JPEG_QUALITY", "55").strip()
try:
    _parsed_worker_dashboard_jpeg_quality = int(_raw_worker_dashboard_jpeg_quality)
except ValueError:
    _parsed_worker_dashboard_jpeg_quality = 55
DEFAULT_WORKER_DASHBOARD_FRAME_JPEG_QUALITY = max(
    30,
    min(95, _parsed_worker_dashboard_jpeg_quality),
)
DEFAULT_WORKER_DETECTOR_IMAGE_SIZE = max(320, min(640, DEFAULT_DETECTOR_IMAGE_SIZE))
_raw_worker_confidence = os.getenv("QUEUE_WORKER_DETECTOR_CONFIDENCE", str(DEFAULT_CONFIDENCE)).strip()
try:
    _parsed_worker_confidence = float(_raw_worker_confidence)
except ValueError:
    _parsed_worker_confidence = DEFAULT_CONFIDENCE
DEFAULT_WORKER_CONFIDENCE = max(0.05, min(0.95, _parsed_worker_confidence))
DEFAULT_WORKER_INFERENCE_DEVICE = os.getenv("QUEUE_INFERENCE_DEVICE", "auto").strip() or "auto"
DEFAULT_ANNOTATED_WEBRTC_PUBLISH_ENABLED = (
    os.getenv(
        "QUEUE_PUBLISHED_WEBRTC_PUBLISH_ENABLED",
        os.getenv("QUEUE_ANNOTATED_WEBRTC_PUBLISH_ENABLED", "1"),
    ).strip().lower()
    in {"1", "true", "yes", "on"}
)
DEFAULT_ANNOTATED_WEBRTC_RTSP_HOST = (
    os.getenv(
        "QUEUE_PUBLISHED_WEBRTC_RTSP_HOST",
        os.getenv("QUEUE_ANNOTATED_WEBRTC_RTSP_HOST", "127.0.0.1"),
    ).strip()
    or "127.0.0.1"
)
_raw_annotated_rtsp_port = os.getenv(
    "QUEUE_PUBLISHED_WEBRTC_RTSP_PORT",
    os.getenv("QUEUE_ANNOTATED_WEBRTC_RTSP_PORT", "8554"),
).strip()
try:
    _parsed_annotated_rtsp_port = int(_raw_annotated_rtsp_port)
except ValueError:
    _parsed_annotated_rtsp_port = 8554
DEFAULT_ANNOTATED_WEBRTC_RTSP_PORT = max(
    1,
    min(65535, _parsed_annotated_rtsp_port),
)
_raw_annotated_fps = os.getenv(
    "QUEUE_PUBLISHED_WEBRTC_FPS",
    os.getenv("QUEUE_ANNOTATED_WEBRTC_FPS", "15"),
).strip()
try:
    _parsed_annotated_fps = int(_raw_annotated_fps)
except ValueError:
    _parsed_annotated_fps = 15
DEFAULT_ANNOTATED_WEBRTC_FPS = max(
    1,
    min(60, _parsed_annotated_fps),
)
DEFAULT_ANNOTATED_WEBRTC_FFMPEG_BINARY = os.getenv(
    "QUEUE_PUBLISHED_WEBRTC_FFMPEG_BINARY",
    os.getenv("QUEUE_ANNOTATED_WEBRTC_FFMPEG_BINARY", "ffmpeg"),
).strip() or "ffmpeg"
DEFAULT_WORKER_PIPELINE_ENGINE = os.getenv("QUEUE_PIPELINE_ENGINE", "opencv").strip().lower() or "opencv"
if DEFAULT_WORKER_PIPELINE_ENGINE not in {"opencv", "gstreamer_hybrid"}:
    DEFAULT_WORKER_PIPELINE_ENGINE = "opencv"
_raw_gstreamer_rtsp_latency_ms = os.getenv("QUEUE_GSTREAMER_RTSP_LATENCY_MS", "150").strip()
try:
    _parsed_gstreamer_rtsp_latency_ms = int(_raw_gstreamer_rtsp_latency_ms)
except ValueError:
    _parsed_gstreamer_rtsp_latency_ms = 150
DEFAULT_WORKER_GSTREAMER_RTSP_LATENCY_MS = max(0, _parsed_gstreamer_rtsp_latency_ms)
DEFAULT_FRAME_CHANNEL_BIND_HOST = os.getenv("QUEUE_DASHBOARD_FRAME_CHANNEL_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
MAX_FRAME_CHANNEL_FRAME_BYTES = max(
    64 * 1024,
    int(os.getenv("QUEUE_DASHBOARD_FRAME_CHANNEL_MAX_FRAME_BYTES", str(8 * 1024 * 1024))),
)
FRAME_CHANNEL_ACTIVITY_TIMEOUT_SEC = max(
    0.5,
    float(os.getenv("QUEUE_DASHBOARD_FRAME_CHANNEL_ACTIVITY_TIMEOUT_SEC", "2.0")),
)
TRANSPORT_SKEW_THRESHOLD_MS = max(
    1.0,
    float(os.getenv("QUEUE_TRANSPORT_SKEW_THRESHOLD_MS", "120.0")),
)
TRANSPORT_SKEW_WARNING_SEC = max(
    0.0,
    float(os.getenv("QUEUE_TRANSPORT_SKEW_WARNING_SEC", "3.0")),
)
TRANSPORT_SKEW_ERROR_SEC = max(
    TRANSPORT_SKEW_WARNING_SEC,
    float(os.getenv("QUEUE_TRANSPORT_SKEW_ERROR_SEC", "8.0")),
)

LOGGER = logging.getLogger(__name__)


class FeedStateError(RuntimeError):
    """Raised when a feed operation is invalid for the current lifecycle state."""


class FeedStartError(RuntimeError):
    """Raised when the runtime cannot launch a worker for a feed."""


def _build_authenticated_rtsp_source(
    source: str,
    username: str | None,
    password: str | None,
) -> str:
    """Embed optional credentials in an RTSP URL for OpenCV capture."""
    if not (username or password):
        return source

    parsed = urlparse(source)
    hostname = parsed.hostname
    if hostname is None:
        return source

    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    user_part = username or ""
    pass_part = f":{password}" if password else ""
    netloc = f"{user_part}{pass_part}@{netloc}"
    return urlunparse(parsed._replace(netloc=netloc))


def build_preview_path(source: str) -> str | None:
    """Return an API preview path when the feed source is a managed upload."""
    if "://" in source:
        return None

    try:
        candidate = Path(source).expanduser().resolve(strict=False)
    except OSError:
        return None

    try:
        candidate.relative_to(UPLOAD_DIR)
    except ValueError:
        return None

    return f"/api/uploads/files/{candidate.name}"


def sanitize_source(source: str) -> str:
    """Strip embedded URL credentials before returning a source to the dashboard."""
    if "://" not in source:
        return source

    parsed = urlparse(source)
    if parsed.username is None and parsed.password is None:
        return source

    hostname = parsed.hostname
    if hostname is None:
        return source

    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return urlunparse(parsed._replace(netloc=netloc))


def build_published_webrtc_path_name(feed_id: str) -> str:
    """Build a stable MediaMTX path name for unified worker-published WebRTC streams."""
    normalized = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in feed_id.strip().lower()
    ).strip("-")
    if not normalized:
        return "ann-feed"
    return f"ann-{normalized}"


def _normalize_publisher_reason(reason: str | None) -> str | None:
    """Normalize legacy/worker reason values to the unified transport vocabulary."""
    if reason is None:
        return None
    normalized = reason.strip().lower()
    if normalized in {"annotated_publisher_not_ready", "publisher_not_ready"}:
        return "publisher_not_ready"
    if normalized in {"annotated_publisher_unavailable", "publisher_unavailable"}:
        return "publisher_unavailable"
    return normalized


def configure_mediamtx_published_path(path_name: str) -> None:
    """Configure MediaMTX to accept worker-published frames on a canonical path."""
    if not path_name.strip():
        raise ValueError("MediaMTX path name must not be blank.")

    encoded_path = quote(path_name.strip(), safe="")
    base_url = MEDIAMTX_CONTROL_API_BASE_URL.rstrip("/")
    patch_endpoint = f"{base_url}/v3/config/paths/patch/{encoded_path}"
    add_endpoint = f"{base_url}/v3/config/paths/add/{encoded_path}"
    
    # Configure path to accept publishing from worker
    # Use minimal configuration - just set source to "publisher" to allow external publishing
    path_payload = {
        "source": "publisher",  # Allow external publishers (worker FFmpeg)
    }

    try:
        # Try to patch existing path first
        patch_response = requests.patch(
            patch_endpoint,
            json=path_payload,
            timeout=MEDIAMTX_WEBRTC_TIMEOUT_SEC,
        )
        
        if patch_response.status_code == 200:
            LOGGER.debug("MediaMTX path %s configured for worker publishing", path_name)
            return
        
        if patch_response.status_code != 404:
            LOGGER.warning(
                "MediaMTX path patch failed (status %d): %s",
                patch_response.status_code,
                patch_response.text[:200],
            )
            # Continue to try adding the path
        
        # Path doesn't exist, create it
        add_response = requests.post(
            add_endpoint,
            json=path_payload,
            timeout=MEDIAMTX_WEBRTC_TIMEOUT_SEC,
        )
        
        if add_response.status_code >= 400:
            LOGGER.error(
                "MediaMTX path creation failed (status %d): %s",
                add_response.status_code,
                add_response.text[:200],
            )
        else:
            LOGGER.info("MediaMTX path %s created for worker publishing", path_name)
            
    except requests.Timeout:
        LOGGER.warning("MediaMTX Control API timed out while configuring published path %s", path_name)
    except requests.RequestException as exc:
        LOGGER.warning("MediaMTX Control API error while configuring published path %s: %s", path_name, exc)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def coerce_datetime(value: object, *, fallback: datetime | None = None) -> datetime:
    """Convert persisted timestamp payloads into aware UTC datetimes."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = fallback or utc_now()

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    return fallback or utc_now()


def serialize_zone_points(zone: ZonePolygon | None) -> list[list[float]] | None:
    """Convert a normalized zone model into JSON-serializable point pairs."""
    if zone is None:
        return None

    return [[point.x, point.y] for point in zone.points]


class FeedPersistencePayload(TypedDict):
    """Typed payload stored in the feed configuration table."""

    feed_id: str
    name: str
    source: str
    manager_user_id: int | None
    model_size: str
    status: str
    log_level: str
    webhook_enabled: bool
    queue_length_warning: int
    created_at: datetime
    updated_at: datetime
    rtsp_username: str | None
    rtsp_password: str | None
    rtsp_transport: str | None
    establishment_id: int | None
    caisse_id: int | None
    zone_points: list[list[float]] | None
    last_error: str | None


def _read_log_tail(log_path: Path | None, max_lines: int = 10) -> str | None:
    """Read the last few non-empty lines from a worker log file."""
    if log_path is None or not log_path.exists():
        return None

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    tail = [line.strip() for line in lines if line.strip()][-max_lines:]
    if not tail:
        return None
    return " | ".join(tail)


def _capture_video_source_snapshot(source: str, jpeg_quality: int = 90) -> tuple[bool, dict]:
    """Capture a JPEG snapshot from a local file path or numeric capture source."""
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "OpenCV is required to capture a preview frame from this feed."
        ) from exc

    capture_source: str | int = int(source) if source.isdigit() else source
    capture = cv2.VideoCapture(capture_source)

    if not capture.isOpened():
        capture.release()
        return False, {"error": f"Could not open source: {source}"}

    ok, frame = capture.read()
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    if not ok or frame is None:
        return False, {"error": f"Could not read a frame from source: {source}"}

    if width <= 0 or height <= 0:
        height, width = frame.shape[:2]

    encoded_ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
    )
    if not encoded_ok:
        return False, {"error": f"Could not encode a snapshot frame from source: {source}"}

    return True, {
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}",
        "mime_type": "image/jpeg",
        "image_base64": base64.b64encode(buffer.tobytes()).decode("ascii"),
    }


def _capture_rtsp_source_snapshot(
    *,
    source: str,
    username: str | None,
    password: str | None,
    transport: str,
) -> tuple[bool, dict]:
    """Capture a snapshot from an RTSP source using stored runtime credentials."""
    try:
        from src.rtsp_camera import RTSPCamera
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RTSP snapshot capture is unavailable because required video dependencies are not installed."
        ) from exc

    return RTSPCamera.capture_snapshot(
        source,
        username=username,
        password=password,
        transport=transport,
    )


@dataclass
class FeedFrameStreamState:
    """Tracks one buffered MJPEG stream source shared across subscribers."""

    feed_id: str
    source: str
    username: str | None
    password: str | None
    transport: Literal["tcp", "udp"]
    mode: Literal["capture", "worker"] = "capture"
    subscribers: int = 0
    latest_frame: bytes | None = None
    frame_index: int = 0
    width: int | None = None
    height: int | None = None
    last_error: str | None = None
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    condition: threading.Condition = field(default_factory=threading.Condition, repr=False)
    worker: threading.Thread | None = field(default=None, repr=False)


class FeedFrameStreamManager:
    """Maintains one persistent frame buffer loop per feed for MJPEG streaming."""

    def __init__(self, *, jpeg_quality: int = 80) -> None:
        self._jpeg_quality = jpeg_quality
        self._states: dict[str, FeedFrameStreamState] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        *,
        feed_id: str,
        source: str,
        username: str | None,
        password: str | None,
        transport: Literal["tcp", "udp"],
    ) -> None:
        stale_state: FeedFrameStreamState | None = None

        async with self._lock:
            state = self._states.get(feed_id)
            if state is not None and (
                state.mode == "capture"
                and (
                state.source != source
                or state.username != username
                or state.password != password
                or state.transport != transport
                )
            ):
                stale_state = state
                state = None

            if state is None:
                state = FeedFrameStreamState(
                    feed_id=feed_id,
                    source=source,
                    username=username,
                    password=password,
                    transport=transport,
                )
                self._states[feed_id] = state

            state.subscribers += 1
            should_start = (
                state.mode == "capture"
                and (state.worker is None or not state.worker.is_alive())
            )

        if stale_state is not None:
            await asyncio.to_thread(self._stop_state, stale_state)

        if should_start:
            await asyncio.to_thread(self._start_state_worker, state)

    async def unsubscribe(self, feed_id: str) -> None:
        state_to_stop: FeedFrameStreamState | None = None

        async with self._lock:
            state = self._states.get(feed_id)
            if state is None:
                return

            state.subscribers = max(0, state.subscribers - 1)
            if state.subscribers == 0:
                state_to_stop = self._states.pop(feed_id, None)

        if state_to_stop is not None:
            await asyncio.to_thread(self._stop_state, state_to_stop)

    async def terminate(self, feed_id: str) -> None:
        state_to_stop: FeedFrameStreamState | None = None

        async with self._lock:
            state_to_stop = self._states.pop(feed_id, None)

        if state_to_stop is not None:
            await asyncio.to_thread(self._stop_state, state_to_stop)

    async def clear(self) -> None:
        async with self._lock:
            states = list(self._states.values())
            self._states.clear()

        for state in states:
            await asyncio.to_thread(self._stop_state, state)

    async def push_worker_frame(
        self,
        *,
        feed_id: str,
        source: str,
        username: str | None,
        password: str | None,
        transport: Literal["tcp", "udp"],
        frame_bytes: bytes,
    ) -> None:
        stale_state: FeedFrameStreamState | None = None
        handoff_frame_index = 0
        handoff_subscribers = 0
        handoff_width: int | None = None
        handoff_height: int | None = None

        async with self._lock:
            state = self._states.get(feed_id)
            if state is not None and state.mode == "capture":
                stale_state = state
                handoff_frame_index = state.frame_index
                handoff_subscribers = state.subscribers
                handoff_width = state.width
                handoff_height = state.height
                state = None

            if state is None:
                state = FeedFrameStreamState(
                    feed_id=feed_id,
                    source=source,
                    username=username,
                    password=password,
                    transport=transport,
                    mode="worker",
                )
                if stale_state is not None:
                    state.frame_index = handoff_frame_index
                    state.subscribers = handoff_subscribers
                    state.width = handoff_width
                    state.height = handoff_height
                self._states[feed_id] = state

            # Keep source metadata in sync in case feed credentials/transport changed.
            state.source = source
            state.username = username
            state.password = password
            state.transport = transport
            state.mode = "worker"

        if stale_state is not None:
            await asyncio.to_thread(self._stop_state, stale_state)
            with state.condition:
                # Keep continuity if capture advanced before the old worker fully stopped.
                state.frame_index = max(state.frame_index, stale_state.frame_index)
                state.subscribers = max(state.subscribers, stale_state.subscribers)
                if state.width is None:
                    state.width = stale_state.width
                if state.height is None:
                    state.height = stale_state.height

        with state.condition:
            state.latest_frame = frame_bytes
            state.frame_index += 1
            state.last_error = None
            state.condition.notify_all()

    async def wait_for_next_frame(
        self,
        feed_id: str,
        *,
        after_frame_index: int,
        timeout_seconds: float = 1.0,
    ) -> tuple[int, bytes] | None:
        async with self._lock:
            state = self._states.get(feed_id)

        if state is None:
            return None

        return await asyncio.to_thread(
            self._wait_for_next_frame_sync,
            state,
            after_frame_index,
            timeout_seconds,
        )

    def _start_state_worker(self, state: FeedFrameStreamState) -> None:
        if state.worker is not None and state.worker.is_alive():
            return

        state.stop_event.clear()
        state.worker = threading.Thread(
            target=self._capture_loop,
            args=(state,),
            name=f"feed-stream-{state.feed_id}",
            daemon=True,
        )
        state.worker.start()

    def _stop_state(self, state: FeedFrameStreamState) -> None:
        state.stop_event.set()
        with state.condition:
            state.condition.notify_all()

        worker = state.worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=1.5)

        state.worker = None

    def _wait_for_next_frame_sync(
        self,
        state: FeedFrameStreamState,
        after_frame_index: int,
        timeout_seconds: float,
    ) -> tuple[int, bytes] | None:
        deadline = time.monotonic() + max(timeout_seconds, 0.01)

        with state.condition:
            while not state.stop_event.is_set():
                if state.latest_frame is not None and state.frame_index > after_frame_index:
                    return state.frame_index, state.latest_frame

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    if (
                        state.latest_frame is not None
                        and state.frame_index > 0
                        and state.frame_index < after_frame_index
                    ):
                        # Recover stalled subscribers when a stream restarts and
                        # the shared frame index sequence is reset to a lower value.
                        return state.frame_index, state.latest_frame
                    return None

                state.condition.wait(timeout=remaining)

        return None

    def _open_capture(self, state: FeedFrameStreamState):
        import cv2

        source = state.source
        if source.lower().startswith("rtsp://"):
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", f"rtsp_transport;{state.transport}")
            capture_source = _build_authenticated_rtsp_source(
                source,
                state.username,
                state.password,
            )
            capture = cv2.VideoCapture(capture_source, cv2.CAP_FFMPEG)
            capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5_000)
            capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5_000)
            return capture

        capture_source: str | int = int(source) if source.isdigit() else source
        return cv2.VideoCapture(capture_source)

    @staticmethod
    def _fps_to_frame_interval(native_fps: float) -> float:
        """Return the per-frame sleep duration that matches a video file's native FPS."""
        return 1.0 / native_fps if native_fps > 0 else 1.0 / 25.0

    def _capture_loop(self, state: FeedFrameStreamState) -> None:
        try:
            import cv2
        except ModuleNotFoundError:
            with state.condition:
                state.last_error = "OpenCV is required for MJPEG streaming."
                state.stop_event.set()
                state.condition.notify_all()
            return

        capture = self._open_capture(state)
        failure_count = 0
        is_rtsp_source = state.source.lower().startswith("rtsp://")
        is_live_source = is_rtsp_source or state.source.isdigit()

        # For file sources, throttle the capture loop to the video's native FPS so
        # the MJPEG stream plays back at real speed and doesn't burn CPU looping.
        frame_interval = (
            self._fps_to_frame_interval(capture.get(cv2.CAP_PROP_FPS))
            if not is_live_source and capture.isOpened()
            else 0.0
        )
        last_frame_time = time.monotonic()

        try:
            while not state.stop_event.is_set():
                if not capture.isOpened():
                    failure_count += 1
                    time.sleep(0.2)
                    capture.release()
                    capture = self._open_capture(state)
                    if not is_live_source and capture.isOpened():
                        frame_interval = self._fps_to_frame_interval(capture.get(cv2.CAP_PROP_FPS))
                    continue

                ok, frame = capture.read()
                if not ok or frame is None:
                    failure_count += 1

                    if is_rtsp_source and failure_count >= 10:
                        capture.release()
                        capture = self._open_capture(state)
                        failure_count = 0
                    elif not is_rtsp_source:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

                    time.sleep(0.05)
                    continue

                failure_count = 0
                encoded_ok, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality],
                )
                if not encoded_ok:
                    time.sleep(0.01)
                    continue

                frame_height, frame_width = frame.shape[:2]

                with state.condition:
                    state.latest_frame = buffer.tobytes()
                    state.frame_index += 1
                    state.width = frame_width
                    state.height = frame_height
                    state.last_error = None
                    state.condition.notify_all()

                if frame_interval > 0:
                    now = time.monotonic()
                    sleep_time = frame_interval - (now - last_frame_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    last_frame_time = time.monotonic()
        finally:
            capture.release()
            with state.condition:
                state.condition.notify_all()


@dataclass(frozen=True)
class FrameChannelBinding:
    """Connection parameters used by one worker to publish encoded frames."""

    host: str
    port: int
    token: str


class WorkerFrameChannelServer:
    """Accepts binary JPEG frames from worker processes over a local TCP socket."""

    def __init__(
        self,
        *,
        on_frame: Callable[[str, bytes], None],
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        bind_host: str = DEFAULT_FRAME_CHANNEL_BIND_HOST,
    ) -> None:
        self._on_frame = on_frame
        self._on_event = on_event
        self._bind_host = bind_host
        self._server_socket: socket.socket | None = None
        self._server_host: str | None = None
        self._server_port: int | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._accept_thread: threading.Thread | None = None
        self._client_threads: set[threading.Thread] = set()
        self._feed_tokens: dict[str, str] = {}
        self._token_feeds: dict[str, str] = {}

        try:
            self._start_server()
        except OSError as exc:
            LOGGER.warning("Worker frame channel server disabled: %s", exc)

    @property
    def available(self) -> bool:
        return self._server_socket is not None and self._server_host is not None and self._server_port is not None

    def register_feed(self, feed_id: str) -> FrameChannelBinding | None:
        if not self.available:
            return None

        token = uuid4().hex
        with self._lock:
            old_token = self._feed_tokens.pop(feed_id, None)
            if old_token is not None:
                self._token_feeds.pop(old_token, None)
            self._feed_tokens[feed_id] = token
            self._token_feeds[token] = feed_id

            host = self._server_host
            port = self._server_port

        if host is None or port is None:
            return None

        return FrameChannelBinding(host=host, port=port, token=token)

    def unregister_feed(self, feed_id: str) -> None:
        with self._lock:
            token = self._feed_tokens.pop(feed_id, None)
            if token is not None:
                self._token_feeds.pop(token, None)

    def close(self) -> None:
        self._stop_event.set()

        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            finally:
                self._server_socket = None

        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.5)
            self._accept_thread = None

        with self._lock:
            client_threads = list(self._client_threads)

        for thread in client_threads:
            thread.join(timeout=1.0)

        with self._lock:
            self._client_threads.clear()
            self._feed_tokens.clear()
            self._token_feeds.clear()

    def _start_server(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self._bind_host, 0))
        server.listen()
        server.settimeout(0.5)

        host, port = server.getsockname()[:2]
        self._server_socket = server
        self._server_host = str(host)
        self._server_port = int(port)

        self._accept_thread = threading.Thread(
            target=self._accept_loop,
            name="worker-frame-channel",
            daemon=True,
        )
        self._accept_thread.start()

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            server = self._server_socket
            if server is None:
                return

            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if not self._stop_event.is_set():
                    LOGGER.debug("Frame channel accept loop stopped due to socket error.")
                return

            thread = threading.Thread(
                target=self._handle_client,
                args=(conn,),
                name="worker-frame-client",
                daemon=True,
            )
            with self._lock:
                self._client_threads.add(thread)
            thread.start()

    def _handle_client(self, conn: socket.socket) -> None:
        thread = threading.current_thread()
        conn.settimeout(1.0)

        try:
            token_len_raw = self._recv_exact(conn, 2)
            if token_len_raw is None:
                return

            token_len = struct.unpack(">H", token_len_raw)[0]
            if token_len <= 0:
                return

            token_raw = self._recv_exact(conn, token_len)
            if token_raw is None:
                return

            token = token_raw.decode("utf-8", errors="ignore")
            with self._lock:
                feed_id = self._token_feeds.get(token)
            if feed_id is None:
                return

            while not self._stop_event.is_set():
                with self._lock:
                    if self._token_feeds.get(token) != feed_id:
                        return

                # Read message type byte (0x01 for frames, 0x02 for events)
                msg_type_raw = self._recv_exact(conn, 1)
                if msg_type_raw is None:
                    return
                
                msg_type = msg_type_raw[0]

                # Read message length
                msg_len_raw = self._recv_exact(conn, 4)
                if msg_len_raw is None:
                    return

                msg_len = struct.unpack(">I", msg_len_raw)[0]
                if msg_len <= 0 or msg_len > MAX_FRAME_CHANNEL_FRAME_BYTES:
                    return

                msg_bytes = self._recv_exact(conn, msg_len)
                if msg_bytes is None:
                    return

                # Route to appropriate handler based on message type
                if msg_type == 0x01:
                    # Frame message
                    self._on_frame(feed_id, msg_bytes)
                elif msg_type == 0x02:
                    # Event message
                    if self._on_event is not None:
                        try:
                            event_dict = json.loads(msg_bytes.decode("utf-8"))
                            if isinstance(event_dict, dict):
                                self._on_event(feed_id, event_dict)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            # Ignore malformed event messages
                            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

            with self._lock:
                self._client_threads.discard(thread)

    @staticmethod
    def _recv_exact(conn: socket.socket, byte_count: int) -> bytes | None:
        chunks: list[bytes] = []
        received = 0

        while received < byte_count:
            try:
                chunk = conn.recv(byte_count - received)
            except socket.timeout:
                continue
            except OSError:
                return None

            if not chunk:
                return None

            chunks.append(chunk)
            received += len(chunk)

        return b"".join(chunks)


@dataclass
class FeedWorkerHandle:
    """Runtime handle for a launched analysis worker."""

    feed_id: str
    command: list[str]
    process: subprocess.Popen | None = field(default=None, repr=False)
    log_path: Path | None = None
    log_stream: TextIO | None = field(default=None, repr=False)
    event_path: Path | None = None
    event_cursor: int = 0
    event_buffer: str = ""


class FeedWorkerRunner(Protocol):
    """Abstract worker launcher so runtime control can be tested without subprocesses."""

    def start(self, record: "FeedRecord") -> FeedWorkerHandle:
        """Launch a worker for the provided feed record."""
        ...

    def stop(self, handle: FeedWorkerHandle) -> None:
        """Stop a previously launched worker."""
        ...

    def poll(self, handle: FeedWorkerHandle) -> int | None:
        """Return the process exit code, or None while still running."""
        ...

    def close(self, handle: FeedWorkerHandle) -> None:
        """Release any open resources associated with the handle."""
        ...

    def exit_details(self, handle: FeedWorkerHandle, exit_code: int) -> str | None:
        """Return a human-readable failure summary for a completed worker."""
        ...



class SubprocessFeedWorkerRunner:
    """Launches the existing CLI analysis pipeline as background subprocesses."""

    def start(self, record: "FeedRecord") -> FeedWorkerHandle:
        RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = RUNTIME_LOG_DIR / f"{record.feed_id}-{utc_now().strftime('%Y%m%dT%H%M%S')}.log"
        event_path = RUNTIME_LOG_DIR / f"{record.feed_id}-{utc_now().strftime('%Y%m%dT%H%M%S')}.events.jsonl"
        command = self._build_command(record, event_path)
        log_stream = log_path.open("a", encoding="utf-8")

        creationflags = 0
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            process = subprocess.Popen(
                command,
                cwd=str(BACKEND_DIR),
                env=dict(os.environ),
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
                creationflags=creationflags,
            )
        except OSError as exc:
            log_stream.close()
            raise FeedStartError(f"Failed to start analysis worker: {exc}") from exc

        return FeedWorkerHandle(
            feed_id=record.feed_id,
            command=command,
            process=process,
            log_path=log_path,
            log_stream=log_stream,
            event_path=event_path,
        )

    def stop(self, handle: FeedWorkerHandle) -> None:
        process = handle.process
        if process is None:
            return

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def poll(self, handle: FeedWorkerHandle) -> int | None:
        if handle.process is None:
            return 0
        return handle.process.poll()

    def close(self, handle: FeedWorkerHandle) -> None:
        if handle.log_stream is not None and not handle.log_stream.closed:
            handle.log_stream.close()

    def exit_details(self, handle: FeedWorkerHandle, exit_code: int) -> str | None:
        if exit_code == 0:
            return None

        tail = _read_log_tail(handle.log_path)
        if tail:
            return f"Worker exited with code {exit_code}. Last output: {tail}"
        return f"Worker exited with code {exit_code}."

    def _build_command(self, record: "FeedRecord", event_path: Path) -> list[str]:
        command = [
            sys.executable,
            "-u",
            "-m",
            "src.main",
            "--source",
            record.source,
            "--model-size",
            record.model_size,
            "--device",
            DEFAULT_WORKER_INFERENCE_DEVICE,
            "--confidence",
            str(DEFAULT_WORKER_CONFIDENCE),
            "--detector-imgsz",
            str(DEFAULT_WORKER_DETECTOR_IMAGE_SIZE),
            "--process-every-n-frames",
            str(DEFAULT_WORKER_PROCESS_EVERY_N_FRAMES),
            "--log-level",
            record.log_level or DEFAULT_LOG_LEVEL,
            "--resize-scale",
            str(DEFAULT_RESIZE_SCALE),
            "--events-file",
            str(event_path),
            "--headless",
            "--pipeline-engine",
            DEFAULT_WORKER_PIPELINE_ENGINE,
            "--gstreamer-rtsp-latency-ms",
            str(DEFAULT_WORKER_GSTREAMER_RTSP_LATENCY_MS),
        ]

        if (
            record.dashboard_frame_channel_host
            and record.dashboard_frame_channel_port is not None
            and record.dashboard_frame_channel_token
        ):
            command.extend(
                [
                    "--dashboard-render-frames",
                    "--dashboard-frame-jpeg-quality",
                    str(DEFAULT_WORKER_DASHBOARD_FRAME_JPEG_QUALITY),
                    "--dashboard-frame-channel-host",
                    record.dashboard_frame_channel_host,
                    "--dashboard-frame-channel-port",
                    str(record.dashboard_frame_channel_port),
                    "--dashboard-frame-channel-token",
                    record.dashboard_frame_channel_token,
                ]
            )

        if DEFAULT_ANNOTATED_WEBRTC_PUBLISH_ENABLED and record.published_webrtc_path:
            command.extend(
                [
                    "--annotated-webrtc-enable",
                    "--annotated-webrtc-path",
                    record.published_webrtc_path,
                    "--annotated-webrtc-rtsp-host",
                    DEFAULT_ANNOTATED_WEBRTC_RTSP_HOST,
                    "--annotated-webrtc-rtsp-port",
                    str(DEFAULT_ANNOTATED_WEBRTC_RTSP_PORT),
                    "--annotated-webrtc-fps",
                    str(DEFAULT_ANNOTATED_WEBRTC_FPS),
                    "--annotated-webrtc-ffmpeg-binary",
                    DEFAULT_ANNOTATED_WEBRTC_FFMPEG_BINARY,
                ]
            )

        if record.zone is not None:
            command.extend(["--zone-points", json.dumps(serialize_zone_points(record.zone))])

        if record.source.lower().startswith("rtsp://"):
            if record.rtsp_username:
                command.extend(["--rtsp-user", record.rtsp_username])
            if record.rtsp_password:
                command.extend(["--rtsp-pass", record.rtsp_password])
            if record.rtsp_transport:
                command.extend(["--rtsp-transport", record.rtsp_transport])

        command.extend(
            [
                "--queue-length-warning",
                str(record.queue_length_warning),
            ]
        )

        if record.establishment_id is not None:
            command.extend(["--establishment-id", str(record.establishment_id)])
        if record.caisse_id is not None:
            command.extend(["--caisse-id", str(record.caisse_id)])
        if not record.webhook_enabled:
            command.append("--disable-webhook")

        return command


@dataclass
class FeedRecord:
    """Mutable in-memory representation of a configured feed."""

    feed_id: str
    name: str
    source: str
    manager_user_id: int | None
    model_size: ModelSize
    status: str
    created_at: datetime
    updated_at: datetime
    log_level: LogLevel = "INFO"
    webhook_enabled: bool = True
    queue_length_warning: int = 8
    rtsp_username: str | None = None
    rtsp_password: str | None = None
    rtsp_transport: Literal["tcp", "udp"] | None = None
    establishment_id: int | None = None
    caisse_id: int | None = None
    zone: ZonePolygon | None = None
    latest_metrics: dict | None = None
    backend_annotations_active: bool = False
    published_webrtc_path: str | None = None
    published_webrtc_ready: bool = False
    published_webrtc_reason: str | None = None
    transport_end_to_end_latency_ms: float | None = None
    transport_metadata_video_skew_ms: float | None = None
    transport_dropped_frame_ratio: float | None = None
    transport_health_state: Literal["ok", "warning", "error"] | None = None
    transport_health_reason: str | None = None
    transport_compatibility_reason: str | None = None
    transport_pipeline_mode: str | None = None
    transport_skew_exceeded_since_monotonic: float | None = None
    transport_last_frame_seq: int | None = None
    transport_frames_seen: int = 0
    transport_frames_dropped: int = 0
    dashboard_frame_channel_host: str | None = None
    dashboard_frame_channel_port: int | None = None
    dashboard_frame_channel_token: str | None = None
    last_worker_frame_at_monotonic: float | None = None
    last_error: str | None = None
    last_warning: str | None = None
    last_warning_code: str | None = None
    worker: FeedWorkerHandle | None = field(default=None, repr=False)
    session_id: int | None = None

    def public_source(self) -> str:
        """Return a frontend-safe source string without embedded credentials."""
        return sanitize_source(self.source)

    def to_transport_capabilities(self) -> FeedTransportCapabilities:
        """Build transport readiness details for the unified WebRTC pipeline."""
        is_running = self.status == "running"
        webrtc_path_name = self.published_webrtc_path or self.feed_id
        webrtc_enabled = bool(webrtc_path_name)
        webrtc_ready = bool(is_running and self.published_webrtc_ready)
        webrtc_reason: str | None = None

        if not is_running:
            webrtc_reason = "feed_not_running"
        elif not webrtc_ready:
            webrtc_reason = self.published_webrtc_reason or "publisher_not_ready"

        return FeedTransportCapabilities.model_validate(
            {
                "webrtc": {
                    "enabled": webrtc_enabled,
                    "ready": webrtc_ready,
                    "path_name": webrtc_path_name,
                    "reason": webrtc_reason,
                    "end_to_end_latency_ms": self.transport_end_to_end_latency_ms,
                    "metadata_video_skew_ms": self.transport_metadata_video_skew_ms,
                    "dropped_frame_ratio": self.transport_dropped_frame_ratio,
                    "health_state": self.transport_health_state or ("warning" if self.transport_compatibility_reason else None),
                    "health_reason": self.transport_health_reason or self.transport_compatibility_reason,
                },
            }
        )

    def to_model(self) -> VideoFeed:
        """Convert the internal dataclass into the public API model."""
        return VideoFeed.model_validate(
            {
                **self.__dict__,
                "source": self.public_source(),
                "preview_path": build_preview_path(self.source),
                "transport": self.to_transport_capabilities(),
            }
        )


class WebSocketHub:
    """Tracks connected websocket clients and broadcasts JSON events."""

    def __init__(self) -> None:
        self._clients: dict[WebSocket, int | None] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, *, owner_user_id: int | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[websocket] = owner_user_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(websocket, None)

    async def broadcast(self, payload: dict) -> None:
        await self._broadcast_to_clients(payload, owner_user_id=None, scoped=False)

    async def _broadcast_to_clients(
        self,
        payload: dict,
        *,
        owner_user_id: int | None,
        scoped: bool,
    ) -> None:
        async with self._lock:
            clients = list(self._clients.items())

        if not clients:
            return

        if scoped:
            clients = [
                (websocket, scope)
                for websocket, scope in clients
                if self._client_can_receive(scope, owner_user_id)
            ]

        if not clients:
            return

        send_results = await asyncio.gather(
            *(self._send_json(websocket, payload) for websocket, _ in clients),
            return_exceptions=False,
        )

        stale_clients: list[WebSocket] = []
        for (websocket, _), delivered in zip(clients, send_results):
            if not delivered:
                stale_clients.append(websocket)

        if stale_clients:
            async with self._lock:
                for websocket in stale_clients:
                    self._clients.pop(websocket, None)

            for websocket in stale_clients:
                try:
                    await websocket.close()
                except RuntimeError:
                    pass
                except WebSocketDisconnect:
                    pass

    async def _send_json(self, websocket: WebSocket, payload: dict) -> bool:
        try:
            await asyncio.wait_for(websocket.send_json(payload), timeout=2.0)
            return True
        except (RuntimeError, WebSocketDisconnect, asyncio.TimeoutError):
            return False

    @staticmethod
    def _client_can_receive(client_owner_scope: int | None, event_owner_scope: int | None) -> bool:
        if client_owner_scope is None:
            return True

        if event_owner_scope is None:
            # Legacy feeds persisted before manager ownership tracking do not have
            # an owner scope. Deliver these events to connected manager clients so
            # pre-migration feeds keep streaming after auth rollout.
            return True

        return client_owner_scope == event_owner_scope

    async def broadcast_feed_event(
        self,
        *,
        action: Literal["created", "updated", "deleted"],
        feed: VideoFeed | None = None,
        feed_id: str | None = None,
        owner_user_id: int | None = None,
    ) -> None:
        event = FeedStatusEvent(
            payload=FeedStatusEventPayload(action=action, feed=feed, feed_id=feed_id),
        )
        await self._broadcast_to_clients(
            event.model_dump(mode="json"),
            owner_user_id=owner_user_id,
            scoped=True,
        )

    async def broadcast_metrics_event(
        self,
        *,
        feed_id: str,
        metrics: QueueMetricsModel,
        owner_user_id: int | None = None,
    ) -> None:
        event = MetricsUpdateEvent(payload=MetricsUpdateEventPayload(feed_id=feed_id, metrics=metrics))
        await self._broadcast_to_clients(
            event.model_dump(mode="json"),
            owner_user_id=owner_user_id,
            scoped=True,
        )

    async def broadcast_alert_event(
        self,
        *,
        feed_id: str,
        alert: AlertModel,
        owner_user_id: int | None = None,
    ) -> None:
        event = AlertFiredEvent(payload=AlertFiredEventPayload(feed_id=feed_id, alert=alert))
        await self._broadcast_to_clients(
            event.model_dump(mode="json"),
            owner_user_id=owner_user_id,
            scoped=True,
        )

    async def broadcast_system_warning(
        self,
        *,
        feed_id: str,
        code: str,
        message: str,
        timestamp: datetime,
        owner_user_id: int | None = None,
    ) -> None:
        event = SystemWarningEvent(
            payload=SystemWarningEventPayload(
                feed_id=feed_id,
                code=code,
                message=message,
                timestamp=timestamp,
            )
        )
        await self._broadcast_to_clients(
            event.model_dump(mode="json"),
            owner_user_id=owner_user_id,
            scoped=True,
        )

    @property
    def client_count(self) -> int:
        return len(self._clients)


class FeedRegistry:
    """Stores configured feeds and exposes async-safe CRUD operations."""

    def __init__(self, broadcaster: WebSocketHub, runner: FeedWorkerRunner | None = None) -> None:
        self._broadcaster = broadcaster
        self._runner = runner or SubprocessFeedWorkerRunner()
        self._frame_streams = FeedFrameStreamManager()
        self._frame_channel: WorkerFrameChannelServer | None = None
        if isinstance(self._runner, SubprocessFeedWorkerRunner):
            self._frame_channel = WorkerFrameChannelServer(
                on_frame=self._on_frame_channel_frame,
                on_event=self._on_frame_channel_event,
            )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._feeds: dict[str, FeedRecord] = {}
        self._lock = asyncio.Lock()
        self._load_persisted_feeds()

    def _bind_event_loop(self) -> None:
        """Capture the running loop so frame-channel threads can enqueue async work."""
        if self._loop is not None and not self._loop.is_closed():
            return

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    @staticmethod
    def _is_record_visible_to_owner_scope(record: FeedRecord, owner_user_id: int | None) -> bool:
        if owner_user_id is None:
            return True
        # Keep feeds created before manager ownership support visible while users
        # migrate existing records to explicit manager assignments.
        if record.manager_user_id is None:
            return True
        return record.manager_user_id == owner_user_id

    def _reserve_frame_channel_binding(self, feed_id: str) -> FrameChannelBinding | None:
        if self._frame_channel is None:
            return None
        return self._frame_channel.register_feed(feed_id)

    def _clear_frame_channel_binding(self, feed_id: str) -> None:
        if self._frame_channel is not None:
            self._frame_channel.unregister_feed(feed_id)

    def _on_frame_channel_frame(self, feed_id: str, frame_bytes: bytes) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or not frame_bytes:
            return

        future = asyncio.run_coroutine_threadsafe(
            self._ingest_worker_frame(feed_id, frame_bytes),
            loop,
        )

        def _consume_result(done_future) -> None:  # noqa: ANN001
            try:
                done_future.result()
            except Exception:
                LOGGER.debug(
                    "Failed to ingest worker frame for feed %s.",
                    feed_id,
                    exc_info=True,
                )

        future.add_done_callback(_consume_result)

    def _on_frame_channel_event(self, feed_id: str, event_dict: dict[str, Any]) -> None:
        """Handle events received via socket channel."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        future = asyncio.run_coroutine_threadsafe(
            self._dispatch_worker_event(feed_id, event_dict),
            loop,
        )

        def _consume_result(done_future) -> None:  # noqa: ANN001
            try:
                done_future.result()
            except Exception:
                LOGGER.debug(
                    "Failed to dispatch worker event for feed %s.",
                    feed_id,
                    exc_info=True,
                )

        future.add_done_callback(_consume_result)

    async def _ingest_worker_frame(self, feed_id: str, frame_bytes: bytes) -> None:
        source = ""
        username: str | None = None
        password: str | None = None
        transport: Literal["tcp", "udp"] = "tcp"

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return

            source = record.source
            username = record.rtsp_username
            password = record.rtsp_password
            transport = record.rtsp_transport or "tcp"
            record.backend_annotations_active = True
            record.last_worker_frame_at_monotonic = time.monotonic()

            if isinstance(record.latest_metrics, dict):
                record.latest_metrics["backend_annotations_active"] = True
                record.latest_metrics["render_frame_jpeg_base64"] = None

        if not source:
            return

        await self._frame_streams.push_worker_frame(
            feed_id=feed_id,
            source=source,
            username=username,
            password=password,
            transport=transport,
            frame_bytes=frame_bytes,
        )

    async def list_feeds(self, *, owner_user_id: int | None = None) -> list[VideoFeed]:
        async with self._lock:
            records = [
                record
                for record in self._feeds.values()
                if self._is_record_visible_to_owner_scope(record, owner_user_id)
            ]
            records.sort(key=lambda item: item.created_at)
            return [record.to_model() for record in records]

    async def get_feed(self, feed_id: str, *, owner_user_id: int | None = None) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None
            return record.to_model()

    async def get_feed_transport_capabilities(
        self,
        feed_id: str,
        *,
        owner_user_id: int | None = None,
    ) -> FeedTransportCapabilities | None:
        """Return frontend playback capability details for one feed."""
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None
            return record.to_transport_capabilities()

    async def create_feed(
        self,
        *,
        name: str,
        source: str,
        manager_user_id: int | None = None,
        model_size: ModelSize = "n",
        zone: ZonePolygon | None = None,
        log_level: LogLevel = "INFO",
        webhook_enabled: bool = True,
        queue_length_warning: int = 8,
        establishment_id: int | None = None,
        caisse_id: int | None = None,
        rtsp_username: str | None = None,
        rtsp_password: str | None = None,
        rtsp_transport: Literal["tcp", "udp"] | None = None,
    ) -> VideoFeed:
        resolved_zone = zone if zone is not None else self._load_saved_zone(caisse_id)
        now = utc_now()
        record = FeedRecord(
            feed_id=str(uuid4()),
            name=name.strip(),
            source=source.strip(),
            manager_user_id=manager_user_id,
            log_level=log_level,
            webhook_enabled=webhook_enabled,
            queue_length_warning=queue_length_warning,
            rtsp_username=rtsp_username.strip() or None if rtsp_username else None,
            rtsp_password=rtsp_password.strip() or None if rtsp_password else None,
            rtsp_transport=rtsp_transport,
            model_size=model_size,
            status="created",
            created_at=now,
            updated_at=now,
            establishment_id=establishment_id,
            caisse_id=caisse_id,
            zone=resolved_zone,
        )
        await self._persist_record(record)

        if resolved_zone is not None and caisse_id is not None:
            await asyncio.to_thread(
                update_caisse_zone_points,
                caisse_id,
                [[point.x, point.y] for point in resolved_zone.points],
            )

        async with self._lock:
            self._feeds[record.feed_id] = record
            model = record.to_model()

        await self._broadcaster.broadcast_feed_event(
            action="created",
            feed=model,
            owner_user_id=record.manager_user_id,
        )
        return model

    async def delete_feed(self, feed_id: str, *, owner_user_id: int | None = None) -> bool:
        async with self._lock:
            record = self._feeds.get(feed_id)

        if record is None:
            return False
        if not self._is_record_visible_to_owner_scope(record, owner_user_id):
            return False

        if record.worker is not None and self._runner.poll(record.worker) is None:
            await self.stop_feed(feed_id)

        async with self._lock:
            removed = self._feeds.pop(feed_id, None)

        if removed is None:
            return False

        self._clear_frame_channel_binding(feed_id)
        await self._frame_streams.terminate(feed_id)
        await asyncio.to_thread(delete_feed_config, feed_id)

        await self._broadcaster.broadcast_feed_event(
            action="deleted",
            feed_id=feed_id,
            owner_user_id=removed.manager_user_id,
        )
        return True

    async def update_zone(
        self,
        feed_id: str,
        zone: ZonePolygon,
        *,
        owner_user_id: int | None = None,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            record.zone = zone
            record.updated_at = utc_now()
            model = record.to_model()

        if record.caisse_id is not None:
            await asyncio.to_thread(
                update_caisse_zone_points,
                record.caisse_id,
                [[point.x, point.y] for point in zone.points],
            )

        await self._persist_record(record)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=model,
            owner_user_id=record.manager_user_id,
        )
        return model

    async def update_thresholds(
        self,
        feed_id: str,
        *,
        queue_length_warning: int,
        owner_user_id: int | None = None,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            record.queue_length_warning = queue_length_warning
            record.updated_at = utc_now()
            model = record.to_model()
            should_restart = record.worker is not None and self._runner.poll(record.worker) is None

        await self._persist_record(record)

        if should_restart:
            await self.restart_feed(feed_id, owner_user_id=owner_user_id)
            return await self.get_feed(feed_id, owner_user_id=owner_user_id)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=model,
            owner_user_id=record.manager_user_id,
        )
        return model

    async def update_source(
        self,
        feed_id: str,
        *,
        source: str,
        restart_if_running: bool = True,
        rtsp_username: str | None = None,
        set_rtsp_username: bool = False,
        rtsp_password: str | None = None,
        set_rtsp_password: bool = False,
        rtsp_transport: Literal["tcp", "udp"] | None = None,
        set_rtsp_transport: bool = False,
        owner_user_id: int | None = None,
    ) -> VideoFeed | None:
        """Update a feed source and optionally restart the worker when running."""
        normalized_source = source.strip()
        if not normalized_source:
            raise FeedStateError("Feed source must not be blank.")

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            record.source = normalized_source

            if set_rtsp_username:
                record.rtsp_username = rtsp_username
            if set_rtsp_password:
                record.rtsp_password = rtsp_password
            if set_rtsp_transport:
                record.rtsp_transport = rtsp_transport

            if record.source.lower().startswith("rtsp://") and record.rtsp_password and not record.rtsp_username:
                raise FeedStateError("RTSP username is required when RTSP password is provided.")

            record.updated_at = utc_now()
            model = record.to_model()
            should_restart = (
                restart_if_running
                and record.worker is not None
                and self._runner.poll(record.worker) is None
            )

        await self._persist_record(record)

        if should_restart:
            await self.restart_feed(feed_id, owner_user_id=owner_user_id)
            return await self.get_feed(feed_id, owner_user_id=owner_user_id)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=model,
            owner_user_id=record.manager_user_id,
        )
        return model

    async def start_feed(
        self,
        feed_id: str,
        *,
        log_level: LogLevel | None = None,
        webhook_enabled: bool | None = None,
        owner_user_id: int | None = None,
    ) -> VideoFeed | None:
        self._bind_event_loop()

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            if record.worker is not None and self._runner.poll(record.worker) is None:
                raise FeedStateError("Feed is already running.")

            if record.worker is not None and self._runner.poll(record.worker) is not None:
                await asyncio.to_thread(self._runner.close, record.worker)
                record.worker = None
                record.session_id = None

            if log_level is not None:
                record.log_level = log_level
            if webhook_enabled is not None:
                record.webhook_enabled = webhook_enabled

            record.status = "initializing"
            record.backend_annotations_active = False
            record.published_webrtc_path = build_published_webrtc_path_name(record.feed_id)
            if DEFAULT_ANNOTATED_WEBRTC_PUBLISH_ENABLED:
                record.published_webrtc_reason = _normalize_publisher_reason("publisher_not_ready")
            else:
                record.published_webrtc_reason = _normalize_publisher_reason("publisher_unavailable")
            record.published_webrtc_ready = False
            record.last_worker_frame_at_monotonic = None
            record.transport_end_to_end_latency_ms = None
            record.transport_metadata_video_skew_ms = None
            record.transport_dropped_frame_ratio = None
            record.transport_health_state = None
            record.transport_health_reason = None
            record.transport_compatibility_reason = None
            record.transport_pipeline_mode = None
            record.transport_skew_exceeded_since_monotonic = None
            record.transport_last_frame_seq = None
            record.transport_frames_seen = 0
            record.transport_frames_dropped = 0
            record.last_error = None
            record.last_warning = None
            record.last_warning_code = None

            frame_binding = self._reserve_frame_channel_binding(record.feed_id)
            if frame_binding is not None:
                record.dashboard_frame_channel_host = frame_binding.host
                record.dashboard_frame_channel_port = frame_binding.port
                record.dashboard_frame_channel_token = frame_binding.token
            else:
                record.dashboard_frame_channel_host = None
                record.dashboard_frame_channel_port = None
                record.dashboard_frame_channel_token = None

            record.updated_at = utc_now()
            initializing_model = record.to_model()

        await self._persist_record(record)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=initializing_model,
            owner_user_id=record.manager_user_id,
        )

        handle: FeedWorkerHandle | None = None
        try:
            handle = await asyncio.to_thread(self._runner.start, record)
            session_id = await asyncio.to_thread(
                create_video_session,
                record.public_source(),
                record.establishment_id,
                record.caisse_id,
            )
        except FeedStartError as exc:
            if handle is not None:
                await asyncio.to_thread(self._runner.stop, handle)
                await asyncio.to_thread(self._runner.close, handle)
            self._clear_frame_channel_binding(feed_id)
            await self._mark_feed_error(feed_id, str(exc))
            raise
        except Exception as exc:
            if handle is not None:
                await asyncio.to_thread(self._runner.stop, handle)
                await asyncio.to_thread(self._runner.close, handle)
            message = f"Failed to launch feed worker: {exc}"
            self._clear_frame_channel_binding(feed_id)
            await self._mark_feed_error(feed_id, message)
            raise FeedStartError(message) from exc

        # Configure MediaMTX path for unified worker publishing if needed.
        if record.published_webrtc_path:
            try:
                await asyncio.to_thread(
                    configure_mediamtx_published_path,
                    record.published_webrtc_path,
                )
            except Exception as exc:
                LOGGER.warning(
                    "Failed to configure MediaMTX path for feed %s: %s",
                    feed_id,
                    exc,
                )
                # Don't fail the feed start, just log the warning
                # The worker will emit transport_status events indicating the issue

        async with self._lock:
            current = self._feeds.get(feed_id)
            if current is None:
                await asyncio.to_thread(self._runner.stop, handle)
                await asyncio.to_thread(self._runner.close, handle)
                await asyncio.to_thread(end_video_session, session_id)
                self._clear_frame_channel_binding(feed_id)
                return None

            current.worker = handle
            current.session_id = session_id
            current.status = "running"
            current.updated_at = utc_now()
            running_model = current.to_model()

        await self._persist_record(current)

        asyncio.create_task(self._monitor_feed(feed_id, handle))
        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=running_model,
            owner_user_id=current.manager_user_id,
        )
        return running_model

    async def stop_feed(self, feed_id: str, *, owner_user_id: int | None = None) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            handle = record.worker
            if handle is None or self._runner.poll(handle) is not None:
                record.worker = None
                record.session_id = None
                raise FeedStateError("Feed is not running.")

            session_id = record.session_id
            record.worker = None
            record.session_id = None

        try:
            await asyncio.to_thread(self._runner.stop, handle)
            await asyncio.to_thread(self._runner.close, handle)
            if session_id is not None:
                await asyncio.to_thread(end_video_session, session_id)
            self._clear_frame_channel_binding(feed_id)
            await self._frame_streams.terminate(feed_id)
        except Exception as exc:
            message = f"Failed to stop feed worker: {exc}"
            await self._mark_feed_error(feed_id, message)
            raise RuntimeError(message) from exc

        async with self._lock:
            current = self._feeds.get(feed_id)
            if current is None:
                return None

            current.status = "stopped"
            current.backend_annotations_active = False
            current.published_webrtc_path = None
            current.published_webrtc_ready = False
            current.published_webrtc_reason = None
            current.last_worker_frame_at_monotonic = None
            current.dashboard_frame_channel_host = None
            current.dashboard_frame_channel_port = None
            current.dashboard_frame_channel_token = None
            current.last_error = None
            current.transport_compatibility_reason = None
            current.transport_pipeline_mode = None
            current.updated_at = utc_now()
            stopped_model = current.to_model()

        await self._persist_record(current)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=stopped_model,
            owner_user_id=current.manager_user_id,
        )
        return stopped_model

    async def restart_feed(
        self,
        feed_id: str,
        *,
        log_level: LogLevel | None = None,
        webhook_enabled: bool | None = None,
        owner_user_id: int | None = None,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            handle = record.worker
            is_running = handle is not None and self._runner.poll(handle) is None

        if is_running:
            await self.stop_feed(feed_id, owner_user_id=owner_user_id)

        return await self.start_feed(
            feed_id,
            log_level=log_level,
            webhook_enabled=webhook_enabled,
            owner_user_id=owner_user_id,
        )

    async def launch_feed_batch(
        self,
        *,
        feeds: list[BatchFeedDraft],
        launch_mode: BatchLaunchMode,
        log_level: LogLevel,
        webhook_enabled: bool,
        manager_user_id: int | None = None,
    ) -> BatchFeedLaunchResponse:
        results: list[BatchFeedLaunchItemResult] = []
        created_count = 0
        started_count = 0
        failed_count = 0

        for draft in feeds:
            try:
                created_feed = await self.create_feed(
                    name=draft.name,
                    source=draft.source,
                    manager_user_id=manager_user_id,
                    model_size=draft.model_size,
                    zone=draft.zone,
                    log_level=log_level,
                    webhook_enabled=webhook_enabled,
                    establishment_id=draft.establishment_id,
                    caisse_id=draft.caisse_id,
                    rtsp_username=draft.rtsp_username,
                    rtsp_password=draft.rtsp_password,
                    rtsp_transport=draft.rtsp_transport,
                )
                created_count += 1
            except Exception as exc:
                failed_count += 1
                results.append(
                    BatchFeedLaunchItemResult(
                        client_id=draft.client_id,
                        status="failed",
                        error=f"Failed to create feed: {exc}",
                    )
                )
                continue

            if launch_mode == "save_only":
                results.append(
                    BatchFeedLaunchItemResult(
                        client_id=draft.client_id,
                        status="created",
                        feed=created_feed,
                    )
                )
                continue

            try:
                started_feed = await self.start_feed(
                    created_feed.feed_id,
                    owner_user_id=manager_user_id,
                )
                if started_feed is None:
                    raise FeedStartError("Feed disappeared during batch start.")

                started_count += 1
                results.append(
                    BatchFeedLaunchItemResult(
                        client_id=draft.client_id,
                        status="started",
                        feed=started_feed,
                    )
                )
            except (FeedStartError, FeedStateError, RuntimeError) as exc:
                failed_count += 1
                current_feed = await self.get_feed(
                    created_feed.feed_id,
                    owner_user_id=manager_user_id,
                )
                results.append(
                    BatchFeedLaunchItemResult(
                        client_id=draft.client_id,
                        status="failed",
                        feed=current_feed,
                        error=str(exc),
                    )
                )

        return BatchFeedLaunchResponse(
            launch_mode=launch_mode,
            runtime=BatchRuntimeSettings(
                log_level=log_level,
                webhook_enabled=webhook_enabled,
            ),
            results=results,
            summary=BatchFeedLaunchSummary(
                total=len(feeds),
                created=created_count,
                started=started_count,
                failed=failed_count,
            ),
        )

    async def capture_feed_snapshot(
        self,
        feed_id: str,
        *,
        owner_user_id: int | None = None,
    ) -> FeedSnapshotResult | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return None

            source = record.source
            public_source = record.public_source()
            username = record.rtsp_username
            password = record.rtsp_password
            transport = record.rtsp_transport or "tcp"

        try:
            if source.lower().startswith("rtsp://"):
                ok, info = await asyncio.to_thread(
                    _capture_rtsp_source_snapshot,
                    source=source,
                    username=username,
                    password=password,
                    transport=transport,
                )
            else:
                ok, info = await asyncio.to_thread(_capture_video_source_snapshot, source)
        except RuntimeError as exc:
            return FeedSnapshotResult(
                feed_id=feed_id,
                source=public_source,
                captured=False,
                error=str(exc),
            )
        except Exception as exc:
            return FeedSnapshotResult(
                feed_id=feed_id,
                source=public_source,
                captured=False,
                error=f"Snapshot capture failed: {exc}",
            )

        image_data_url = None
        if ok and info.get("image_base64"):
            image_data_url = f"data:{info.get('mime_type', 'image/jpeg')};base64,{info['image_base64']}"

        return FeedSnapshotResult(
            feed_id=feed_id,
            source=public_source,
            captured=ok,
            resolution=info.get("resolution") if ok else None,
            width=info.get("width") if ok else None,
            height=info.get("height") if ok else None,
            image_data_url=image_data_url,
            error=info.get("error") if not ok else None,
        )

    async def resolve_feed_webrtc_source(
        self,
        feed_id: str,
        *,
        owner_user_id: int | None = None,
    ) -> tuple[
        Literal["ok", "not_found", "not_running", "not_ready"],
        str | None,
        str | None,
    ]:
        """Resolve a unified WebRTC published path for preview handshakes."""
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return "not_found", None, None
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return "not_found", None, None

            if record.status != "running":
                return "not_running", None, None

            published_path = record.published_webrtc_path
            published_ready = record.published_webrtc_ready
            published_reason = record.published_webrtc_reason

        if published_path and published_ready:
            return "ok", published_path, None

        return "not_ready", None, _normalize_publisher_reason(published_reason) or "publisher_not_ready"

    async def subscribe_feed_stream(
        self,
        feed_id: str,
        *,
        owner_user_id: int | None = None,
    ) -> Literal["ok", "not_found", "not_running"]:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return "not_found"
            if not self._is_record_visible_to_owner_scope(record, owner_user_id):
                return "not_found"

            if record.status not in {"running", "initializing"}:
                return "not_running"

            source = record.source
            username = record.rtsp_username
            password = record.rtsp_password
            transport: Literal["tcp", "udp"] = record.rtsp_transport or "tcp"

        await self._frame_streams.subscribe(
            feed_id=feed_id,
            source=source,
            username=username,
            password=password,
            transport=transport,
        )
        return "ok"

    async def unsubscribe_feed_stream(self, feed_id: str) -> None:
        await self._frame_streams.unsubscribe(feed_id)

    async def next_feed_stream_frame(
        self,
        feed_id: str,
        *,
        after_frame_index: int,
        timeout_seconds: float = 1.0,
    ) -> tuple[int, bytes] | None:
        return await self._frame_streams.wait_for_next_frame(
            feed_id,
            after_frame_index=after_frame_index,
            timeout_seconds=timeout_seconds,
        )

    async def clear(self) -> None:
        async with self._lock:
            feed_ids = list(self._feeds.keys())

        for feed_id in feed_ids:
            try:
                await self.stop_feed(feed_id)
            except FeedStateError:
                pass

        async with self._lock:
            self._feeds.clear()

        await self._frame_streams.clear()
        if self._frame_channel is not None:
            self._frame_channel.close()

    def _load_saved_zone(self, caisse_id: int | None) -> ZonePolygon | None:
        if caisse_id is None:
            return None

        caisse = get_caisse_by_id(caisse_id)
        if not caisse or not caisse.get("zone_points"):
            return None

        return coerce_zone_polygon(caisse["zone_points"])

    async def _persist_record(self, record: FeedRecord) -> None:
        """Persist the durable feed fields to SQLite."""
        payload = self._build_persistence_payload(record)
        await asyncio.to_thread(upsert_feed_config, **payload)

    def _persist_record_sync(self, record: FeedRecord) -> None:
        """Persist the durable feed fields to SQLite from sync startup paths."""
        upsert_feed_config(**self._build_persistence_payload(record))

    def _build_persistence_payload(self, record: FeedRecord) -> FeedPersistencePayload:
        """Build the durable feed payload stored in SQLite."""
        return {
            "feed_id": record.feed_id,
            "name": record.name,
            "source": record.source,
            "manager_user_id": record.manager_user_id,
            "model_size": record.model_size,
            "status": record.status,
            "log_level": record.log_level,
            "webhook_enabled": record.webhook_enabled,
            "queue_length_warning": record.queue_length_warning,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "rtsp_username": record.rtsp_username,
            "rtsp_password": record.rtsp_password,
            "rtsp_transport": record.rtsp_transport,
            "establishment_id": record.establishment_id,
            "caisse_id": record.caisse_id,
            "zone_points": serialize_zone_points(record.zone),
            "last_error": record.last_error,
        }

    def _load_persisted_feeds(self) -> None:
        """Restore configured feeds from SQLite and recover stale runtime state."""
        persisted_feeds = get_feed_configs()
        if not persisted_feeds:
            return

        end_open_video_sessions()
        recovered_at = utc_now()

        for persisted in persisted_feeds:
            original_status = persisted.get("status") or "created"
            status = original_status
            last_error = persisted.get("last_error")
            last_warning: str | None = None
            last_warning_code: str | None = None
            updated_at = coerce_datetime(persisted.get("updated_at"), fallback=recovered_at)

            if original_status in {"running", "initializing"}:
                status = "stopped"
                last_error = None
                updated_at = recovered_at

            record = FeedRecord(
                feed_id=str(persisted["feed_id"]),
                name=str(persisted["name"]),
                source=str(persisted["source"]),
                manager_user_id=int(persisted["manager_user_id"]) if persisted.get("manager_user_id") is not None else None,
                model_size=cast(ModelSize, persisted.get("model_size") or "n"),
                status=str(status),
                created_at=coerce_datetime(persisted.get("created_at"), fallback=recovered_at),
                updated_at=updated_at,
                log_level=cast(LogLevel, persisted.get("log_level") or "INFO"),
                webhook_enabled=bool(persisted.get("webhook_enabled", True)),
                queue_length_warning=int(persisted.get("queue_length_warning", 8)),
                rtsp_username=persisted.get("rtsp_username") if isinstance(persisted.get("rtsp_username"), str) else None,
                rtsp_password=persisted.get("rtsp_password") if isinstance(persisted.get("rtsp_password"), str) else None,
                rtsp_transport=persisted.get("rtsp_transport") if persisted.get("rtsp_transport") in {"tcp", "udp"} else None,
                establishment_id=int(persisted["establishment_id"]) if persisted.get("establishment_id") is not None else None,
                caisse_id=int(persisted["caisse_id"]) if persisted.get("caisse_id") is not None else None,
                zone=coerce_zone_polygon(persisted.get("zone_points")),
                last_error=str(last_error) if last_error else None,
                last_warning=last_warning,
                last_warning_code=last_warning_code,
            )
            self._feeds[record.feed_id] = record

            if original_status in {"running", "initializing"}:
                self._persist_record_sync(record)

    async def _mark_feed_error(self, feed_id: str, message: str) -> VideoFeed | None:
        self._clear_frame_channel_binding(feed_id)

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None

            record.status = "error"
            record.backend_annotations_active = False
            record.published_webrtc_path = None
            record.published_webrtc_ready = False
            record.published_webrtc_reason = None
            record.last_worker_frame_at_monotonic = None
            record.transport_end_to_end_latency_ms = None
            record.transport_metadata_video_skew_ms = None
            record.transport_dropped_frame_ratio = None
            record.transport_health_state = None
            record.transport_health_reason = None
            record.transport_compatibility_reason = None
            record.transport_pipeline_mode = None
            record.transport_skew_exceeded_since_monotonic = None
            record.transport_last_frame_seq = None
            record.transport_frames_seen = 0
            record.transport_frames_dropped = 0
            record.dashboard_frame_channel_host = None
            record.dashboard_frame_channel_port = None
            record.dashboard_frame_channel_token = None
            record.last_error = message
            record.last_warning = None
            record.last_warning_code = None
            record.updated_at = utc_now()
            model = record.to_model()

        await self._persist_record(record)

        await self._broadcaster.broadcast_feed_event(
            action="updated",
            feed=model,
            owner_user_id=record.manager_user_id,
        )
        return model

    async def _apply_metrics_update(self, feed_id: str, metrics: QueueMetricsModel) -> None:
        metrics_without_frame = metrics.model_copy(
            update={
                "render_frame_jpeg_base64": None,
            }
        )

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return

            owner_user_id = record.manager_user_id
            should_broadcast_feed_update = False

            now_monotonic = time.monotonic()
            backend_annotations_active = bool(
                record.last_worker_frame_at_monotonic is not None
                and (now_monotonic - record.last_worker_frame_at_monotonic) <= FRAME_CHANNEL_ACTIVITY_TIMEOUT_SEC
            )
            record.backend_annotations_active = backend_annotations_active
            metrics_without_frame = metrics_without_frame.model_copy(
                update={
                    "backend_annotations_active": backend_annotations_active,
                }
            )
            record.latest_metrics = metrics_without_frame.model_dump(mode="python")

            now_ms = time.time() * 1000.0
            end_to_end_latency_ms: float | None = None
            if metrics.server_emitted_at_ms is not None:
                end_to_end_latency_ms = max(0.0, now_ms - float(metrics.server_emitted_at_ms))

            metadata_video_skew_ms: float | None = None
            if metrics.pts_ms is not None:
                metadata_video_skew_ms = abs(now_ms - float(metrics.pts_ms))

            if metrics.frame_seq is not None:
                if record.transport_last_frame_seq is not None and metrics.frame_seq > record.transport_last_frame_seq:
                    dropped = max(0, metrics.frame_seq - record.transport_last_frame_seq - 1)
                    record.transport_frames_dropped += dropped
                record.transport_last_frame_seq = metrics.frame_seq
                record.transport_frames_seen += 1

            total_frames = record.transport_frames_seen + record.transport_frames_dropped
            dropped_frame_ratio: float | None = None
            if total_frames > 0:
                dropped_frame_ratio = record.transport_frames_dropped / total_frames

            previous_health_state = record.transport_health_state
            previous_health_reason = record.transport_health_reason
            next_health_state: Literal["ok", "warning", "error"] | None = None
            next_health_reason: str | None = None

            if metadata_video_skew_ms is not None:
                if metadata_video_skew_ms > TRANSPORT_SKEW_THRESHOLD_MS:
                    if record.transport_skew_exceeded_since_monotonic is None:
                        record.transport_skew_exceeded_since_monotonic = now_monotonic
                    exceed_duration_sec = now_monotonic - record.transport_skew_exceeded_since_monotonic
                    if exceed_duration_sec >= TRANSPORT_SKEW_ERROR_SEC:
                        next_health_state = "error"
                    elif exceed_duration_sec >= TRANSPORT_SKEW_WARNING_SEC:
                        next_health_state = "warning"
                    else:
                        next_health_state = "ok"
                    next_health_reason = (
                        f"metadata_video_skew_above_{int(TRANSPORT_SKEW_THRESHOLD_MS)}ms"
                        if next_health_state in {"warning", "error"}
                        else None
                    )
                else:
                    record.transport_skew_exceeded_since_monotonic = None
                    next_health_state = "ok"
                    next_health_reason = None

            record.transport_end_to_end_latency_ms = end_to_end_latency_ms
            record.transport_metadata_video_skew_ms = metadata_video_skew_ms
            record.transport_dropped_frame_ratio = dropped_frame_ratio
            record.transport_health_state = next_health_state
            record.transport_health_reason = next_health_reason

            if previous_health_state != next_health_state or previous_health_reason != next_health_reason:
                record.updated_at = utc_now()
                should_broadcast_feed_update = True
                model = record.to_model()

        await self._broadcaster.broadcast_metrics_event(
            feed_id=feed_id,
            metrics=metrics_without_frame,
            owner_user_id=owner_user_id,
        )

        if should_broadcast_feed_update:
            await self._persist_record(record)
            await self._broadcaster.broadcast_feed_event(
                action="updated",
                feed=model,
                owner_user_id=owner_user_id,
            )

    async def _apply_alert_fired(self, feed_id: str, alert: AlertModel) -> None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            owner_user_id = record.manager_user_id if record is not None else None

        await self._broadcaster.broadcast_alert_event(
            feed_id=feed_id,
            alert=alert,
            owner_user_id=owner_user_id,
        )

    async def _apply_system_warning(
        self,
        feed_id: str,
        *,
        code: str,
        message: str,
        timestamp: datetime,
    ) -> None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            owner_user_id = record.manager_user_id if record is not None else None
            if record is not None:
                record.last_warning = message
                record.last_warning_code = code

        await self._broadcaster.broadcast_system_warning(
            feed_id=feed_id,
            code=code,
            message=message,
            timestamp=timestamp,
            owner_user_id=owner_user_id,
        )

    async def _apply_transport_status(
        self,
        feed_id: str,
        *,
        published_webrtc_ready: bool | None = None,
        published_webrtc_path: str | None = None,
        reason: str | None = None,
        compatibility_reason: str | None = None,
        pipeline_mode: str | None = None,
        performance: dict[str, Any] | None = None,
    ) -> None:
        should_broadcast = False
        model: VideoFeed | None = None
        owner_user_id: int | None = None

        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return

            owner_user_id = record.manager_user_id

            if published_webrtc_path is not None and record.published_webrtc_path != published_webrtc_path:
                record.published_webrtc_path = published_webrtc_path
                should_broadcast = True

            if published_webrtc_ready is not None and record.published_webrtc_ready != published_webrtc_ready:
                record.published_webrtc_ready = published_webrtc_ready
                should_broadcast = True

            normalized_reason = _normalize_publisher_reason(reason)
            if normalized_reason is not None and record.published_webrtc_reason != normalized_reason:
                record.published_webrtc_reason = normalized_reason
                should_broadcast = True
            elif published_webrtc_ready is True and normalized_reason is None and record.published_webrtc_reason is not None:
                record.published_webrtc_reason = None
                should_broadcast = True

            normalized_compatibility_reason = (
                compatibility_reason.strip().lower()
                if isinstance(compatibility_reason, str) and compatibility_reason.strip()
                else None
            )
            if record.transport_compatibility_reason != normalized_compatibility_reason:
                record.transport_compatibility_reason = normalized_compatibility_reason
                should_broadcast = True

            normalized_pipeline_mode = (
                pipeline_mode.strip().lower()
                if isinstance(pipeline_mode, str) and pipeline_mode.strip()
                else None
            )
            if record.transport_pipeline_mode != normalized_pipeline_mode:
                record.transport_pipeline_mode = normalized_pipeline_mode
                should_broadcast = True

            if performance:
                LOGGER.info("feed %s transport perf: %s", feed_id, json.dumps(performance, sort_keys=True))

            if should_broadcast:
                record.updated_at = utc_now()
                model = record.to_model()

        if should_broadcast and model is not None:
            await self._persist_record(record)
            await self._broadcaster.broadcast_feed_event(
                action="updated",
                feed=model,
                owner_user_id=owner_user_id,
            )

    async def _drain_worker_events(self, feed_id: str, handle: FeedWorkerHandle) -> None:
        events = self._read_worker_events(handle)
        if not events:
            return

        latest_metrics_event: dict[str, Any] | None = None
        for event in events:
            event_type = event.get("event")
            if event_type == "metrics_update":
                latest_metrics_event = event
                continue
            await self._dispatch_worker_event(feed_id, event)

        if latest_metrics_event is not None:
            await self._dispatch_worker_event(feed_id, latest_metrics_event)

    def _read_worker_events(self, handle: FeedWorkerHandle) -> list[dict[str, Any]]:
        if handle.event_path is None or not handle.event_path.exists():
            return []

        try:
            with handle.event_path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(handle.event_cursor)
                chunk = stream.read()
                handle.event_cursor = stream.tell()
        except OSError:
            return []

        if not chunk:
            return []

        text = f"{handle.event_buffer}{chunk}"
        handle.event_buffer = ""

        records: list[dict[str, Any]] = []
        for line in text.splitlines(keepends=True):
            if not line.endswith(("\n", "\r")):
                handle.event_buffer = line
                continue

            stripped = line.strip()
            if not stripped:
                continue

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, dict):
                records.append(parsed)

        return records

    async def _dispatch_worker_event(self, feed_id: str, event: dict[str, Any]) -> None:
        event_type = event.get("event")
        payload = event.get("payload")
        if not isinstance(event_type, str) or not isinstance(payload, dict):
            return

        if event_type == "metrics_update":
            metrics_payload = payload.get("metrics")
            if not isinstance(metrics_payload, dict):
                return
            metrics = QueueMetricsModel.model_validate(metrics_payload)
            await self._apply_metrics_update(feed_id, metrics)
            return

        if event_type == "alert_fired":
            alert_payload = payload.get("alert")
            if not isinstance(alert_payload, dict):
                return
            alert = AlertModel.model_validate(alert_payload)
            await self._apply_alert_fired(feed_id, alert)
            return

        if event_type == "system_warning":
            code = payload.get("code")
            message = payload.get("message")
            timestamp = payload.get("timestamp")
            if not isinstance(code, str) or not isinstance(message, str):
                return
            await self._apply_system_warning(
                feed_id,
                code=code,
                message=message,
                timestamp=coerce_datetime(timestamp),
            )
            return

        if event_type == "transport_status":
            ready_value = payload.get("published_webrtc_ready")
            if ready_value is None:
                ready_value = payload.get("annotated_webrtc_ready")
            path_value = payload.get("published_webrtc_path")
            if path_value is None:
                path_value = payload.get("annotated_webrtc_path")
            reason_value = payload.get("reason")
            compatibility_reason_value = payload.get("compatibility_reason")
            pipeline_mode_value = payload.get("pipeline_mode")
            performance_value = payload.get("performance")
            ready = ready_value if isinstance(ready_value, bool) else None
            path = path_value if isinstance(path_value, str) else None
            reason = reason_value if isinstance(reason_value, str) else None
            compatibility_reason = (
                compatibility_reason_value
                if isinstance(compatibility_reason_value, str)
                else None
            )
            pipeline_mode = (
                pipeline_mode_value
                if isinstance(pipeline_mode_value, str)
                else None
            )
            performance = performance_value if isinstance(performance_value, dict) else None
            await self._apply_transport_status(
                feed_id,
                published_webrtc_ready=ready,
                published_webrtc_path=path,
                reason=reason,
                compatibility_reason=compatibility_reason,
                pipeline_mode=pipeline_mode,
                performance=performance,
            )

    async def _monitor_feed(self, feed_id: str, handle: FeedWorkerHandle) -> None:
        while True:
            await self._drain_worker_events(feed_id, handle)
            exit_code = await asyncio.to_thread(self._runner.poll, handle)
            if exit_code is None:
                await asyncio.sleep(DASHBOARD_EVENT_POLL_INTERVAL_SEC)
                continue

            await self._drain_worker_events(feed_id, handle)

            await asyncio.to_thread(self._runner.close, handle)

            async with self._lock:
                record = self._feeds.get(feed_id)
                if record is None or record.worker is not handle:
                    return

                record.worker = None
                session_id = record.session_id
                record.session_id = None
                record.updated_at = utc_now()

                if exit_code == 0:
                    record.status = "stopped"
                    record.last_error = None
                else:
                    record.status = "error"
                    record.last_error = self._runner.exit_details(handle, exit_code)

                record.backend_annotations_active = False
                record.published_webrtc_path = None
                record.published_webrtc_ready = False
                record.published_webrtc_reason = None
                record.last_worker_frame_at_monotonic = None
                record.transport_end_to_end_latency_ms = None
                record.transport_metadata_video_skew_ms = None
                record.transport_dropped_frame_ratio = None
                record.transport_health_state = None
                record.transport_health_reason = None
                record.transport_compatibility_reason = None
                record.transport_pipeline_mode = None
                record.transport_skew_exceeded_since_monotonic = None
                record.transport_last_frame_seq = None
                record.transport_frames_seen = 0
                record.transport_frames_dropped = 0
                record.dashboard_frame_channel_host = None
                record.dashboard_frame_channel_port = None
                record.dashboard_frame_channel_token = None

                model = record.to_model()

            await self._persist_record(record)

            if session_id is not None:
                await asyncio.to_thread(end_video_session, session_id)

            self._clear_frame_channel_binding(feed_id)
            await self._frame_streams.terminate(feed_id)

            await self._broadcaster.broadcast_feed_event(
                action="updated",
                feed=model,
                owner_user_id=record.manager_user_id,
            )
            return

