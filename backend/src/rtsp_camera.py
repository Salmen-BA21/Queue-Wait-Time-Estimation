"""
RTSP camera connection with authentication, connection testing, and
automatic reconnection on stream loss.

Typical usage
-------------
    # Test first, then stream
    ok, info = RTSPCamera.test_connection("rtsp://192.168.1.10/stream")
    if ok:
        with RTSPCamera("rtsp://192.168.1.10/stream") as cam:
            for frame in cam.frames():
                ...

    # With credentials embedded at runtime (URL kept clean in logs)
    with RTSPCamera(
        "rtsp://192.168.1.10/stream",
        username="admin",
        password="secret",
    ) as cam:
        ...

    # Discover ONVIF devices on network
    devices = RTSPCamera.discover_onvif_devices()
    for device in devices:
        print(f"Found camera: {device['name']} at {device['ip']}")
"""

from __future__ import annotations

import base64
import logging
import os
import select
import socket
import time
import uuid
from typing import Generator
from urllib.parse import unquote, urlparse, urlunparse
from xml.etree import ElementTree as ET

import cv2
import numpy as np
import requests

from src.config import (
    RTSP_CONNECTION_TIMEOUT_SEC,
    RTSP_RECONNECT_ATTEMPTS,
    RTSP_RECONNECT_DELAY_SEC,
    RTSP_TRANSPORT,
)

