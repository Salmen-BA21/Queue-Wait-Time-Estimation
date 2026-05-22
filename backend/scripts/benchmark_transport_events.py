"""Summarize dashboard transport latency/fps telemetry from worker event logs.

Usage:
    python -m backend.scripts.benchmark_transport_events --events-file backend/data/runtime/<feed>.events.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((p / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def iter_telemetry(event_path: Path) -> Iterable[dict[str, float]]:
    for line in event_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event = payload.get("event")
        body = payload.get("payload")
        if not isinstance(body, dict):
            continue
        performance = body.get("performance")
        if event not in {"metrics_update", "transport_status"} or not isinstance(performance, dict):
            continue
        item: dict[str, float] = {}
        for key in (
            "dashboard_emit_fps",
            "dashboard_jpeg_encode_ms",
            "queue_age_ms",
            "end_to_end_frame_age_ms",
        ):
            value = performance.get(key)
            if isinstance(value, (int, float)):
                item[key] = float(value)
        if item:
            yield item


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute p50/p95 transport telemetry from worker event logs.")
    parser.add_argument("--events-file", required=True, help="Path to worker .events.jsonl log file.")
    args = parser.parse_args()

    event_path = Path(args.events_file).expanduser().resolve()
    if not event_path.exists():
        raise SystemExit(f"Events file not found: {event_path}")

    emit_fps: list[float] = []
    encode_ms: list[float] = []
    queue_age_ms: list[float] = []
    frame_age_ms: list[float] = []

    for item in iter_telemetry(event_path):
        if "dashboard_emit_fps" in item:
            emit_fps.append(item["dashboard_emit_fps"])
        if "dashboard_jpeg_encode_ms" in item:
            encode_ms.append(item["dashboard_jpeg_encode_ms"])
        if "queue_age_ms" in item:
            queue_age_ms.append(item["queue_age_ms"])
        if "end_to_end_frame_age_ms" in item:
            frame_age_ms.append(item["end_to_end_frame_age_ms"])

    print(f"events_file={event_path}")
    print(f"samples={len(frame_age_ms)}")
    print(f"emit_fps_p50={percentile(emit_fps, 50):.2f} emit_fps_p95={percentile(emit_fps, 95):.2f}")
    print(f"encode_ms_p50={percentile(encode_ms, 50):.2f} encode_ms_p95={percentile(encode_ms, 95):.2f}")
    print(f"queue_age_ms_p50={percentile(queue_age_ms, 50):.2f} queue_age_ms_p95={percentile(queue_age_ms, 95):.2f}")
    print(f"e2e_frame_age_ms_p50={percentile(frame_age_ms, 50):.2f} e2e_frame_age_ms_p95={percentile(frame_age_ms, 95):.2f}")


if __name__ == "__main__":
    main()
