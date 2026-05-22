"""Run repeatable transport validation scenarios and emit a JSON report.

Usage examples:
    .\\.venv\\Scripts\\python.exe -m backend.scripts.run_transport_validation --scenario ip_cam_like
    .\\.venv\\Scripts\\python.exe -m backend.scripts.run_transport_validation --scenario mp4_realtime_long_run --events-dir backend/data/runtime
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((p / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _default_venv_python() -> Path:
    windows = Path(".venv/Scripts/python.exe")
    if windows.exists():
        return windows.resolve()
    posix = Path(".venv/bin/python")
    if posix.exists():
        return posix.resolve()
    return Path(sys.executable).resolve()


@dataclass(frozen=True)
class TestSpec:
    id: str
    path: str
    required: bool = True
    extra_args: tuple[str, ...] = ()


SCENARIO_TESTS: dict[str, list[TestSpec]] = {
    "ip_cam_like": [
        TestSpec("metrics_preservation", "backend/tests/test_metrics_preservation.py"),
        TestSpec("socket_event_communication", "backend/tests/test_socket_event_communication.py"),
        TestSpec(
            "api_transport_contract",
            "backend/tests/test_api_app.py",
            extra_args=("-k", "transport or webrtc_offer or non_rtsp_worker_command"),
        ),
    ],
    "mp4_realtime_long_run": [
        TestSpec("metrics_preservation", "backend/tests/test_metrics_preservation.py"),
        TestSpec("metrics_latency_bugfix", "backend/tests/test_metrics_latency_bugfix.py", required=False),
    ],
    "multi_feed_degraded": [
        TestSpec("socket_event_communication", "backend/tests/test_socket_event_communication.py"),
        TestSpec("metrics_preservation", "backend/tests/test_metrics_preservation.py"),
        TestSpec("metrics_latency_bugfix", "backend/tests/test_metrics_latency_bugfix.py", required=False),
    ],
}


SCENARIO_THRESHOLDS: dict[str, dict[str, float | bool]] = {
    "ip_cam_like": {
        "max_skew_p95_ms": 120.0,
        "require_no_drift": True,
        "max_drift_delta_ms": 20.0,
    },
    "mp4_realtime_long_run": {
        "max_skew_p95_ms": 120.0,
        "require_no_drift": True,
        "max_drift_delta_ms": 20.0,
    },
    "multi_feed_degraded": {
        "max_skew_p95_ms": 180.0,
        "require_no_drift": False,
        "max_drift_delta_ms": 40.0,
    },
}


def _normalize_pytest_args(raw_args: tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for arg in raw_args:
        if arg.strip() == "-k":
            normalized.append("-k")
        elif arg.startswith(" -k "):
            normalized.extend(["-k", arg.replace(" -k ", "", 1)])
        else:
            normalized.append(arg)
    return normalized


def run_pytest_case(venv_python: Path, spec: TestSpec) -> dict[str, Any]:
    command = [str(venv_python), "-m", "pytest", spec.path, "-q", *(_normalize_pytest_args(spec.extra_args))]
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    return {
        "id": spec.id,
        "path": spec.path,
        "required": spec.required,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
        "command": command,
    }


def _iter_event_records(event_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in event_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def summarize_event_files(event_files: list[Path]) -> dict[str, Any]:
    emit_fps: list[float] = []
    encode_ms: list[float] = []
    queue_age_ms: list[float] = []
    frame_age_ms: list[float] = []
    skew_ms: list[float] = []
    dropped_ratio: list[float] = []
    health_counts: dict[str, int] = {}
    compatibility_reason_counts: dict[str, int] = {}
    pipeline_mode_counts: dict[str, int] = {}
    source_samples: list[float] = []

    for event_path in event_files:
        for record in _iter_event_records(event_path):
            event = record.get("event")
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue

            performance = payload.get("performance")
            if event in {"metrics_update", "transport_status"} and isinstance(performance, dict):
                for key, target in (
                    ("dashboard_emit_fps", emit_fps),
                    ("dashboard_jpeg_encode_ms", encode_ms),
                    ("queue_age_ms", queue_age_ms),
                    ("end_to_end_frame_age_ms", frame_age_ms),
                ):
                    value = performance.get(key)
                    if isinstance(value, (int, float)):
                        target.append(float(value))

            metrics = payload.get("metrics")
            if isinstance(metrics, dict):
                pts = metrics.get("pts_ms")
                emitted = metrics.get("server_emitted_at_ms")
                if isinstance(pts, (int, float)) and isinstance(emitted, (int, float)):
                    sample = abs(float(emitted) - float(pts))
                    skew_ms.append(sample)
                    source_samples.append(sample)

                drop = metrics.get("dropped_frame_ratio")
                if isinstance(drop, (int, float)):
                    dropped_ratio.append(float(drop))

            for health_key in ("health_state",):
                health = payload.get(health_key)
                if isinstance(health, str):
                    health_counts[health] = health_counts.get(health, 0) + 1

            compatibility_reason = payload.get("compatibility_reason")
            if isinstance(compatibility_reason, str) and compatibility_reason.strip():
                key = compatibility_reason.strip().lower()
                compatibility_reason_counts[key] = compatibility_reason_counts.get(key, 0) + 1
            pipeline_mode = payload.get("pipeline_mode")
            if isinstance(pipeline_mode, str) and pipeline_mode.strip():
                mode_key = pipeline_mode.strip().lower()
                pipeline_mode_counts[mode_key] = pipeline_mode_counts.get(mode_key, 0) + 1

    skew_p50 = percentile(skew_ms, 50)
    skew_p95 = percentile(skew_ms, 95)
    drop_p50 = percentile(dropped_ratio, 50)
    drop_p95 = percentile(dropped_ratio, 95)
    drift_delta: float | None = None
    no_drift: bool | None = None
    if len(source_samples) >= 10:
        window = max(1, len(source_samples) // 10)
        head = sum(source_samples[:window]) / window
        tail = sum(source_samples[-window:]) / window
        drift_delta = abs(tail - head)
        no_drift = True

    return {
        "event_files": [str(p) for p in event_files],
        "samples": {
            "emit_fps": len(emit_fps),
            "encode_ms": len(encode_ms),
            "queue_age_ms": len(queue_age_ms),
            "frame_age_ms": len(frame_age_ms),
            "skew_ms": len(skew_ms),
            "dropped_frame_ratio": len(dropped_ratio),
        },
        "transport_metrics": {
            "emit_fps_p50": percentile(emit_fps, 50),
            "emit_fps_p95": percentile(emit_fps, 95),
            "encode_ms_p50": percentile(encode_ms, 50),
            "encode_ms_p95": percentile(encode_ms, 95),
            "queue_age_ms_p50": percentile(queue_age_ms, 50),
            "queue_age_ms_p95": percentile(queue_age_ms, 95),
            "end_to_end_frame_age_ms_p50": percentile(frame_age_ms, 50),
            "end_to_end_frame_age_ms_p95": percentile(frame_age_ms, 95),
            "metadata_video_skew_ms_p50": skew_p50,
            "metadata_video_skew_ms_p95": skew_p95,
            "dropped_frame_ratio_p50": drop_p50,
            "dropped_frame_ratio_p95": drop_p95,
            "health_state_counts": health_counts,
            "codec_compatibility_reason_counts": compatibility_reason_counts,
            "codec_fallback_active": bool(compatibility_reason_counts),
            "pipeline_mode_counts": pipeline_mode_counts,
            "drift_delta_ms": drift_delta,
            "no_drift": no_drift,
        },
    }


def evaluate_pass_fail(
    test_results: list[dict[str, Any]],
    event_summary: dict[str, Any],
    thresholds: dict[str, float | bool],
) -> dict[str, Any]:
    required_tests = [result for result in test_results if result["required"]]
    tests_ok = all(result["passed"] for result in required_tests)

    metrics = event_summary.get("transport_metrics", {})
    skew_p95 = metrics.get("metadata_video_skew_ms_p95")
    max_skew = float(thresholds["max_skew_p95_ms"])
    skew_ok = skew_p95 is None or (isinstance(skew_p95, (int, float)) and float(skew_p95) <= max_skew)

    require_no_drift = bool(thresholds.get("require_no_drift", False))
    no_drift = metrics.get("no_drift")
    drift_delta = metrics.get("drift_delta_ms")
    max_drift = float(thresholds.get("max_drift_delta_ms", 20.0))
    drift_ok = True
    if require_no_drift:
        drift_ok = bool(no_drift is True and isinstance(drift_delta, (int, float)) and float(drift_delta) <= max_drift)

    overall_pass = bool(tests_ok and skew_ok and drift_ok)
    return {
        "overall_pass": overall_pass,
        "checks": {
            "required_tests_passed": tests_ok,
            "skew_p95_within_threshold": skew_ok,
            "no_drift_check": drift_ok,
        },
        "thresholds": thresholds,
    }


def discover_event_files(events_dir: Path, explicit_files: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in explicit_files:
        if path.exists():
            files.append(path.resolve())
    if events_dir.exists():
        files.extend(sorted(p.resolve() for p in events_dir.glob("*.events.jsonl")))
    deduped = list(dict.fromkeys(files))
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description="Run transport validation harness with scenario presets.")
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIO_TESTS.keys()),
        default="ip_cam_like",
        help="Validation scenario preset.",
    )
    parser.add_argument("--venv-python", default=str(_default_venv_python()), help="Path to Python executable in venv.")
    parser.add_argument(
        "--output-json",
        default="backend/data/runtime/transport_validation_report.json",
        help="Output report path.",
    )
    parser.add_argument(
        "--events-dir",
        default="backend/data/runtime",
        help="Directory to scan for *.events.jsonl files.",
    )
    parser.add_argument(
        "--events-file",
        action="append",
        default=[],
        help="Explicit events file path (can be repeated).",
    )
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest execution and only build report from events.")
    args = parser.parse_args()

    venv_python = Path(args.venv_python).expanduser().resolve()
    output_path = Path(args.output_json).expanduser().resolve()
    events_dir = Path(args.events_dir).expanduser().resolve()
    explicit_event_files = [Path(item).expanduser().resolve() for item in args.events_file]

    test_specs = SCENARIO_TESTS[args.scenario]
    test_results: list[dict[str, Any]] = []
    if not args.skip_pytest:
        for spec in test_specs:
            test_results.append(run_pytest_case(venv_python, spec))

    event_files = discover_event_files(events_dir, explicit_event_files)
    event_summary = summarize_event_files(event_files)
    thresholds = SCENARIO_THRESHOLDS[args.scenario]
    evaluation = evaluate_pass_fail(test_results, event_summary, thresholds)

    report = {
        "scenario": args.scenario,
        "venv_python": str(venv_python),
        "tests": test_results,
        "event_summary": event_summary,
        "evaluation": evaluation,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"scenario={args.scenario}")
    print(f"report={output_path}")
    print(f"required_tests_passed={evaluation['checks']['required_tests_passed']}")
    print(f"skew_p95_within_threshold={evaluation['checks']['skew_p95_within_threshold']}")
    print(f"no_drift_check={evaluation['checks']['no_drift_check']}")
    print(f"overall_pass={evaluation['overall_pass']}")


if __name__ == "__main__":
    main()
