#!/usr/bin/env python
"""
Standalone script to interactively define queue zone polygon.

Usage::
    python select_zone.py videos/retail_store.mp4
    # Click to define cashier area, then press 'c' to confirm
"""

import sys
from src.utils.zone_selector import select_zone


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python select_zone.py <video_path>")
        print("\nExamples:")
        print("  python select_zone.py videos/retail_store.mp4")
        print("  python select_zone.py videos/supermarket_crowd.mp4")
        sys.exit(1)
    
    video_path = sys.argv[1]
    coords = select_zone(video_path)
    
    if coords:
        sys.exit(0)
    else:
        sys.exit(1)
