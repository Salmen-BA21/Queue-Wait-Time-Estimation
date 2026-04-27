# Sprint 2: Backend Services & API Integration

**Focus:** Transforming the pipeline into a managed service with IP camera support and API access.

## Accomplishments

- ✅ **RTSP & ONVIF:** Native support for IP cameras, including automated discovery and secure stream handling.
- ✅ **BFF API:** Implementation of a Backend-for-Frontend (BFF) to manage feeds, metadata, and snapshots.
- ✅ **Auth & RBAC:** Session-based authentication system with Admin and Manager roles.
- ✅ **Video Transport:** High-performance video delivery via WebRTC with MJPEG fallbacks.
- ✅ **Persistence Layer:** SQLite integration for storing configurations, historical alerts, and user data.

## Key Endpoints
- `GET /api/feeds` - List all monitored sources.
- `POST /api/auth/login` - Secure session bootstrap.
- `GET /api/onvif/discover` - Automatic camera discovery.

## Technical Notes
- `MediaMTX` is used as the primary media server for WebRTC/RTSP orchestration.
- `FastAPI` powers the BFF layer for high-concurrency event handling.
