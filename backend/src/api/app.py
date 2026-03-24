"""FastAPI application for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

import asyncio
import mimetypes
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src import __version__
from src.api.models import (
    ApiResponse,
    BatchFeedLaunchRequest,
    BatchFeedLaunchResponse,
    Caisse,
    CreateFeedRequest,
    CreateCaisseRequest,
    CreateEstablishmentRequest,
    Establishment,
    FeedSnapshotResult,
    FeedSnapshotEvent,
    ONVIFCameraTestRequest,
    ONVIFCameraTestResult,
    ONVIFDevice,
    ONVIFDiscoveryRequest,
    ONVIFStream,
    ONVIFStreamResolutionRequest,
    RTSPConnectionTestRequest,
    RTSPConnectionTestResult,
    RTSPSnapshotRequest,
    RTSPSnapshotResult,
    SystemHealth,
    UploadVideoResponse,
    VideoFeed,
    ZoneUpdateRequest,
    coerce_zone_polygon,
)
from src.api.runtime import FeedRegistry, FeedStartError, FeedStateError, WebSocketHub
from src.database import (
    create_caisse,
    create_establishment,
    get_caisse_by_id,
    get_caisses_by_establishment,
    get_establishment_by_id,
    get_establishments,
    init_db,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def build_upload_preview_path(file_path: Path) -> str:
    """Return the frontend-consumable API path for an uploaded video."""
    return f"/api/uploads/files/{file_path.name}"


def run_rtsp_connection_test(
    *,
    url: str,
    username: str | None,
    password: str | None,
    transport: str,
) -> tuple[bool, dict]:
    """Delegate RTSP probing to the backend camera utility with lazy imports."""
    try:
        from src.rtsp_camera import RTSPCamera
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RTSP support is unavailable because required video dependencies are not installed."
        ) from exc

    return RTSPCamera.test_connection(
        url,
        username=username,
        password=password,
        transport=transport,
    )


def run_rtsp_snapshot_capture(
    *,
    url: str,
    username: str | None,
    password: str | None,
    transport: str,
) -> tuple[bool, dict]:
    """Delegate RTSP snapshot capture to the backend camera utility with lazy imports."""
    try:
        from src.rtsp_camera import RTSPCamera
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "RTSP snapshot capture is unavailable because required video dependencies are not installed."
        ) from exc

    return RTSPCamera.capture_snapshot(
        url,
        username=username,
        password=password,
        transport=transport,
    )


def run_onvif_discovery(*, timeout_seconds: float) -> list[dict]:
    """Delegate ONVIF discovery to the backend camera utility with lazy imports."""
    try:
        from src.onvif_client import discover_onvif_devices
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ONVIF discovery is unavailable because required video dependencies are not installed."
        ) from exc

    return discover_onvif_devices(timeout_seconds)


def run_onvif_stream_resolution(
    *,
    device: dict,
    username: str | None,
    password: str | None,
) -> list[str]:
    """Resolve RTSP stream URLs for a discovered ONVIF device with lazy imports."""
    try:
        from src.onvif_client import get_rtsp_urls_from_onvif_device
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "ONVIF stream resolution is unavailable because required video dependencies are not installed."
        ) from exc

    return get_rtsp_urls_from_onvif_device(device, username=username, password=password)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize runtime services when the API starts."""
    init_db()
    broadcaster = WebSocketHub()
    registry = FeedRegistry(broadcaster=broadcaster)
    app.state.broadcaster = broadcaster
    app.state.registry = registry
    try:
        yield
    finally:
        await registry.clear()


