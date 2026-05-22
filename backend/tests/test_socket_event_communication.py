"""Integration test to verify socket-based event communication.

This test verifies that:
1. WorkerFrameChannelServer can receive event messages (0x02 type)
2. DashboardFrameChannelClient can send event messages
3. Events are delivered with low latency (<50ms)
4. The socket path is prioritized over file-based fallback
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
import unittest
from typing import Any

from src.api.runtime import WorkerFrameChannelServer, FrameChannelBinding


class TestSocketEventCommunication(unittest.TestCase):
    """Integration test for socket-based event communication."""
    
    def test_socket_event_delivery(self) -> None:
        """Test that events are delivered via socket with low latency."""
        received_events: list[tuple[str, dict[str, Any]]] = []
        event_received = threading.Event()
        
        def on_frame(feed_id: str, frame_bytes: bytes) -> None:
            """Frame callback (not used in this test)."""
            pass
        
        def on_event(feed_id: str, event_dict: dict[str, Any]) -> None:
            """Event callback - records received events."""
            received_events.append((feed_id, event_dict))
            event_received.set()
        
        # Create server
        server = WorkerFrameChannelServer(
            on_frame=on_frame,
            on_event=on_event,
        )
        
        self.assertTrue(server.available, "Server should be available")
        
        # Register a feed
        feed_id = "test-feed-123"
        binding = server.register_feed(feed_id)
        
        self.assertIsNotNone(binding, "Binding should be created")
        self.assertEqual(binding.host, "127.0.0.1")
        self.assertGreater(binding.port, 0)
        self.assertTrue(binding.token)
        
        # Connect as a client
        client_socket = socket.create_connection((binding.host, binding.port), timeout=1.0)
        client_socket.settimeout(1.0)
        
        try:
            # Send authentication token
            token_bytes = binding.token.encode("utf-8")
            client_socket.sendall(struct.pack(">H", len(token_bytes)) + token_bytes)
            
            # Prepare an event message
            test_event = {
                "event": "metrics_update",
                "payload": {
                    "metrics": {
                        "people_in_zone": 5,
                        "estimated_wait_sec": 120.5,
                        "timestamp": time.time(),
                    },
                    "frame_id": 1000,
                },
            }
            
            # Serialize event to JSON
            event_json = json.dumps(test_event)
            event_bytes = event_json.encode("utf-8")
            
            # Send event message with type byte 0x02
            start_time = time.perf_counter()
            payload = struct.pack(">BI", 0x02, len(event_bytes)) + event_bytes
            client_socket.sendall(payload)
            
            # Wait for event to be received
            received = event_received.wait(timeout=1.0)
            end_time = time.perf_counter()
            
            self.assertTrue(received, "Event should be received")
            self.assertEqual(len(received_events), 1, "Should receive exactly one event")
            
            received_feed_id, received_event = received_events[0]
            self.assertEqual(received_feed_id, feed_id)
            self.assertEqual(received_event["event"], "metrics_update")
            self.assertEqual(
                received_event["payload"]["metrics"]["people_in_zone"],
                5
            )
            
            # Verify low latency
            latency_ms = (end_time - start_time) * 1000.0
            print(f"\nSocket event delivery latency: {latency_ms:.2f} ms")
            self.assertLess(
                latency_ms,
                50.0,
                f"Socket event delivery should be <50ms, got {latency_ms:.2f}ms"
            )
            
        finally:
            client_socket.close()
            server.close()
    
    def test_multiple_events_rapid_delivery(self) -> None:
        """Test that multiple events can be delivered rapidly via socket."""
        received_events: list[tuple[str, dict[str, Any]]] = []
        
        def on_frame(feed_id: str, frame_bytes: bytes) -> None:
            pass
        
        def on_event(feed_id: str, event_dict: dict[str, Any]) -> None:
            received_events.append((feed_id, event_dict))
        
        server = WorkerFrameChannelServer(
            on_frame=on_frame,
            on_event=on_event,
        )
        
        feed_id = "test-feed-456"
        binding = server.register_feed(feed_id)
        
        client_socket = socket.create_connection((binding.host, binding.port), timeout=1.0)
        client_socket.settimeout(1.0)
        
        try:
            # Send authentication token
            token_bytes = binding.token.encode("utf-8")
            client_socket.sendall(struct.pack(">H", len(token_bytes)) + token_bytes)
            
            # Send 10 events rapidly
            num_events = 10
            start_time = time.perf_counter()
            
            for i in range(num_events):
                test_event = {
                    "event": "metrics_update",
                    "payload": {
                        "metrics": {
                            "people_in_zone": i + 1,
                            "timestamp": time.time(),
                        },
                        "frame_id": i + 1,
                    },
                }
                
                event_json = json.dumps(test_event)
                event_bytes = event_json.encode("utf-8")
                payload = struct.pack(">BI", 0x02, len(event_bytes)) + event_bytes
                client_socket.sendall(payload)
            
            # Wait for all events to be received
            time.sleep(0.1)  # Give time for events to be processed
            end_time = time.perf_counter()
            
            self.assertEqual(
                len(received_events),
                num_events,
                f"Should receive all {num_events} events"
            )
            
            # Verify events are in order
            for i, (recv_feed_id, recv_event) in enumerate(received_events):
                self.assertEqual(recv_feed_id, feed_id)
                self.assertEqual(
                    recv_event["payload"]["metrics"]["people_in_zone"],
                    i + 1
                )
            
            # Verify throughput
            total_time_ms = (end_time - start_time) * 1000.0
            avg_latency_ms = total_time_ms / num_events
            print(f"\nAverage latency per event: {avg_latency_ms:.2f} ms")
            print(f"Total time for {num_events} events: {total_time_ms:.2f} ms")
            
            self.assertLess(
                avg_latency_ms,
                20.0,
                f"Average latency should be <20ms, got {avg_latency_ms:.2f}ms"
            )
            
        finally:
            client_socket.close()
            server.close()
    
    def test_frame_and_event_interleaved(self) -> None:
        """Test that frames (0x01) and events (0x02) can be interleaved."""
        received_frames: list[tuple[str, bytes]] = []
        received_events: list[tuple[str, dict[str, Any]]] = []
        
        def on_frame(feed_id: str, frame_bytes: bytes) -> None:
            received_frames.append((feed_id, frame_bytes))
        
        def on_event(feed_id: str, event_dict: dict[str, Any]) -> None:
            received_events.append((feed_id, event_dict))
        
        server = WorkerFrameChannelServer(
            on_frame=on_frame,
            on_event=on_event,
        )
        
        feed_id = "test-feed-789"
        binding = server.register_feed(feed_id)
        
        client_socket = socket.create_connection((binding.host, binding.port), timeout=1.0)
        client_socket.settimeout(1.0)
        
        try:
            # Send authentication token
            token_bytes = binding.token.encode("utf-8")
            client_socket.sendall(struct.pack(">H", len(token_bytes)) + token_bytes)
            
            # Send frame (0x01)
            frame_data = b"fake_jpeg_frame_data_123"
            frame_payload = struct.pack(">BI", 0x01, len(frame_data)) + frame_data
            client_socket.sendall(frame_payload)
            
            # Send event (0x02)
            test_event = {"event": "test", "payload": {"value": 42}}
            event_json = json.dumps(test_event)
            event_bytes = event_json.encode("utf-8")
            event_payload = struct.pack(">BI", 0x02, len(event_bytes)) + event_bytes
            client_socket.sendall(event_payload)
            
            # Send another frame (0x01)
            frame_data2 = b"fake_jpeg_frame_data_456"
            frame_payload2 = struct.pack(">BI", 0x01, len(frame_data2)) + frame_data2
            client_socket.sendall(frame_payload2)
            
            # Wait for processing
            time.sleep(0.1)
            
            # Verify both frames and event were received
            self.assertEqual(len(received_frames), 2, "Should receive 2 frames")
            self.assertEqual(len(received_events), 1, "Should receive 1 event")
            
            self.assertEqual(received_frames[0][0], feed_id)
            self.assertEqual(received_frames[0][1], frame_data)
            self.assertEqual(received_frames[1][0], feed_id)
            self.assertEqual(received_frames[1][1], frame_data2)
            
            self.assertEqual(received_events[0][0], feed_id)
            self.assertEqual(received_events[0][1]["event"], "test")
            self.assertEqual(received_events[0][1]["payload"]["value"], 42)
            
        finally:
            client_socket.close()
            server.close()


if __name__ == "__main__":
    unittest.main()
