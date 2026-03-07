"""Pydantic API models for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator


FeedStatus = Literal["created", "initializing", "running", "stopped", "error"]
EventType = Literal["snapshot", "feed_status", "metrics_update", "system_warning"]

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Consistent response envelope for frontend-facing endpoints."""

    success: bool = True
    data: T
    message: str | None = None


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


class QueueMetricsModel(BaseModel):
    """Frontend-facing queue metrics snapshot."""

    timestamp: float
    people_in_zone: int = Field(ge=0)
    arrival_rate: float = Field(ge=0.0)
    service_rate: float = Field(ge=0.0)
    wait_time_seconds: float | None = Field(default=None, ge=0.0)
    wait_time_ci: list[float] | None = None
    uncertainty_level: str
    queue_stable: bool


class VideoFeed(BaseModel):
    """Configured feed plus its latest runtime state."""

    feed_id: str
    name: str
    source: str
    status: FeedStatus
    created_at: datetime
    updated_at: datetime
    establishment_id: int | None = None
    caisse_id: int | None = None
    zone: ZonePolygon | None = None
    latest_metrics: QueueMetricsModel | None = None
    last_error: str | None = None


class CreateFeedRequest(BaseModel):
    """Payload to register a new video feed."""

    name: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=512)
    establishment_id: int | None = Field(default=None, ge=1)
    caisse_id: int | None = Field(default=None, ge=1)


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