app = FastAPI(
    title="QueueVision BFF",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_registry() -> FeedRegistry:
    """Typed accessor for the feed registry stored in app state."""
    registry = getattr(app.state, "registry", None)
    broadcaster = getattr(app.state, "broadcaster", None)

    if registry is None or broadcaster is None:
        init_db()
        broadcaster = WebSocketHub()
        registry = FeedRegistry(broadcaster=broadcaster)
        app.state.broadcaster = broadcaster
        app.state.registry = registry

    return registry


def get_broadcaster() -> WebSocketHub:
    """Typed accessor for the websocket broadcaster stored in app state."""
    broadcaster = getattr(app.state, "broadcaster", None)
    if broadcaster is None:
        _ = get_registry()
        broadcaster = app.state.broadcaster
    return broadcaster


def build_establishment_model(record: dict) -> Establishment:
    """Convert a raw establishment row into the public API model."""
    return Establishment.model_validate(record)


def build_caisse_model(record: dict) -> Caisse:
    """Convert a raw caisse row into the public API model."""
    payload = dict(record)
    payload["zone"] = coerce_zone_polygon(payload.pop("zone_points", None))
    payload.pop("zone_points_json", None)
    return Caisse.model_validate(payload)


def build_onvif_device_model(record: dict) -> ONVIFDevice:
    """Convert a raw ONVIF discovery payload into the public API model."""
    payload = dict(record)
    payload["services"] = dict(payload.get("services") or {})
    return ONVIFDevice.model_validate(payload)


def strip_url_credentials(url: str) -> str:
    """Remove embedded credentials from a URL before returning it to the frontend."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        return url

    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return urlunparse(parsed._replace(netloc=netloc))


def build_onvif_stream_models(urls: list[str]) -> list[ONVIFStream]:
    """Convert raw RTSP URLs into sanitized frontend-facing stream candidates."""
    unique_urls: list[str] = []
    seen: set[str] = set()

    for url in urls:
        sanitized = strip_url_credentials(url)
        if sanitized in seen:
            continue
        seen.add(sanitized)
        unique_urls.append(sanitized)

    return [ONVIFStream(url=url) for url in unique_urls]


def build_onvif_camera_test_result(
    *,
    streams: list[str],
    connected: bool,
    transport: str,
    info: dict | None = None,
    error: str | None = None,
) -> ONVIFCameraTestResult:
    """Build a frontend-facing ONVIF camera test result."""
    stream_models = build_onvif_stream_models(streams)
    tested_stream = stream_models[0] if stream_models else None
    info = info or {}

    return ONVIFCameraTestResult(
        connected=connected,
        transport=info.get("transport", transport),
        stream_count=len(stream_models),
        tested_stream=tested_stream,
        streams=stream_models,
        resolution=info.get("resolution") if connected else None,
        width=info.get("width") if connected else None,
        height=info.get("height") if connected else None,
        fps=info.get("fps") if connected else None,
        error=error if not connected else None,
    )


@app.post("/api/sources/rtsp/test", response_model=ApiResponse[RTSPConnectionTestResult])
async def test_rtsp_source(
    request: RTSPConnectionTestRequest,
) -> ApiResponse[RTSPConnectionTestResult]:
    try:
        ok, info = await asyncio.to_thread(
            run_rtsp_connection_test,
            url=request.url,
            username=request.username,
            password=request.password,
            transport=request.transport,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RTSP connection test failed: {exc}") from exc

    result = RTSPConnectionTestResult(
        connected=ok,
        transport=info.get("transport", request.transport),
        resolution=info.get("resolution") if ok else None,
        width=info.get("width") if ok else None,
        height=info.get("height") if ok else None,
        fps=info.get("fps") if ok else None,
        error=info.get("error") if not ok else None,
    )

    return ApiResponse(
        data=result,
        message="RTSP connection successful." if ok else "RTSP connection failed.",
    )


@app.post("/api/sources/rtsp/snapshot", response_model=ApiResponse[RTSPSnapshotResult])
async def capture_rtsp_snapshot(
    request: RTSPSnapshotRequest,
) -> ApiResponse[RTSPSnapshotResult]:
    try:
        ok, info = await asyncio.to_thread(
            run_rtsp_snapshot_capture,
            url=request.url,
            username=request.username,
            password=request.password,
            transport=request.transport,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RTSP snapshot capture failed: {exc}") from exc

    image_data_url = None
    if ok and info.get("image_base64"):
        image_data_url = f"data:{info.get('mime_type', 'image/jpeg')};base64,{info['image_base64']}"

    result = RTSPSnapshotResult(
        captured=ok,
        transport=info.get("transport", request.transport),
        resolution=info.get("resolution") if ok else None,
        width=info.get("width") if ok else None,
        height=info.get("height") if ok else None,
        image_data_url=image_data_url,
        error=info.get("error") if not ok else None,
    )

    return ApiResponse(
        data=result,
        message="RTSP snapshot captured successfully." if ok else "RTSP snapshot capture failed.",
    )


@app.post("/api/sources/onvif/discover", response_model=ApiResponse[list[ONVIFDevice]])
async def discover_onvif_devices(
    request: ONVIFDiscoveryRequest,
) -> ApiResponse[list[ONVIFDevice]]:
    try:
        devices = await asyncio.to_thread(
            run_onvif_discovery,
            timeout_seconds=request.timeout_seconds,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ONVIF discovery failed: {exc}") from exc

    models = [build_onvif_device_model(device) for device in devices]
    message = "ONVIF discovery completed." if models else "No ONVIF devices found."
    return ApiResponse(data=models, message=message)


@app.post("/api/sources/onvif/streams", response_model=ApiResponse[list[ONVIFStream]])
async def resolve_onvif_streams(
    request: ONVIFStreamResolutionRequest,
) -> ApiResponse[list[ONVIFStream]]:
    try:
        urls = await asyncio.to_thread(
            run_onvif_stream_resolution,
            device=request.device.model_dump(mode="python"),
            username=request.username,
            password=request.password,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ONVIF stream resolution failed: {exc}") from exc

    models = build_onvif_stream_models(urls)
    message = "ONVIF streams resolved successfully." if models else "No RTSP streams found for this device."
    return ApiResponse(data=models, message=message)


@app.post("/api/sources/onvif/test", response_model=ApiResponse[ONVIFCameraTestResult])
async def test_onvif_camera(
    request: ONVIFCameraTestRequest,
) -> ApiResponse[ONVIFCameraTestResult]:
    try:
        urls = await asyncio.to_thread(
            run_onvif_stream_resolution,
            device=request.device.model_dump(mode="python"),
            username=request.username,
            password=request.password,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ONVIF stream resolution failed: {exc}") from exc

    if not urls:
        result = build_onvif_camera_test_result(
            streams=[],
            connected=False,
            transport=request.transport,
            error="No RTSP streams found",
        )
        return ApiResponse(data=result, message="ONVIF camera test failed.")

    try:
        ok, info = await asyncio.to_thread(
            run_rtsp_connection_test,
            url=urls[0],
            username=request.username,
            password=request.password,
            transport=request.transport,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ONVIF camera test failed: {exc}") from exc

    result = build_onvif_camera_test_result(
        streams=urls,
        connected=ok,
        transport=request.transport,
        info=info,
        error=info.get("error") if not ok else None,
    )
    return ApiResponse(
        data=result,
        message="ONVIF camera test successful." if ok else "ONVIF camera test failed.",
    )


@app.get("/api/establishments", response_model=ApiResponse[list[Establishment]])
async def list_establishments() -> ApiResponse[list[Establishment]]:
    records = await asyncio.to_thread(get_establishments)
    return ApiResponse(data=[build_establishment_model(record) for record in records])


@app.post("/api/establishments", response_model=ApiResponse[Establishment], status_code=201)
async def create_establishment_endpoint(
    request: CreateEstablishmentRequest,
) -> ApiResponse[Establishment]:
    try:
        establishment_id = await asyncio.to_thread(create_establishment, request.name)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Establishment already exists.") from exc

    record = await asyncio.to_thread(get_establishment_by_id, establishment_id)
    if record is None:
        raise HTTPException(status_code=500, detail="Created establishment could not be loaded.")

    return ApiResponse(
        data=build_establishment_model(record),
        message="Establishment created successfully.",
    )


@app.get("/api/establishments/{establishment_id}/caisses", response_model=ApiResponse[list[Caisse]])
async def list_caisses(establishment_id: int) -> ApiResponse[list[Caisse]]:
    establishment = await asyncio.to_thread(get_establishment_by_id, establishment_id)
    if establishment is None:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    records = await asyncio.to_thread(get_caisses_by_establishment, establishment_id)
    return ApiResponse(data=[build_caisse_model(record) for record in records])


@app.post("/api/establishments/{establishment_id}/caisses", response_model=ApiResponse[Caisse], status_code=201)
async def create_caisse_endpoint(
    establishment_id: int,
    request: CreateCaisseRequest,
) -> ApiResponse[Caisse]:
    establishment = await asyncio.to_thread(get_establishment_by_id, establishment_id)
    if establishment is None:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    zone_points = None
    if request.zone is not None:
        zone_points = [[point.x, point.y] for point in request.zone.points]

    try:
        caisse_id = await asyncio.to_thread(create_caisse, request.name, establishment_id, zone_points)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Caisse already exists for this establishment.",
        ) from exc

    record = await asyncio.to_thread(get_caisse_by_id, caisse_id)
    if record is None:
        raise HTTPException(status_code=500, detail="Created caisse could not be loaded.")

    return ApiResponse(
        data=build_caisse_model(record),
        message="Caisse created successfully.",
    )


@app.post("/api/upload", response_model=ApiResponse[UploadVideoResponse], status_code=201)
@app.post("/api/uploads/video", response_model=ApiResponse[UploadVideoResponse], status_code=201)
async def upload_video_file(file: UploadFile = File(...)) -> ApiResponse[UploadVideoResponse]:
    """Upload a video file and return a backend-readable source path."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was provided.")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported video type. Allowed extensions: .avi, .mkv, .mov, .mp4.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    source_name = Path(file.filename).stem.strip() or "video"
    destination = UPLOAD_DIR / f"{source_name}-{uuid4().hex[:8]}{file_ext}"

    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded video.") from exc
    finally:
        await file.close()

    return ApiResponse(
        data=UploadVideoResponse(
            file_name=file.filename,
            file_path=str(destination.resolve()),
            preview_path=build_upload_preview_path(destination),
        ),
        message="Video uploaded successfully.",
    )


