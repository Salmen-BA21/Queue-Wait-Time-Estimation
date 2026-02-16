"""
Uncertainty quantification module – **placeholder**.

This module will later implement methods to quantify the uncertainty
associated with the queue metrics (arrival rate, service rate, wait time).

Planned approaches:
* **Bootstrap resampling** of event windows.
* **Bayesian estimation** of λ and μ (conjugate Gamma priors on Poisson rates).
* **Conformal prediction** wrappers for point estimates → intervals.
* Propagation of detection-confidence uncertainty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("queue_system.uncertainty")


@dataclass
class UncertaintyEstimate:
    """Container for an uncertain scalar value.

    Attributes
    ----------
    mean : float
        Point estimate (central value).
    lower : float
        Lower bound of the credible / confidence interval.
    upper : float
        Upper bound of the credible / confidence interval.
    confidence_level : float
        Nominal coverage probability (e.g. 0.95 for a 95 % interval).
    method : str
        Name of the method that produced the estimate.
    """

    mean: float = 0.0
    lower: float = 0.0
    upper: float = 0.0
    confidence_level: float = 0.95
    method: str = "none"


def estimate_rate_uncertainty(
    event_count: int,
    window_sec: float,
    confidence: float = 0.95,
) -> UncertaintyEstimate:
    """Placeholder – return a dummy uncertainty estimate for a Poisson rate.

    A proper implementation will use a Gamma posterior:
        ``rate ~ Gamma(α = event_count + 1, β = window_sec)``

    Parameters
    ----------
    event_count : int
        Number of events observed in the window.
    window_sec : float
        Length of the observation window in seconds.
    confidence : float
        Desired coverage probability.

    Returns
    -------
    UncertaintyEstimate
        Dummy estimate (mean = count / window, trivial bounds).
    """
    if window_sec <= 0:
        return UncertaintyEstimate()

    rate = event_count / window_sec
    # TODO: Replace with scipy.stats.gamma.interval or bootstrap
    logger.debug(
        "Uncertainty estimation not yet implemented – returning point estimate."
    )
    return UncertaintyEstimate(
        mean=rate,
        lower=rate,
        upper=rate,
        confidence_level=confidence,
        method="placeholder",
    )
