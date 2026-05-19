from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.tracking_validation import evaluate_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay-based tracking reliability validation")
    parser.add_argument(
        "--manifest",
        type=str,
        default="backend/data/tracking_dataset/manifest.json",
        help="Path to tracking dataset manifest JSON",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["quick", "full"],
        default="quick",
        help="quick runs clips marked quick=true; full runs all clips",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="backend/data/tracking_reports",
        help="Directory for per-clip CSV and summary JSON reports",
    )
    parser.add_argument(
        "--no-compare-previous",
        action="store_true",
        help="Disable regression checks against previous latest_summary.json",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    manifest = Path(args.manifest).resolve()
    output_dir = Path(args.output_dir).resolve()

    summary = evaluate_manifest(
        manifest,
        mode=args.mode,
        output_dir=output_dir,
        compare_previous=not args.no_compare_previous,
    )

    print(json.dumps(summary, indent=2))
    if summary.get("status") != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
