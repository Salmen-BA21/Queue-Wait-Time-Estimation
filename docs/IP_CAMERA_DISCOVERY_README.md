# IP Camera Discovery

This feature automatically discovers IP cameras on your local network using standard discovery protocols.

## 🎯 Features

- **Automatic Discovery**: Uses WS-Discovery protocol to find IP cameras on your network
- **Broad Camera Support**: Compatible with diverse ONVIF implementations (standard and vendor-specific)
- **Device Information**: Extracts camera details (name, manufacturer, model, IP, serial number, hardware version, location)
- **RTSP Stream Detection**: Automatically retrieves RTSP stream URLs from discovered devices
  - Tries ONVIF media service first (standard method)
  - Resolves media service via device capabilities when WS-Discovery does not expose it directly
  - Returns an empty list if ONVIF does not provide usable stream URIs (no URL guessing)
- **Authentication Support**: Handles username/password authentication for device queries and stream access
- **GUI Integration**: Fully integrated into the queue monitoring GUI application
- **Connection Testing**: Test RTSP streams with credentials before adding to monitoring

## 🚀 GUI Integration

The IP camera discovery feature is fully integrated into the main GUI application:

### Step-by-Step Usage

1. **Launch the GUI**:
   ```bash
   python -m backend.src.gui.app
   ```

2. **Navigate to Step 1** (Video Source Selection)

3. **Select "IP Camera Discovery" Tab**:
   - Choose this tab from the notebook interface
   - Click "🔍 Discover Cameras" to scan your network
   - Wait for the discovery process (typically 5 seconds)

4. **Review Discovered Cameras**:
   - Camera list shows: Name, Manufacturer, Model, IP Address
   - Click on any camera to view detailed information
   - Details include: serial number, hardware version, location, available services

5. **Test Camera Connections**:
   - Select a camera from the list
   - Click "Test Selected Camera"
   - Enter credentials if required (username/password dialog)
   - View connection results (resolution, FPS, stream count)

6. **Add Cameras to Analysis**:
   - Select one or multiple cameras
   - Click "+ Add Selected Cameras"
   - Enter credentials for each camera
   - Cameras are added to the main video sources list

### GUI Features

- **Multi-Select Support**: Add multiple cameras at once
- **Credential Management**: Secure credential entry for each camera
- **Connection Validation**: Test before adding to prevent configuration errors
- **Progress Feedback**: Real-time status updates during discovery
- **Error Handling**: Clear error messages for network/firewall issues

## 📋 Programmatic Usage

### Basic Discovery

```python
from backend.src.onvif_client import discover_ip_devices

# Discover all IP cameras on the network
devices = discover_ip_devices(timeout=5.0)

for device in devices:
    print(f"Found camera: {device['name']}")
    print(f"IP: {device['ip']}")
    print(f"Manufacturer: {device['manufacturer']}")
    print(f"Model: {device['model']}")
```

### Get RTSP Streams

```python
from backend.src.onvif_client import get_rtsp_urls_from_onvif_device
from backend.src.rtsp_camera import RTSPCamera

# Get RTSP URLs from a discovered device
rtsp_urls = get_rtsp_urls_from_onvif_device(
    device,
    username="admin",  # Optional
    password="password123"  # Optional
)

for url in rtsp_urls:
    print(f"RTSP Stream: {url}")

    # Test the connection
    ok, info = RTSPCamera.test_connection(url, username="admin", password="password123")
    if ok:
        print(f"  Resolution: {info['width']}x{info['height']}")
        print(f"  FPS: {info['fps']}")
```

## 🔍 How RTSP Stream Discovery Works

The system uses a **two-step approach** to find RTSP streams, ensuring compatibility with a broad range of cameras:

### Stage 1: ONVIF Media Service (Primary)

1. Checks if discovered device exposes an ONVIF media service
2. Sends SOAP request to get available stream profiles
3. Requests RTSP URI for each profile
4. Returns discovered URLs with credentials embedded

**Pros**: Standard method, most reliable  
**Cons**: Requires media service endpoint (not all cameras expose this)

### Stage 2: Resolve Media XAddr from Device Service

If WS-Discovery does not list the media service directly, the system queries the device service capabilities:

1. Calls `GetCapabilities` on the device service endpoint
2. Reads the advertised `Media` or `Media2` XAddr
3. Re-runs the media profile/URI lookup against that endpoint

**Pros**: Handles cameras that hide media from discovery but still advertise it through device capabilities  
**Cons**: Adds one SOAP round-trip before stream resolution

### Example: Discovering Camera Without Media Service

```python
from backend.src.onvif_client import discover_onvif_devices, get_rtsp_urls_from_onvif_device

# Discover device (e.g., Digital Watchdog DVR)
devices = discover_onvif_devices()
device = devices[0]

# No media service in device['services']
print(device['services'])  # Output: {'device': '...'}

# Stage 2 resolves the media XAddr from device capabilities
urls = get_rtsp_urls_from_onvif_device(
    device,
    username="admin",
    password="password123"
)

# If ONVIF does not expose a usable RTSP URI, this returns an empty list.
print(urls)
```

### Integration with Queue System

