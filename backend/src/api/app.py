"""FastAPI application for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

import asyncio
import mimetypes
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse
from uuid import uuid4

import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

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
    FeedWebRTCOfferRequest,
    FeedWebRTCOfferResponse,
    FeedTransportCapabilities,
    FeedSnapshotResult,
    FeedSnapshotEvent,
    QueueAlertArchiveRequest,
    QueueAlertArchiveResponse,
    WebhookIntegrationStatus,
    WebhookIntegrationTestResult,
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
    QueueThresholdUpdateRequest,
    SystemHealth,
    UploadVideoResponse,
    VideoFeed,
    WebRTCSessionDescription,
    ZoneUpdateRequest,
    coerce_zone_polygon,
)
from src.api.runtime import FeedRegistry, FeedStartError, FeedStateError, WebSocketHub
from src.database import (
    archive_alert_payload,
    create_caisse,
    create_establishment,
    get_caisse_by_id,
    get_caisses_by_establishment,
    get_establishment_by_id,
    get_establishments,
    init_db,
)
from src.config import (
    MEDIAMTX_CONTROL_API_BASE_URL,
    MEDIAMTX_WEBRTC_PREVIEW_ENABLED,
    MEDIAMTX_WEBRTC_TIMEOUT_SEC,
    MEDIAMTX_WHEP_BASE_URL,
    N8N_WEBHOOK_SECRET,
    N8N_WEBHOOK_URL,
    WEBHOOK_ENABLED,
)
from src.queue_analyzer import QueueMetrics
from src.webhook_client import WebhookClient


BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
DEFAULT_CORS_ORIGIN_REGEX = (
    r"https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(:\d+)?$"
)


class MediaMTXConnectionError(RuntimeError):
    """Raised when the API cannot reach MediaMTX."""


class MediaMTXUpstreamError(RuntimeError):
    """Raised when MediaMTX rejects a signaling request."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def parse_csv_env(value: str | None) -> list[str]:
    """Parse a comma-separated environment variable into a list of values."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_upload_preview_path(file_path: Path) -> str:
    """Return the frontend-consumable API path for an uploaded video."""
    return f"/api/uploads/files/{file_path.name}"


def build_mediamtx_path_name(feed_id: str) -> str:
    """Build a stable MediaMTX path name from a feed identifier."""
    normalized = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "-"
        for char in feed_id.strip().lower()
    ).strip("-")

    if not normalized:
        raise ValueError("Feed identifier cannot be converted into a valid MediaMTX path.")

    return normalized


def extract_mediamtx_error_detail(response: requests.Response) -> str:
    """Extract a readable MediaMTX error payload from HTTP responses."""
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    fallback = response.text.strip()
    return fallback or f"MediaMTX returned HTTP {response.status_code}."


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


def ensure_mediamtx_path_configuration(
    *,
    path_name: str,
    source: str,
    control_api_base_url: str,
    timeout_seconds: float,
) -> None:
    """Ensure a MediaMTX path exists and points to the RTSP source."""
    if not path_name.strip():
        raise ValueError("MediaMTX path name must not be blank.")

    encoded_path = quote(path_name.strip(), safe="")
    base_url = control_api_base_url.rstrip("/")
    patch_endpoint = f"{base_url}/v3/config/paths/patch/{encoded_path}"
    add_endpoint = f"{base_url}/v3/config/paths/add/{encoded_path}"
    path_payload = {
        "source": source,
        "sourceOnDemand": True,
        "sourceOnDemandStartTimeout": "10s",
        "sourceOnDemandCloseAfter": "10s",
        "rtspTransport": "tcp",
    }

    try:
        patch_response = requests.patch(
            patch_endpoint,
            json=path_payload,
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise MediaMTXConnectionError(
            "MediaMTX Control API timed out while preparing the stream path."
        ) from exc
    except requests.RequestException as exc:
        raise MediaMTXConnectionError(
            "MediaMTX Control API could not be reached while preparing the stream path."
        ) from exc

    if patch_response.status_code == 200:
        return

    if patch_response.status_code != 404:
        detail = extract_mediamtx_error_detail(patch_response)
        raise MediaMTXUpstreamError(
            status_code=patch_response.status_code,
            detail=f"path patch failed: {detail}",
        )

    try:
        add_response = requests.post(
            add_endpoint,
            json=path_payload,
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise MediaMTXConnectionError(
            "MediaMTX Control API timed out while creating the stream path."
        ) from exc
    except requests.RequestException as exc:
        raise MediaMTXConnectionError(
            "MediaMTX Control API could not be reached while creating the stream path."
        ) from exc

    if add_response.status_code >= 400:
        detail = extract_mediamtx_error_detail(add_response)
        raise MediaMTXUpstreamError(
            status_code=add_response.status_code,
            detail=f"path creation failed: {detail}",
        )


def run_mediamtx_webrtc_offer(
    *,
    path_name: str,
    offer_sdp: str,
    whep_base_url: str,
    timeout_seconds: float,
) -> str:
    """Proxy a browser SDP offer to MediaMTX WHEP and return the SDP answer."""
    if not offer_sdp.strip():
        raise ValueError("WebRTC SDP offer must not be blank.")
    if not path_name.strip():
        raise ValueError("MediaMTX path name must not be blank.")

    endpoint = f"{whep_base_url.rstrip('/')}/{quote(path_name.strip(), safe='')}/whep"

    try:
        response = requests.post(
            endpoint,
            data=offer_sdp.encode("utf-8"),
            headers={
                "Content-Type": "application/sdp",
                "Accept": "application/sdp, text/plain, application/json",
            },
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise MediaMTXConnectionError("MediaMTX timed out while creating a WebRTC preview session.") from exc
    except requests.RequestException as exc:
        raise MediaMTXConnectionError("MediaMTX could not be reached for WebRTC preview.") from exc

    if response.status_code not in {200, 201}:
        detail = extract_mediamtx_error_detail(response)
        raise MediaMTXUpstreamError(status_code=response.status_code, detail=detail)

    answer_sdp = response.text
    if not answer_sdp.strip():
        raise MediaMTXUpstreamError(status_code=502, detail="MediaMTX returned an empty SDP answer.")

    return answer_sdp


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

cors_origins = parse_csv_env(os.getenv("QUEUEVISION_CORS_ORIGINS")) or DEFAULT_CORS_ORIGINS
cors_origin_regex = os.getenv("QUEUEVISION_CORS_ORIGIN_REGEX") or DEFAULT_CORS_ORIGIN_REGEX

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
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


@app.post("/api/alerts/archive", response_model=ApiResponse[QueueAlertArchiveResponse])
async def archive_queue_alerts(request: QueueAlertArchiveRequest) -> ApiResponse[QueueAlertArchiveResponse]:
    try:
        archived_alerts = await asyncio.to_thread(
            archive_alert_payload,
            request.model_dump(mode="python"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to archive alert payload: {exc}") from exc

    return ApiResponse(
        data=QueueAlertArchiveResponse(
            archived_alerts=archived_alerts,
            camera_id=request.camera_id,
            zone_id=request.zone_id,
            timestamp=request.timestamp,
        ),
        message="Alert payload archived successfully.",
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


@app.get("/api/feeds/{feed_id}/transport", response_model=ApiResponse[FeedTransportCapabilities])
async def get_feed_transport(feed_id: str) -> ApiResponse[FeedTransportCapabilities]:
    capabilities = await get_registry().get_feed_transport_capabilities(feed_id)
    if capabilities is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=capabilities)


@app.post("/api/feeds/{feed_id}/webrtc/offer", response_model=ApiResponse[FeedWebRTCOfferResponse])
async def create_feed_webrtc_offer(
    feed_id: str,
    request: FeedWebRTCOfferRequest,
) -> ApiResponse[FeedWebRTCOfferResponse]:
    if not MEDIAMTX_WEBRTC_PREVIEW_ENABLED:
        raise HTTPException(status_code=503, detail="WebRTC preview is disabled on this backend.")

    source_status, source = await get_registry().resolve_feed_webrtc_source(feed_id)
    if source_status == "not_found":
        raise HTTPException(status_code=404, detail="Feed not found.")
    if source_status == "not_running":
        raise HTTPException(
            status_code=409,
            detail="Feed must be running before creating a WebRTC preview session.",
        )
    if source_status == "unsupported_source":
        raise HTTPException(
            status_code=409,
            detail="WebRTC preview currently supports RTSP feed sources only.",
        )
    if source is None:
        raise HTTPException(status_code=500, detail="WebRTC source resolution failed unexpectedly.")

    transport = await get_registry().get_feed_transport_capabilities(feed_id)
    if transport is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    webrtc_transport = transport.webrtc
    if not webrtc_transport.enabled or not webrtc_transport.ready:
        reason = webrtc_transport.reason or "webrtc_not_ready"
        raise HTTPException(
            status_code=409,
            detail=f"WebRTC transport unavailable: {reason}",
        )

    path_name = build_mediamtx_path_name(webrtc_transport.path_name or feed_id)

    try:
        if webrtc_transport.source_mode == "direct":
            await asyncio.to_thread(
                ensure_mediamtx_path_configuration,
                path_name=path_name,
                source=source,
                control_api_base_url=MEDIAMTX_CONTROL_API_BASE_URL,
                timeout_seconds=MEDIAMTX_WEBRTC_TIMEOUT_SEC,
            )
        answer_sdp = await asyncio.to_thread(
            run_mediamtx_webrtc_offer,
            path_name=path_name,
            offer_sdp=request.offer.sdp,
            whep_base_url=MEDIAMTX_WHEP_BASE_URL,
            timeout_seconds=MEDIAMTX_WEBRTC_TIMEOUT_SEC,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MediaMTXConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MediaMTXUpstreamError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"MediaMTX WebRTC upstream error ({exc.status_code}): {exc.detail}",
        ) from exc

    return ApiResponse(
        data=FeedWebRTCOfferResponse(
            answer=WebRTCSessionDescription(type="answer", sdp=answer_sdp),
        ),
        message="WebRTC offer proxied successfully.",
    )


@app.get("/api/feeds/{feed_id}/snapshot", response_model=ApiResponse[FeedSnapshotResult])
async def get_feed_snapshot(feed_id: str) -> ApiResponse[FeedSnapshotResult]:
    snapshot = await get_registry().capture_feed_snapshot(feed_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(
        data=snapshot,
        message="Feed snapshot captured successfully." if snapshot.captured else "Feed snapshot capture failed.",
    )


@app.get("/api/feeds/{feed_id}/stream")
async def stream_feed(feed_id: str) -> StreamingResponse:
    registry = get_registry()
    stream_status = await registry.subscribe_feed_stream(feed_id)
    if stream_status == "not_found":
        raise HTTPException(status_code=404, detail="Feed not found.")
    if stream_status == "not_running":
        raise HTTPException(status_code=409, detail="Feed must be running before opening the stream.")

    async def iter_mjpeg():
        last_frame_index = 0
        try:
            while True:
                try:
                    frame = await registry.next_feed_stream_frame(
                        feed_id,
                        after_frame_index=last_frame_index,
                        timeout_seconds=1.5,
                    )
                except StopAsyncIteration:
                    break

                if frame is None:
                    feed = await registry.get_feed(feed_id)
                    if feed is None or feed.status not in {"running", "initializing"}:
                        break
                    await asyncio.sleep(0.05)
                    continue

                last_frame_index, jpeg_bytes = frame
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode("ascii")
                    + jpeg_bytes
                    + b"\r\n"
                )
        finally:
            await registry.unsubscribe_feed_stream(feed_id)

    return StreamingResponse(
        iter_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
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


@app.post("/api/feeds/{feed_id}/thresholds", response_model=ApiResponse[VideoFeed])
async def update_feed_thresholds(feed_id: str, request: QueueThresholdUpdateRequest) -> ApiResponse[VideoFeed]:
    feed = await get_registry().update_thresholds(
        feed_id,
        queue_length_warning=request.queue_length_warning,
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed, message="Feed thresholds updated successfully.")


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


@app.get("/api/system/webhook", response_model=ApiResponse[WebhookIntegrationStatus])
async def get_webhook_integration_status() -> ApiResponse[WebhookIntegrationStatus]:
    return ApiResponse(
        data=WebhookIntegrationStatus(
            webhook_url=N8N_WEBHOOK_URL or None,
            webhook_enabled=WEBHOOK_ENABLED,
            secret_configured=bool(N8N_WEBHOOK_SECRET),
        ),
        message="Webhook integration status loaded successfully.",
    )


@app.post("/api/system/webhook/test", response_model=ApiResponse[WebhookIntegrationTestResult])
async def test_webhook_integration() -> ApiResponse[WebhookIntegrationTestResult]:
    if not N8N_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="N8N webhook URL is not configured.")

    client = WebhookClient(N8N_WEBHOOK_URL, webhook_secret=N8N_WEBHOOK_SECRET)
    sample_metrics = QueueMetrics(
        timestamp=datetime.now().timestamp(),
        people_in_zone=3,
        arrival_rate=0.05,
        service_rate=0.10,
        estimated_wait_sec=5.0,
        queue_stable=True,
        arrival_rate_lower=0.02,
        arrival_rate_upper=0.09,
        service_rate_lower=0.06,
        service_rate_upper=0.15,
        wait_time_lower=3.0,
        wait_time_upper=8.5,
        uncertainty_level="Low",
    )

    try:
        success = await asyncio.to_thread(
            client.send_metrics,
            metrics=sample_metrics,
            frame_id=1,
            source="settings-page-test",
            feed_id="settings_test",
            alert_triggered=False,
            alert_reason="Webhook test payload from settings page",
            alert_severity="info",
        )
    finally:
        client.close()

    if not success:
        raise HTTPException(status_code=502, detail="Webhook test payload could not be delivered.")

    return ApiResponse(
        data=WebhookIntegrationTestResult(
            success=True,
            webhook_url=N8N_WEBHOOK_URL,
            message="Webhook test payload delivered successfully.",
        ),
        message="Webhook test completed successfully.",
    )


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