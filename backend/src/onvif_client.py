"""ONVIF discovery and RTSP stream resolution helpers.

This module isolates the ONVIF control-plane logic from the RTSP capture
implementation so the camera helper stays focused on OpenCV streaming.
"""

from __future__ import annotations

import logging
import select
import socket
import time
import uuid
from urllib.parse import unquote
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

logger = logging.getLogger("queue_system.rtsp_camera")


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
    return [
        HTTPDigestAuth(auth_username, auth_password),
        HTTPBasicAuth(auth_username, auth_password),
        None,
    ]


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

        if "media" in namespace.lower():
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
    soap_action_prefix = (
        "http://www.onvif.org/ver20/media/wsdl" if is_media2 else "http://www.onvif.org/ver10/media/wsdl"
    )

    headers = {
        "Content-Type": "application/soap+xml; charset=utf-8",
        "SOAPAction": f'"{soap_action_prefix}/GetProfiles"',
    }

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
            rtsp_urls.append(rtsp_url)
            logger.info("Found RTSP stream: %s", rtsp_url)

    return rtsp_urls


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

            namespaces = {
                "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
                "wsd10": "http://docs.oasis-open.org/ws-dd/ns/discovery/2009/01",
                "dn": "http://www.onvif.org/ver10/network/wsdl",
                "soap": "http://www.w3.org/2003/05/soap-envelope",
            }

            xaddrs_elem = None
            for prefix in ("d", "wsd10", "dn"):
                xaddrs_elem = root.find(f".//{prefix}:XAddrs", namespaces)
                if xaddrs_elem is not None and xaddrs_elem.text:
                    break
            if xaddrs_elem is None or not xaddrs_elem.text:
                return None

            xaddrs = xaddrs_elem.text.strip()
            device_ip = sender_addr[0]

            scopes_elem = None
            for prefix in ("d", "wsd10", "dn"):
                scopes_elem = root.find(f".//{prefix}:Scopes", namespaces)
                if scopes_elem is not None and scopes_elem.text:
                    break
            scopes = scopes_elem.text if scopes_elem is not None else ""

            device_info = {
                "ip": device_ip,
                "name": "Unknown",
                "manufacturer": "Unknown",
                "model": "Unknown",
                "serial": "Unknown",
                "hardware": "Unknown",
                "location": "Unknown",
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
        """Return all /24 host IPs for each routable local IP."""
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
        """Return all non-loopback local IPv4 addresses."""
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
        """Discover ONVIF devices on the network using WS-Discovery."""
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
                try:
                    bind_ip = local_ip if local_ip != "0.0.0.0" else ""
                    sock.bind((bind_ip, 0))
                    if local_ip != "0.0.0.0":
                        sock.setsockopt(
                            socket.IPPROTO_IP,
                            socket.IP_MULTICAST_IF,
                            socket.inet_aton(local_ip),
                        )
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

            subnet_hosts = ONVIFDiscovery._get_subnet_hosts(local_ips)
            unicast_sock: socket.socket | None = None
            if subnet_hosts:
                logger.info(
                    "Sending unicast ONVIF probes to %d hosts on local subnets …",
                    len(subnet_hosts),
                )
                unicast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                unicast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                unicast_sock.bind(("", 0))
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


def discover_ip_devices(timeout: float = 5.0) -> list[dict]:
    """Backward-compatible alias for :meth:`discover_onvif_devices`."""
    return ONVIFDiscovery.discover_devices(timeout)


def discover_onvif_devices(timeout: float = 5.0) -> list[dict]:
    """Discover ONVIF-compatible IP cameras on the local network."""
    return ONVIFDiscovery.discover_devices(timeout)


def get_rtsp_urls_from_onvif_device(
    device: dict,
    username: str | None = None,
    password: str | None = None,
) -> list[str]:
    """Extract RTSP stream URLs from an ONVIF device."""
    rtsp_urls: list[str] = []
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
