# MJPEG Streaming Optimization Requirements

## Introduction

This document specifies requirements for optimizing MJPEG video streaming performance in the QueueVision web dashboard. The current implementation experiences slow streaming performance, impacting real-time monitoring capabilities. The optimization will focus on improving frame encoding efficiency, adaptive quality control, network transmission optimization, and intelligent frame rate management to deliver smooth, low-latency video streaming to web clients.

## Glossary

- MJPEG_Streamer: The backend component responsible for encoding frames and streaming them via multipart/x-mixed-replace HTTP responses
- Frame_Encoder: The component that converts raw video frames to JPEG format using OpenCV
- Quality_Controller: The component that dynamically adjusts JPEG compression quality based on performance metrics
- Frame_Rate_Manager: The component that controls frame emission intervals and frame skipping logic
- Stream_Buffer: The in-memory buffer holding encoded frames awaiting transmission to clients
- Dashboard_Client: The web browser receiving and displaying the MJPEG stream
- Bandwidth_Monitor: The component that tracks network throughput and latency metrics
- Adaptive_Scaler: The component that dynamically adjusts frame resolution based on performance constraints

## Requirements

### Requirement 1: JPEG Encoding Optimization

**User Story:** As a system administrator, I want optimized JPEG encoding parameters, so that frames are compressed efficiently without excessive CPU usage.

**Acceptance Criteria**
- THE Frame_Encoder SHALL use OpenCV JPEG encoding with configurable quality parameter (1-100)
- THE Frame_Encoder SHALL support configurable JPEG optimization flag to enable entropy optimization
- THE Frame_Encoder SHALL support configurable progressive JPEG encoding for improved perceived loading
- WHEN encoding a frame, THE Frame_Encoder SHALL apply the configured quality and optimization parameters
- THE Frame_Encoder SHALL measure and log encoding time per frame
- WHERE hardware acceleration is available, THE Frame_Encoder SHALL utilize GPU-accelerated encoding

### Requirement 2: Adaptive Quality Control

**User Story:** As a dashboard user, I want video quality to adapt to network conditions, so that streaming remains smooth even with bandwidth constraints.

**Acceptance Criteria**
- THE Quality_Controller SHALL monitor frame encoding time and adjust quality when encoding exceeds target latency
- WHEN average encoding time exceeds 50ms over 10 frames, THE Quality_Controller SHALL decrease JPEG quality by 5 points
- WHEN average encoding time is below 20ms over 10 frames AND quality is below maximum, THE Quality_Controller SHALL increase JPEG quality by 5 points
- THE Quality_Controller SHALL maintain JPEG quality within configured minimum and maximum bounds
- THE Quality_Controller SHALL expose current quality level via metrics endpoint
- THE Quality_Controller SHALL log quality adjustment events with timestamp and reason

### Requirement 3: Dynamic Frame Resolution Scaling

**User Story:** As a system administrator, I want automatic frame resolution adjustment, so that streaming performance adapts to system load.

**Acceptance Criteria**
- THE Adaptive_Scaler SHALL support configurable target resolutions (e.g., 1920x1080, 1280x720, 640x480, 320x240)
- WHEN system CPU usage exceeds 80% for 5 consecutive seconds, THE Adaptive_Scaler SHALL reduce frame resolution to the next lower tier
- WHEN system CPU usage is below 50% for 10 consecutive seconds AND resolution is below maximum, THE Adaptive_Scaler SHALL increase frame resolution to the next higher tier
- THE Adaptive_Scaler SHALL maintain aspect ratio when scaling frames
- THE Adaptive_Scaler SHALL use high-quality interpolation (INTER_AREA for downscaling, INTER_CUBIC for upscaling)
- THE Adaptive_Scaler SHALL expose current resolution via metrics endpoint

### Requirement 4: Intelligent Frame Rate Management

**User Story:** As a dashboard user, I want consistent frame rates without dropped frames, so that video playback is smooth.

**Acceptance Criteria**
- THE Frame_Rate_Manager SHALL support configurable target frame rates (5, 10, 15, 20, 25, 30 FPS)
- THE Frame_Rate_Manager SHALL calculate frame emission interval from target FPS (interval = 1.0 / target_fps)
- WHEN the time since last frame emission exceeds the calculated interval, THE Frame_Rate_Manager SHALL emit the next available frame
- THE Frame_Rate_Manager SHALL skip intermediate frames when processing cannot keep pace with target FPS
- THE Frame_Rate_Manager SHALL maintain frame emission timing accuracy within ±10ms of target interval
- THE Frame_Rate_Manager SHALL track and expose frame skip count via metrics endpoint

### Requirement 5: Stream Buffer Management

**User Story:** As a system administrator, I want efficient buffer management, so that memory usage remains bounded and latency is minimized.

**Acceptance Criteria**
- THE Stream_Buffer SHALL maintain a fixed-size circular buffer for encoded frames
- THE Stream_Buffer SHALL support configurable buffer size (default: 3 frames)
- WHEN the buffer is full AND a new frame arrives, THE Stream_Buffer SHALL discard the oldest frame
- THE Stream_Buffer SHALL provide non-blocking read access to the most recent frame
- THE Stream_Buffer SHALL track buffer utilization percentage and expose it via metrics
- WHEN buffer utilization exceeds 90% for 5 consecutive seconds, THE Stream_Buffer SHALL log a warning

### Requirement 6: Network Transmission Optimization

**User Story:** As a dashboard user, I want minimal network latency, so that I can monitor queues in real-time.

