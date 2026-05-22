"""Evaluate baseline vs candidate transport validation reports for rollout promotion.

Usage:
  .\\.venv\\Scripts\\python.exe -m backend.scripts.evaluate_pipeline_promotion ^
      --baseline-report backend/data/runtime/transport_validation_opencv.json ^
      --candidate-report backend/data/runtime/transport_validation_gstreamer_hybrid.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    return json.loads(p.read_text(encoding="utf-8"))


def _metric(payload: dict, key: str) -> float | None:
    metrics = payload.get("event_summary", {}).get("transport_metrics", {})
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare transport validation reports for pipeline promotion.")
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--candidate-report", required=True)
    parser.add_argument("--max-skew-regression-ms", type=float, default=10.0)
    parser.add_argument("--max-drift-regression-ms", type=float, default=10.0)
    args = parser.parse_args()

    baseline = _load(args.baseline_report)
    candidate = _load(args.candidate_report)

    baseline_pass = bool(baseline.get("evaluation", {}).get("overall_pass"))
    candidate_pass = bool(candidate.get("evaluation", {}).get("overall_pass"))

    baseline_skew = _metric(baseline, "metadata_video_skew_ms_p95")
    candidate_skew = _metric(candidate, "metadata_video_skew_ms_p95")
    baseline_drift = _metric(baseline, "drift_delta_ms")
    candidate_drift = _metric(candidate, "drift_delta_ms")

    skew_regression_ok = True
    if baseline_skew is not None and candidate_skew is not None:
        skew_regression_ok = (candidate_skew - baseline_skew) <= float(args.max_skew_regression_ms)

    drift_regression_ok = True
    if baseline_drift is not None and candidate_drift is not None:
        drift_regression_ok = (candidate_drift - baseline_drift) <= float(args.max_drift_regression_ms)

    promote = bool(candidate_pass and baseline_pass and skew_regression_ok and drift_regression_ok)

    print(f"baseline_pass={baseline_pass}")
    print(f"candidate_pass={candidate_pass}")
    print(f"baseline_skew_p95_ms={baseline_skew}")
    print(f"candidate_skew_p95_ms={candidate_skew}")
    print(f"baseline_drift_delta_ms={baseline_drift}")
    print(f"candidate_drift_delta_ms={candidate_drift}")
    print(f"skew_regression_ok={skew_regression_ok}")
    print(f"drift_regression_ok={drift_regression_ok}")
    print(f"promotion_decision={'PROMOTE' if promote else 'HOLD'}")


if __name__ == "__main__":
    main()
