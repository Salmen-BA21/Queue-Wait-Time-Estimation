"""FastAPI application for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

import asyncio
import mimetypes
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlparse, urlunparse
from uuid import uuid4

import requests
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src import __version__
from src.auth import (
    ACCESS_TOKEN_COOKIE_MAX_AGE,
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_MAX_AGE,
    REFRESH_TOKEN_COOKIE_NAME,
    AuthenticatedUser,
    create_access_token,
    create_refresh_session_id,
    decode_access_token,
    ensure_bootstrap_admin_account,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    is_account_locked,
    lockout_threshold_reached,
    next_lockout_until_iso,
    parse_iso_datetime,
    refresh_token_expiry_iso,
    user_record_to_authenticated_user,
    validate_password_policy,
    verify_password,
)
from src.api.models import (
    AuthUserModel,
    ApiResponse,
    BatchFeedLaunchRequest,
    BatchFeedLaunchResponse,
    Caisse,
    CreateManagerRequest,
    CreateFeedRequest,
    CreateCaisseRequest,
    CreateEstablishmentRequest,
    Establishment,
    FeedWebRTCOfferRequest,
    FeedWebRTCOfferResponse,
    FeedSourceUpdateRequest,
    FeedTransportCapabilities,
    FeedSnapshotResult,
    FeedSnapshotEvent,
    LoginRequest,
    LoginResponse,
    QueueAlertArchiveRequest,
    QueueAlertArchiveResponse,
    RegisterRequest,
    ResetManagerPasswordRequest,
    SessionStatusResponse,
    StatisticsDateRange,
    StatisticsOverviewResponse,
    TimeSeriesStatisticsItem,
    ZoneStatisticsItem,
    AlertDistributionItem,
    UpdateManagerStatusRequest,
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
    create_auth_audit_event,
    create_caisse,
    create_establishment,
    create_refresh_session,
    create_user,
    get_refresh_session_by_token_hash,
    get_caisse_by_id,
    get_caisses_by_establishment,
    get_alert_distribution_statistics,
    get_overview_statistics,
    get_establishment_by_id,
    get_establishments,
    get_time_based_statistics,
    get_user_by_email,
    get_user_by_id,
    get_zone_statistics,
    init_db,
    list_users_by_role,
    record_failed_login_attempt,
    record_successful_login,
    revoke_refresh_session,
    revoke_refresh_session_by_token_hash,
    set_user_active,
    touch_refresh_session,
    update_user_password_hash,
)
from src.config import (
    AUTH_COOKIE_SAMESITE,
    AUTH_COOKIE_SECURE,
    AUTH_ENFORCE_API,
    AUTH_MIN_PASSWORD_LENGTH,
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
    ensure_bootstrap_admin_account()
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


def build_auth_user_model(user: AuthenticatedUser) -> AuthUserModel:
    """Convert dependency-level auth user to API response model."""
    return AuthUserModel(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    """Attach signed session cookies to response."""
    samesite_value: Literal["lax", "strict", "none"]
    if AUTH_COOKIE_SAMESITE == "strict":
        samesite_value = "strict"
    elif AUTH_COOKIE_SAMESITE == "none":
        samesite_value = "none"
    else:
        samesite_value = "lax"
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        max_age=ACCESS_TOKEN_COOKIE_MAX_AGE,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=samesite_value,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_COOKIE_MAX_AGE,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=samesite_value,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire auth cookies on the client."""
    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE_NAME, path="/")


def get_request_client_metadata(request: Request) -> tuple[str | None, str | None]:
    """Extract client metadata for refresh-session auditing."""
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client_ip = forwarded_for or (request.client.host if request.client else None)
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


def resolve_access_token(
    request: Request,
    authorization_header: str | None,
) -> str | None:
    """Read access token from Authorization header or cookie."""
    if authorization_header:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()

    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()
    return None


async def get_optional_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser | None:
    """Resolve authenticated user if an access token is present and valid."""
    raw_token = resolve_access_token(request, authorization)
    if not raw_token:
        return None

    decoded = decode_access_token(raw_token)
    if decoded is None:
        return None

    user_record = await asyncio.to_thread(get_user_by_id, decoded.user_id)
    if user_record is None:
        return None

    user = user_record_to_authenticated_user(user_record)
    if not user.is_active:
        return None
    return user


