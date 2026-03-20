#!/usr/bin/env python3
"""
Test script for IP camera discovery functionality.
"""

import logging
import sys
import os

# Add backend to path so the 'src' package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.onvif_client import discover_onvif_devices, get_rtsp_urls_from_onvif_device

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    print("🔍 Discovering ONVIF devices on the network...")
    print("This may take up to 5 seconds...\n")

    try:
        devices = discover_onvif_devices(timeout=5.0)

        if not devices:
            print("❌ No ONVIF devices found on the network.")
            print("\nPossible reasons:")
            print("- No ONVIF cameras are connected to your network")
            print("- Cameras are not ONVIF-compliant")
            print("- Firewall blocking multicast UDP traffic")
            print("- Cameras are on a different subnet")
            return

        print(f"✅ Found {len(devices)} ONVIF device(s):\n")

        for i, device in enumerate(devices, 1):
            print(f"📹 Device {i}:")
            print(f"   Name: {device['name']}")
            print(f"   IP Address: {device['ip']}")
            print(f"   Manufacturer: {device['manufacturer']}")
            print(f"   Model: {device['model']}")
            print(f"   Serial: {device['serial']}")
            print(f"   Hardware: {device['hardware']}")
            print(f"   Location: {device['location']}")

            if device['services']:
                print("   Services:")
                for service_type, url in device['services'].items():
                    print(f"     {service_type}: {url}")
            else:
                print("   Services: None found")

            print()

            # Try to get RTSP URLs (without credentials for now)
            print("   Attempting to get RTSP stream URLs...")
            try:
                rtsp_urls = get_rtsp_urls_from_onvif_device(device)
                if rtsp_urls:
                    print("   RTSP Streams:")
                    for url in rtsp_urls:
                        print(f"     {url}")
                else:
                    print("   No RTSP streams found (may require authentication)")
            except Exception as e:
                print(f"   Error getting RTSP URLs: {e}")

            print("-" * 60)

    except Exception as e:
        print(f"❌ Error during discovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()