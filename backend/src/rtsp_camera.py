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
from typing import Any, Generator
from urllib.parse import unquote, urlparse, urlunparse
from xml.etree import ElementTree as ET

import cv2
import numpy as np
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

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



def _iter_soap_auth_candidates(
    username: str | None,
    password: str | None,
) -> list[HTTPDigestAuth | HTTPBasicAuth | None]:
    """Return auth candidates for ONVIF SOAP requests.

    Many cameras expect HTTP Digest for ONVIF services, while others still
    accept basic auth. We try both before giving up.
    """
    if not username and not password:
        return [None]

    auth_username = username or ""
    auth_password = password or ""
    return [HTTPDigestAuth(auth_username, auth_password), HTTPBasicAuth(auth_username, auth_password), None]


def _soap_post_with_auth_fallback(
    url: str,
    *,
    data: str,
    headers: dict[str, str],
    username: str | None = None,
    password: str | None = None,
    timeout: float = 10,
) -> requests.Response | None:
    """POST a SOAP request using digest/basic/no-auth fallbacks."""
    last_exc: Exception | None = None
    for auth in _iter_soap_auth_candidates(username, password):
        try:
            response = requests.post(url, data=data, headers=headers, auth=auth, timeout=timeout)
        except requests.RequestException as exc:
            last_exc = exc
            continue

        if response.status_code in {200, 500}:
            # 500 may still carry a SOAP fault or malformed response; callers
            # inspect the body and/or status before deciding whether to continue.
            return response

    if last_exc is not None:
        logger.warning("SOAP request to %s failed: %s", url, last_exc)
    return None


def _extract_capability_xaddr(response_content: bytes, capability_name: str) -> str | None:
    """Extract a service XAddr from an ONVIF GetCapabilities response."""
    try:
        root = ET.fromstring(response_content)
    except ET.ParseError:
        return None

    capability_names = {capability_name, capability_name.lower(), capability_name.upper()}

    for element in root.iter():
        if not element.tag.endswith("Capabilities"):
            continue

        for child in list(element):
            child_name = child.tag.rsplit("}", 1)[-1]
            if child_name not in capability_names:
                continue

            for grandchild in list(child):
                if grandchild.tag.rsplit("}", 1)[-1] == "XAddr" and grandchild.text:
                    return grandchild.text.strip()

    return None


def _extract_service_xaddr_from_services_response(response_content: bytes) -> str | None:
    """Extract the media service XAddr from an ONVIF GetServices response."""
    try:
        root = ET.fromstring(response_content)
    except ET.ParseError:
        return None

    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "Service":
            continue

        namespace = None
        xaddr = None
        for child in list(element):
            child_name = child.tag.rsplit("}", 1)[-1]
            if child_name == "Namespace" and child.text:
                namespace = child.text.strip()
            elif child_name == "XAddr" and child.text:
                xaddr = child.text.strip()

        if not namespace or not xaddr:
            continue

        namespace_lower = namespace.lower()
        if "media" in namespace_lower:
            return xaddr

    return None


