"""Pydantic API models for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator


FeedStatus = Literal["created", "initializing", "running", "stopped", "error"]
EventType = Literal["snapshot", "feed_status", "metrics_update", "alert_fired", "system_warning"]
ModelSize = Literal["n", "s", "m", "l", "x"]
RTSPTransport = Literal["tcp", "udp"]
WebRTCSessionType = Literal["offer", "answer"]
WebRTCTransportSourceMode = Literal["annotated", "direct", "none"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
BatchLaunchMode = Literal["save_only", "create_and_start"]
BatchLaunchItemStatus = Literal["created", "started", "failed"]
AlertSeverity = Literal["warning"]
AuthRole = Literal["admin", "manager"]

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Consistent response envelope for frontend-facing endpoints."""

    success: bool = True
    data: T
    message: str | None = None


class AuthUserModel(BaseModel):
    """Authenticated user profile returned to the frontend."""

    id: int = Field(ge=1)
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    role: AuthRole
    is_active: bool
    created_at: str
    last_login_at: str | None = None


class LoginRequest(BaseModel):
    """Credential payload for session login."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Email must be valid.")
        return normalized


class RegisterRequest(BaseModel):
    """Self-service registration payload for manager accounts."""

    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Email must be valid.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must not be blank.")
        return trimmed


class LoginResponse(BaseModel):
    """Login response payload for cookie-based sessions."""

    user: AuthUserModel


class SessionStatusResponse(BaseModel):
    """Response payload for current-session introspection."""

    authenticated: bool
    user: AuthUserModel | None = None


class CreateManagerRequest(BaseModel):
    """Payload used by administrators to create manager accounts."""

    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Email must be valid.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must not be blank.")
        return trimmed


class UpdateManagerStatusRequest(BaseModel):
    """Payload used to activate or deactivate manager accounts."""

    is_active: bool


class ResetManagerPasswordRequest(BaseModel):
    """Payload used to rotate manager account credentials."""

    password: str = Field(min_length=1, max_length=255)


class QueueAlertItem(BaseModel):
    """Single alert emitted by the queue analysis pipeline."""

    type: str
    severity: str
    message: str
    value: float | None = None
    threshold: float | None = None


class QueueAlertMetrics(BaseModel):
    """Metrics snapshot associated with an archived alert payload."""

    people_in_zone: int = Field(ge=0)
    arrival_rate: float = Field(ge=0.0)
    service_rate: float = Field(ge=0.0)
    wait_time_seconds: float = Field(ge=0.0)
    queue_stable: bool


class QueueAlertArchiveRequest(BaseModel):
    """Payload archived from the n8n workflow for later analysis."""

    timestamp: datetime
    camera_id: str = Field(min_length=1, max_length=120)
    zone_id: str = Field(min_length=1, max_length=120)
    metrics: QueueAlertMetrics
    alerts: list[QueueAlertItem] = Field(default_factory=list)
    raw_detection_count: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0.0)


class QueueAlertArchiveResponse(BaseModel):
    """Response returned after persisting an alert archive payload."""

    archived_alerts: int = Field(ge=0)
    camera_id: str
    zone_id: str
    timestamp: datetime


class WebhookIntegrationStatus(BaseModel):
    """Current n8n webhook configuration exposed to the settings page."""

    webhook_url: str | None = None
    webhook_enabled: bool
    secret_configured: bool


class WebhookIntegrationTestResult(BaseModel):
    """Result of sending a test payload to the configured webhook."""

    success: bool
    webhook_url: str | None = None
    message: str


class UploadVideoResponse(BaseModel):
    """Location of a video uploaded through the dashboard."""

    file_name: str
    file_path: str
    preview_path: str


class ZonePoint(BaseModel):
    """Normalized polygon point in the range [0, 1]."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class ZonePolygon(BaseModel):
    """Normalized polygon payload for queue zones."""

    points: list[ZonePoint]

    @model_validator(mode="after")
    def validate_points(self) -> "ZonePolygon":
        if len(self.points) < 3:
            raise ValueError("Zone polygon must contain at least 3 points.")
        return self


