# Sprint 1: Perception & Queue Analytics

**Focus:** Building the core pipeline from raw video to queue metrics.

## Accomplishments

- ✅ **Environment Setup:** Python environment and YOLOv8/v26 model integration.
- ✅ **Detection & Tracking:** Reliable person detection and identity continuity using ByteTrack.
- ✅ **Zone Filtering:** Implementation of polygon-based ROI filtering for queue areas.
- ✅ **Queue Modeling:** M/M/1 queueing theory implementation for arrival/service rates and wait time.
- ✅ **Multi-Video GUI:** Support for configuring and analyzing multiple video sources simultaneously.

## Metrics Delivered
- People in zone (Occupancy)
- Arrival rate (λ)
- Service rate (μ)
- Estimated wait time (W)
- Queue stability flag

## Technical Notes
- Uses `ultralytics` for inference.
- Uses `supervision` for zone management and tracking overlays.
- All uncertainty quantification features have been excluded to maintain focus on core metric stability.
