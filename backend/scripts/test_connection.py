"""
Standalone connection-test utility.

Tests whether a given video source (MP4 file, webcam, or RTSP camera)
is readable before launching the full pipeline.

Usage
-----
    # Test an RTSP camera
    python -m scripts.test_connection rtsp://192.168.1.10:554/live/main

    # With authentication
    python -m scripts.test_connection rtsp://192.168.1.10/stream \\
        --user admin --password secret

    # Test a local MP4 file
    python -m scripts.test_connection videos/test.mp4

    # Test the default webcam
    python -m scripts.test_connection 0

Exit codes
----------
    0 – source is readable
    1 – source could not be opened or no frames could be read
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow `python -m scripts.test_connection` from the backend root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="test-connection",
        description="Verify that a video source is reachable and readable.",
    )
    parser.add_argument(
        "source",
        type=str,
        help=(
            "Video source to test: '0' for webcam, a file path (mp4/avi), "
            "or an RTSP URL (rtsp://...)."
        ),
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="RTSP username (ignored for non-RTSP sources).",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="RTSP password (ignored for non-RTSP sources).",
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["tcp", "udp"],
        default="tcp",
        help="RTSP transport protocol (default: tcp).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Connection timeout in seconds (default: 10.0).",
    )
    return parser.parse_args()


def _test_rtsp(args: argparse.Namespace) -> int:
    from src.rtsp_camera import RTSPCamera

    print(f"[RTSP] Testing: {args.source}")
    if args.user:
        print(f"       username={args.user}  transport={args.transport}")

    ok, info = RTSPCamera.test_connection(
        args.source,
        username=args.user,
        password=args.password,
        transport=args.transport,
        timeout=args.timeout,
    )

    if ok:
        print(
            f"\n  OK  Stream is readable\n"
            f"      Resolution : {info['resolution']}\n"
            f"      FPS        : {info['fps']:.1f}\n"
            f"      Transport  : {info['transport']}"
        )
        return 0
    else:
        print(f"\n  FAIL  {info['error']}")
        return 1


def _test_file_or_webcam(source: str, timeout: float) -> int:
    import cv2

    source_repr = source
    cap_source: int | str = int(source) if source.isdigit() else source

    if isinstance(cap_source, str) and not os.path.isfile(cap_source):
        print(f"  FAIL  File not found: {source}")
        return 1

    label = "Webcam" if str(source).isdigit() else "File"
    print(f"[{label}] Testing: {source_repr}")

    cap = cv2.VideoCapture(cap_source)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)

    if not cap.isOpened():
        cap.release()
        print(f"\n  FAIL  Cannot open source: {source_repr}")
        return 1

    ok, _ = cap.read()
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
    fps = raw_fps if raw_fps > 0 else 30.0
    cap.release()

    if not ok:
        print(f"\n  FAIL  Opened but could not read a frame: {source_repr}")
        return 1

    print(
        f"\n  OK  Source is readable\n"
        f"      Resolution : {width}x{height}\n"
        f"      FPS        : {fps:.1f}"
    )
    return 0


def main() -> None:
    args = _parse_args()

    if args.source.lower().startswith("rtsp://"):
        exit_code = _test_rtsp(args)
    else:
        exit_code = _test_file_or_webcam(args.source, args.timeout)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