def _normalize_name(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Name must not be blank.")
    return trimmed


def _normalize_optional_string(value: str | None) -> str | None:
    if value is None:
        return None

    trimmed = value.strip()
    return trimmed or None


def _normalize_rtsp_url(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("RTSP URL must not be blank.")
    if not trimmed.lower().startswith("rtsp://"):
        raise ValueError("RTSP URL must start with rtsp://")
    return trimmed


def coerce_zone_polygon(points: object) -> ZonePolygon | None:
    """Convert raw stored point pairs into a normalized zone model when valid."""
    if not points:
        return None

    if not isinstance(points, (list, tuple)):
        return None

    try:
        raw_points = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return None

            raw_points.append({"x": float(point[0]), "y": float(point[1])})
    except (TypeError, ValueError, IndexError):
        return None

    try:
        return ZonePolygon.model_validate({"points": raw_points})
    except ValueError:
        return None


class QueueMetricsModel(BaseModel):
    """Frontend-facing queue metrics snapshot."""

    timestamp: float
    people_in_zone: int = Field(ge=0)
    arrival_rate: float = Field(ge=0.0)
    service_rate: float = Field(ge=0.0)
    wait_time_seconds: float | None = Field(default=None, ge=0.0)
    queue_stable: bool
    detections: list[list[float]] | None = None
    render_frame_jpeg_base64: str | None = None
    backend_annotations_active: bool = False


class FeedWebRTCTransportCapability(BaseModel):
    """WebRTC transport readiness for a single feed."""

    enabled: bool = False
    ready: bool = False
    source_mode: WebRTCTransportSourceMode = "none"
    path_name: str | None = None
    reason: str | None = None


class FeedMJPEGTransportCapability(BaseModel):
    """MJPEG transport readiness for a single feed."""

    enabled: bool = True
    ready: bool = False
    reason: str | None = None


class FeedTransportCapabilities(BaseModel):
    """Frontend-facing transport capability contract for one feed."""

    backend_annotations: bool = False
    webrtc: FeedWebRTCTransportCapability = Field(default_factory=FeedWebRTCTransportCapability)
    mjpeg: FeedMJPEGTransportCapability = Field(default_factory=FeedMJPEGTransportCapability)


class AlertModel(BaseModel):
    """Frontend-facing alert payload broadcast from the analysis pipeline."""

    alert_type: str
    severity: AlertSeverity
    message: str
    threshold_name: str
    current_value: float
    threshold_value: float
    frame_id: int = Field(ge=0)
    timestamp: datetime


class VideoFeed(BaseModel):
    """Configured feed plus its latest runtime state."""

    feed_id: str
    name: str
    source: str
    preview_path: str | None = None
    model_size: ModelSize = "n"
    status: FeedStatus
    created_at: datetime
    updated_at: datetime
    establishment_id: int | None = None
    caisse_id: int | None = None
    zone: ZonePolygon | None = None
    queue_length_warning: int = Field(default=8, ge=0)
    latest_metrics: QueueMetricsModel | None = None
    transport: FeedTransportCapabilities = Field(default_factory=FeedTransportCapabilities)
    last_error: str | None = None
    last_warning: str | None = None
    last_warning_code: str | None = None


class QueueThresholdConfig(BaseModel):
    """Per-feed queue length thresholds used by the worker and dashboard."""

    queue_length_warning: int = Field(default=8, ge=0)


class QueueThresholdUpdateRequest(BaseModel):
    """Payload used to update a feed's queue thresholds."""

    queue_length_warning: int = Field(ge=0)


class FeedSourceUpdateRequest(BaseModel):
    """Payload used to update a feed source after onboarding (for example IP changes)."""

    source: str = Field(min_length=1, max_length=512)
    rtsp_username: str | None = Field(default=None, max_length=120)
    rtsp_password: str | None = Field(default=None, max_length=120)
    rtsp_transport: RTSPTransport | None = None
    restart_if_running: bool = True

    @field_validator("source")
    @classmethod
    def validate_source_not_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Source must not be blank.")
        return trimmed

    @field_validator("rtsp_username", "rtsp_password")
    @classmethod
    def normalize_optional_rtsp_credentials(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)


class CreateFeedRequest(BaseModel):
    """Payload to register a new video feed."""

    name: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=512)
    model_size: ModelSize = "n"
    establishment_id: int | None = Field(default=None, ge=1)
    caisse_id: int | None = Field(default=None, ge=1)
    rtsp_username: str | None = Field(default=None, max_length=120)
    rtsp_password: str | None = Field(default=None, max_length=120)
    rtsp_transport: RTSPTransport | None = None

    @field_validator("rtsp_username", "rtsp_password")
    @classmethod
    def normalize_optional_rtsp_credentials(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)

    @model_validator(mode="after")
    def validate_rtsp_credentials(self) -> "CreateFeedRequest":
        if self.rtsp_password and not self.rtsp_username:
            raise ValueError("RTSP username is required when RTSP password is provided.")
        return self


class BatchRuntimeSettings(BaseModel):
    """Shared runtime options applied to every launched feed in a staged batch."""

    webhook_enabled: bool = True
    log_level: LogLevel = "INFO"


class BatchFeedDraft(CreateFeedRequest):
    """Single staged feed payload used by the future multi-source review flow."""

    client_id: str = Field(min_length=1, max_length=120)
    zone: ZonePolygon | None = None

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Client id must not be blank.")
        return trimmed


class BatchFeedLaunchRequest(BaseModel):
    """Contract for creating and optionally starting multiple staged feeds at once."""

    feeds: list[BatchFeedDraft] = Field(min_length=1, max_length=25)
    launch_mode: BatchLaunchMode = "create_and_start"
    runtime: BatchRuntimeSettings = Field(default_factory=BatchRuntimeSettings)


class BatchFeedLaunchItemResult(BaseModel):
    """Per-feed result returned from a batch launch attempt."""

    client_id: str = Field(min_length=1, max_length=120)
    status: BatchLaunchItemStatus
    feed: VideoFeed | None = None
    error: str | None = None


class BatchFeedLaunchSummary(BaseModel):
    """Aggregated counters for a batch launch response."""

    total: int = Field(ge=0)
    created: int = Field(ge=0)
    started: int = Field(ge=0)
    failed: int = Field(ge=0)


class BatchFeedLaunchResponse(BaseModel):
    """Response payload for the planned multi-source launch endpoint."""

    launch_mode: BatchLaunchMode
    runtime: BatchRuntimeSettings
    results: list[BatchFeedLaunchItemResult] = Field(default_factory=list)
    summary: BatchFeedLaunchSummary


class Establishment(BaseModel):
    """Frontend-facing establishment record."""

    id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    created_at: datetime


class CreateEstablishmentRequest(BaseModel):
    """Payload used to create a new establishment."""

    name: str = Field(max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_name(value)


class Caisse(BaseModel):
    """Frontend-facing caisse metadata record."""

    id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    establishment_id: int = Field(ge=1)
    created_at: datetime
    zone: ZonePolygon | None = None


class CreateCaisseRequest(BaseModel):
    """Payload used to create a new caisse inside an establishment."""

    name: str = Field(max_length=120)
    zone: ZonePolygon | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_name(value)


class RTSPConnectionTestRequest(BaseModel):
    """Payload used to validate an RTSP source before feed creation."""

    url: str = Field(max_length=512)
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=120)
    transport: RTSPTransport = "tcp"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _normalize_rtsp_url(value)

    @field_validator("username", "password")
    @classmethod
    def normalize_optional_credentials(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)


class RTSPConnectionTestResult(BaseModel):
    """Result of probing an RTSP source through the backend."""

    connected: bool
    transport: RTSPTransport
    resolution: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0.0)
    error: str | None = None


