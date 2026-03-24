"""In-memory runtime services for the FastAPI backend-for-frontend layer."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol, TextIO, TypedDict, cast
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

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


BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = (BACKEND_DIR / "data" / "uploads").resolve()
RUNTIME_LOG_DIR = (BACKEND_DIR / "data" / "runtime").resolve()
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_RESIZE_SCALE = 0.5
class FeedStateError(RuntimeError):
    """Raised when a feed operation is invalid for the current lifecycle state."""


class FeedStartError(RuntimeError):
    """Raised when the runtime cannot launch a worker for a feed."""


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


def _resolve_source_dimensions(source: str) -> tuple[int, int]:
    """Open the source long enough to resolve frame dimensions for zone conversion."""
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise FeedStartError(
            "OpenCV is required to convert normalized zones into worker pixel coordinates."
        ) from exc

    capture_source: str | int = int(source) if source.isdigit() else source
    capture = cv2.VideoCapture(capture_source)

    if not capture.isOpened():
        raise FeedStartError(
            f"Unable to open source '{source}' to resolve zone coordinates."
        )

    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if width > 0 and height > 0:
            return width, height

        ok, frame = capture.read()
        if not ok or frame is None:
            raise FeedStartError(
                f"Unable to read a frame from source '{source}' to resolve zone coordinates."
            )

        frame_height, frame_width = frame.shape[:2]
        return frame_width, frame_height
    finally:
        capture.release()


def denormalize_zone_points(source: str, zone: ZonePolygon) -> list[list[int]]:
    """Convert normalized zone points into the pixel coordinates expected by src.main."""
    frame_width, frame_height = _resolve_source_dimensions(source)
    max_x = max(frame_width - 1, 0)
    max_y = max(frame_height - 1, 0)

    points: list[list[int]] = []
    for point in zone.points:
        pixel_x = min(max(int(round(point.x * frame_width)), 0), max_x)
        pixel_y = min(max(int(round(point.y * frame_height)), 0), max_y)
        points.append([pixel_x, pixel_y])

    return points


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
            "--log-level",
            record.log_level or DEFAULT_LOG_LEVEL,
            "--resize-scale",
            str(DEFAULT_RESIZE_SCALE),
            "--events-file",
            str(event_path),
            "--headless",
        ]

        if record.zone is not None:
            command.extend(
                ["--zone-points", json.dumps(denormalize_zone_points(record.source, record.zone))]
            )

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
    last_error: str | None = None
    last_warning: str | None = None
    last_warning_code: str | None = None
    worker: FeedWorkerHandle | None = field(default=None, repr=False)
    session_id: int | None = None

    def public_source(self) -> str:
        """Return a frontend-safe source string without embedded credentials."""
        return sanitize_source(self.source)

    def to_model(self) -> VideoFeed:
        """Convert the internal dataclass into the public API model."""
        return VideoFeed.model_validate(
            {
                **self.__dict__,
                "source": self.public_source(),
                "preview_path": build_preview_path(self.source),
            }
        )


class WebSocketHub:
    """Tracks connected websocket clients and broadcasts JSON events."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        async with self._lock:
            clients = list(self._clients)

        stale_clients: list[WebSocket] = []
        for websocket in clients:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale_clients.append(websocket)
            except WebSocketDisconnect:
                stale_clients.append(websocket)

        if stale_clients:
            async with self._lock:
                for websocket in stale_clients:
                    self._clients.discard(websocket)

    async def broadcast_feed_event(
        self,
        *,
        action: Literal["created", "updated", "deleted"],
        feed: VideoFeed | None = None,
        feed_id: str | None = None,
    ) -> None:
        event = FeedStatusEvent(
            payload=FeedStatusEventPayload(action=action, feed=feed, feed_id=feed_id),
        )
        await self.broadcast(event.model_dump(mode="json"))

    async def broadcast_metrics_event(self, *, feed_id: str, metrics: QueueMetricsModel) -> None:
        event = MetricsUpdateEvent(payload=MetricsUpdateEventPayload(feed_id=feed_id, metrics=metrics))
        await self.broadcast(event.model_dump(mode="json"))

    async def broadcast_alert_event(self, *, feed_id: str, alert: AlertModel) -> None:
        event = AlertFiredEvent(payload=AlertFiredEventPayload(feed_id=feed_id, alert=alert))
        await self.broadcast(event.model_dump(mode="json"))

    async def broadcast_system_warning(
        self,
        *,
        feed_id: str,
        code: str,
        message: str,
        timestamp: datetime,
    ) -> None:
        event = SystemWarningEvent(
            payload=SystemWarningEventPayload(
                feed_id=feed_id,
                code=code,
                message=message,
                timestamp=timestamp,
            )
        )
        await self.broadcast(event.model_dump(mode="json"))

    @property
    def client_count(self) -> int:
        return len(self._clients)