```python
from backend.src.onvif_client import discover_onvif_devices, get_rtsp_urls_from_onvif_device
from backend.src.rtsp_camera import RTSPCamera

# Add discovered cameras to your queue monitoring
devices = discover_onvif_devices()

camera_configs = []
for device in devices:
    rtsp_urls = get_rtsp_urls_from_onvif_device(device)

    for rtsp_url in rtsp_urls:
        # Test connection first
        ok, info = RTSPCamera.test_connection(rtsp_url)
        if ok:
            camera_configs.append({
                'name': f"{device['name']} - {device['ip']}",
                'rtsp_url': rtsp_url,
                'resolution': f"{info['width']}x{info['height']}",
                'fps': info['fps']
            })

# Use camera_configs in your monitoring system
for config in camera_configs:
    print(f"Monitoring: {config['name']} at {config['rtsp_url']}")
```

## 🖥️ GUI vs Programmatic Usage

| Feature | GUI Method | Programmatic Method |
|---------|------------|-------------------|
| **Discovery** | Click "Discover Cameras" button | `discover_ip_devices()` |
| **Device Selection** | Multi-select from listbox | Iterate through devices list |
| **Credential Entry** | Secure dialog prompts | Pass username/password parameters |
| **Connection Testing** | Built-in test button | `RTSPCamera.test_connection()` |
| **Integration** | Automatic addition to video sources | Manual configuration building |
| **Best For** | Interactive setup, multiple cameras | Scripting, automation, CI/CD |

## 📋 Device Information Structure

Each discovered device returns a dictionary with:

```python
{
    "ip": "192.168.1.100",           # Device IP address
    "name": "Front Door Camera",     # Device name
    "manufacturer": "Hikvision",     # Manufacturer
    "model": "DS-2CD2043G0-I",       # Model number
    "serial": "DS2CD2043G0I123456",  # Serial number
    "hardware": "DS-2CD2043G0-I",    # Hardware version
    "location": "Building A",        # Physical location
    "services": {                    # Device service endpoints
        "device": "http://192.168.1.100:80/device_service",
        "media": "http://192.168.1.100:80/media",
        "ptz": "http://192.168.1.100:80/ptz",
        "events": "http://192.168.1.100:80/events"
    },
    "xaddrs": "http://192.168.1.100:80/device_service ..."  # Raw endpoints
}
```

## 🔧 Troubleshooting

### GUI-Specific Issues

#### Discovery Button Not Working
- **Symptom**: Clicking "Discover Cameras" shows no progress or hangs
- **Solution**: Check Windows Firewall settings for multicast UDP traffic
- **Test**: Run `python backend/scripts/test_ip_camera_discovery.py` from command line

#### Cameras Not Appearing in List
- **Symptom**: Discovery completes but no cameras shown
- **Solution**:
  - Ensure cameras are powered on and connected to the same network
  - Check if cameras are behind a different subnet/router
  - Try running the GUI as Administrator (right-click → Run as administrator)

#### Connection Test Fails
- **Symptom**: "Test Selected Camera" shows connection error
- **Solution**:
  - Verify camera credentials (default is often `admin`/`admin` or `admin`/`12345`)
  - Check RTSP port (usually 554) is not blocked by firewall
  - Try different transport protocols (TCP vs UDP) in advanced settings

### General Discovery Issues

#### No Devices Found
- **Network**: Ensure cameras are on the same subnet as your computer
- **Firewall**: Verify multicast UDP traffic (port 3702) isn't blocked
- **Compatibility**: Confirm cameras support standard IP camera protocols
- **Timeout**: Try increasing timeout: `discover_ip_devices(timeout=10.0)`

#### Authentication Issues
- Some cameras require authentication for media service queries
- Try providing username/password to `get_rtsp_urls_from_onvif_device()`
- Default credentials vary by manufacturer:
  - Hikvision: `admin`/`12345`
  - Dahua: `admin`/`admin`
  - Axis: `root`/`pass`

#### Connection Issues
- Test RTSP URLs manually with `RTSPCamera.test_connection()`
- Check RTSP transport settings (TCP vs UDP)
- Verify camera RTSP service is enabled in camera web interface

## 📋 Requirements

- `lxml` library for XML parsing (installed via `requirements.txt`)
- Network access to multicast UDP traffic (port 3702)
- Cameras reachable on the same subnet
- IP cameras supporting ONVIF/WS-Discovery

## 📊 Example Output

```
🔍 Discovering IP cameras on the network...
INFO: Sent discovery probe, listening for responses...
INFO: Discovered device: Front Door Camera at 192.168.1.100
INFO: Discovery completed. Found 1 devices.

📹 Device 1:
   Name: Front Door Camera
   IP Address: 192.168.1.100
   Manufacturer: Hikvision
   Model: DS-2CD2043G0-I
   Serial: DS2CD2043G0I123456
   Hardware: DS-2CD2043G0-I
   Location: Building A
   Services:
     device: http://192.168.1.100:80/device_service
     media: http://192.168.1.100:80/media
     ptz: http://192.168.1.100:80/ptz
     events: http://192.168.1.100:80/events

   RTSP Streams:
     rtsp://192.168.1.100:554/Streaming/Channels/101
     rtsp://192.168.1.100:554/Streaming/Channels/102
```