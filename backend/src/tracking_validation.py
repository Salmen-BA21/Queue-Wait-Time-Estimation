from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.config import AppConfig
from src.detector import PersonDetector
from src.queue_analyzer import QueueAnalyzer
from src.tracker import ObjectTracker
from src.video_capture import open_video_source
from src.zone_manager import ZoneManager


@dataclass
class DetectionRecord:
    frame_id: int
    timestamp_sec: float
    clip: str
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    tracker_id: int
    in_zone: bool


@dataclass
class ClipMetrics:
    clip: str
    frame_count: int
    detection_count: int
    tracked_detection_count: int
    id_switch_count: int
    track_fragmentation_count: int
    lost_recovered_count: int
    average_track_lifetime_frames: float
    arrivals: int
    departures: int
    final_occupancy: int
    occupancy_drift: int
    id_switch_rate: float
    fragmentation_rate: float


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


def summarize_records(records: list[DetectionRecord], *, iou_match_threshold: float = 0.6, recovery_window_frames: int = 60) -> ClipMetrics:
    if not records:
        return ClipMetrics(
            clip="",
            frame_count=0,
            detection_count=0,
            tracked_detection_count=0,
            id_switch_count=0,
            track_fragmentation_count=0,
            lost_recovered_count=0,
            average_track_lifetime_frames=0.0,
            arrivals=0,
            departures=0,
            final_occupancy=0,
            occupancy_drift=0,
            id_switch_rate=0.0,
            fragmentation_rate=0.0,
        )

    clip_name = records[0].clip
    by_frame: dict[int, list[DetectionRecord]] = {}
    for row in records:
        by_frame.setdefault(row.frame_id, []).append(row)

    sorted_frames = sorted(by_frame)
    previous: list[DetectionRecord] = []
    id_switches = 0
    fragments = 0

    for frame_id in sorted_frames:
        current = by_frame[frame_id]
        assigned_prev: set[int] = set()
        for cur in current:
            if cur.tracker_id < 0:
                continue
            best_idx = -1
            best_iou = 0.0
            for idx, prev in enumerate(previous):
                if idx in assigned_prev or prev.tracker_id < 0:
                    continue
                overlap = _iou((cur.x1, cur.y1, cur.x2, cur.y2), (prev.x1, prev.y1, prev.x2, prev.y2))
                if overlap > best_iou:
                    best_iou = overlap
                    best_idx = idx
            if best_idx >= 0 and best_iou >= iou_match_threshold:
                assigned_prev.add(best_idx)
                prev_tid = previous[best_idx].tracker_id
                if prev_tid != cur.tracker_id:
                    id_switches += 1
                    fragments += 1
        previous = current

    tracker_frames: dict[int, list[int]] = {}
    for row in records:
        if row.tracker_id >= 0:
            tracker_frames.setdefault(row.tracker_id, []).append(row.frame_id)

    recovered = 0
    for frames in tracker_frames.values():
        frames_sorted = sorted(set(frames))
        for idx in range(1, len(frames_sorted)):
            gap = frames_sorted[idx] - frames_sorted[idx - 1]
            if 1 < gap <= recovery_window_frames:
                recovered += 1

    lifetimes = [len(set(frames)) for frames in tracker_frames.values()]
    average_lifetime = float(sum(lifetimes) / len(lifetimes)) if lifetimes else 0.0

    in_zone_by_frame: dict[int, set[int]] = {}
    for frame_id, frame_rows in by_frame.items():
        in_zone_ids = {r.tracker_id for r in frame_rows if r.in_zone and r.tracker_id >= 0}
        in_zone_by_frame[frame_id] = in_zone_ids

    arrivals = 0
    departures = 0
    previous_ids: set[int] = set()
    for frame_id in sorted_frames:
        cur_ids = in_zone_by_frame[frame_id]
        arrivals += len(cur_ids - previous_ids)
        departures += len(previous_ids - cur_ids)
        previous_ids = cur_ids

    final_occupancy = len(previous_ids)
    occupancy_drift = abs((arrivals - departures) - final_occupancy)

    tracked_count = sum(1 for row in records if row.tracker_id >= 0)
    detection_count = len(records)
    max_frame = max(sorted_frames) if sorted_frames else 0
    frame_count = max_frame

    id_switch_rate = (id_switches / tracked_count) if tracked_count else 0.0
    fragmentation_rate = (fragments / tracked_count) if tracked_count else 0.0

    return ClipMetrics(
        clip=clip_name,
        frame_count=frame_count,
        detection_count=detection_count,
        tracked_detection_count=tracked_count,
        id_switch_count=id_switches,
        track_fragmentation_count=fragments,
        lost_recovered_count=recovered,
        average_track_lifetime_frames=round(average_lifetime, 3),
        arrivals=arrivals,
        departures=departures,
        final_occupancy=final_occupancy,
        occupancy_drift=occupancy_drift,
        id_switch_rate=round(id_switch_rate, 6),
        fragmentation_rate=round(fragmentation_rate, 6),
    )


