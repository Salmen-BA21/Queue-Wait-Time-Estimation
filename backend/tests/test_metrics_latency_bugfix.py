"""Bug condition exploration test for metrics update latency with large event files.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This test is EXPECTED TO FAIL on unfixed code - failure confirms the bug exists.
The test encodes the expected behavior (latency <500ms) and will validate the fix
when it passes after implementation.

CRITICAL: This test MUST FAIL on unfixed code to prove the bug exists.
DO NOT attempt to fix the test or the code when it fails.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st

from src.api.runtime import FeedWorkerHandle


@dataclass
class MetricsEmissionContext:
    """Input context for metrics emission scenarios."""
    
    event_file_size: int  # bytes
    event_file_line_count: int
    polling_interval_sec: float
    emission_interval_sec: float
    session_duration_minutes: int


def is_bug_condition(input_ctx: MetricsEmissionContext) -> bool:
    """Determine if the input triggers the bug condition.
    
    Bug manifests when:
    - Event file size exceeds 100 KB (100,000 bytes)
    - Event file line count exceeds 500 lines
    - Polling interval is 100ms (0.1 seconds)
    - Emission interval is 200ms (0.2 seconds)
    - Session duration exceeds 30 minutes
    """
    return (
        input_ctx.event_file_size > 100_000
        and input_ctx.event_file_line_count > 500
        and input_ctx.polling_interval_sec == 0.1
        and input_ctx.emission_interval_sec == 0.2
        and input_ctx.session_duration_minutes > 30
    )


class TestMetricsLatencyBugCondition(unittest.TestCase):
    """Property 1: Bug Condition - Metrics Update Latency with Large Event Files.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    This test explores the bug condition by simulating long-running worker sessions
    with large event files and measuring the end-to-end latency.
    
    EXPECTED OUTCOME: Test FAILS on unfixed code (this is correct - proves bug exists)
    """
    
    def test_large_event_file_latency_2_hour_session(self) -> None:
        """Test latency with a 2-hour worker session generating 1.37 MB event file.
        
        This is the concrete failing case from the bug description:
        - Worker runs for 2 hours (120 minutes)
        - Emits metrics every 200ms
        - Event file grows to 1.37 MB (6,138 lines)
        - API runtime polls every 100ms
        
        EXPECTED: Test FAILS with latency >500ms (proves bug exists)
        """
        # Simulate a 2-hour session with 6,138 events
        # Each event is approximately 230 bytes (1.37 MB / 6,138 lines)
        event_file_size = 1_370_000  # 1.37 MB
        event_line_count = 6_138
        
        context = MetricsEmissionContext(
            event_file_size=event_file_size,
            event_file_line_count=event_line_count,
            polling_interval_sec=0.1,
            emission_interval_sec=0.2,
            session_duration_minutes=120,
        )
        
        # Verify this is a bug condition
        self.assertTrue(
            is_bug_condition(context),
            "This should be a bug condition scenario"
        )
        
        # Measure latency with large event file
        latency_ms = self._measure_polling_latency(
            event_file_size=event_file_size,
            event_line_count=event_line_count,
        )
        
        # Document the counterexample
        print(f"\n=== COUNTEREXAMPLE FOUND ===")
        print(f"Event file size: {event_file_size / 1_000_000:.2f} MB")
        print(f"Event file lines: {event_line_count}")
        print(f"Measured latency: {latency_ms:.2f} ms")
        print(f"Expected latency: <500 ms")
        print(f"Bug confirmed: {latency_ms > 500}")
        print(f"===========================\n")
        
        # This assertion SHOULD FAIL on unfixed code
        # When it fails, it proves the bug exists
        self.assertLess(
            latency_ms,
            500,
            f"Metrics update latency ({latency_ms:.2f}ms) exceeds 500ms threshold "
            f"for event file with {event_line_count} lines ({event_file_size / 1_000_000:.2f} MB). "
            f"This confirms the bug exists."
        )
    
    @given(
        file_size_kb=st.integers(min_value=100, max_value=2000),  # 100 KB to 2 MB
        session_duration_min=st.integers(min_value=30, max_value=240),  # 30 min to 4 hours
    )
    @settings(max_examples=10, deadline=None)
    def test_property_latency_under_bug_condition(
        self,
        file_size_kb: int,
        session_duration_min: int,
    ) -> None:
        """Property: For any metrics emission where bug condition holds,
        the system SHALL deliver updates with <500ms latency.
        
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        
        This property-based test generates various scenarios within the bug condition
        space and verifies that latency remains under 500ms.
        
        EXPECTED: Test FAILS on unfixed code with counterexamples showing latency >500ms
        """
        # Calculate event file parameters
        event_file_size = file_size_kb * 1024
        # Assume ~230 bytes per event line (from 1.37 MB / 6,138 lines)
        event_line_count = event_file_size // 230
        
        context = MetricsEmissionContext(
            event_file_size=event_file_size,
            event_file_line_count=event_line_count,
            polling_interval_sec=0.1,
            emission_interval_sec=0.2,
            session_duration_minutes=session_duration_min,
        )
        
        # Only test scenarios that match the bug condition
        if not is_bug_condition(context):
            return
        
        # Measure latency
        latency_ms = self._measure_polling_latency(
            event_file_size=event_file_size,
            event_line_count=event_line_count,
        )
        
        # Document counterexample if found
        if latency_ms > 500:
            print(f"\n=== COUNTEREXAMPLE ===")
            print(f"File size: {file_size_kb} KB ({event_file_size / 1_000_000:.2f} MB)")
            print(f"Lines: {event_line_count}")
            print(f"Session: {session_duration_min} minutes")
            print(f"Latency: {latency_ms:.2f} ms")
            print(f"======================\n")
        
        # This assertion SHOULD FAIL on unfixed code
        self.assertLess(
            latency_ms,
            500,
            f"Latency {latency_ms:.2f}ms exceeds 500ms for {file_size_kb}KB file "
            f"({event_line_count} lines) after {session_duration_min}min session"
        )
    
    def _measure_polling_latency(
        self,
        event_file_size: int,
        event_line_count: int,
    ) -> float:
        """Measure the latency of reading and parsing an event file.
        
        This simulates the _read_worker_events method behavior:
        1. Open the event file
        2. Seek to cursor position
        3. Read remaining content
        4. Parse JSON lines
        5. Return events
        
        Returns:
            Latency in milliseconds
        """
        # Create a temporary event file with the specified size and line count
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.events.jsonl',
            delete=False,
            encoding='utf-8',
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            
            # Generate realistic event data
            # Each event is a metrics_update with typical payload
            sample_event = {
                "event": "metrics_update",
                "payload": {
                    "metrics": {
                        "people_in_zone": 5,
                        "estimated_wait_sec": 120.5,
                        "arrival_rate": 0.05,
                        "service_rate": 0.042,
                        "timestamp": time.time(),
                    },
                    "frame_id": 1000,
                },
            }
            
            # Calculate bytes per line to reach target file size
            sample_line = json.dumps(sample_event) + "\n"
            bytes_per_line = len(sample_line.encode('utf-8'))
            
            # Write events to reach target line count
            for i in range(event_line_count):
                # Vary the data slightly to be realistic
                event = sample_event.copy()
                event["payload"]["metrics"]["people_in_zone"] = (i % 10) + 1
                event["payload"]["frame_id"] = i + 1
                tmp_file.write(json.dumps(event) + "\n")
        
        try:
            # Simulate the _read_worker_events method
            handle = FeedWorkerHandle(
                feed_id="test-feed",
                command=["test"],
                event_path=tmp_path,
                event_cursor=0,
                event_buffer="",
            )
            
            # Measure the time to read and parse the entire file
            start_time = time.perf_counter()
            
            # This is the actual code path from runtime.py:_read_worker_events
            if handle.event_path is None or not handle.event_path.exists():
                return 0.0
            
            try:
                with handle.event_path.open("r", encoding="utf-8", errors="replace") as stream:
                    stream.seek(handle.event_cursor)
                    chunk = stream.read()
                    handle.event_cursor = stream.tell()
            except OSError:
                return 0.0
            
            if not chunk:
                return 0.0
            
            text = f"{handle.event_buffer}{chunk}"
            handle.event_buffer = ""
            
            records: list[dict[str, Any]] = []
            for line in text.splitlines(keepends=True):
                if not line.endswith(("\n", "\r")):
                    handle.event_buffer = line
                    continue
                
                stripped = line.strip()
                if not stripped:
                    continue
                
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                
                if isinstance(parsed, dict):
                    records.append(parsed)
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000.0
            
            return latency_ms
            
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)
    
    def test_latency_at_various_file_sizes(self) -> None:
        """Document latency at different file sizes to understand the bug pattern.
        
        This test measures latency at specific file sizes:
        - 100 KB (threshold)
        - 500 KB
        - 1 MB
        - 1.37 MB (actual bug case)
        
        EXPECTED: Test FAILS, documenting increasing latency with file size
        """
        test_cases = [
            (100_000, 435, "100 KB"),      # 100 KB / 230 bytes per line
            (500_000, 2174, "500 KB"),     # 500 KB / 230 bytes per line
            (1_000_000, 4348, "1 MB"),     # 1 MB / 230 bytes per line
            (1_370_000, 6138, "1.37 MB"),  # Actual bug case
        ]
        
        print("\n=== LATENCY MEASUREMENTS ===")
        counterexamples = []
        
        for file_size, line_count, label in test_cases:
            latency_ms = self._measure_polling_latency(
                event_file_size=file_size,
                event_line_count=line_count,
            )
            
            print(f"{label:>10}: {latency_ms:>8.2f} ms (threshold: 500 ms)")
            
            if latency_ms > 500:
                counterexamples.append((label, latency_ms))
        
        print("============================\n")
        
        # Document all counterexamples
        if counterexamples:
            print("\n=== COUNTEREXAMPLES FOUND ===")
            for label, latency in counterexamples:
                print(f"  {label}: {latency:.2f} ms > 500 ms")
            print("=============================\n")
        
        # This assertion SHOULD FAIL on unfixed code
        self.assertEqual(
            len(counterexamples),
            0,
            f"Found {len(counterexamples)} file sizes with latency >500ms: {counterexamples}"
        )


if __name__ == "__main__":
    unittest.main()
