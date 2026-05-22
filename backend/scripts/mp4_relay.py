"""
Stream MP4 file to MediaMTX in a loop.

Usage:
    python scripts/mp4_relay.py \
        --source "data/uploads/retail_store-bdfcb2a6.mp4" \
        --output-path "test-mp4-stream" \
        --mediamtx-host "127.0.0.1" \
        --mediamtx-port 8554 \
        --loop
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Stream MP4 file to MediaMTX")
    parser.add_argument("--source", required=True, help="Path to MP4 file")
    parser.add_argument("--output-path", required=True, help="MediaMTX path name")
    parser.add_argument("--mediamtx-host", default="127.0.0.1", help="MediaMTX host")
    parser.add_argument("--mediamtx-port", type=int, default=8554, help="MediaMTX RTSP port")
    parser.add_argument("--loop", action="store_true", help="Loop the video indefinitely")
    parser.add_argument("--fps", type=int, default=None, help="Override FPS (optional)")
    parser.add_argument("--ffmpeg-binary", default="ffmpeg", help="FFmpeg binary path")
    
    args = parser.parse_args()
    
    # Verify source file exists
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source file not found: {source_path}", file=sys.stderr)
        return 1
    
    # Build MediaMTX RTSP URL
    output_url = f"rtsp://{args.mediamtx_host}:{args.mediamtx_port}/{args.output_path}"
    
    # Build FFmpeg command
    command = [
        args.ffmpeg_binary,
        "-re",  # Read input at native frame rate (realtime)
    ]
    
    # Add loop option
    if args.loop:
        command.extend(["-stream_loop", "-1"])  # Loop indefinitely
    
    command.extend([
        "-i", str(source_path),
        "-c:v", "copy",  # Copy video codec (no re-encoding)
        "-c:a", "copy",  # Copy audio codec
    ])
    
    # Override FPS if specified
    if args.fps:
        command.extend(["-r", str(args.fps)])
    
    command.extend([
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        output_url,
    ])
    
    print(f"Streaming MP4 to MediaMTX:")
    print(f"  Source: {source_path}")
    print(f"  Output: {output_url}")
    print(f"  Loop: {'Yes' if args.loop else 'No'}")
    if args.fps:
        print(f"  FPS: {args.fps}")
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
