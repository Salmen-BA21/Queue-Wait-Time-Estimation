"""Unit tests for ONVIF media resolution in the RTSP camera helper."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.rtsp_camera import (  # noqa: E402
  RTSPCamera,
)
from src.onvif_client import (
  _discover_media_xaddr_from_device_service,
  _extract_capability_xaddr,
  _extract_rtsp_uri_from_stream_response,
  get_rtsp_urls_from_onvif_device,
  _query_onvif_media_streams,
)


class TestOnvifMediaResolution(unittest.TestCase):
    """Validate the ONVIF media lookup path before RTSP fallback."""

    def test_extract_capability_xaddr_returns_media_endpoint(self) -> None:
        response_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetCapabilitiesResponse>
      <tds:Capabilities>
        <tds:Media>
          <tds:XAddr>http://192.168.1.90/onvif/media</tds:XAddr>
        </tds:Media>
      </tds:Capabilities>
    </tds:GetCapabilitiesResponse>
  </soap:Body>
</soap:Envelope>
"""

        xaddr = _extract_capability_xaddr(response_xml, "Media")

        self.assertEqual(xaddr, "http://192.168.1.90/onvif/media")

    def test_extract_rtsp_uri_from_stream_response(self) -> None:
        response_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
               xmlns:tt="http://www.onvif.org/ver10/schema">
  <soap:Body>
    <trt:GetStreamUriResponse>
      <trt:MediaUri>
        <tt:Uri>rtsp://192.168.1.90:554/profile1</tt:Uri>
      </trt:MediaUri>
    </trt:GetStreamUriResponse>
  </soap:Body>
</soap:Envelope>
"""

        uri = _extract_rtsp_uri_from_stream_response(response_xml)

        self.assertEqual(uri, "rtsp://192.168.1.90:554/profile1")

    @patch("src.onvif_client.requests.post")
    def test_query_onvif_media_streams_returns_profile_uri(self, mock_post) -> None:
        profile_response = SimpleNamespace(
            status_code=200,
            content=b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <soap:Body>
    <trt:GetProfilesResponse>
      <trt:Profiles token="profile1"/>
    </trt:GetProfilesResponse>
  </soap:Body>
</soap:Envelope>
""",
        )

        stream_response = SimpleNamespace(
            status_code=200,
            content=b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <soap:Body>
    <trt:GetStreamUriResponse>
      <trt:MediaUri>
        <trt:Uri>rtsp://192.168.1.90:554/profile1</trt:Uri>
      </trt:MediaUri>
    </trt:GetStreamUriResponse>
  </soap:Body>
</soap:Envelope>
""",
        )

        def post_side_effect(*args, **kwargs):  # noqa: ANN001
            body = kwargs.get("data", "")
            if "GetProfiles" in body:
                return profile_response
            if "GetStreamUri" in body:
                return stream_response
            raise AssertionError(f"Unexpected SOAP body: {body}")

        mock_post.side_effect = post_side_effect

        urls = _query_onvif_media_streams("http://192.168.1.90/onvif/media")

        self.assertEqual(urls, ["rtsp://192.168.1.90:554/profile1"])

    def test_discover_media_xaddr_can_be_resolved_from_device_service(self) -> None:
        device_response = b"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <soap:Body>
    <tds:GetCapabilitiesResponse>
      <tds:Capabilities>
        <tds:Media>
          <tds:XAddr>http://192.168.1.90/onvif/media</tds:XAddr>
        </tds:Media>
      </tds:Capabilities>
    </tds:GetCapabilitiesResponse>
  </soap:Body>
</soap:Envelope>
"""

        fake_response = SimpleNamespace(status_code=200, content=device_response)

        with patch("src.onvif_client.requests.post", return_value=fake_response):
            xaddr = _discover_media_xaddr_from_device_service(
                "http://192.168.1.90/onvif/device_service"
            )

        self.assertEqual(xaddr, "http://192.168.1.90/onvif/media")

    def test_get_rtsp_urls_from_onvif_device_prefers_onvif_streams(self) -> None:
        device = {
            "ip": "192.168.1.90",
            "services": {"device": "http://192.168.1.90/onvif/device_service"},
        }

        with (
            patch("src.onvif_client._discover_media_xaddr_from_device_service", return_value="http://192.168.1.90/onvif/media"),
            patch("src.onvif_client._query_onvif_media_streams", return_value=["rtsp://192.168.1.90:554/custom"]),
          patch("src.rtsp_camera.RTSPCamera.test_connection") as mock_test_connection,
        ):
          urls = get_rtsp_urls_from_onvif_device(device)

        mock_test_connection.assert_not_called()
        self.assertEqual(urls, ["rtsp://192.168.1.90:554/custom"])


if __name__ == "__main__":
    unittest.main(verbosity=2)