class RTSPSnapshotRequest(RTSPConnectionTestRequest):
    """Payload used to capture a preview frame from an RTSP source."""


class RTSPSnapshotResult(BaseModel):
    """Single preview frame captured from an RTSP source."""

    captured: bool
    transport: RTSPTransport
    resolution: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    image_data_url: str | None = None
    error: str | None = None


class FeedSnapshotResult(BaseModel):
    """Snapshot captured from an already-registered feed source."""

    feed_id: str
    source: str
    captured: bool
    resolution: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    image_data_url: str | None = None
    error: str | None = None


class WebRTCSessionDescription(BaseModel):
    """WebRTC session description used for browser-to-gateway signaling."""

    type: WebRTCSessionType
    sdp: str = Field(min_length=1, max_length=40000)

    @field_validator("sdp")
    @classmethod
    def validate_sdp_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("SDP must not be blank.")
        return value


class FeedWebRTCOfferRequest(BaseModel):
    """Frontend offer payload proxied to the MediaMTX WebRTC gateway."""

    offer: WebRTCSessionDescription

    @model_validator(mode="after")
    def validate_offer_type(self) -> "FeedWebRTCOfferRequest":
        if self.offer.type != "offer":
            raise ValueError("Offer description type must be 'offer'.")
        return self


class FeedWebRTCOfferResponse(BaseModel):
    """Gateway answer returned to the browser for WebRTC preview."""

    answer: WebRTCSessionDescription