logger = logging.getLogger("queue_system.rtsp_camera")


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _build_rtsp_url(
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Embed *username* and *password* into an RTSP URL if provided.

    If the URL already contains credentials they are **replaced** by the
    supplied values so the caller doesn't have to strip them manually.
    """
    if not (username or password):
        return url

    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if username or password:
        user_part = username or ""
        pass_part = f":{password}" if password else ""
        netloc = f"{user_part}{pass_part}@{netloc}"

    return urlunparse(parsed._replace(netloc=netloc))


def _safe_url(url: str) -> str:
    """Return the URL with the password redacted for log messages."""
    parsed = urlparse(url)
    if parsed.password:
        masked = parsed._replace(
            netloc=parsed.netloc.replace(f":{parsed.password}", ":***")
        )
        return urlunparse(masked)
    return url


def _apply_rtsp_env(transport: str) -> None:
    """Set OpenCV / FFMPEG environment variables for RTSP transport."""
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", f"rtsp_transport;{transport}")


# ──────────────────────────────────────────────────────────────────────
# ONVIF Device Discovery
# ──────────────────────────────────────────────────────────────────────

class ONVIFDiscovery:
    """ONVIF device discovery using WS-Discovery protocol."""

    MULTICAST_ADDR = "239.255.255.250"
    MULTICAST_PORT = 3702
    DISCOVERY_TIMEOUT = 5.0

    @staticmethod
    def _create_probe_message() -> str:
        """Create WS-Discovery Probe message for ONVIF devices."""
        message_id = str(uuid.uuid4())
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
               xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
    <soap:Header>
        <wsa:MessageID>uuid:{message_id}</wsa:MessageID>
        <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    </soap:Header>
    <soap:Body>
        <d:Probe>
            <d:Types>dn:NetworkVideoTransmitter</d:Types>
        </d:Probe>
    </soap:Body>
</soap:Envelope>"""

    @staticmethod
    def _parse_probe_match(response_data: str, sender_addr: tuple) -> dict | None:
        """Parse ProbeMatch response and extract device information."""
        try:
            root = ET.fromstring(response_data)

            # ONVIF cameras commonly use WS-Discovery 2005/04. Some vendors reply
            # with the OASIS 2009 namespace, so check both for compatibility.
            namespaces = {
                "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
                "wsd10": "http://docs.oasis-open.org/ws-dd/ns/discovery/2009/01",
                "dn": "http://www.onvif.org/ver10/network/wsdl",
                "soap": "http://www.w3.org/2003/05/soap-envelope",
            }

            # Extract XAddrs (device service endpoints)
            xaddrs_elem = None
            for prefix in ("d", "wsd10", "dn"):
                xaddrs_elem = root.find(f".//{prefix}:XAddrs", namespaces)
                if xaddrs_elem is not None and xaddrs_elem.text:
                    break
            if xaddrs_elem is None or not xaddrs_elem.text:
                return None

            xaddrs = xaddrs_elem.text.strip()
            device_ip = sender_addr[0]

            # Extract device information from scopes
            scopes_elem = None
            for prefix in ("d", "wsd10", "dn"):
                scopes_elem = root.find(f".//{prefix}:Scopes", namespaces)
                if scopes_elem is not None and scopes_elem.text:
                    break
            scopes = scopes_elem.text if scopes_elem is not None else ""

            # Parse scopes for device info
            device_info = {
                "ip": device_ip,
                "name": "Unknown",
                "manufacturer": "Unknown",
                "model": "Unknown",
                "serial": "Unknown",
                "hardware": "Unknown",
                "location": "Unknown"
            }

            if scopes:
                scope_parts = scopes.split()
                for scope in scope_parts:
                    if scope.startswith("onvif://www.onvif.org/name/"):
                        device_info["name"] = unquote(scope.replace("onvif://www.onvif.org/name/", ""))
                    elif scope.startswith("onvif://www.onvif.org/manufacturer/"):
                        device_info["manufacturer"] = unquote(
                            scope.replace("onvif://www.onvif.org/manufacturer/", "")
                        )
                    elif scope.startswith("onvif://www.onvif.org/model/"):
                        device_info["model"] = unquote(scope.replace("onvif://www.onvif.org/model/", ""))
                    elif scope.startswith("onvif://www.onvif.org/hardware/"):
                        device_info["hardware"] = unquote(
                            scope.replace("onvif://www.onvif.org/hardware/", "")
                        )
                    elif scope.startswith("onvif://www.onvif.org/serial/"):
                        device_info["serial"] = unquote(scope.replace("onvif://www.onvif.org/serial/", ""))
                    elif scope.startswith("onvif://www.onvif.org/location/"):
                        device_info["location"] = unquote(
                            scope.replace("onvif://www.onvif.org/location/", "")
                        )

            # Extract service endpoints
            services = {}
            for addr in xaddrs.split():
                if "device_service" in addr or "/onvif/device" in addr:
                    services["device"] = addr
                elif "media" in addr or "/onvif/media" in addr:
                    services["media"] = addr
                elif "ptz" in addr or "/onvif/ptz" in addr:
                    services["ptz"] = addr
                elif "events" in addr or "/onvif/events" in addr:
                    services["events"] = addr

            device_info["services"] = services
            device_info["xaddrs"] = xaddrs

            return device_info

        except ET.ParseError as e:
            logger.warning(
                "Failed to parse ONVIF ProbeMatch response from %s: %s",
                sender_addr[0],
                e,
            )
            return None

    @staticmethod
    def _get_subnet_hosts(local_ips: list[str]) -> list[str]:
        """Return all /24 host IPs for each routable local IP.

        Used to send unicast WS-Discovery probes when a camera ignores
        multicast (common on cheap/consumer IP cameras).
        Link-local (169.254.x.x) addresses are excluded.
        """
        hosts: list[str] = []
        seen_prefixes: set[str] = set()
        for ip in local_ips:
            parts = ip.split(".")
            if len(parts) != 4 or parts[0] == "169" or parts[0] == "127":
                continue
            prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            hosts.extend(f"{prefix}.{i}" for i in range(1, 255))
        return hosts

    @staticmethod
    def _get_local_ips() -> list[str]:
        """Return all non-loopback local IPv4 addresses.

        Uses two complementary methods so at least one succeeds on any platform:
        1. ``getaddrinfo`` via the hostname.
        2. A dummy UDP connect to determine the default-route interface IP.
        """
        ips: set[str] = set()

        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if isinstance(ip, str) and not ip.startswith("127."):
                    ips.add(ip)
        except OSError:
            pass

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.add(s.getsockname()[0])
        except OSError:
            pass

        if not ips:
            logger.warning("Could not determine local IPs; falling back to default interface.")
            return ["0.0.0.0"]

        logger.debug("ONVIF discovery will probe on interfaces: %s", sorted(ips))
        return list(ips)

    @staticmethod
    def discover_devices(timeout: float = DISCOVERY_TIMEOUT) -> list[dict]:
        """Discover ONVIF devices on the network using WS-Discovery.

        Sends WS-Discovery Probes via two strategies in parallel:

        1. **Multicast** – one probe per local interface, covers cameras that
           listen on the ``239.255.255.250:3702`` group.
        2. **Unicast subnet scan** – one probe per host on each /24 subnet
           reachable from a local interface, covers cameras (common on
           consumer hardware) that silently ignore multicast probes.

        All sockets are polled concurrently with ``select`` for the full
        *timeout* so both strategies share the same listening window.

        Returns
        -------
        list[dict]
            List of discovered devices with their information.
        """
        devices: list[dict] = []
        seen_ips: set[str] = set()
        probe_msg = ONVIFDiscovery._create_probe_message().encode("utf-8")
        local_ips = ONVIFDiscovery._get_local_ips()

        sockets: list[socket.socket] = []
        try:
            for local_ip in local_ips:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Keep blocking for the send phase; switch to non-blocking before select().
                try:
                    bind_ip = local_ip if local_ip != "0.0.0.0" else ""
                    sock.bind((bind_ip, 0))
                    if local_ip != "0.0.0.0":
                        sock.setsockopt(
                            socket.IPPROTO_IP,
                            socket.IP_MULTICAST_IF,
                            socket.inet_aton(local_ip),
                        )
                    # Strategy 1: multicast probe
                    sock.sendto(
                        probe_msg,
                        (ONVIFDiscovery.MULTICAST_ADDR, ONVIFDiscovery.MULTICAST_PORT),
                    )
                    logger.info("Sent ONVIF multicast probe on interface %s", local_ip)
                    sock.setblocking(False)
                    sockets.append(sock)
                except OSError as exc:
                    logger.warning("Skipping interface %s: %s", local_ip, exc)
                    sock.close()

            if not sockets:
                logger.warning("No usable network interfaces for ONVIF discovery.")
                return devices

            # Strategy 2: unicast probe to every host on each /24 subnet.
            # Many cameras (including consumer IP cameras) ignore multicast but
            # respond correctly to a unicast WS-Discovery probe on port 3702.
            # Bind to INADDR_ANY so the OS routing table picks the correct
            # source interface for each destination — binding to a specific IP
            # can result in the wrong source being chosen and the camera never
            # receiving the response.
            subnet_hosts = ONVIFDiscovery._get_subnet_hosts(local_ips)
            unicast_sock: socket.socket | None = None
            if subnet_hosts:
                logger.info(
                    "Sending unicast ONVIF probes to %d hosts on local subnets …",
                    len(subnet_hosts),
                )
                unicast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                unicast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                unicast_sock.bind(("", 0))  # INADDR_ANY — let the OS route correctly
                for host_ip in subnet_hosts:
                    try:
                        unicast_sock.sendto(probe_msg, (host_ip, ONVIFDiscovery.MULTICAST_PORT))
                    except OSError:
                        pass
                unicast_sock.setblocking(False)
                sockets.append(unicast_sock)
            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                readable, _, _ = select.select(sockets, [], [], min(remaining, 0.5))
                for sock in readable:
                    try:
                        data, addr = sock.recvfrom(8192)
                        response = data.decode("utf-8", errors="ignore")
                        if "ProbeMatch" in response:
                            device = ONVIFDiscovery._parse_probe_match(response, addr)
                            if device and device["ip"] not in seen_ips:
                                seen_ips.add(device["ip"])
                                devices.append(device)
                                logger.info(
                                    "Discovered ONVIF device: %s at %s",
                                    device["name"],
                                    device["ip"],
                                )
                    except OSError:
                        continue

        finally:
            for sock in sockets:
                sock.close()

        logger.info("ONVIF discovery completed. Found %d devices.", len(devices))
        return devices


# ──────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────

class RTSPCamera:
    """Robust RTSP camera stream.

    Parameters
    ----------
    url : str
        RTSP URL, e.g. ``rtsp://192.168.1.10:554/live/main``.
    username : str | None
        Optional username (embedded into the URL at connect time).
    password : str | None
        Optional password (embedded into the URL at connect time).
    reconnect_attempts : int
        How many times to try reconnecting after a dropped stream.
        ``0`` means no retries (fail immediately).
    reconnect_delay : float
        Seconds to wait between reconnect attempts.
    transport : str
        RTSP transport protocol – ``"tcp"`` (default) or ``"udp"``.
    """

    def __init__(
        self,
        url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        reconnect_attempts: int = RTSP_RECONNECT_ATTEMPTS,
        reconnect_delay: float = RTSP_RECONNECT_DELAY_SEC,
        transport: str = RTSP_TRANSPORT,
    ) -> None:
        self._raw_url = url
        self._username = username
        self._password = password
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._transport = transport
        self._cap: cv2.VideoCapture | None = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def _auth_url(self) -> str:
        """RTSP URL with credentials embedded (never logged directly)."""
        return _build_rtsp_url(self._raw_url, self._username, self._password)

    @property
    def width(self) -> int:
        assert self._cap is not None
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        assert self._cap is not None
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def fps(self) -> float:
        assert self._cap is not None
        raw = float(self._cap.get(cv2.CAP_PROP_FPS))
        return raw if raw > 0 else 30.0

    @property
    def resolution(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── Connection ───────────────────────────────────────────────────

    def open(self) -> "RTSPCamera":
        """Open the RTSP stream. Raises ``RuntimeError`` on failure."""
        _apply_rtsp_env(self._transport)
        safe = _safe_url(self._auth_url)
        logger.info("Connecting to RTSP stream: %s (transport=%s)", safe, self._transport)
        self._cap = cv2.VideoCapture(self._auth_url, cv2.CAP_FFMPEG)
        self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_CONNECTION_TIMEOUT_SEC * 1000)
        self._cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_CONNECTION_TIMEOUT_SEC * 1000)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open RTSP stream: {safe}")
        logger.info(
            "Connected – %dx%d @ %.1f FPS", self.width, self.height, self.fps
        )
        return self

    def close(self) -> None:
        """Release the capture device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("RTSP stream released: %s", _safe_url(self._raw_url))

    def __enter__(self) -> "RTSPCamera":
        return self.open()

    def __exit__(self, *_exc) -> None:  # noqa: ANN001
        self.close()

    # ── Frame reading ────────────────────────────────────────────────

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read one frame. Returns ``(success, frame)``."""
        if self._cap is None:
            return False, None
        return self._cap.read()

    def frames(self) -> Generator[np.ndarray, None, None]:
        """Yield frames, automatically reconnecting on stream loss.

        Stops after exhausting all reconnect attempts.
        """
        consecutive_failures = 0

        while True:
            ok, frame = self.read()

            if ok and frame is not None:
                consecutive_failures = 0
                yield frame
                continue

            # ── Stream lost ──────────────────────────────────────────
            consecutive_failures += 1
            if consecutive_failures > self._reconnect_attempts:
                logger.error(
                    "RTSP stream lost after %d reconnect attempts. Stopping.",
                    self._reconnect_attempts,
                )
                break

            logger.warning(
                "RTSP frame read failed (attempt %d/%d). Reconnecting in %.1fs …",
                consecutive_failures,
                self._reconnect_attempts,
                self._reconnect_delay,
            )
            time.sleep(self._reconnect_delay)
            self.close()
            try:
                self.open()
            except RuntimeError as exc:
                logger.warning("Reconnect failed: %s", exc)

    # ── Static helpers ───────────────────────────────────────────────

    @staticmethod
    def test_connection(
        url: str,
        username: str | None = None,
        password: str | None = None,
        transport: str = RTSP_TRANSPORT,
        timeout: float = RTSP_CONNECTION_TIMEOUT_SEC,
    ) -> tuple[bool, dict]:
        """Probe an RTSP URL without starting the full pipeline.

        Returns
        -------
        tuple[bool, dict]
            ``(success, info)`` where *info* contains stream metadata on
            success or an ``"error"`` key on failure.

        Example
        -------
        ::

            ok, info = RTSPCamera.test_connection("rtsp://192.168.1.10/stream")
            if ok:
                print(info["width"], info["height"], info["fps"])
            else:
                print(info["error"])
        """
        _apply_rtsp_env(transport)
        auth_url = _build_rtsp_url(url, username, password)
        safe = _safe_url(auth_url)
        logger.info("Testing RTSP connection: %s", safe)

        cap = cv2.VideoCapture(auth_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)

        if not cap.isOpened():
            cap.release()
            msg = f"Could not open stream: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        # Try to grab one frame to confirm live data
        ok, _ = cap.read()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
        fps = raw_fps if raw_fps > 0 else 30.0
        cap.release()

        if not ok:
            msg = f"Stream opened but could not read a frame: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        info = {
            "url": url,
            "width": width,
            "height": height,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "transport": transport,
        }
        logger.info(
            "RTSP test OK – %dx%d @ %.1f FPS", width, height, fps
        )
        return True, info

    @staticmethod
    def capture_snapshot(
        url: str,
        username: str | None = None,
        password: str | None = None,
        transport: str = RTSP_TRANSPORT,
        timeout: float = RTSP_CONNECTION_TIMEOUT_SEC,
        jpeg_quality: int = 90,
    ) -> tuple[bool, dict]:
        """Capture a single JPEG snapshot from an RTSP source."""
        _apply_rtsp_env(transport)
        auth_url = _build_rtsp_url(url, username, password)
        safe = _safe_url(auth_url)
        logger.info("Capturing RTSP snapshot: %s", safe)

        cap = cv2.VideoCapture(auth_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)

        if not cap.isOpened():
            cap.release()
            msg = f"Could not open stream: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        ok, frame = cap.read()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if not ok or frame is None:
            msg = f"Stream opened but could not read a frame: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        encoded_ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )
        if not encoded_ok:
            msg = f"Could not encode snapshot frame: {safe}"
            logger.warning(msg)
            return False, {"error": msg, "url": url}

        image_base64 = base64.b64encode(buffer.tobytes()).decode("ascii")
        info = {
            "url": url,
            "width": width,
            "height": height,
            "resolution": f"{width}x{height}",
            "transport": transport,
            "image_base64": image_base64,
            "mime_type": "image/jpeg",
        }
        logger.info("RTSP snapshot captured – %dx%d", width, height)
        return True, info

    @staticmethod
    def discover_ip_devices(timeout: float = 5.0) -> list[dict]:
        """Backward-compatible alias for :meth:`discover_onvif_devices`.

        This method is provided to match older documentation and examples
        that refer to ``discover_ip_devices``. New code should prefer
        :meth:`discover_onvif_devices`.
        """
        return RTSPCamera.discover_onvif_devices(timeout)

    @staticmethod
    def discover_onvif_devices(timeout: float = 5.0) -> list[dict]:
        """Discover ONVIF-compatible IP cameras on the local network.

        This method uses WS-Discovery protocol to automatically find
        ONVIF devices without needing to know their IP addresses in advance.

        Parameters
        ----------
        timeout : float
            Seconds to wait for device responses (default: 5.0).

        Returns
        -------
        list[dict]
            List of discovered devices. Each device dict contains:
            - ip: Device IP address
            - name: Device name
            - manufacturer: Device manufacturer
            - model: Device model
            - serial: Device serial number
            - hardware: Hardware version
            - location: Physical location
            - services: Dict of ONVIF service endpoints
            - xaddrs: Raw service addresses string

        Example
        -------
        ::

            devices = RTSPCamera.discover_onvif_devices()
            for device in devices:
                print(f"Camera: {device['name']} ({device['manufacturer']} {device['model']})")
                print(f"IP: {device['ip']}")
                if 'media' in device['services']:
                    print(f"Media service: {device['services']['media']}")
        """
        return ONVIFDiscovery.discover_devices(timeout)

    @staticmethod
    def _generate_candidate_rtsp_urls(device: dict) -> list[str]:
        """Generate candidate RTSP URLs for cameras with no media service.

        Uses common ONVIF and camera manufacturer paths. This fallback is
        essential for cameras like Digital Watchdog DVRs that don't expose
        an ONVIF media service but do respond on standard RTSP paths.

        Parameters
        ----------
        device : dict
            Device info from discover_onvif_devices()

        Returns
        -------
        list[str]
            List of candidate RTSP URLs to test.
        """
        ip = device['ip']
        candidates = []

        # Standard ONVIF profile paths
        for profile in ["profile0", "profile1", "profile2"]:
            candidates.append(f"rtsp://{ip}:554/{profile}")

        # Generic stream paths
        for stream in ["stream0", "stream1", "stream2"]:
            candidates.append(f"rtsp://{ip}:554/{stream}")

        # Live/main stream variants
        candidates.extend([
            f"rtsp://{ip}:554/live",
            f"rtsp://{ip}:554/live/main",
            f"rtsp://{ip}:554/live/0",
            f"rtsp://{ip}:554/live/1",
        ])

        # Fallback to root path
        candidates.append(f"rtsp://{ip}:554/")

        logger.debug("Generated %d candidate RTSP URLs for fallback testing", len(candidates))
        return candidates

    @staticmethod
    def get_rtsp_urls_from_onvif_device(device: dict, username: str | None = None, password: str | None = None) -> list[str]:
        """Extract RTSP stream URLs from an ONVIF device.

        First tries the ONVIF media service. If that fails or is unavailable,
        tests common RTSP paths to discover working streams.

        Parameters
        ----------
        device : dict
            Device info from discover_onvif_devices()
        username : str | None
            Optional username for authentication
        password : str | None
            Optional password for authentication

        Returns
        -------
        list[str]
            List of RTSP URLs for available streams
        """
        rtsp_urls = []

        if 'media' in device['services']:
            media_url = device['services']['media']

            try:
                # Create SOAP request for GetProfiles
                auth = (username, password) if username and password else None
                headers = {
                    'Content-Type': 'application/soap+xml; charset=utf-8',
                    'SOAPAction': '"http://www.onvif.org/ver10/media/wsdl/GetProfiles"'
                }

                # GetProfiles request
                profiles_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="http://www.onvif.org/ver10/media/wsdl">
    <soap:Body>
        <media:GetProfiles/>
    </soap:Body>
