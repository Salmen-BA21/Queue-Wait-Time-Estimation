"""In-memory runtime services for the FastAPI backend-for-frontend layer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from src.api.models import FeedStatusEvent, FeedStatusEventPayload, VideoFeed, ZonePolygon
from src.database import get_caisse_by_id, update_caisse_zone_points


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class FeedRecord:
    """Mutable in-memory representation of a configured feed."""

    feed_id: str
    name: str
    source: str
    status: str
    created_at: datetime
    updated_at: datetime
    establishment_id: int | None = None
    caisse_id: int | None = None
    zone: ZonePolygon | None = None
    latest_metrics: dict | None = None
    last_error: str | None = None

    def to_model(self) -> VideoFeed:
        """Convert the internal dataclass into the public API model."""
        return VideoFeed.model_validate(self.__dict__)


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
        action: str,
        feed: VideoFeed | None = None,
        feed_id: str | None = None,
    ) -> None:
        event = FeedStatusEvent(
            payload=FeedStatusEventPayload(action=action, feed=feed, feed_id=feed_id),
        )
        await self.broadcast(event.model_dump(mode="json"))

    @property
    def client_count(self) -> int:
        return len(self._clients)


class FeedRegistry:
    """Stores configured feeds and exposes async-safe CRUD operations."""

    def __init__(self, broadcaster: WebSocketHub) -> None:
        self._broadcaster = broadcaster
        self._feeds: dict[str, FeedRecord] = {}
        self._lock = asyncio.Lock()

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
        establishment_id: int | None = None,
        caisse_id: int | None = None,
    ) -> VideoFeed:
        zone = self._load_saved_zone(caisse_id)
        now = utc_now()
        record = FeedRecord(
            feed_id=str(uuid4()),
            name=name.strip(),
            source=source.strip(),
            status="created",
            created_at=now,
            updated_at=now,
            establishment_id=establishment_id,
            caisse_id=caisse_id,
            zone=zone,
        )
        async with self._lock:
            self._feeds[record.feed_id] = record
            model = record.to_model()

        await self._broadcaster.broadcast_feed_event(action="created", feed=model)
        return model

    async def delete_feed(self, feed_id: str) -> bool:
        async with self._lock:
            removed = self._feeds.pop(feed_id, None)

        if removed is None:
            return False

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
            update_caisse_zone_points(
                record.caisse_id,
                [[point.x, point.y] for point in zone.points],
            )

        await self._broadcaster.broadcast_feed_event(action="updated", feed=model)
        return model

    async def clear(self) -> None:
        async with self._lock:
            self._feeds.clear()

    def _load_saved_zone(self, caisse_id: int | None) -> ZonePolygon | None:
        if caisse_id is None:
            return None

        caisse = get_caisse_by_id(caisse_id)
        if not caisse or not caisse.get("zone_points"):
            return None

        points = caisse["zone_points"]
        return ZonePolygon.model_validate(
            {"points": [{"x": point[0], "y": point[1]} for point in points]}
        )