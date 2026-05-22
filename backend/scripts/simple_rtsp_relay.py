"""
Simple RTSP to MediaMTX relay without detection/tracking.

Usage:
    python scripts/simple_rtsp_relay.py \
        --source "rtsp://admin:password@192.168.1.23:554/profile2" \
        --output-path "test-camera" \
        --mediamtx-host "127.0.0.1" \
        --mediamtx-port 8554
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Relay RTSP stream to MediaMTX")
    parser.add_argument("--source", required=True, help="RTSP source URL")
    parser.add_argument("--output-path", required=True, help="MediaMTX path name")
    parser.add_argument("--mediamtx-host", default="127.0.0.1", help="MediaMTX host")
    parser.add_argument("--mediamtx-port", type=int, default=8554, help="MediaMTX RTSP port")
    parser.add_argument("--ffmpeg-binary", default="ffmpeg", help="FFmpeg binary path")
    
    args = parser.parse_args()
    
    # Build MediaMTX RTSP URL
    output_url = f"rtsp://{args.mediamtx_host}:{args.mediamtx_port}/{args.output_path}"
    
    # Build FFmpeg command with proper RTSP options
    command = [
        args.ffmpeg_binary,
        "-rtsp_transport", "tcp",  # Use TCP for input
        "-i", args.source,
        "-c:v", "copy",  # Copy video codec
        "-c:a", "copy",  # Copy audio codec (if present)
        "-f", "rtsp",
        "-rtsp_transport", "tcp",  # Use TCP for output
        output_url,
    ]
    
    print(f"Starting RTSP relay:")
    print(f"  Source: {args.source}")
    print(f"  Output: {output_url}")
    print(f"  Command: {' '.join(command)}")
    print()
    print("Press Ctrl+C to stop...")
    
    try:
        subprocess.run(command, check=True)
    except KeyboardInterrupt:
        print("\nStopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\nFFmpeg error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
