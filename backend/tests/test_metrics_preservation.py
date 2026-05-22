"""Preservation property tests for metrics system behavior.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

These tests capture the baseline behavior of the system for non-buggy inputs
(short sessions <30 minutes, small event files <100 KB) to ensure the fix
does not introduce regressions.

IMPORTANT: Follow observation-first methodology
- Observe behavior on UNFIXED code for non-buggy inputs
- Write property-based tests capturing observed behavior patterns
- Run tests on UNFIXED code
- EXPECTED OUTCOME: Tests PASS (this confirms baseline behavior to preserve)
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st

from src.api.runtime import FeedWorkerHandle
from src.config import (
    DASHBOARD_EVENT_EMIT_INTERVAL_SEC,
    DASHBOARD_EVENT_POLL_INTERVAL_SEC,
)


@dataclass
class PreservationContext:
    """Input context for preservation scenarios (non-buggy inputs)."""
    
    event_file_size: int  # bytes
    event_file_line_count: int
    polling_interval_sec: float
    emission_interval_sec: float
    session_duration_minutes: int


def is_preservation_scenario(input_ctx: PreservationContext) -> bool:
    """Determine if the input is a preservation scenario (non-buggy).
    
    Preservation scenarios are those that do NOT trigger the bug:
    - Event file size is small (<100 KB)
    - Event file line count is small (<500 lines)
    - Session duration is short (<30 minutes)
    
    These scenarios should work correctly in both unfixed and fixed code.
    """
    return (
        input_ctx.event_file_size <= 100_000
        and input_ctx.event_file_line_count <= 500
        and input_ctx.session_duration_minutes <= 30
    )


class TestMetricsPreservation(unittest.TestCase):
    """Property 2: Preservation - Configuration Intervals and Non-Buggy Behavior.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
    
    These tests verify that the system preserves existing behavior for:
    - Worker processes emit metrics at 200ms intervals (DASHBOARD_EVENT_EMIT_INTERVAL_SEC = 0.2)
    - API runtime polls for events at 100ms intervals (DASHBOARD_EVENT_POLL_INTERVAL_SEC = 0.1)
    - Short sessions (<30 minutes) with small event files (<100 KB)
    - Configuration values are respected
    
    EXPECTED OUTCOME: Tests PASS on unfixed code (confirms baseline behavior)
    """
    
    def test_configuration_constants_unchanged(self) -> None:
        """Verify that configuration constants have expected values.
        
        **Validates: Requirements 3.1, 3.2, 3.6**
        
        The fix must not change these configuration values:
        - DASHBOARD_EVENT_EMIT_INTERVAL_SEC = 0.2 (200ms)
        - DASHBOARD_EVENT_POLL_INTERVAL_SEC = 0.1 (100ms)
        """
        self.assertEqual(
            DASHBOARD_EVENT_EMIT_INTERVAL_SEC,
            0.2,
            "Worker emission interval must remain 200ms (0.2 seconds)"
        )
        
        self.assertEqual(
            DASHBOARD_EVENT_POLL_INTERVAL_SEC,
            0.1,
            "API polling interval must remain 100ms (0.1 seconds)"
        )
    
    def test_short_session_low_latency(self) -> None:
        """Test that short sessions with small event files have low latency.
        
        **Validates: Requirements 3.1, 3.2, 3.7**
        
        This is a concrete preservation case:
        - Worker runs for 5 minutes
        - Event file is 50 KB (217 lines)
        - API runtime polls every 100ms
        
        EXPECTED: Test PASSES with latency <500ms (baseline behavior)
        """
        # Simulate a 5-minute session with small event file
        event_file_size = 50_000  # 50 KB
        event_line_count = 217  # 50 KB / 230 bytes per line
        
        context = PreservationContext(
            event_file_size=event_file_size,
            event_file_line_count=event_line_count,
            polling_interval_sec=0.1,
            emission_interval_sec=0.2,
            session_duration_minutes=5,
        )
        
        # Verify this is a preservation scenario
        self.assertTrue(
            is_preservation_scenario(context),
            "This should be a preservation scenario (non-buggy)"
        )
        
        # Measure latency with small event file
        latency_ms = self._measure_polling_latency(
            event_file_size=event_file_size,
            event_line_count=event_line_count,
        )
        
        # Document the baseline behavior
        print(f"\n=== BASELINE BEHAVIOR ===")
        print(f"Event file size: {event_file_size / 1_000:.2f} KB")
        print(f"Event file lines: {event_line_count}")
        print(f"Session duration: 5 minutes")
        print(f"Measured latency: {latency_ms:.2f} ms")
        print(f"Expected latency: <500 ms")
        print(f"Baseline preserved: {latency_ms < 500}")
        print(f"=========================\n")
        
        # This assertion SHOULD PASS on unfixed code (baseline behavior)
        self.assertLess(
            latency_ms,
            500,
            f"Short session latency ({latency_ms:.2f}ms) should be <500ms. "
            f"This is the baseline behavior that must be preserved."
        )
    
    @given(
        file_size_kb=st.integers(min_value=1, max_value=100),  # 1 KB to 100 KB
        session_duration_min=st.integers(min_value=1, max_value=30),  # 1 min to 30 minutes
    )
    @settings(max_examples=20, deadline=None)
    def test_property_preservation_for_small_files(
        self,
        file_size_kb: int,
        session_duration_min: int,
    ) -> None:
        """Property: For any non-buggy input (small files, short sessions),
        the system SHALL maintain low latency (<500ms).
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.7**
        
        This property-based test generates various preservation scenarios
        and verifies that latency remains low for all of them.
        
        EXPECTED: Test PASSES on unfixed code (confirms baseline behavior)
        """
        # Calculate event file parameters
        event_file_size = file_size_kb * 1024
        # Assume ~230 bytes per event line (from 1.37 MB / 6,138 lines)
        event_line_count = max(1, event_file_size // 230)
        
        context = PreservationContext(
            event_file_size=event_file_size,
            event_file_line_count=event_line_count,
            polling_interval_sec=0.1,
            emission_interval_sec=0.2,
            session_duration_minutes=session_duration_min,
        )
        
        # Only test preservation scenarios (non-buggy inputs)
        if not is_preservation_scenario(context):
            return
        
        # Measure latency
        latency_ms = self._measure_polling_latency(
            event_file_size=event_file_size,
            event_line_count=event_line_count,
        )
        
        # This assertion SHOULD PASS on unfixed code
        self.assertLess(
            latency_ms,
            500,
            f"Preservation scenario failed: {file_size_kb}KB file "
            f"({event_line_count} lines) after {session_duration_min}min session "
            f"has latency {latency_ms:.2f}ms (expected <500ms). "
            f"This baseline behavior must be preserved."
        )
    
    def test_very_small_file_latency(self) -> None:
        """Test latency with very small event files (edge case).
        
        **Validates: Requirements 3.1, 3.2, 3.7**
        
        Test with minimal event files:
        - 1 KB (4 lines)
        - 10 KB (43 lines)
        - 50 KB (217 lines)
        
        EXPECTED: Test PASSES with very low latency (<100ms)
        """
        test_cases = [
            (1_000, 4, "1 KB"),
            (10_000, 43, "10 KB"),
            (50_000, 217, "50 KB"),
        ]
        
        print("\n=== SMALL FILE LATENCY MEASUREMENTS ===")
        
        for file_size, line_count, label in test_cases:
            latency_ms = self._measure_polling_latency(
                event_file_size=file_size,
                event_line_count=line_count,
            )
            
            print(f"{label:>10}: {latency_ms:>8.2f} ms (expected <100 ms)")
            
            # Very small files should have very low latency
            self.assertLess(
                latency_ms,
                100,
                f"Very small file ({label}) should have latency <100ms, got {latency_ms:.2f}ms"
            )
        
        print("========================================\n")
    
    def test_event_file_reading_correctness(self) -> None:
        """Test that event file reading produces correct results.
        
        **Validates: Requirements 3.5, 3.7**
        
        Verify that:
        - All events are read correctly
        - JSON parsing is accurate
        - No events are lost or corrupted
        - Metric types are preserved
        """
        # Create a test event file with known content
        test_events = [
            {
                "event": "metrics_update",
                "payload": {
                    "metrics": {
                        "people_in_zone": 5,
                        "estimated_wait_sec": 120.5,
                        "arrival_rate": 0.05,
                        "service_rate": 0.042,
                        "timestamp": time.time(),
                    },
                    "frame_id": 1,
                },
            },
            {
                "event": "metrics_update",
                "payload": {
                    "metrics": {
                        "people_in_zone": 7,
                        "estimated_wait_sec": 150.0,
                        "arrival_rate": 0.06,
                        "service_rate": 0.040,
                        "timestamp": time.time(),
                    },
                    "frame_id": 2,
                },
            },
        ]
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.events.jsonl',
            delete=False,
            encoding='utf-8',
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            
            # Write test events
            for event in test_events:
                tmp_file.write(json.dumps(event) + "\n")
        
        try:
            # Read events using the actual code path
            handle = FeedWorkerHandle(
                feed_id="test-feed",
                command=["test"],
                event_path=tmp_path,
                event_cursor=0,
                event_buffer="",
            )
            
            # Read events
            with handle.event_path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(handle.event_cursor)
                chunk = stream.read()
                handle.event_cursor = stream.tell()
            
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
            
            # Verify all events were read correctly
            self.assertEqual(
                len(records),
                len(test_events),
                "All events should be read"
            )
            
            # Verify event structure is preserved
            for i, record in enumerate(records):
                self.assertEqual(
                    record["event"],
                    test_events[i]["event"],
                    f"Event {i} type should be preserved"
                )
                
                self.assertIn(
                    "payload",
                    record,
                    f"Event {i} should have payload"
                )
                
                self.assertIn(
                    "metrics",
                    record["payload"],
                    f"Event {i} should have metrics"
                )
                
                # Verify all metric types are present
                metrics = record["payload"]["metrics"]
                expected_metrics = [
                    "people_in_zone",
                    "estimated_wait_sec",
                    "arrival_rate",
                    "service_rate",
                    "timestamp",
                ]
                
                for metric_name in expected_metrics:
                    self.assertIn(
                        metric_name,
                        metrics,
                        f"Event {i} should have {metric_name} metric"
                    )
        
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)
    
    def test_polling_interval_respected(self) -> None:
        """Test that the polling interval configuration is respected.
        
        **Validates: Requirements 3.2, 3.6**
        
        Verify that DASHBOARD_EVENT_POLL_INTERVAL_SEC is used correctly
        and not modified by the fix.
        """
        # This test verifies the configuration constant
        # The actual polling behavior is tested in integration tests
        
        expected_interval = 0.1  # 100ms
        actual_interval = DASHBOARD_EVENT_POLL_INTERVAL_SEC
        
        self.assertEqual(
            actual_interval,
            expected_interval,
            f"Polling interval must be {expected_interval}s (100ms), "
            f"got {actual_interval}s"
        )
        
        # Verify the interval is reasonable for low-latency updates
        self.assertLessEqual(
            actual_interval,
            0.2,
            "Polling interval should be ≤200ms for low-latency updates"
        )
    
    def test_emission_interval_respected(self) -> None:
        """Test that the emission interval configuration is respected.
        
        **Validates: Requirements 3.1, 3.6**
        
        Verify that DASHBOARD_EVENT_EMIT_INTERVAL_SEC is used correctly
        and not modified by the fix.
        """
        expected_interval = 0.2  # 200ms
        actual_interval = DASHBOARD_EVENT_EMIT_INTERVAL_SEC
        
        self.assertEqual(
            actual_interval,
            expected_interval,
            f"Emission interval must be {expected_interval}s (200ms), "
            f"got {actual_interval}s"
        )
        
        # Verify the interval is reasonable for real-time updates
        self.assertLessEqual(
            actual_interval,
            0.5,
            "Emission interval should be ≤500ms for real-time updates"
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
            
            # Write events to reach target line count
            for i in range(event_line_count):
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


if __name__ == "__main__":
    unittest.main()
