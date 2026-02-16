# Daily Progress Log – 2026-02-12  
**Phase:** 1 – Research & Core Implementation  
**Task completed:** Core Detection Pipeline & Queueing Theory Integration  

## Summary (1–2 sentences)
Implemented the fundamental computer vision pipeline using YOLOv11 and ByteTrack, and integrated an M/M/1 queuing model to estimate real-time service metrics from video data.

## What I did today (step-by-step)
1. Developed `src/detector.py`: Wrapper for YOLOv11 to filter for "person" class and optimize inference.
2. Developed `src/tracker.py`: Integrated `supervision.ByteTrack` to maintain unique IDs for individuals across frames.
3. Developed `src/zone_manager.py`: Implemented `PolygonZone` to define wait-areas and calculate "count-in-zone".
4. Developed `src/queue_analyzer.py`: Formulated the mathematical backend to calculate:
   - **Arrival Rate ($\lambda$):** New people joining the queue per minute.
   - **Service Rate ($\mu$):** Processing speed at the cashier.
   - **Wait Time ($W$):** Expected time an individual spends in the queue.
5. Created the modular CLI structure in `src/main.py` with `argparse`.

## Important code / configuration
**src/queue_analyzer.py** (Wait-time logic)
```python
# M/M/1 estimation formula
# W = L / (lambda * (1 - rho)) or simplified Little's Law
wait_time = current_count / arrival_rate if arrival_rate > 0 else 0
```

## Results / Observations
- **Accuracy**: YOLOv11n provides excellent accuracy for person detection in indoor environments.
- **Latency**: The full pipeline (Detection + Tracking + Math) runs at ~25+ FPS on CPU, meeting real-time requirements.
- **Stability**: ByteTrack successfully handles partial occlusions when people walk behind each other in line.

## Problems encountered & solutions
- **Problem:** Fluctuating queue counts causing "jumpy" wait-time estimates.
  - **→ Solution:** Implemented an exponential moving average (EMA) in `QueueAnalyzer` to smooth the metrics over time.

## Decisions made / Notes for later
- Used **Supervision** library for ROI (Region of Interest) management as it's more robust than manual OpenCV contour checking.
- Decided to support JSON-based polygon points via CLI for easy external configuration.

## Time spent
~6 hours

## Next planned tasks
1. Develop an interactive GUI to replace the CLI for non-technical users.
2. Add video file selection and visual "Zone Selector" tool.

**Mood / feeling:** Extremely productive day. The core mathematical model is working as expected.