async def require_authenticated_user(
    current_user: AuthenticatedUser | None = Depends(get_optional_current_user),
) -> AuthenticatedUser:
    """Enforce authentication for strict auth endpoints."""
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return current_user


async def require_admin(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AuthenticatedUser:
    """Enforce Administrator role for account governance endpoints."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    return current_user


async def require_manager_for_api(
    current_user: AuthenticatedUser | None = Depends(get_optional_current_user),
) -> AuthenticatedUser | None:
    """Conditionally enforce manager role for operational endpoints.

    During rollout, enforcement can stay disabled via QUEUEVISION_AUTH_ENFORCE_API.
    """
    if not AUTH_ENFORCE_API:
        return current_user

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    if current_user.role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required.")

    return current_user


def resolve_feed_owner_scope(current_user: AuthenticatedUser | None) -> int | None:
    """Return manager feed ownership scope for API/feed websocket queries."""
    if current_user is None:
        return None
    if current_user.role != "manager":
        return None
    return current_user.id


async def resolve_websocket_current_user(websocket: WebSocket) -> AuthenticatedUser | None:
    """Resolve authenticated user for websocket sessions using cookie or bearer token."""
    access_token = websocket.cookies.get(ACCESS_TOKEN_COOKIE_NAME)

    if not access_token:
        authorization = websocket.headers.get("authorization")
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer" and token:
                access_token = token.strip()

    if not access_token:
        return None

    decoded = decode_access_token(access_token)
    if decoded is None:
        return None

    user_record = await asyncio.to_thread(get_user_by_id, decoded.user_id)
    if user_record is None:
        return None

    user = user_record_to_authenticated_user(user_record)
    if not user.is_active:
        return None
    return user


def build_establishment_model(record: dict) -> Establishment:
    """Convert a raw establishment row into the public API model."""
    return Establishment.model_validate(record)


def build_caisse_model(record: dict) -> Caisse:
    """Convert a raw caisse row into the public API model."""
    payload = dict(record)
    payload["zone"] = coerce_zone_polygon(payload.pop("zone_points", None))
    payload.pop("zone_points_json", None)
    return Caisse.model_validate(payload)


def build_statistics_date_range(from_date: date | None, to_date: date | None) -> StatisticsDateRange:
    """Convert query parameters into a normalized date range model."""
    return StatisticsDateRange(from_date=from_date, to_date=to_date)


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


@app.post("/api/auth/register", response_model=ApiResponse[LoginResponse], status_code=201)
async def register(
    request: RegisterRequest,
    response: Response,
    http_request: Request,
) -> ApiResponse[LoginResponse]:
    password_issue = validate_password_policy(request.password)
    if password_issue:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_issue)

    try:
        user_id = await asyncio.to_thread(
            create_user,
            email=request.email,
            display_name=request.display_name,
            password_hash=hash_password(request.password),
            role="manager",
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use.") from exc

    user_record = await asyncio.to_thread(get_user_by_id, user_id)
    if user_record is None:
        raise HTTPException(status_code=500, detail="Created account could not be loaded.")

    await asyncio.to_thread(record_successful_login, user_id)
    user_record = await asyncio.to_thread(get_user_by_id, user_id)
    if user_record is None:
        raise HTTPException(status_code=500, detail="Created account could not be loaded.")

    user = user_record_to_authenticated_user(user_record)
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )
    refresh_token = generate_refresh_token()
    client_ip, user_agent = get_request_client_metadata(http_request)
    await asyncio.to_thread(
        create_refresh_session,
        session_id=create_refresh_session_id(),
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expiry_iso(),
        ip_address=client_ip,
        user_agent=user_agent,
    )

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    await asyncio.to_thread(
        create_auth_audit_event,
        user_id=user.id,
        event_type="register",
        event_status="success",
        details={"email": user.email},
    )

    return ApiResponse(
        data=LoginResponse(user=build_auth_user_model(user)),
        message="Account created successfully.",
    )


@app.post("/api/auth/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: LoginRequest,
    response: Response,
    http_request: Request,
) -> ApiResponse[LoginResponse]:
    user_record = await asyncio.to_thread(get_user_by_email, request.email)
    if user_record is None:
        await asyncio.to_thread(
            create_auth_audit_event,
            user_id=None,
            event_type="login",
            event_status="failed",
            details={"email": request.email, "reason": "unknown_email"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    user = user_record_to_authenticated_user(user_record)

    if not user.is_active:
        await asyncio.to_thread(
            create_auth_audit_event,
            user_id=user.id,
            event_type="login",
            event_status="failed",
            details={"email": user.email, "reason": "inactive_account"},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    if is_account_locked(user_record):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is temporarily locked. Please retry later.",
        )

    if not verify_password(request.password, str(user_record["password_hash"])):
        current_failures = int(user_record.get("failed_login_attempts") or 0)
        next_failures = current_failures + 1
        lock_until = next_lockout_until_iso() if lockout_threshold_reached(next_failures) else None
        applied_failures = await asyncio.to_thread(
            record_failed_login_attempt,
            user.id,
            locked_until=lock_until,
        )
        await asyncio.to_thread(
            create_auth_audit_event,
            user_id=user.id,
            event_type="login",
            event_status="failed",
            details={
                "email": user.email,
                "reason": "invalid_password",
                "failed_attempts": applied_failures,
            },
        )
        if lock_until is not None:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account is temporarily locked due to repeated failed attempts.",
            )

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    await asyncio.to_thread(record_successful_login, user.id)

    refreshed_record = await asyncio.to_thread(get_user_by_id, user.id)
    if refreshed_record is None:
        raise HTTPException(status_code=500, detail="Failed to load authenticated account.")

    refreshed_user = user_record_to_authenticated_user(refreshed_record)
    access_token = create_access_token(
        user_id=refreshed_user.id,
        email=refreshed_user.email,
        role=refreshed_user.role,
    )
    refresh_token = generate_refresh_token()
    client_ip, user_agent = get_request_client_metadata(http_request)
    await asyncio.to_thread(
        create_refresh_session,
        session_id=create_refresh_session_id(),
        user_id=refreshed_user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expiry_iso(),
        ip_address=client_ip,
        user_agent=user_agent,
    )

    set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    await asyncio.to_thread(
        create_auth_audit_event,
        user_id=refreshed_user.id,
        event_type="login",
        event_status="success",
        details={"email": refreshed_user.email},
    )

    return ApiResponse(
        data=LoginResponse(user=build_auth_user_model(refreshed_user)),
        message="Login successful.",
    )


@app.post("/api/auth/refresh", response_model=ApiResponse[LoginResponse])
async def refresh_auth_session(response: Response, request: Request) -> ApiResponse[LoginResponse]:
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not raw_refresh_token:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session refresh token missing.")

    token_hash = hash_refresh_token(raw_refresh_token)
    session_record = await asyncio.to_thread(get_refresh_session_by_token_hash, token_hash)
    if session_record is None or session_record.get("revoked_at"):
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid.")

    expires_at = parse_iso_datetime(session_record.get("expires_at"))
    if expires_at is None or datetime.now(timezone.utc) >= expires_at:
        await asyncio.to_thread(revoke_refresh_session, str(session_record["id"]))
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired.")

    user_record = await asyncio.to_thread(get_user_by_id, int(session_record["user_id"]))
    if user_record is None:
        await asyncio.to_thread(revoke_refresh_session, str(session_record["id"]))
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user is unavailable.")

    user = user_record_to_authenticated_user(user_record)
    if not user.is_active:
        await asyncio.to_thread(revoke_refresh_session, str(session_record["id"]))
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    await asyncio.to_thread(revoke_refresh_session, str(session_record["id"]))
    client_ip, user_agent = get_request_client_metadata(request)
    new_refresh_token = generate_refresh_token()
    new_session_id = create_refresh_session_id()
    await asyncio.to_thread(
        create_refresh_session,
        session_id=new_session_id,
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=refresh_token_expiry_iso(),
        ip_address=client_ip,
        user_agent=user_agent,
    )
    await asyncio.to_thread(touch_refresh_session, new_session_id)

    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookies(response, access_token=access_token, refresh_token=new_refresh_token)

    return ApiResponse(data=LoginResponse(user=build_auth_user_model(user)), message="Session refreshed.")


@app.post("/api/auth/logout", response_model=ApiResponse[dict[str, bool]])
async def logout(response: Response, request: Request) -> ApiResponse[dict[str, bool]]:
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if raw_refresh_token:
        await asyncio.to_thread(revoke_refresh_session_by_token_hash, hash_refresh_token(raw_refresh_token))

    clear_auth_cookies(response)
    return ApiResponse(data={"logged_out": True}, message="Logged out successfully.")


@app.get("/api/auth/me", response_model=ApiResponse[SessionStatusResponse])
async def get_current_session(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> ApiResponse[SessionStatusResponse]:
    return ApiResponse(
        data=SessionStatusResponse(authenticated=True, user=build_auth_user_model(current_user)),
        message="Session loaded successfully.",
    )


@app.get("/api/admin/managers", response_model=ApiResponse[list[AuthUserModel]])
async def list_manager_accounts(
    _admin: AuthenticatedUser = Depends(require_admin),
) -> ApiResponse[list[AuthUserModel]]:
    manager_records = await asyncio.to_thread(list_users_by_role, "manager")
    manager_models = [
        build_auth_user_model(user_record_to_authenticated_user(record))
        for record in manager_records
    ]
    return ApiResponse(data=manager_models)


@app.post("/api/admin/managers", response_model=ApiResponse[AuthUserModel], status_code=201)
async def create_manager_account(
    request: CreateManagerRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
) -> ApiResponse[AuthUserModel]:
    password_issue = validate_password_policy(request.password)
    if password_issue:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_issue)

    try:
        manager_id = await asyncio.to_thread(
            create_user,
            email=request.email,
            display_name=request.display_name,
            password_hash=hash_password(request.password),
            role="manager",
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use.") from exc

    manager_record = await asyncio.to_thread(get_user_by_id, manager_id)
    if manager_record is None:
        raise HTTPException(status_code=500, detail="Created manager account could not be loaded.")

    manager_user = user_record_to_authenticated_user(manager_record)
    await asyncio.to_thread(
        create_auth_audit_event,
        user_id=manager_user.id,
        event_type="manager_create",
        event_status="success",
        details={"email": manager_user.email},
    )
    return ApiResponse(data=build_auth_user_model(manager_user), message="Manager account created.")


@app.post("/api/admin/managers/{user_id}/status", response_model=ApiResponse[AuthUserModel])
async def update_manager_account_status(
    user_id: int,
    request: UpdateManagerStatusRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
) -> ApiResponse[AuthUserModel]:
    manager_record = await asyncio.to_thread(get_user_by_id, user_id)
    if manager_record is None or manager_record.get("role") != "manager":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager account not found.")

    updated = await asyncio.to_thread(set_user_active, user_id, request.is_active)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update manager status.")

    manager_record = await asyncio.to_thread(get_user_by_id, user_id)
    if manager_record is None:
        raise HTTPException(status_code=500, detail="Updated manager account could not be loaded.")

    manager_user = user_record_to_authenticated_user(manager_record)
    await asyncio.to_thread(
        create_auth_audit_event,
        user_id=manager_user.id,
        event_type="manager_status_update",
        event_status="success",
        details={"is_active": request.is_active},
    )
    return ApiResponse(data=build_auth_user_model(manager_user), message="Manager status updated.")


@app.post("/api/admin/managers/{user_id}/reset-password", response_model=ApiResponse[dict[str, bool]])
async def reset_manager_account_password(
    user_id: int,
    request: ResetManagerPasswordRequest,
    _admin: AuthenticatedUser = Depends(require_admin),
) -> ApiResponse[dict[str, bool]]:
    manager_record = await asyncio.to_thread(get_user_by_id, user_id)
    if manager_record is None or manager_record.get("role") != "manager":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manager account not found.")

    password_issue = validate_password_policy(request.password)
    if password_issue:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_issue)

    updated = await asyncio.to_thread(update_user_password_hash, user_id, hash_password(request.password))
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to reset manager password.")

    await asyncio.to_thread(
        create_auth_audit_event,
        user_id=user_id,
        event_type="manager_password_reset",
        event_status="success",
        details={"min_password_length": AUTH_MIN_PASSWORD_LENGTH},
    )
    return ApiResponse(data={"password_reset": True}, message="Manager password reset.")


@app.post("/api/sources/rtsp/test", response_model=ApiResponse[RTSPConnectionTestResult])
async def test_rtsp_source(
    request: RTSPConnectionTestRequest,
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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


@app.get("/api/statistics/overview", response_model=ApiResponse[StatisticsOverviewResponse])
async def get_statistics_overview(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[StatisticsOverviewResponse]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    stats = await asyncio.to_thread(
        get_overview_statistics,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        owner_user_id=owner_user_id,
    )
    return ApiResponse(
        data=StatisticsOverviewResponse(
            date_range=build_statistics_date_range(from_date, to_date),
            avg_wait_time=float(stats.get("avg_wait_time", 0) or 0),
            peak_queue_length=int(stats.get("peak_queue_length", 0) or 0),
            stability_score=float(stats.get("stability_score", 0) or 0),
            total_alerts=int(stats.get("total_alerts", 0) or 0),
            critical_alerts=int(stats.get("critical_alerts", 0) or 0),
            warning_alerts=int(stats.get("warning_alerts", 0) or 0),
            avg_people_in_zone=float(stats.get("avg_people_in_zone", 0) or 0),
            avg_service_rate=float(stats.get("avg_service_rate", 0) or 0),
            avg_arrival_rate=float(stats.get("avg_arrival_rate", 0) or 0),
        ),
        message="Statistics overview loaded successfully.",
    )


@app.get("/api/statistics/by-zone", response_model=ApiResponse[list[ZoneStatisticsItem]])
async def get_statistics_by_zone(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[ZoneStatisticsItem]]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    rows = await asyncio.to_thread(
        get_zone_statistics,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        owner_user_id=owner_user_id,
    )
    return ApiResponse(
        data=[ZoneStatisticsItem.model_validate(row) for row in rows],
        message="Zone statistics loaded successfully.",
    )


@app.get("/api/statistics/by-time", response_model=ApiResponse[list[TimeSeriesStatisticsItem]])
async def get_statistics_by_time(
    period: Literal["hourly", "daily", "weekly"] = Query(default="daily"),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[TimeSeriesStatisticsItem]]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    rows = await asyncio.to_thread(
        get_time_based_statistics,
        period=period,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        owner_user_id=owner_user_id,
    )
    return ApiResponse(
        data=[TimeSeriesStatisticsItem.model_validate(row) for row in rows],
        message="Time-based statistics loaded successfully.",
    )


@app.get("/api/statistics/alerts", response_model=ApiResponse[list[AlertDistributionItem]])
async def get_statistics_alerts(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[AlertDistributionItem]]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    rows = await asyncio.to_thread(
        get_alert_distribution_statistics,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        owner_user_id=owner_user_id,
    )
    return ApiResponse(
        data=[AlertDistributionItem.model_validate(row) for row in rows],
        message="Alert analytics loaded successfully.",
    )


@app.get("/api/establishments", response_model=ApiResponse[list[Establishment]])
async def list_establishments(
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[Establishment]]:
    records = await asyncio.to_thread(get_establishments)
    return ApiResponse(data=[build_establishment_model(record) for record in records])


@app.post("/api/establishments", response_model=ApiResponse[Establishment], status_code=201)
async def create_establishment_endpoint(
    request: CreateEstablishmentRequest,
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
async def list_caisses(
    establishment_id: int,
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[Caisse]]:
    establishment = await asyncio.to_thread(get_establishment_by_id, establishment_id)
    if establishment is None:
        raise HTTPException(status_code=404, detail="Establishment not found.")

    records = await asyncio.to_thread(get_caisses_by_establishment, establishment_id)
    return ApiResponse(data=[build_caisse_model(record) for record in records])


@app.post("/api/establishments/{establishment_id}/caisses", response_model=ApiResponse[Caisse], status_code=201)
async def create_caisse_endpoint(
    establishment_id: int,
    request: CreateCaisseRequest,
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
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
async def upload_video_file(
    file: UploadFile = File(...),
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[UploadVideoResponse]:
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
async def serve_uploaded_video(
    file_name: str,
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> FileResponse:
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
async def list_feeds(
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[list[VideoFeed]]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feeds = await get_registry().list_feeds(owner_user_id=owner_user_id)
    return ApiResponse(data=feeds)


@app.post("/api/feeds", response_model=ApiResponse[VideoFeed], status_code=201)
async def create_feed(
    request: CreateFeedRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feed = await get_registry().create_feed(
        name=request.name,
        source=request.source,
        manager_user_id=owner_user_id,
        model_size=request.model_size,
        establishment_id=request.establishment_id,
        caisse_id=request.caisse_id,
        rtsp_username=request.rtsp_username,
        rtsp_password=request.rtsp_password,
        rtsp_transport=request.rtsp_transport,
    )
    return ApiResponse(data=feed, message="Feed registered successfully.")


@app.post("/api/feeds/batch-launch", response_model=ApiResponse[BatchFeedLaunchResponse])
async def batch_launch_feeds(
    request: BatchFeedLaunchRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[BatchFeedLaunchResponse]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    result = await get_registry().launch_feed_batch(
        feeds=request.feeds,
        launch_mode=request.launch_mode,
        log_level=request.runtime.log_level,
        webhook_enabled=request.runtime.webhook_enabled,
        manager_user_id=owner_user_id,
    )
    return ApiResponse(data=result, message="Batch feed launch processed.")


@app.get("/api/feeds/{feed_id}/status", response_model=ApiResponse[VideoFeed])
async def get_feed_status(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feed = await get_registry().get_feed(feed_id, owner_user_id=owner_user_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed)


@app.get("/api/feeds/{feed_id}/transport", response_model=ApiResponse[FeedTransportCapabilities])
async def get_feed_transport(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[FeedTransportCapabilities]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    capabilities = await get_registry().get_feed_transport_capabilities(
        feed_id,
        owner_user_id=owner_user_id,
    )
    if capabilities is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=capabilities)


@app.post("/api/feeds/{feed_id}/webrtc/offer", response_model=ApiResponse[FeedWebRTCOfferResponse])
async def create_feed_webrtc_offer(
    feed_id: str,
    request: FeedWebRTCOfferRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[FeedWebRTCOfferResponse]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    if not MEDIAMTX_WEBRTC_PREVIEW_ENABLED:
        raise HTTPException(status_code=503, detail="WebRTC preview is disabled on this backend.")

    source_status, source_or_path, status_reason = await get_registry().resolve_feed_webrtc_source(
        feed_id,
        owner_user_id=owner_user_id,
    )
    if source_status == "not_found":
        raise HTTPException(status_code=404, detail="Feed not found.")
    if source_status == "not_running":
        raise HTTPException(
            status_code=409,
            detail="Feed must be running before creating a WebRTC preview session.",
        )
    if source_status == "not_ready":
        reason = status_reason or "webrtc_not_ready"
        raise HTTPException(status_code=409, detail=f"WebRTC transport unavailable: {reason}")
    if source_or_path is None:
        raise HTTPException(status_code=500, detail="WebRTC source resolution failed unexpectedly.")

    transport = await get_registry().get_feed_transport_capabilities(
        feed_id,
        owner_user_id=owner_user_id,
    )
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
async def get_feed_snapshot(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[FeedSnapshotResult]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    snapshot = await get_registry().capture_feed_snapshot(feed_id, owner_user_id=owner_user_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(
        data=snapshot,
        message="Feed snapshot captured successfully." if snapshot.captured else "Feed snapshot capture failed.",
    )


@app.post("/api/feeds/{feed_id}/start", response_model=ApiResponse[VideoFeed])
async def start_feed(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    try:
        feed = await get_registry().start_feed(feed_id, owner_user_id=owner_user_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeedStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed started successfully.")


@app.post("/api/feeds/{feed_id}/stop", response_model=ApiResponse[VideoFeed])
async def stop_feed(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    try:
        feed = await get_registry().stop_feed(feed_id, owner_user_id=owner_user_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed stopped successfully.")


@app.post("/api/feeds/{feed_id}/restart", response_model=ApiResponse[VideoFeed])
async def restart_feed(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    try:
        feed = await get_registry().restart_feed(feed_id, owner_user_id=owner_user_id)
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeedStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    return ApiResponse(data=feed, message="Feed restarted successfully.")


@app.delete("/api/feeds/{feed_id}", response_model=ApiResponse[dict[str, str]])
async def delete_feed(
    feed_id: str,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[dict[str, str]]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    removed = await get_registry().delete_feed(feed_id, owner_user_id=owner_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data={"feed_id": feed_id}, message="Feed deleted successfully.")


@app.post("/api/feeds/{feed_id}/zone", response_model=ApiResponse[VideoFeed])
async def update_feed_zone(
    feed_id: str,
    request: ZoneUpdateRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feed = await get_registry().update_zone(feed_id, request.zone, owner_user_id=owner_user_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed, message="Zone updated successfully.")


@app.post("/api/feeds/{feed_id}/thresholds", response_model=ApiResponse[VideoFeed])
async def update_feed_thresholds(
    feed_id: str,
    request: QueueThresholdUpdateRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feed = await get_registry().update_thresholds(
        feed_id,
        queue_length_warning=request.queue_length_warning,
        owner_user_id=owner_user_id,
    )
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed, message="Feed thresholds updated successfully.")


@app.post("/api/feeds/{feed_id}/source", response_model=ApiResponse[VideoFeed])
async def update_feed_source(
    feed_id: str,
    request: FeedSourceUpdateRequest,
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[VideoFeed]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    fields_set = request.model_fields_set

    try:
        feed = await get_registry().update_source(
            feed_id,
            source=request.source,
            restart_if_running=request.restart_if_running,
            rtsp_username=request.rtsp_username,
            set_rtsp_username="rtsp_username" in fields_set,
            rtsp_password=request.rtsp_password,
            set_rtsp_password="rtsp_password" in fields_set,
            rtsp_transport=request.rtsp_transport,
            set_rtsp_transport="rtsp_transport" in fields_set,
            owner_user_id=owner_user_id,
        )
    except FeedStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeedStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")

    message = "Feed source updated successfully."
    if request.restart_if_running:
        message = "Feed source updated successfully (worker restart applied when running)."
    return ApiResponse(data=feed, message=message)


@app.get("/api/system/health", response_model=ApiResponse[SystemHealth])
async def get_system_health(
    current_user: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[SystemHealth]:
    owner_user_id = resolve_feed_owner_scope(current_user)
    feeds = await get_registry().list_feeds(owner_user_id=owner_user_id)
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
async def get_webhook_integration_status(
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[WebhookIntegrationStatus]:
    return ApiResponse(
        data=WebhookIntegrationStatus(
            webhook_url=N8N_WEBHOOK_URL or None,
            webhook_enabled=WEBHOOK_ENABLED,
            secret_configured=bool(N8N_WEBHOOK_SECRET),
        ),
        message="Webhook integration status loaded successfully.",
    )


@app.post("/api/system/webhook/test", response_model=ApiResponse[WebhookIntegrationTestResult])
async def test_webhook_integration(
    _manager: AuthenticatedUser | None = Depends(require_manager_for_api),
) -> ApiResponse[WebhookIntegrationTestResult]:
    if not N8N_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="N8N webhook URL is not configured.")

    client = WebhookClient(N8N_WEBHOOK_URL, webhook_secret=N8N_WEBHOOK_SECRET)
    sample_metrics = QueueMetrics(
        timestamp=datetime.now().timestamp(),
        people_in_zone=3,
        arrival_rate=0.05,
        service_rate=0.10,
        estimated_wait_sec=5.0,
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
    current_user = await resolve_websocket_current_user(websocket)
    owner_user_id = resolve_feed_owner_scope(current_user)
    await broadcaster.connect(websocket, owner_user_id=owner_user_id)

    snapshot = FeedSnapshotEvent(payload={"feeds": await registry.list_feeds(owner_user_id=owner_user_id)})
    await websocket.send_json(snapshot.model_dump(mode="json"))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.disconnect(websocket)