**Acceptance Criteria**
- THE MJPEG_Streamer SHALL set HTTP response headers to disable caching (Cache-Control: no-cache, no-store)
- THE MJPEG_Streamer SHALL set X-Accel-Buffering: no to disable proxy buffering
- THE MJPEG_Streamer SHALL use chunked transfer encoding for streaming responses
- THE MJPEG_Streamer SHALL send multipart boundary markers immediately before each frame
- THE MJPEG_Streamer SHALL include Content-Length header for each JPEG part
- WHEN a client disconnects, THE MJPEG_Streamer SHALL immediately release associated resources

### Requirement 7: Bandwidth Monitoring and Metrics

**User Story:** As a system administrator, I want visibility into streaming performance, so that I can diagnose issues and optimize configuration.

**Acceptance Criteria**
- THE Bandwidth_Monitor SHALL track bytes transmitted per second for each active stream
- THE Bandwidth_Monitor SHALL calculate average frame size over a 10-second window
- THE Bandwidth_Monitor SHALL track number of active stream connections
- THE Bandwidth_Monitor SHALL measure end-to-end latency from frame capture to transmission
- THE Bandwidth_Monitor SHALL expose metrics via `/api/metrics/streaming` endpoint
- THE Bandwidth_Monitor SHALL include metrics: `active_streams`, `bytes_per_second`, `avg_frame_size_kb`, `avg_latency_ms`, `current_fps`, `current_quality`, `current_resolution`

### Requirement 8: Configuration Management

**User Story:** As a system administrator, I want centralized streaming configuration, so that I can tune performance without code changes.

**Acceptance Criteria**
- THE System SHALL support environment variable `MJPEG_TARGET_FPS` (default: 15)
- THE System SHALL support environment variable `MJPEG_JPEG_QUALITY_MIN` (default: 20)
- THE System SHALL support environment variable `MJPEG_JPEG_QUALITY_MAX` (default: 80)
- THE System SHALL support environment variable `MJPEG_JPEG_QUALITY_DEFAULT` (default: 30)
- THE System SHALL support environment variable `MJPEG_ENABLE_ADAPTIVE_QUALITY` (default: true)
- THE System SHALL support environment variable `MJPEG_ENABLE_ADAPTIVE_RESOLUTION` (default: false)
- THE System SHALL support environment variable `MJPEG_BUFFER_SIZE` (default: 3)
- THE System SHALL support environment variable `MJPEG_TARGET_RESOLUTIONS` (default: "1920x1080,1280x720,640x480")
- THE System SHALL validate all configuration values at startup and log warnings for invalid values
- WHEN an invalid configuration value is detected, THE System SHALL use the documented default value

### Requirement 9: Client Connection Management

**User Story:** As a system administrator, I want efficient handling of multiple concurrent streams, so that system resources are used optimally.

**Acceptance Criteria**
- THE MJPEG_Streamer SHALL support configurable maximum concurrent connections per feed (default: 10)
- WHEN maximum connections is reached, THE MJPEG_Streamer SHALL reject new connection attempts with HTTP 503
- THE MJPEG_Streamer SHALL implement per-client frame subscription to avoid duplicate encoding
- THE MJPEG_Streamer SHALL detect stale connections via idle timeout (default: 12 seconds)
- WHEN a connection is idle beyond timeout, THE MJPEG_Streamer SHALL close the connection and release resources
- THE MJPEG_Streamer SHALL track connection duration and expose it via metrics

### Requirement 10: Performance Monitoring and Alerting

**User Story:** As a system administrator, I want automatic alerts for performance degradation, so that I can proactively address issues.

**Acceptance Criteria**
- THE System SHALL monitor average frame encoding time over a 30-second window
- WHEN average encoding time exceeds 100ms, THE System SHALL log a warning with current configuration
- THE System SHALL monitor frame drop rate (skipped frames / total frames)
- WHEN frame drop rate exceeds 20% over 60 seconds, THE System SHALL log a warning
- THE System SHALL monitor stream buffer overflow events
- WHEN buffer overflows occur more than 5 times in 60 seconds, THE System SHALL log a critical warning
- THE System SHALL include performance metrics in existing webhook notifications to n8n

### Requirement 11: Graceful Degradation

**User Story:** As a dashboard user, I want streaming to continue even under high load, so that I maintain visibility into queue status.

**Acceptance Criteria**
- WHEN system resources are constrained, THE System SHALL prioritize frame delivery over frame quality
- WHEN encoding time consistently exceeds frame interval, THE System SHALL automatically reduce quality before reducing frame rate
- WHEN quality reaches minimum AND encoding still exceeds frame interval, THE System SHALL reduce frame rate
- WHEN resolution scaling is enabled AND quality and frame rate are at minimum, THE System SHALL reduce resolution
- THE System SHALL log all degradation actions with timestamp and triggering condition
- WHEN system resources recover, THE System SHALL gradually restore quality, frame rate, and resolution in reverse order

### Requirement 12: Backward Compatibility

**User Story:** As a developer, I want existing API contracts maintained, so that frontend clients continue to work without changes.

**Acceptance Criteria**
- THE System SHALL maintain the existing `/api/feeds/{feed_id}/stream` endpoint path
- THE System SHALL maintain the multipart/x-mixed-replace content type
- THE System SHALL maintain existing HTTP response headers
- THE System SHALL maintain existing authentication and authorization requirements
- THE System SHALL maintain existing error response formats
- WHERE new configuration options are added, THE System SHALL provide backward-compatible defaults

---

*Document created: MJPEG streaming optimization requirements for QueueVision.*