class ONVIFDiscoveryRequest(BaseModel):
    """Payload used to trigger ONVIF device discovery."""

    timeout_seconds: float = Field(default=5.0, gt=0.0, le=30.0)


class ONVIFDevice(BaseModel):
    """Discovered ONVIF device details returned to the frontend."""

    ip: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    manufacturer: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=255)
    serial: str = Field(min_length=1, max_length=255)
    hardware: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    services: dict[str, str] = Field(default_factory=dict)
    xaddrs: str | None = Field(default=None, max_length=2048)


class ONVIFStreamResolutionRequest(BaseModel):
    """Payload used to resolve RTSP stream URLs for a discovered ONVIF device."""

    device: ONVIFDevice
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=120)

    @field_validator("username", "password")
    @classmethod
    def normalize_optional_credentials(cls, value: str | None) -> str | None:
        return _normalize_optional_string(value)


class ONVIFStream(BaseModel):
    """Resolved RTSP stream candidate returned from an ONVIF device."""

    url: str = Field(min_length=1, max_length=512)


class ONVIFCameraTestRequest(ONVIFStreamResolutionRequest):
    """Payload used to test a discovered ONVIF camera end-to-end."""

    transport: RTSPTransport = "tcp"


class ONVIFCameraTestResult(BaseModel):
    """Result of resolving and testing a discovered ONVIF camera."""

    connected: bool
    transport: RTSPTransport
    stream_count: int = Field(ge=0)
    tested_stream: ONVIFStream | None = None
    streams: list[ONVIFStream] = Field(default_factory=list)
    resolution: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0.0)
    error: str | None = None


class ZoneUpdateRequest(BaseModel):
    """Payload for assigning or replacing a feed's queue zone."""

    zone: ZonePolygon


class SystemHealth(BaseModel):
    """Top-level API health summary for the dashboard."""

    status: Literal["ok", "degraded"]
    api_version: str
    total_feeds: int = Field(ge=0)
    active_feeds: int = Field(ge=0)
    websocket_clients: int = Field(ge=0)
    timestamp: datetime


class FeedSnapshotEvent(BaseModel):
    """Initial event sent when a WebSocket client connects."""

    event: Literal["snapshot"] = "snapshot"
    payload: dict[str, list[VideoFeed]]


class FeedStatusEventPayload(BaseModel):
    """Feed lifecycle update broadcast over WebSocket."""

    action: Literal["created", "updated", "deleted"]
    feed: VideoFeed | None = None
    feed_id: str | None = None


class FeedStatusEvent(BaseModel):
    """WebSocket event used for feed lifecycle changes."""

    event: Literal["feed_status"] = "feed_status"
    payload: FeedStatusEventPayload


class MetricsUpdateEventPayload(BaseModel):
    """Latest metrics snapshot for a running feed."""

    feed_id: str
    metrics: QueueMetricsModel


class MetricsUpdateEvent(BaseModel):
    """WebSocket event carrying queue metrics updates."""

    event: Literal["metrics_update"] = "metrics_update"
    payload: MetricsUpdateEventPayload


class AlertFiredEventPayload(BaseModel):
    """Alert raised by the queue analysis pipeline."""

    feed_id: str
    alert: AlertModel


class AlertFiredEvent(BaseModel):
    """WebSocket event carrying threshold alerts."""

    event: Literal["alert_fired"] = "alert_fired"
    payload: AlertFiredEventPayload


class SystemWarningEventPayload(BaseModel):
    """Non-fatal warning emitted by the worker pipeline."""

    feed_id: str
    code: str
    message: str
    timestamp: datetime


class SystemWarningEvent(BaseModel):
    """WebSocket event carrying worker warnings."""

    event: Literal["system_warning"] = "system_warning"
    payload: SystemWarningEventPayload