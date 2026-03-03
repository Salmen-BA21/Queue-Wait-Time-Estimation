"""
Uncertainty quantification module.

This module implements methods to quantify the uncertainty
associated with the queue metrics (arrival rate, service rate, wait time).

Current approaches:
* **Bayesian estimation** of λ and μ using conjugate Gamma priors on Poisson rates.
* **Variance-based** quantification from recent measurements.
* **Confidence-weighted** uncertainty from YOLO detection scores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import stats

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
    """Estimate uncertainty for a Poisson rate using Bayesian Gamma posterior.

    Uses a conjugate Gamma prior for Poisson rates:
        - Prior: Gamma(α=1, β=1) [uninformative]
        - Likelihood: Poisson(λ) with event_count observations
        - Posterior: Gamma(α=event_count+1, β=window_sec)

    The posterior mean is the point estimate, and the credible interval
    is derived from the Gamma quantiles.

    Parameters
    ----------
    event_count : int
        Number of events observed in the window.
    window_sec : float
        Length of the observation window in seconds.
    confidence : float
        Desired credible interval coverage (e.g., 0.95 for 95%).

    Returns
    -------
    UncertaintyEstimate
        Bayesian posterior estimate with credible interval bounds.
    """
    if window_sec <= 0:
        logger.warning("Invalid window_sec=%s, returning zero estimate", window_sec)
        return UncertaintyEstimate(
            mean=0.0, lower=0.0, upper=0.0, confidence_level=confidence, method="gamma"
        )

    # Bayesian posterior: Gamma(α=event_count+1, β=window_sec)
    # This comes from Poisson likelihood with Gamma(1,1) prior
    alpha = event_count + 1.0  # shape parameter
    beta = window_sec  # rate/scale parameter (using rate parameterization)

    # Posterior mean and variance
    mean_rate = alpha / beta
    variance = alpha / (beta**2)
    std_dev = np.sqrt(variance)

    # Credible interval using Gamma quantiles
    # Convert confidence (two-tailed) to quantile bounds
    lower_quantile = (1.0 - confidence) / 2.0
    upper_quantile = 1.0 - lower_quantile

    try:
        # Using scipy.stats.gamma with scale parameterization (shape, scale)
        # where scale = 1/beta
        lower_bound = stats.gamma.ppf(lower_quantile, a=alpha, scale=1.0 / beta)
        upper_bound = stats.gamma.ppf(upper_quantile, a=alpha, scale=1.0 / beta)
    except Exception as e:
        logger.error("Error computing Gamma quantiles: %s", e)
        # Fallback to symmetric interval using standard deviation
        lower_bound = max(0.0, mean_rate - 1.96 * std_dev)
        upper_bound = mean_rate + 1.96 * std_dev

    logger.debug(
        "Rate uncertainty: events=%d, window=%.1fs → λ=%.4f [%.4f, %.4f] (%.0f%% credible)",
        event_count,
        window_sec,
        mean_rate,
        lower_bound,
        upper_bound,
        confidence * 100,
    )

    return UncertaintyEstimate(
        mean=float(mean_rate),
        lower=float(max(0.0, lower_bound)),  # Rates must be non-negative
        upper=float(upper_bound),
        confidence_level=confidence,
        method="bayesian_gamma",
    )

def estimate_wait_time_uncertainty_from_variance(
    recent_wait_times: list[float],
    confidence: float = 0.95,
    min_samples: int = 3,
) -> UncertaintyEstimate:
    """Estimate wait time uncertainty from recent measurement variance.

    Calculates variance and standard error of recent wait time estimates
    and derives a confidence interval assuming approximately normal distribution
    (via Central Limit Theorem with sufficient samples).

    Parameters
    ----------
    recent_wait_times : list[float]
        List of recent wait time estimates (in seconds).
    confidence : float
        Desired confidence level for interval (e.g., 0.95 for 95%).
    min_samples : int
        Minimum number of samples required (default 3).

    Returns
    -------
    UncertaintyEstimate
        Variance-based uncertainty estimate with confidence interval.
    """
    if not recent_wait_times or len(recent_wait_times) < min_samples:
        logger.debug(
            "Insufficient samples (%d < %d) for variance-based uncertainty",
            len(recent_wait_times),
            min_samples,
        )
        # Return point estimate with no bounds if insufficient data
        mean_wait = float(np.mean(recent_wait_times)) if recent_wait_times else 0.0
        return UncertaintyEstimate(
            mean=mean_wait,
            lower=mean_wait,
            upper=mean_wait,
            confidence_level=confidence,
            method="variance_insufficient",
        )

    # Calculate statistics
    wait_array = np.array(recent_wait_times)
    mean_wait = float(np.mean(wait_array))
    std_dev = float(np.std(wait_array, ddof=1))  # Use sample std (N-1)
    n_samples = len(recent_wait_times)

    # Standard error of the mean
    se_mean = std_dev / np.sqrt(n_samples)

    # t-critical value for confidence interval (using t-distribution for small samples)
    alpha = 1.0 - confidence
    df = n_samples - 1  # degrees of freedom
    t_crit = stats.t.ppf(1 - alpha / 2, df)

    # Confidence interval
    margin_of_error = t_crit * se_mean
    lower_bound = max(0.0, mean_wait - margin_of_error)  # Wait times are non-negative
    upper_bound = mean_wait + margin_of_error

    logger.debug(
        "Wait time variance uncertainty: mean=%.2fs, std=%.2fs, n=%d → [%.2f, %.2f] (%.0f%% CI)",
        mean_wait,
        std_dev,
        n_samples,
        lower_bound,
        upper_bound,
        confidence * 100,
    )

    return UncertaintyEstimate(
        mean=mean_wait,
        lower=float(lower_bound),
        upper=float(upper_bound),
        confidence_level=confidence,
        method="variance_based",
    )


def estimate_uncertainty_from_detection_confidence(
    point_estimate: float,
    confidence_scores: list[float] | np.ndarray,
    confidence_level: float = 0.95,
) -> UncertaintyEstimate:
    """Estimate uncertainty weighted by YOLO detection confidence.

    Lower average detection confidence → wider uncertainty interval.
    Higher average confidence → narrower uncertainty interval.

    Uses the assumption that detection confidence reflects the reliability
    of the underlying measurement.

    Parameters
    ----------
    point_estimate : float
        The point estimate (e.g., wait time, arrival rate).
    confidence_scores : list[float] | np.ndarray
        Array of detection confidence scores (typically 0-1 from YOLO).
    confidence_level : float
        Desired confidence level for interval.

    Returns
    -------
    UncertaintyEstimate
        Confidence-weighted uncertainty estimate.
    """
    if not confidence_scores or len(confidence_scores) == 0:
        logger.warning("No confidence scores provided, returning point estimate")
        return UncertaintyEstimate(
            mean=point_estimate,
            lower=point_estimate,
            upper=point_estimate,
            confidence_level=confidence_level,
            method="confidence_no_data",
        )

    scores = np.array(confidence_scores)
    mean_confidence = float(np.mean(scores))
    min_confidence = float(np.min(scores))

    # Clamp to valid range [0, 1]
    mean_confidence = np.clip(mean_confidence, 0.0, 1.0)
    min_confidence = np.clip(min_confidence, 0.0, 1.0)

    # Uncertainty magnitude is inversely proportional to confidence
    # When confidence = 1.0 → uncertainty factor = 1.0 (minimum)
    # When confidence = 0.5 → uncertainty factor = 2.0 (double)
    # When confidence = 0.1 → uncertainty factor = 10.0 (very wide)
    uncertainty_factor = 1.0 / (mean_confidence + 0.01)  # Add small constant to avoid division by zero

    # Use t-distribution critical value for symmetric interval
    # Assume approximately 20 degrees of freedom (moderate sample size)
    df = 20
    alpha = 1.0 - confidence_level
    t_crit = stats.t.ppf(1 - alpha / 2, df)

    # Interval width based on confidence and uncertainty factor
    # Scale by point estimate to make interval relative to magnitude
    half_width = t_crit * point_estimate * uncertainty_factor

    lower_bound = max(0.0, point_estimate - half_width)
    upper_bound = point_estimate + half_width

    logger.debug(
        "Confidence-weighted uncertainty: estimate=%.2f, mean_conf=%.3f, "
        "uncertainty_factor=%.2f → [%.2f, %.2f]",
        point_estimate,
        mean_confidence,
        uncertainty_factor,
        lower_bound,
        upper_bound,
    )

    return UncertaintyEstimate(
        mean=point_estimate,
        lower=float(lower_bound),
        upper=float(upper_bound),
        confidence_level=confidence_level,
        method="confidence_weighted",
    )


def classify_uncertainty_level(
    uncertainty_estimate: UncertaintyEstimate,
    point_estimate: float | None = None,
) -> str:
    """Classify uncertainty as 'Low', 'Medium', or 'High'.

    Uses coefficient of variation (CV) to classify uncertainty:
        - CV < 0.15 → Low
        - 0.15 ≤ CV < 0.35 → Medium
        - CV ≥ 0.35 → High

    Parameters
    ----------
    uncertainty_estimate : UncertaintyEstimate
        The uncertainty estimate object with mean and bounds.
    point_estimate : float | None
        Explicit point estimate (defaults to uncertainty_estimate.mean).

    Returns
    -------
    str
        One of: "Low", "Medium", "High"
    """
    if point_estimate is None:
        point_estimate = uncertainty_estimate.mean

    if point_estimate <= 0:
        # For zero/near-zero estimates, use absolute width
        width = uncertainty_estimate.upper - uncertainty_estimate.lower
        cv = width / (abs(point_estimate) + 1.0)  # Add 1 to avoid division issues
    else:
        # Calculate coefficient of variation (margin of error / mean)
        margin_of_error = uncertainty_estimate.upper - point_estimate
        cv = margin_of_error / point_estimate

    # Classify based on CV thresholds
    if cv < 0.15:
        level = "Low"
    elif cv < 0.35:
        level = "Medium"
    else:
        level = "High"

    logger.debug(
        "Uncertainty classification: CV=%.3f → %s (estimate=%.2f, width=[%.2f, %.2f])",
        cv,
        level,
        point_estimate,
        uncertainty_estimate.lower,
        uncertainty_estimate.upper,
    )

    return level


def get_uncertainty_summary(
    uncertainty_estimate: UncertaintyEstimate,
    point_estimate: float | None = None,
) -> str:
    """Generate a human-readable uncertainty summary string.

    Example: "5.2s (±1.1s, Medium)"

    Parameters
    ----------
    uncertainty_estimate : UncertaintyEstimate
        The uncertainty estimate.
    point_estimate : float | None
        Optional explicit point estimate.

    Returns
    -------
    str
        Formatted string like "X.Xs (±Y.Zs, Level)"
    """
    if point_estimate is None:
        point_estimate = uncertainty_estimate.mean

    level = classify_uncertainty_level(uncertainty_estimate, point_estimate)
    margin = (uncertainty_estimate.upper - uncertainty_estimate.lower) / 2.0

    return f"{point_estimate:.1f} (±{margin:.1f}, {level})"

