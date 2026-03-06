#!/usr/bin/env python3
"""
IP Camera Discovery Example

This script demonstrates how to automatically discover IP cameras
on your network and extract their RTSP stream URLs.

Usage:
    python discover_cameras.py

Requirements:
    - lxml library (pip install lxml)
    - ONVIF-compatible IP cameras on the network
"""

import sys
import os

# Add backend/src to Python path
backend_dir = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'src'))

from src.rtsp_camera import RTSPCamera

def main():
    print("🔍 IP Camera Discovery Example")
    print("=" * 50)

    # Discover ONVIF devices
    print("\n1. Discovering ONVIF devices...")
    devices = RTSPCamera.discover_onvif_devices(timeout=5.0)

    if not devices:
        print("❌ No ONVIF devices found.")
        print("\nTroubleshooting:")
        print("- Ensure cameras are ONVIF-compliant")
        print("- Check that cameras are on the same network subnet")
        print("- Verify firewall allows multicast UDP traffic")
        print("- Try running as administrator (some systems restrict multicast)")
        return

    print(f"✅ Found {len(devices)} device(s)")

    # Process each device
    for i, device in enumerate(devices, 1):
        print(f"\n📹 Device {i}: {device['name']}")
        print(f"   IP: {device['ip']}")
        print(f"   Manufacturer: {device['manufacturer']}")
        print(f"   Model: {device['model']}")

        # Try to get RTSP streams
        print("\n   Getting RTSP streams...")
        try:
            rtsp_urls = RTSPCamera.get_rtsp_urls_from_onvif_device(device)

            if rtsp_urls:
                print("   ✅ Found RTSP streams:")
                for j, url in enumerate(rtsp_urls, 1):
                    print(f"      {j}. {url}")

                    # Test the connection
                    print("         Testing connection...")
                    ok, info = RTSPCamera.test_connection(url)
                    if ok:
                        print(f"         ✅ Working - {info['width']}x{info['height']} @ {info['fps']} FPS")
                    else:
                        print(f"         ❌ Failed - {info.get('error', 'Unknown error')}")
            else:
                print("   ⚠️  No RTSP streams found (may require authentication)")
                print("      Try: RTSPCamera.get_rtsp_urls_from_onvif_device(device, username='admin', password='password')")

        except Exception as e:
            print(f"   ❌ Error getting streams: {e}")

        print("-" * 50)

    # Summary
    print(f"\n📊 Summary: {len(devices)} ONVIF device(s) discovered")

    # Show how to use in queue system
    print("\n💡 Integration Example:")
    print("""
# Add discovered cameras to your queue monitoring system
camera_configs = []

for device in devices:
    rtsp_urls = RTSPCamera.get_rtsp_urls_from_onvif_device(device)
    for url in rtsp_urls:
        ok, info = RTSPCamera.test_connection(url)
        if ok:
            camera_configs.append({
                'name': f"{device['name']} - {device['ip']}",
                'rtsp_url': url,
                'resolution': f"{info['width']}x{info['height']}",
                'fps': info['fps']
            })

# Now use camera_configs in your main application
for config in camera_configs:
    print(f"Monitoring: {config['name']} at {config['rtsp_url']}")
""")

if __name__ == "__main__":
    main()