class FeedRegistry:
    """Stores configured feeds and exposes async-safe CRUD operations."""

    def __init__(self, broadcaster: WebSocketHub, runner: FeedWorkerRunner | None = None) -> None:
        self._broadcaster = broadcaster
        self._runner = runner or SubprocessFeedWorkerRunner()
        self._feeds: dict[str, FeedRecord] = {}
        self._lock = asyncio.Lock()
        self._load_persisted_feeds()

    async def list_feeds(self) -> list[VideoFeed]:
        async with self._lock:
            records = sorted(self._feeds.values(), key=lambda item: item.created_at)
            return [record.to_model() for record in records]

    async def get_feed(self, feed_id: str) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            return record.to_model() if record else None

    async def create_feed(
        self,
        *,
        name: str,
        source: str,
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

        await self._broadcaster.broadcast_feed_event(action="created", feed=model)
        return model

    async def delete_feed(self, feed_id: str) -> bool:
        async with self._lock:
            record = self._feeds.get(feed_id)

        if record is None:
            return False

        if record.worker is not None and self._runner.poll(record.worker) is None:
            await self.stop_feed(feed_id)

        async with self._lock:
            removed = self._feeds.pop(feed_id, None)

        if removed is None:
            return False

        await asyncio.to_thread(delete_feed_config, feed_id)

        await self._broadcaster.broadcast_feed_event(action="deleted", feed_id=feed_id)
        return True

    async def update_zone(self, feed_id: str, zone: ZonePolygon) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
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

        await self._broadcaster.broadcast_feed_event(action="updated", feed=model)
        return model

    async def update_thresholds(
        self,
        feed_id: str,
        *,
        queue_length_warning: int,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None

            record.queue_length_warning = queue_length_warning
            record.updated_at = utc_now()
            model = record.to_model()
            should_restart = record.worker is not None and self._runner.poll(record.worker) is None

        await self._persist_record(record)

        if should_restart:
            await self.restart_feed(feed_id)
            return await self.get_feed(feed_id)

        await self._broadcaster.broadcast_feed_event(action="updated", feed=model)
        return model

    async def start_feed(
        self,
        feed_id: str,
        *,
        log_level: LogLevel | None = None,
        webhook_enabled: bool | None = None,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
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
            record.last_error = None
            record.last_warning = None
            record.last_warning_code = None
            record.updated_at = utc_now()
            initializing_model = record.to_model()

        await self._persist_record(record)

        await self._broadcaster.broadcast_feed_event(action="updated", feed=initializing_model)

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
            await self._mark_feed_error(feed_id, str(exc))
            raise
        except Exception as exc:
            if handle is not None:
                await asyncio.to_thread(self._runner.stop, handle)
                await asyncio.to_thread(self._runner.close, handle)
            message = f"Failed to launch feed worker: {exc}"
            await self._mark_feed_error(feed_id, message)
            raise FeedStartError(message) from exc

        async with self._lock:
            current = self._feeds.get(feed_id)
            if current is None:
                await asyncio.to_thread(self._runner.stop, handle)
                await asyncio.to_thread(self._runner.close, handle)
                await asyncio.to_thread(end_video_session, session_id)
                return None

            current.worker = handle
            current.session_id = session_id
            current.status = "running"
            current.updated_at = utc_now()
            running_model = current.to_model()

        await self._persist_record(current)

        asyncio.create_task(self._monitor_feed(feed_id, handle))
        await self._broadcaster.broadcast_feed_event(action="updated", feed=running_model)
        return running_model

    async def stop_feed(self, feed_id: str) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
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
        except Exception as exc:
            message = f"Failed to stop feed worker: {exc}"
            await self._mark_feed_error(feed_id, message)
            raise RuntimeError(message) from exc

        async with self._lock:
            current = self._feeds.get(feed_id)
            if current is None:
                return None

            current.status = "stopped"
            current.last_error = None
            current.updated_at = utc_now()
            stopped_model = current.to_model()

        await self._persist_record(current)

        await self._broadcaster.broadcast_feed_event(action="updated", feed=stopped_model)
        return stopped_model

    async def restart_feed(
        self,
        feed_id: str,
        *,
        log_level: LogLevel | None = None,
        webhook_enabled: bool | None = None,
    ) -> VideoFeed | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None

            handle = record.worker
            is_running = handle is not None and self._runner.poll(handle) is None

        if is_running:
            await self.stop_feed(feed_id)

        return await self.start_feed(
            feed_id,
            log_level=log_level,
            webhook_enabled=webhook_enabled,
        )

    async def launch_feed_batch(
        self,
        *,
        feeds: list[BatchFeedDraft],
        launch_mode: BatchLaunchMode,
        log_level: LogLevel,
        webhook_enabled: bool,
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
                started_feed = await self.start_feed(created_feed.feed_id)
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
                current_feed = await self.get_feed(created_feed.feed_id)
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

    async def capture_feed_snapshot(self, feed_id: str) -> FeedSnapshotResult | None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
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
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return None

            record.status = "error"
            record.last_error = message
            record.last_warning = None
            record.last_warning_code = None
            record.updated_at = utc_now()
            model = record.to_model()

        await self._persist_record(record)

        await self._broadcaster.broadcast_feed_event(action="updated", feed=model)
        return model

    async def _apply_metrics_update(self, feed_id: str, metrics: QueueMetricsModel) -> None:
        async with self._lock:
            record = self._feeds.get(feed_id)
            if record is None:
                return

            record.latest_metrics = metrics.model_dump(mode="python")

        await self._broadcaster.broadcast_metrics_event(feed_id=feed_id, metrics=metrics)

    async def _apply_alert_fired(self, feed_id: str, alert: AlertModel) -> None:
        await self._broadcaster.broadcast_alert_event(feed_id=feed_id, alert=alert)

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
            if record is not None:
                record.last_warning = message
                record.last_warning_code = code

        await self._broadcaster.broadcast_system_warning(
            feed_id=feed_id,
            code=code,
            message=message,
            timestamp=timestamp,
        )

    async def _drain_worker_events(self, feed_id: str, handle: FeedWorkerHandle) -> None:
        for event in self._read_worker_events(handle):
            await self._dispatch_worker_event(feed_id, event)

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

    async def _monitor_feed(self, feed_id: str, handle: FeedWorkerHandle) -> None:
        while True:
            await self._drain_worker_events(feed_id, handle)
            exit_code = await asyncio.to_thread(self._runner.poll, handle)
            if exit_code is None:
                await asyncio.sleep(0.25)
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

                model = record.to_model()

            await self._persist_record(record)

            if session_id is not None:
                await asyncio.to_thread(end_video_session, session_id)

            await self._broadcaster.broadcast_feed_event(action="updated", feed=model)
            return