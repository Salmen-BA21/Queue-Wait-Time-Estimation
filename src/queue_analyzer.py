"""
Queue analyser – count people in zone, estimate arrival/service rates
and expected waiting time with uncertainty quantification.

Uses a simple sliding-window approach:
* **λ (arrival rate)**: persons entering the zone per second.
* **μ (service rate)**: persons leaving the zone per second.
* **W (expected wait)**: estimated via M/M/1 queueing formula ``1 / (μ − λ)``
  when the queue is stable (λ < μ).  Falls back to ``queue_size / μ`` otherwise.
* **Uncertainty**: Bayesian rate estimates + variance-based wait time intervals.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from src.config import ARRIVAL_WINDOW_SEC, MIN_EVENTS_FOR_RATE, SERVICE_WINDOW_SEC
from src.uncertainty import (
    classify_uncertainty_level,
    estimate_rate_uncertainty,
    estimate_uncertainty_from_detection_confidence,
    estimate_wait_time_uncertainty_from_variance,
)

logger = logging.getLogger("queue_system.queue_analyzer")


@dataclass
class QueueMetrics:
    """Snapshot of current queue metrics with uncertainty quantification."""

    timestamp: float = 0.0
    people_in_zone: int = 0
    arrival_rate: float = 0.0   # λ – persons / sec
    service_rate: float = 0.0   # μ – persons / sec
    estimated_wait_sec: float = 0.0
    queue_stable: bool = True
    
    # Uncertainty quantification fields
    arrival_rate_lower: float = 0.0  # 95% credible interval lower bound
    arrival_rate_upper: float = 0.0  # 95% credible interval upper bound
    service_rate_lower: float = 0.0
    service_rate_upper: float = 0.0
    wait_time_lower: float = 0.0
    wait_time_upper: float = 0.0
    uncertainty_level: str = "Low"  # "Low", "Medium", or "High"


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
    ) -> None:
        self._arrival_window = arrival_window
        self._service_window = service_window

        # Timestamps of recent arrivals / departures
        self._arrivals: deque[float] = deque()
        self._departures: deque[float] = deque()

        # Set of tracker IDs currently known inside the zone
        self._ids_in_zone: set[int] = set()

        self._metrics = QueueMetrics()
        
        # Uncertainty history tracking (for variance-based uncertainty calculation)
        self._wait_times_history: deque[float] = deque(maxlen=30)  # Keep last 30 measurements
        self._confidence_scores_history: deque[list[float]] = deque(maxlen=30)

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

        # Arrivals: IDs appearing that were not previously in zone
        new_arrivals = current_ids - self._ids_in_zone
        for _ in new_arrivals:
            self._arrivals.append(now)

        # Departures: IDs that were in zone but are no longer
        new_departures = self._ids_in_zone - current_ids
        for _ in new_departures:
            self._departures.append(now)

        self._ids_in_zone = current_ids

        # Purge old events
        self._purge(self._arrivals, now, self._arrival_window)
        self._purge(self._departures, now, self._service_window)

        # Compute rates
        lam = self._rate(self._arrivals, self._arrival_window)
        mu = self._rate(self._departures, self._service_window)

        # Wait time estimation
        people = len(current_ids)
        stable = lam < mu if mu > 0 else False

        if stable and mu > 0:
            wait = 1.0 / (mu - lam)       # M/M/1 sojourn time
        elif mu > 0:
            wait = people / mu             # rough fallback
        else:
            wait = 0.0

        # Store wait time for variance-based uncertainty
        self._wait_times_history.append(max(wait, 0.0))

        # ── Uncertainty Quantification ────────────────────────
        
        # 1. Rate uncertainties (Bayesian Gamma)
        arrival_unc = estimate_rate_uncertainty(len(self._arrivals), self._arrival_window)
        service_unc = estimate_rate_uncertainty(len(self._departures), self._service_window)
        
        # 2. Wait time uncertainty (from variance if enough history)
        if len(self._wait_times_history) >= 5:
            wait_unc = estimate_wait_time_uncertainty_from_variance(
                list(self._wait_times_history), confidence=0.95
            )
        else:
            # Fallback: use ±20% if insufficient history
            wait_unc_margin = wait * 0.2
            from src.uncertainty import UncertaintyEstimate
            wait_unc = UncertaintyEstimate(
                mean=wait,
                lower=max(0.0, wait - wait_unc_margin),
                upper=wait + wait_unc_margin,
                confidence_level=0.95,
                method="fallback",
            )
        
        # 3. Overall uncertainty classification
        uncertainty_level = classify_uncertainty_level(wait_unc, point_estimate=wait)

        self._metrics = QueueMetrics(
            timestamp=now,
            people_in_zone=people,
            arrival_rate=round(lam, 4),
            service_rate=round(mu, 4),
            estimated_wait_sec=round(max(wait, 0.0), 1),
            queue_stable=stable,
            # Uncertainty fields
            arrival_rate_lower=round(arrival_unc.lower, 4),
            arrival_rate_upper=round(arrival_unc.upper, 4),
            service_rate_lower=round(service_unc.lower, 4),
            service_rate_upper=round(service_unc.upper, 4),
            wait_time_lower=round(wait_unc.lower, 1),
            wait_time_upper=round(wait_unc.upper, 1),
            uncertainty_level=uncertainty_level,
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
