"""
Queue analyser – count people in zone, estimate arrival/service rates
and expected waiting time.

Uses a simple sliding-window approach:
* **λ (arrival rate)**: persons entering the zone per second.
* **μ (service rate)**: persons leaving the zone per second.
* **W (expected wait)**: estimated via M/M/1 queueing formula ``1 / (μ − λ)``
  when the queue is stable (λ < μ).  Falls back to ``queue_size / μ`` otherwise.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from src.config import (
    ARRIVAL_WINDOW_SEC,
    ID_ABSENCE_GRACE_SEC,
    MIN_EVENTS_FOR_RATE,
    SERVICE_WINDOW_SEC,
)

logger = logging.getLogger("queue_system.queue_analyzer")


@dataclass
class QueueMetrics:
    """Snapshot of current queue metrics."""

    timestamp: float = 0.0
    people_in_zone: int = 0
    arrival_rate: float = 0.0   # λ – persons / sec
    service_rate: float = 0.0   # μ – persons / sec
    estimated_wait_sec: float = 0.0


class QueueAnalyzer:
    """Track enter/exit events and compute queue metrics.

    Parameters
    ----------
    arrival_window : float
        Sliding window (seconds) for computing arrival rate.
    service_window : float
        Sliding window (seconds) for computing service rate.
    """

    def __init__(
        self,
        arrival_window: float = ARRIVAL_WINDOW_SEC,
        service_window: float = SERVICE_WINDOW_SEC,
        id_absence_grace_sec: float = ID_ABSENCE_GRACE_SEC,
    ) -> None:
        self._arrival_window = arrival_window
        self._service_window = service_window
        self._id_absence_grace_sec = max(0.0, float(id_absence_grace_sec))

        # Timestamps of recent arrivals / departures
        self._arrivals: deque[float] = deque()
        self._departures: deque[float] = deque()

        # Set of tracker IDs currently known inside the zone
        self._ids_in_zone: set[int] = set()
        # IDs that disappeared recently and may reappear without counting as a departure.
        self._missing_since: dict[int, float] = {}

        self._metrics = QueueMetrics()

    # ── Main update ───────────────────────────────────────────

    def update(
        self,
        in_zone_mask: np.ndarray,
        tracker_ids: np.ndarray | None,
    ) -> QueueMetrics:
        """Process one frame's zone results.

        Parameters
        ----------
        in_zone_mask : np.ndarray
            Boolean mask from ``ZoneManager.trigger()``.
        tracker_ids : np.ndarray | None
            Array of tracker IDs matching the detections.

        Returns
        -------
        QueueMetrics
            Updated metrics snapshot.
        """
        now = time.monotonic()

        if tracker_ids is None or len(tracker_ids) == 0:
            current_ids: set[int] = set()
        else:
            current_ids = set(int(tid) for tid, inside in zip(tracker_ids, in_zone_mask) if inside)

        # Graceful departures: only count as departure if missing for longer than grace window.
        expired_ids: set[int] = set()
        if self._missing_since:
            for tid, missing_since in list(self._missing_since.items()):
                if (now - missing_since) > self._id_absence_grace_sec:
                    expired_ids.add(tid)
                    self._missing_since.pop(tid, None)
                    self._ids_in_zone.discard(tid)
                    self._departures.append(now)

        # IDs seen again cancel pending graceful departure.
        for tid in current_ids:
            self._missing_since.pop(tid, None)

        # Arrivals: IDs appearing that were not previously in-zone and not in a pending state.
        new_arrivals = current_ids - self._ids_in_zone
        for _ in new_arrivals:
            self._arrivals.append(now)

        # Start grace timer for IDs that are absent this frame.
        for tid in (self._ids_in_zone - current_ids):
            if tid not in expired_ids and tid not in self._missing_since:
                self._missing_since[tid] = now

        # Keep recently-missing IDs in the active set so they can return without double counting.
        self._ids_in_zone.update(current_ids)

        # Purge old events
        self._purge(self._arrivals, now, self._arrival_window)
        self._purge(self._departures, now, self._service_window)

        # Compute rates
        lam = self._rate(self._arrivals, self._arrival_window)
        mu = self._rate(self._departures, self._service_window)

        # Wait time estimation
        people = len(current_ids)

        if lam < mu and mu > 0:
            wait = 1.0 / (mu - lam)       # M/M/1 sojourn time
        elif mu > 0:
            wait = people / mu             # rough fallback
        else:
            wait = 0.0

        self._metrics = QueueMetrics(
            timestamp=now,
            people_in_zone=people,
            arrival_rate=round(lam, 4),
            service_rate=round(mu, 4),
            estimated_wait_sec=round(max(wait, 0.0), 1),
        )
        return self._metrics

    @property
    def metrics(self) -> QueueMetrics:
        """Return the latest metrics without re-computing."""
        return self._metrics

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _purge(dq: deque[float], now: float, window: float) -> None:
        """Remove events older than *window* seconds."""
        while dq and (now - dq[0]) > window:
            dq.popleft()

    @staticmethod
    def _rate(dq: deque[float], window: float) -> float:
        """Compute event rate (events / second) from a deque of timestamps."""
        if len(dq) < MIN_EVENTS_FOR_RATE:
            return 0.0
        return len(dq) / window