@app.get("/api/uploads/files/{file_name}")
async def serve_uploaded_video(file_name: str) -> FileResponse:
    candidate = (UPLOAD_DIR / Path(file_name).name).resolve()

    try:
        candidate.relative_to(UPLOAD_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid upload path.") from exc

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Uploaded video not found.")

    media_type, _ = mimetypes.guess_type(candidate.name)
    return FileResponse(candidate, media_type=media_type or "application/octet-stream")


@app.get("/api/feeds", response_model=ApiResponse[list[VideoFeed]])
async def list_feeds() -> ApiResponse[list[VideoFeed]]:
    feeds = await get_registry().list_feeds()
    return ApiResponse(data=feeds)


@app.post("/api/feeds", response_model=ApiResponse[VideoFeed], status_code=201)
async def create_feed(request: CreateFeedRequest) -> ApiResponse[VideoFeed]:
    feed = await get_registry().create_feed(
        name=request.name,
        source=request.source,
        model_size=request.model_size,
        establishment_id=request.establishment_id,
        caisse_id=request.caisse_id,
        rtsp_username=request.rtsp_username,
        rtsp_password=request.rtsp_password,
        rtsp_transport=request.rtsp_transport,
    )
    return ApiResponse(data=feed, message="Feed registered successfully.")


@app.post("/api/feeds/batch-launch", response_model=ApiResponse[BatchFeedLaunchResponse])
async def batch_launch_feeds(request: BatchFeedLaunchRequest) -> ApiResponse[BatchFeedLaunchResponse]:
    result = await get_registry().launch_feed_batch(
        feeds=request.feeds,
        launch_mode=request.launch_mode,
        log_level=request.runtime.log_level,
        webhook_enabled=request.runtime.webhook_enabled,
    )
    return ApiResponse(data=result, message="Batch feed launch processed.")


@app.get("/api/feeds/{feed_id}/status", response_model=ApiResponse[VideoFeed])
async def get_feed_status(feed_id: str) -> ApiResponse[VideoFeed]:
    feed = await get_registry().get_feed(feed_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed)


@app.get("/api/feeds/{feed_id}/snapshot", response_model=ApiResponse[FeedSnapshotResult])
async def get_feed_snapshot(feed_id: str) -> ApiResponse[FeedSnapshotResult]:
    snapshot = await get_registry().capture_feed_snapshot(feed_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(
        data=snapshot,
        message="Feed snapshot captured successfully." if snapshot.captured else "Feed snapshot capture failed.",
    )


@app.post("/api/feeds/{feed_id}/start", response_model=ApiResponse[VideoFeed])
async def start_feed(feed_id: str) -> ApiResponse[VideoFeed]:
    try:
        feed = await get_registry().start_feed(feed_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeedStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed started successfully.")


@app.post("/api/feeds/{feed_id}/stop", response_model=ApiResponse[VideoFeed])
async def stop_feed(feed_id: str) -> ApiResponse[VideoFeed]:
    try:
        feed = await get_registry().stop_feed(feed_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed stopped successfully.")


@app.post("/api/feeds/{feed_id}/restart", response_model=ApiResponse[VideoFeed])
async def restart_feed(feed_id: str) -> ApiResponse[VideoFeed]:
    try:
        feed = await get_registry().restart_feed(feed_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeedStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed restarted successfully.")


@app.delete("/api/feeds/{feed_id}", response_model=ApiResponse[dict[str, str]])
async def delete_feed(feed_id: str) -> ApiResponse[dict[str, str]]:
    removed = await get_registry().delete_feed(feed_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data={"feed_id": feed_id}, message="Feed deleted successfully.")


@app.post("/api/feeds/{feed_id}/zone", response_model=ApiResponse[VideoFeed])
async def update_feed_zone(feed_id: str, request: ZoneUpdateRequest) -> ApiResponse[VideoFeed]:
    feed = await get_registry().update_zone(feed_id, request.zone)
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed, message="Zone updated successfully.")


@app.get("/api/system/health", response_model=ApiResponse[SystemHealth])
async def get_system_health() -> ApiResponse[SystemHealth]:
    feeds = await get_registry().list_feeds()
    active_feeds = sum(1 for feed in feeds if feed.status == "running")
    health = SystemHealth(
        status="ok",
        api_version=__version__,
        total_feeds=len(feeds),
        active_feeds=active_feeds,
        websocket_clients=get_broadcaster().client_count,
        timestamp=datetime.now(timezone.utc),
    )
    return ApiResponse(data=health)


@app.websocket("/ws/metrics")
async def metrics_websocket(websocket: WebSocket) -> None:
    broadcaster = get_broadcaster()
    registry = get_registry()
    await broadcaster.connect(websocket)

    snapshot = FeedSnapshotEvent(payload={"feeds": await registry.list_feeds()})
    await websocket.send_json(snapshot.model_dump(mode="json"))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.disconnect(websocket)