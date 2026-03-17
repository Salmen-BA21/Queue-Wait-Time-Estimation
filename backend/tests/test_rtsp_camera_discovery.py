"""Unit tests for ONVIF WS-Discovery payload parsing."""

from __future__ import annotations

import sys
from pathlib import Path
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.rtsp_camera import ONVIFDiscovery


class TestONVIFDiscoveryParsing(unittest.TestCase):
    """Validate compatibility with common WS-Discovery namespace variants."""

    def test_parse_probe_match_with_ws_discovery_2005_namespace(self) -> None:
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"
               xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
               xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <soap:Body>
    <d:ProbeMatches>
      <d:ProbeMatch>
        <d:Scopes>onvif://www.onvif.org/name/Front%20Door%20Camera onvif://www.onvif.org/manufacturer/Hikvision onvif://www.onvif.org/model/DS-2CD2043G0-I</d:Scopes>
        <d:XAddrs>http://192.168.1.80/onvif/device_service http://192.168.1.80/onvif/media</d:XAddrs>
      </d:ProbeMatch>
    </d:ProbeMatches>
  </soap:Body>
</soap:Envelope>
"""

        device = ONVIFDiscovery._parse_probe_match(response_xml, ("192.168.1.80", 3702))

        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device["ip"], "192.168.1.80")
        self.assertEqual(device["name"], "Front Door Camera")
        self.assertEqual(device["manufacturer"], "Hikvision")
        self.assertEqual(device["model"], "DS-2CD2043G0-I")
        self.assertIn("device", device["services"])

    def test_parse_probe_match_with_ws_discovery_oasis_namespace(self) -> None:
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://www.w3.org/2003/05/soap-envelope"
              xmlns:wsd="http://docs.oasis-open.org/ws-dd/ns/discovery/2009/01"
              xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <env:Body>
    <wsd:ProbeMatches>
      <wsd:ProbeMatch>
        <wsd:Scopes>onvif://www.onvif.org/name/Lobby%20Camera onvif://www.onvif.org/location/Front%20Lobby</wsd:Scopes>
        <wsd:XAddrs>http://192.168.1.90/onvif/device_service</wsd:XAddrs>
      </wsd:ProbeMatch>
    </wsd:ProbeMatches>
  </env:Body>
</env:Envelope>
"""

        device = ONVIFDiscovery._parse_probe_match(response_xml, ("192.168.1.90", 3702))

        self.assertIsNotNone(device)
        assert device is not None
        self.assertEqual(device["ip"], "192.168.1.90")
        self.assertEqual(device["name"], "Lobby Camera")
        self.assertEqual(device["location"], "Front Lobby")
        self.assertIn("device", device["services"])

    def test_probe_message_uses_ws_discovery_probe_elements(self) -> None:
        probe_xml = ONVIFDiscovery._create_probe_message()

        self.assertIn('xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"', probe_xml)
        self.assertIn("<d:Probe>", probe_xml)
        self.assertIn("<d:Types>dn:NetworkVideoTransmitter</d:Types>", probe_xml)


if __name__ == "__main__":
    unittest.main()