</soap:Envelope>"""

                response = requests.post(media_url, data=profiles_soap, headers=headers, auth=auth, timeout=10)

                if response.status_code == 200:
                    root = ET.fromstring(response.content)

                    # Define namespaces for XPath queries
                    namespaces = {
                        'media': 'http://www.onvif.org/ver10/media/wsdl',
                        'soap': 'http://www.w3.org/2003/05/soap-envelope'
                    }

                    # Extract profile tokens
                    profiles = root.findall(".//media:Profiles", namespaces)
                    for profile in profiles:
                        profile_token = profile.get('token')
                        if profile_token:
                            # GetStreamUri request for this profile
                            stream_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="http://www.onvif.org/ver10/media/wsdl">
    <soap:Body>
        <media:GetStreamUri>
            <media:StreamSetup>
                <media:Stream>RTP-Unicast</media:Stream>
                <media:Transport>
                    <media:Protocol>RTSP</media:Protocol>
                </media:Transport>
            </media:StreamSetup>
            <media:ProfileToken>{profile_token}</media:ProfileToken>
        </media:GetStreamUri>
    </soap:Body>
</soap:Envelope>"""

                            stream_response = requests.post(media_url, data=stream_soap, headers=headers, auth=auth, timeout=10)

                            if stream_response.status_code == 200:
                                stream_root = ET.fromstring(stream_response.content)
                                uri_elem = stream_root.find(".//media:Uri", namespaces)
                                if uri_elem is not None and uri_elem.text:
                                    rtsp_url = uri_elem.text.strip()
                                    if username and password:
                                        rtsp_url = _build_rtsp_url(rtsp_url, username, password)
                                    rtsp_urls.append(rtsp_url)
                                    logger.info("Found RTSP stream: %s", _safe_url(rtsp_url))

                else:
                    logger.warning("Failed to get profiles from %s: HTTP %d", media_url, response.status_code)

            except requests.RequestException as e:
                logger.warning("Failed to query media service %s: %s", media_url, e)
            except ET.ParseError as e:
                logger.warning("Failed to parse SOAP response from %s: %s", media_url, e)

        # If ONVIF media service didn't work, or if we got no profiles, test candidate URLs
        if not rtsp_urls:
            logger.info("Testing candidate RTSP paths for device %s", device['ip'])
            candidates = RTSPCamera._generate_candidate_rtsp_urls(device)

            for candidate in candidates:
                # Build URL with credentials if provided
                if username or password:
                    test_url = _build_rtsp_url(candidate, username, password)
                else:
                    test_url = candidate

                # Test if this URL works
                ok, info = RTSPCamera.test_connection(test_url, timeout=3.0)
                if ok:
                    rtsp_urls.append(test_url)
                    logger.info("Candidate RTSP path works: %s", _safe_url(test_url))

                # Return after finding first working stream to avoid timeout
                if rtsp_urls:
                    break

        return rtsp_urls