def run_clip_evaluation(
    clip_path: Path,
    *,
    model_path: str,
    confidence: float,
    detector_imgsz: int,
    process_every_n_frames: int,
    tracker_frame_rate: int,
    tracker_buffer: int,
    zone_points: list[list[float]] | None = None,
) -> list[DetectionRecord]:
    detector = PersonDetector(
        model_path=model_path,
        confidence=confidence,
        device="auto",
        image_size=detector_imgsz if detector_imgsz > 0 else None,
    )
    tracker = ObjectTracker(frame_rate=tracker_frame_rate, track_buffer=tracker_buffer)
    analyzer = QueueAnalyzer()

    records: list[DetectionRecord] = []

    stream = open_video_source(str(clip_path))
    with stream:
        zone = ZoneManager(
            polygon_points=zone_points if zone_points else [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            frame_resolution=stream.resolution,
        )
        stride = max(1, int(process_every_n_frames))
        frame_id = 0
        for frame in stream.frames():
            frame_id += 1
            if frame_id % stride != 0:
                continue

            detections = detector.detect(frame)
            tracked = tracker.update(detections)
            in_zone = zone.trigger(tracked)
            analyzer.update(in_zone, tracked.tracker_id)

            for idx, box in enumerate(tracked.xyxy):
                tracker_id = -1
                if tracked.tracker_id is not None and idx < len(tracked.tracker_id):
                    tracker_id = int(tracked.tracker_id[idx])

                confidence_value = 0.0
                if tracked.confidence is not None and idx < len(tracked.confidence):
                    confidence_value = float(tracked.confidence[idx])

                class_id = -1
                if tracked.class_id is not None and idx < len(tracked.class_id):
                    class_id = int(tracked.class_id[idx])

                records.append(
                    DetectionRecord(
                        frame_id=frame_id,
                        timestamp_sec=frame_id / max(float(stream.fps), 1.0),
                        clip=clip_path.name,
                        x1=float(box[0]),
                        y1=float(box[1]),
                        x2=float(box[2]),
                        y2=float(box[3]),
                        confidence=confidence_value,
                        class_id=class_id,
                        tracker_id=tracker_id,
                        in_zone=bool(in_zone[idx]) if idx < len(in_zone) else False,
                    )
                )

    return records


def _write_records_csv(path: Path, records: list[DetectionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(asdict(records[0]).keys()) if records else [
            "frame_id", "timestamp_sec", "clip", "x1", "y1", "x2", "y2", "confidence", "class_id", "tracker_id", "in_zone"
        ])
        writer.writeheader()
        for row in records:
            writer.writerow(asdict(row))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)


def evaluate_manifest(
    manifest_path: Path,
    *,
    mode: str,
    output_dir: Path,
    compare_previous: bool,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    model = manifest.get("defaults", {}).get("model_path", "yolo26n.pt")
    confidence = float(manifest.get("defaults", {}).get("confidence", 0.3))
    imgsz = int(manifest.get("defaults", {}).get("detector_imgsz", 512))
    stride = int(manifest.get("defaults", {}).get("process_every_n_frames", 1))
    tracker_buffer = int(manifest.get("defaults", {}).get("track_buffer", 60))

    clips: list[dict[str, Any]] = manifest.get("clips", [])
    if mode == "quick":
        clips = [c for c in clips if c.get("quick", False)]

    reports: list[dict[str, Any]] = []
    failures: list[str] = []

    for clip in clips:
        clip_path = (manifest_path.parent / clip["path"]).resolve()
        if not clip_path.exists():
            failures.append(f"missing clip file: {clip_path}")
            continue

        records = run_clip_evaluation(
            clip_path,
            model_path=model,
            confidence=confidence,
            detector_imgsz=imgsz,
            process_every_n_frames=stride,
            tracker_frame_rate=int(clip.get("fps", 30)),
            tracker_buffer=tracker_buffer,
            zone_points=clip.get("zone_points"),
        )
        metrics = summarize_records(records)

        clip_output_dir = output_dir / clip.get("id", clip_path.stem)
        _write_records_csv(clip_output_dir / "detections.csv", records)

        metric_dict = asdict(metrics)
        metric_dict["clip_id"] = clip.get("id", clip_path.stem)

        thresholds = clip.get("thresholds", {})
        if metric_dict["id_switch_rate"] > float(thresholds.get("max_id_switch_rate", 1.0)):
            failures.append(f"{clip.get('id')}: id_switch_rate={metric_dict['id_switch_rate']}")
        if metric_dict["fragmentation_rate"] > float(thresholds.get("max_fragmentation_rate", 1.0)):
            failures.append(f"{clip.get('id')}: fragmentation_rate={metric_dict['fragmentation_rate']}")
        if metric_dict["occupancy_drift"] > int(thresholds.get("max_occupancy_drift", 1_000_000)):
            failures.append(f"{clip.get('id')}: occupancy_drift={metric_dict['occupancy_drift']}")

        reports.append(metric_dict)

    summary: dict[str, Any] = {
        "manifest": str(manifest_path),
        "mode": mode,
        "clip_reports": reports,
        "failures": failures,
        "status": "failed" if failures else "passed",
    }

    if compare_previous:
        previous_path = output_dir / "latest_summary.json"
        if previous_path.exists():
            previous = _load_json(previous_path)
            previous_by_id = {x.get("clip_id", x.get("clip")): x for x in previous.get("clip_reports", [])}
            for current in reports:
                clip_id = current.get("clip_id", current.get("clip"))
                old = previous_by_id.get(clip_id)
                if not old:
                    continue
                if current["id_switch_rate"] > float(old.get("id_switch_rate", 0.0)) + 0.02:
                    failures.append(f"{clip_id}: id_switch_rate regressed by > 0.02")
                if current["fragmentation_rate"] > float(old.get("fragmentation_rate", 0.0)) + 0.02:
                    failures.append(f"{clip_id}: fragmentation_rate regressed by > 0.02")
            summary["failures"] = failures
            summary["status"] = "failed" if failures else "passed"

    _save_json(output_dir / "latest_summary.json", summary)
    _save_json(output_dir / f"summary_{mode}.json", summary)
    return summary
