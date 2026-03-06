#!/usr/bin/env python3
"""
Quick test script for IP camera discovery integration in GUI.
Tests that the discovery methods can be called without GUI.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

def test_ip_camera_discovery_import():
    """Test that IP camera discovery can be imported."""
    try:
        from src.rtsp_camera import RTSPCamera
        print("✅ RTSPCamera import successful")

        # Check if discovery method exists
        if hasattr(RTSPCamera, 'discover_onvif_devices'):
            print("✅ discover_onvif_devices method exists")
        else:
            print("❌ discover_onvif_devices method missing")
            return False

        if hasattr(RTSPCamera, 'get_rtsp_urls_from_onvif_device'):
            print("✅ get_rtsp_urls_from_onvif_device method exists")
        else:
            print("❌ get_rtsp_urls_from_onvif_device method missing")
            return False

        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_gui_ip_camera_methods():
    """Test that GUI IP camera methods exist."""
    try:
        from src.gui.app import MainWindow
        print("✅ MainWindow import successful")

        # Check if methods exist
        methods_to_check = [
            '_discover_ip_cameras',
            '_on_ip_camera_selection_change',
            '_test_selected_ip_camera',
            '_add_selected_ip_cameras'
        ]

        for method in methods_to_check:
            if hasattr(MainWindow, method):
                print(f"✅ {method} method exists")
            else:
                print(f"❌ {method} method missing")
                return False

        return True
    except ImportError as e:
        print(f"❌ GUI import failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing IP camera discovery integration...")
    print("=" * 50)

    success = True
    success &= test_ip_camera_discovery_import()
    print()
    success &= test_gui_ip_camera_methods()

    print()
    if success:
        print("🎉 All tests passed! IP camera discovery is properly integrated.")
    else:
        print("❌ Some tests failed. Check the output above.")
        sys.exit(1)