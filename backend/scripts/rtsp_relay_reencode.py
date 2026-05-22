"""
RTSP to MediaMTX relay WITH re-encoding (for compatibility).

This version re-encodes the stream with H.264 low-latency settings
to ensure compatibility with MediaMTX.

Usage:
    python scripts/rtsp_relay_reencode.py \
        --source "rtsp://admin:password@192.168.1.23:554/profile1" \
        --output-path "test-camera" \
        --mediamtx-host "127.0.0.1" \
        --mediamtx-port 8554
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Relay RTSP stream to MediaMTX with re-encoding")
    parser.add_argument("--source", required=True, help="RTSP source URL")
    parser.add_argument("--output-path", required=True, help="MediaMTX path name")
    parser.add_argument("--mediamtx-host", default="127.0.0.1", help="MediaMTX host")
    parser.add_argument("--mediamtx-port", type=int, default=8554, help="MediaMTX RTSP port")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS")
    parser.add_argument("--ffmpeg-binary", default="ffmpeg", help="FFmpeg binary path")
    
    args = parser.parse_args()
    
    # Build MediaMTX RTSP URL
    output_url = f"rtsp://{args.mediamtx_host}:{args.mediamtx_port}/{args.output_path}"
    
    # Build FFmpeg command with re-encoding for compatibility
    command = [
        args.ffmpeg_binary,
        "-rtsp_transport", "tcp",
        "-i", args.source,
        "-c:v", "libx264",  # Re-encode with H.264
        "-preset", "ultrafast",  # Fast encoding
        "-tune", "zerolatency",  # Low latency
        "-r", str(args.fps),  # Target FPS
        "-g", str(args.fps * 2),  # Keyframe interval
        "-b:v", "2M",  # Bitrate
        "-maxrate", "2M",
        "-bufsize", "4M",
        "-pix_fmt", "yuv420p",  # Ensure compatible pixel format
        "-an",  # No audio (simplify for now)
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        output_url,
    ]
    
    print(f"Starting RTSP relay with re-encoding:")
    print(f"  Source: {args.source}")
    print(f"  Output: {output_url}")
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