def _discover_media_xaddr_from_device_service(
    device_service_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Query the device service for the advertised media endpoint.

    Some cameras do not expose the media XAddr in WS-Discovery ProbeMatch
    responses but do publish it through the device service capabilities. This
    helper asks the device service for GetCapabilities and returns the media
    XAddr when present.
    """
    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": '"http://www.onvif.org/ver10/device/wsdl/GetCapabilities"',
    }
    request_body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <soap:Body>
        <tds:GetCapabilities>
            <tds:Category>All</tds:Category>
        </tds:GetCapabilities>
    </soap:Body>
</soap:Envelope>"""

    try:
        response = _soap_post_with_auth_fallback(
            device_service_url,
            data=request_body,
            headers=headers,
            username=username,
            password=password,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to get capabilities from %s: %s", device_service_url, exc)
        return None

    if response is None:
        return None

    if response.status_code != 200:
        logger.warning(
            "Failed to get capabilities from %s: HTTP %d",
            device_service_url,
            response.status_code,
        )
        return None

    media_xaddr = _extract_capability_xaddr(response.content, "Media")
    if media_xaddr:
        return media_xaddr

    # Media2 is a valid ONVIF media endpoint on newer cameras. We still return
    # it here so callers can decide whether to use the media2-specific flow.
    media_xaddr = _extract_capability_xaddr(response.content, "Media2")
    if media_xaddr:
        return media_xaddr

    services_headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": '"http://www.onvif.org/ver10/device/wsdl/GetServices"',
    }
    services_request_body = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
    <soap:Body>
        <tds:GetServices>
            <tds:IncludeCapability>true</tds:IncludeCapability>
        </tds:GetServices>
    </soap:Body>
</soap:Envelope>"""

    try:
        response = _soap_post_with_auth_fallback(
            device_service_url,
            data=services_request_body,
            headers=services_headers,
            username=username,
            password=password,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to query device services from %s: %s", device_service_url, exc)
        return None

    if response is None or response.status_code != 200:
        return None

    return _extract_service_xaddr_from_services_response(response.content)


def _extract_rtsp_uri_from_stream_response(response_content: bytes) -> str | None:
    """Parse the RTSP URI from an ONVIF GetStreamUri response."""
    try:
        root = ET.fromstring(response_content)
    except ET.ParseError:
        return None

    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] != "Uri":
            continue

        if elem.text:
            uri = elem.text.strip()
            if uri.startswith("rtsp://"):
                return uri

    return None


def _query_onvif_media_streams(
    media_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
) -> list[str]:
    """Return RTSP stream URLs advertised by an ONVIF media service."""
    is_media2 = "ver20" in media_url or "media2" in media_url.lower()
    media_namespace = (
        "http://www.onvif.org/ver20/media/wsdl" if is_media2 else "http://www.onvif.org/ver10/media/wsdl"
    )
    soap_action_prefix = "http://www.onvif.org/ver20/media/wsdl" if is_media2 else "http://www.onvif.org/ver10/media/wsdl"

    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": f'"{soap_action_prefix}/GetProfiles"',
    }

    if is_media2:
        profiles_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="{media_namespace}">
    <soap:Body>
        <media:GetProfiles/>
    </soap:Body>
</soap:Envelope>"""
    else:
        profiles_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="{media_namespace}">
    <soap:Body>
        <media:GetProfiles/>
    </soap:Body>
</soap:Envelope>"""

    try:
        response = _soap_post_with_auth_fallback(
            media_url,
            data=profiles_soap,
            headers=headers,
            username=username,
            password=password,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Failed to query media service %s: %s", media_url, exc)
        return []

    if response is None:
        return []

    if response.status_code != 200:
        logger.warning("Failed to get profiles from %s: HTTP %d", media_url, response.status_code)
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.warning("Failed to parse SOAP response from %s: %s", media_url, exc)
        return []

    namespaces = {
        "media": "http://www.onvif.org/ver10/media/wsdl",
        "media2": "http://www.onvif.org/ver20/media/wsdl",
    }

    profile_tokens: list[str] = []
    for profile in root.iter():
        if profile.tag.rsplit("}", 1)[-1] != "Profiles":
            continue

        token = profile.attrib.get("token") or profile.attrib.get("_token")
        if token:
            profile_tokens.append(token)

    rtsp_urls: list[str] = []
    for profile_token in profile_tokens:
        if is_media2:
            stream_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="{media_namespace}">
    <soap:Body>
        <media:GetStreamUri>
            <media:Protocol>RTSP</media:Protocol>
            <media:ProfileToken>{profile_token}</media:ProfileToken>
        </media:GetStreamUri>
    </soap:Body>
</soap:Envelope>"""
        else:
            stream_soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:media="{media_namespace}">
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

        try:
            stream_response = _soap_post_with_auth_fallback(
                media_url,
                data=stream_soap,
                headers={
                    "Content-Type": "application/soap+xml; charset=utf-8",
                    "SOAPAction": f'"{soap_action_prefix}/GetStreamUri"',
                },
                timeout=10,
                username=username,
                password=password,
            )
        except requests.RequestException as exc:
            logger.warning("Failed to query stream URI from %s: %s", media_url, exc)
            continue

        if stream_response is None:
            continue

        if stream_response.status_code != 200:
            continue

        rtsp_url = _extract_rtsp_uri_from_stream_response(stream_response.content)
        if rtsp_url:
            if username and password:
                rtsp_url = _build_rtsp_url(rtsp_url, username, password)
            rtsp_urls.append(rtsp_url)
            logger.info("Found RTSP stream: %s", _safe_url(rtsp_url))

    return rtsp_urls


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
    def get_rtsp_urls_from_onvif_device(
        device: dict,
        username: str | None = None,
        password: str | None = None,
    ) -> list[str]:
        """Extract RTSP stream URLs from an ONVIF device.

        First tries the ONVIF media service. If that fails or is unavailable,
        it resolves the media service from the device service capabilities and
        the device service list.

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
        device_service_url = device.get("services", {}).get("device")

        media_urls: list[str] = []
        if device.get("services", {}).get("media"):
            media_urls.append(device["services"]["media"])

        if not media_urls and device_service_url:
            resolved_media_url = _discover_media_xaddr_from_device_service(
                device_service_url,
                username=username,
                password=password,
            )
            if resolved_media_url:
                media_urls.append(resolved_media_url)
                logger.info(
                    "Resolved media service for %s via device capabilities: %s",
                    device.get("ip", "unknown"),
                    resolved_media_url,
                )

        for media_url in media_urls:
            rtsp_urls.extend(
                url
                for url in _query_onvif_media_streams(
                    media_url,
                    username=username,
                    password=password,
                )
                if url not in rtsp_urls
            )

            if rtsp_urls:
                break

        return rtsp_urls

