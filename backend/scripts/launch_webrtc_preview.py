"""Terminal helper for launching and inspecting a WebRTC-ready feed.

This script talks to the FastAPI backend, creates or reuses a feed, starts it,
and prints the MediaMTX URLs that the GUI would normally derive for playback.

It does not replace a native browser WebRTC client. For terminal-only viewing,
use ``--watch`` to open the MediaMTX relay with ffplay.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


DEFAULT_API_BASE_URL = os.getenv("QUEUEVISION_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_MEDIAMTX_WHEP_BASE_URL = os.getenv("MEDIAMTX_WHEP_BASE_URL", "http://127.0.0.1:8889").rstrip("/")
DEFAULT_MEDIAMTX_CONTROL_API_BASE_URL = os.getenv(
    "MEDIAMTX_CONTROL_API_BASE_URL",
    "http://127.0.0.1:9997",
).rstrip("/")
DEFAULT_RTSP_RELAY_HOST = os.getenv("MEDIAMTX_RTSP_RELAY_HOST", "127.0.0.1").strip() or "127.0.0.1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENV_FFPLAY = PROJECT_ROOT / ".venv" / "Scripts" / "ffplay.exe"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="launch-webrtc-preview",
        description="Create or reuse a feed, start it, and print the MediaMTX playback URLs.",
    )
    parser.add_argument("--source", required=True, help="RTSP source URL to register and launch.")
    parser.add_argument(
        "--name",
        default=None,
        help="Feed name. Defaults to a name derived from the source host.",
    )
    parser.add_argument(
        "--model-size",
        choices=["n", "s", "m", "l", "x"],
        default="s",
        help="YOLO model size to register with the feed. (default: s)",
    )
    parser.add_argument("--rtsp-user", default=None, help="Optional RTSP username.")
    parser.add_argument("--rtsp-pass", default=None, help="Optional RTSP password.")
    parser.add_argument(
        "--rtsp-transport",
        choices=["tcp", "udp"],
        default="tcp",
        help="RTSP transport for the backend worker. (default: tcp)",
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help=f"Backend API base URL. (default: {DEFAULT_API_BASE_URL})",
    )
    parser.add_argument(
        "--mediamtx-whep-base-url",
        default=DEFAULT_MEDIAMTX_WHEP_BASE_URL,
        help=f"MediaMTX WHEP base URL. (default: {DEFAULT_MEDIAMTX_WHEP_BASE_URL})",
    )
    parser.add_argument(
        "--mediamtx-control-api-base-url",
        default=DEFAULT_MEDIAMTX_CONTROL_API_BASE_URL,
        help=f"MediaMTX Control API base URL. (default: {DEFAULT_MEDIAMTX_CONTROL_API_BASE_URL})",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Open the MediaMTX RTSP relay in ffplay after the feed is ready.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for the feed to become WebRTC-ready. (default: 20.0)",
    )
    return parser.parse_args()


def _api_request(session: requests.Session, method: str, url: str, **kwargs: Any) -> Any:
    try:
        response = session.request(method, url, timeout=kwargs.pop("timeout", 10.0), **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach the backend API at {url}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code >= 400:
        detail: str | None = None
        if isinstance(payload, dict):
            candidate = payload.get("detail") or payload.get("message")
            if isinstance(candidate, str):
                detail = candidate
            else:
                detail = str(candidate) if candidate is not None else None

        raise RuntimeError(
            f"HTTP {response.status_code} from {url}: {detail or response.text.strip() or 'unknown error'}"
        )

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]

    return payload


def _default_feed_name(source: str) -> str:
    source = source.strip()
    if "@" in source and "://" in source:
        source = source.rsplit("@", 1)[-1]
    host = source.split("/", 1)[0]
    host = host.split(":", 1)[0].strip()
    if not host:
        return "terminal-preview"
    return f"terminal-preview-{host.replace('.', '-')}"


def _find_existing_feed(feeds: list[dict[str, Any]], name: str, source: str) -> dict[str, Any] | None:
    for feed in feeds:
        if feed.get("name") == name and feed.get("source") == source:
            return feed
    return None


def _ensure_running_feed(session: requests.Session, api_base_url: str, args: argparse.Namespace) -> dict[str, Any]:
    feeds = _api_request(session, "GET", f"{api_base_url}/api/feeds")
    if not isinstance(feeds, list):
        raise RuntimeError("Unexpected feed list payload returned by the backend.")

    feed_name = args.name or _default_feed_name(args.source)
    feed = _find_existing_feed(feeds, feed_name, args.source)

    if feed is None:
        create_payload: dict[str, Any] = {
            "name": feed_name,
            "source": args.source,
            "model_size": args.model_size,
        }
        if args.rtsp_user:
            create_payload["rtsp_username"] = args.rtsp_user
        if args.rtsp_pass:
            create_payload["rtsp_password"] = args.rtsp_pass
        if args.rtsp_transport:
            create_payload["rtsp_transport"] = args.rtsp_transport

        feed = _api_request(session, "POST", f"{api_base_url}/api/feeds", json=create_payload)

    feed_id = feed.get("feed_id")
    if not isinstance(feed_id, str) or not feed_id.strip():
        raise RuntimeError("Backend returned a feed without a valid feed_id.")

    if feed.get("status") != "running":
        try:
            feed = _api_request(session, "POST", f"{api_base_url}/api/feeds/{feed_id}/start")
        except RuntimeError as exc:
            message = str(exc)
            if "Feed is already running" not in message:
                raise

    return feed


def _wait_for_webrtc_ready(
    session: requests.Session,
    api_base_url: str,
    feed_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    last_capabilities: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        capabilities = _api_request(session, "GET", f"{api_base_url}/api/feeds/{feed_id}/transport")
        if not isinstance(capabilities, dict):
            raise RuntimeError("Unexpected transport payload returned by the backend.")

        last_capabilities = capabilities
        webrtc = capabilities.get("webrtc") or {}
        if isinstance(webrtc, dict) and webrtc.get("enabled") and webrtc.get("ready"):
            return capabilities

        time.sleep(0.5)

    if last_capabilities is None:
        raise RuntimeError("Timed out waiting for transport capabilities.")

    webrtc = last_capabilities.get("webrtc") or {}
    reason = webrtc.get("reason") if isinstance(webrtc, dict) else None
    raise RuntimeError(f"WebRTC was not ready before timeout: {reason or 'unknown reason'}")


def _ensure_mediamtx_path(session: requests.Session, control_api_base_url: str, source: str, path_name: str) -> None:
    payload = {
        "source": source,
        "sourceOnDemand": True,
        "sourceOnDemandStartTimeout": "10s",
        "sourceOnDemandCloseAfter": "10s",
        "rtspTransport": "tcp",
    }
    encoded_path = requests.utils.quote(path_name.strip(), safe="")
    patch_url = f"{control_api_base_url.rstrip('/')}/v3/config/paths/patch/{encoded_path}"
    add_url = f"{control_api_base_url.rstrip('/')}/v3/config/paths/add/{encoded_path}"

    response = session.patch(patch_url, json=payload, timeout=10.0)
    if response.status_code == 200:
        return

    if response.status_code != 404:
        raise RuntimeError(
            f"MediaMTX path patch failed with HTTP {response.status_code}: {response.text.strip() or 'unknown error'}"
        )

    response = session.post(add_url, json=payload, timeout=10.0)
    if response.status_code >= 400:
        raise RuntimeError(
            f"MediaMTX path creation failed with HTTP {response.status_code}: {response.text.strip() or 'unknown error'}"
        )


def _print_summary(feed: dict[str, Any], capabilities: dict[str, Any], whep_base_url: str, rtsp_relay_host: str) -> None:
    feed_id = str(feed["feed_id"])
    webrtc = capabilities["webrtc"]
    path_name = webrtc.get("path_name") or feed_id
    whep_url = f"{whep_base_url}/{path_name}/whep"
    web_url = f"{whep_base_url}/{path_name}"
    rtsp_url = f"rtsp://{rtsp_relay_host}:8554/{path_name}"

    print(f"Feed ID      : {feed_id}")
    print(f"Feed status  : {feed.get('status')}")
    print(f"WebRTC ready : {webrtc.get('ready')} ({webrtc.get('source_mode')})")
    print(f"Path name    : {path_name}")
    print(f"WebRTC page  : {web_url}")
    print(f"WHEP URL     : {whep_url}")
    print(f"RTSP relay   : {rtsp_url}")


def _watch_with_ffplay(rtsp_url: str) -> int:
    ffplay_command = str(VENV_FFPLAY) if VENV_FFPLAY.is_file() else "ffplay"
    command = [
        ffplay_command,
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-framedrop",
        "-rtsp_transport",
        "tcp",
        rtsp_url,
    ]

    try:
        return subprocess.call(command)
    except FileNotFoundError:
        print(f"ffplay was not found at {ffplay_command}.")
        print(f"Run this command instead: {' '.join(command)}")
        return 1


def main() -> None:
    args = _parse_args()
    if args.source.strip().lower().startswith("rtsp://") and args.rtsp_pass and not args.rtsp_user:
        raise SystemExit("--rtsp-pass requires --rtsp-user.")

    session = requests.Session()

    feed = _ensure_running_feed(session, args.api_base_url, args)
    feed_id = str(feed["feed_id"])
    capabilities = _wait_for_webrtc_ready(session, args.api_base_url, feed_id, args.timeout)
    _print_summary(feed, capabilities, args.mediamtx_whep_base_url, DEFAULT_RTSP_RELAY_HOST)

    if args.watch:
        path_name = capabilities["webrtc"].get("path_name") or feed_id
        _ensure_mediamtx_path(session, args.mediamtx_control_api_base_url, args.source, path_name)
        rtsp_url = f"rtsp://{DEFAULT_RTSP_RELAY_HOST}:8554/{path_name}"
        raise SystemExit(_watch_with_ffplay(rtsp_url))


if __name__ == "__main__":
    main()