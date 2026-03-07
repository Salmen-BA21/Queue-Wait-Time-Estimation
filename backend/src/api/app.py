"""FastAPI application for the QueueVision backend-for-frontend layer."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.models import (
    ApiResponse,
    CreateFeedRequest,
    FeedSnapshotEvent,
    SystemHealth,
    VideoFeed,
    ZoneUpdateRequest,
)
from src.api.runtime import FeedRegistry, WebSocketHub
from src.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize runtime services when the API starts."""
    init_db()
    broadcaster = WebSocketHub()
    registry = FeedRegistry(broadcaster=broadcaster)
    app.state.broadcaster = broadcaster
    app.state.registry = registry
    yield


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
    return app.state.registry


def get_broadcaster() -> WebSocketHub:
    """Typed accessor for the websocket broadcaster stored in app state."""
    return app.state.broadcaster


@app.get("/api/feeds", response_model=ApiResponse[list[VideoFeed]])
async def list_feeds() -> ApiResponse[list[VideoFeed]]:
    feeds = await get_registry().list_feeds()
    return ApiResponse(data=feeds)


@app.post("/api/feeds", response_model=ApiResponse[VideoFeed], status_code=201)
async def create_feed(request: CreateFeedRequest) -> ApiResponse[VideoFeed]:
    feed = await get_registry().create_feed(
        name=request.name,
        source=request.source,
        establishment_id=request.establishment_id,
        caisse_id=request.caisse_id,
    )
    return ApiResponse(data=feed, message="Feed registered successfully.")


@app.get("/api/feeds/{feed_id}/status", response_model=ApiResponse[VideoFeed])
async def get_feed_status(feed_id: str) -> ApiResponse[VideoFeed]:
    feed = await get_registry().get_feed(feed_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found.")
    return ApiResponse(data=feed)


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
    finally:
        await broadcaster.disconnect(websocket)