---
name: queue-uncertainty-theory
description: "Deeper math for confidence intervals, robust fallbacks for sparse data, model switching between M/M/1 and M/M/∞, service-rate spikes, drift detection, and the model stale payload flag."
user-invocable: true
---

# 📐 Skill: queue-uncertainty-theory

> Deeper math for confidence intervals, robust fallbacks for sparse data, model switching between M/M/1 and M/M/∞, service-rate spikes, drift detection, and the "model stale" payload flag.

---

## 🔢 Bayesian Confidence Intervals — Full Derivation

### Arrival Rate λ (Poisson process)
```
Observations:  k arrivals in T seconds
Prior:         Gamma(α₀=1, β₀=1)   ← uninformative (1 pseudo-count)

Posterior:     Gamma(α=k+1, β=T)
                 mean = (k+1)/T
                 mode = k/T           ← maximum likelihood estimate
                 variance = (k+1)/T²

95% Credible Interval:
  lower = gamma_ppf(0.025, α, scale=1/β)
  upper = gamma_ppf(0.975, α, scale=1/β)
```

### Service Rate μ (exponential service times)
```
Observations:  n completions in T seconds
Prior:         Gamma(α₀=1, β₀=1)

Posterior:     Gamma(α=n+1, β=T)
  (identical form to λ — same conjugate structure)
```

### Python Implementation
```python
from scipy.stats import gamma as gamma_dist
import numpy as np

def lambda_posterior_ci(arrivals: int, window_seconds: float,
                         confidence: float = 0.95) -> tuple[float, float, float]:
    """
    Returns (point_estimate, ci_lower, ci_upper) for arrival rate.
    Uses Gamma(alpha=arrivals+1, scale=1/window) posterior.
    """
    alpha = arrivals + 1
    beta  = window_seconds        # rate parameter
    scale = 1.0 / beta            # scipy uses scale=1/rate

    tail = (1 - confidence) / 2
    lower = gamma_dist.ppf(tail,    alpha, scale=scale)
    upper = gamma_dist.ppf(1-tail,  alpha, scale=scale)
    mean  = alpha / beta

    return mean, lower, upper

def mu_posterior_ci(exits: int, window_seconds: float,
                    confidence: float = 0.95) -> tuple[float, float, float]:
    """Same structure as lambda — service completions are also Poisson."""
    return lambda_posterior_ci(exits, window_seconds, confidence)
```

---

## ⚠️ Robust Fallbacks for Sparse Data (n < 10)

When few events have been observed, CIs become very wide and point estimates are unreliable. Apply these fallbacks:

```python
MIN_ARRIVALS_FOR_RELIABLE_CI = 5    # Below this → "HIGH" uncertainty forced
MIN_EXITS_FOR_RELIABLE_CI    = 5
MIN_WINDOW_SECONDS           = 30   # Don't compute rates on windows shorter than this

def classify_uncertainty(arrivals: int, exits: int,
                          ci_width_lambda: float, ci_width_mu: float,
                          lambda_mean: float, mu_mean: float) -> str:
    """
    Classify uncertainty level. Priority order matters (worst first).
    """
    # Sparse data override — always HIGH
    if arrivals < MIN_ARRIVALS_FOR_RELIABLE_CI or exits < MIN_EXITS_FOR_RELIABLE_CI:
        return "HIGH"

    # CI width relative to point estimate
    rel_lambda = ci_width_lambda / (lambda_mean + 1e-9)
    rel_mu     = ci_width_mu    / (mu_mean + 1e-9)

    if rel_lambda > 0.8 or rel_mu > 0.8:
        return "HIGH"
    if rel_lambda > 0.4 or rel_mu > 0.4:
        return "MEDIUM"
    return "LOW"
```

### Sparse Data Output Conventions
```python
# When data is insufficient to compute W reliably:
SPARSE_PAYLOAD_DEFAULTS = {
    "wait_time_seconds": -1.0,           # sentinel: "unknown"
    "wait_time_ci": [-1.0, -1.0],       # sentinel: "unknown"
    "queue_stable": False,               # conservative default
    "uncertainty": {"level": "HIGH"},
}
# Frontend and n8n must handle wait_time_seconds == -1 as "Insufficient data"
```

---

## 🔄 Model Switching: M/M/1 → M/M/∞

### When to Use Each Model

| Model | When | Formula |
|-------|------|---------|
| **M/M/1** | Single cashier / server | `W = λ / (μ - λ)` |
| **M/M/c** | Multiple servers (c cashiers) | See below |
| **M/M/∞** | Self-service / unlimited capacity | `W = 1/μ` (just service time) |
| **M/G/1** | Non-exponential service (e.g., retail mix) | `W = λE[S²] / (2(1-ρ)) + 1/μ` |

### M/M/c Formula (c servers)
```python
import math
from scipy.special import factorial

def erlang_c(lambda_: float, mu: float, c: int) -> float:
    """
    Erlang-C formula: probability that an arriving customer must wait.
    Returns P(wait) — used to compute W for M/M/c queue.
    """
    rho = lambda_ / (c * mu)
    if rho >= 1.0:
        return 1.0  # System saturated

    a = lambda_ / mu  # traffic intensity
    sum_terms = sum((a**n) / math.factorial(n) for n in range(c))
    last_term  = (a**c) / (math.factorial(c) * (1 - rho))
    C = last_term / (sum_terms + last_term)
    return C

def wait_time_mmc(lambda_: float, mu: float, c: int) -> float:
    """Expected wait time (in queue) for M/M/c model."""
    rho = lambda_ / (c * mu)
    if rho >= 1.0:
        return float("inf")
    C = erlang_c(lambda_, mu, c)
    W_q = C / (c * mu - lambda_)   # Wait in queue (not counting service time)
    W   = W_q + 1 / mu              # Total: wait + service
    return W

# Usage:
# Two cashiers open:
# W = wait_time_mmc(lambda_=0.15, mu=0.10, c=2)
```

### Model Selection Logic
```python
def select_queue_model(num_servers: int, service_type: str) -> str:
    if service_type == "self_service":
        return "MM_inf"
    if num_servers == 1:
        return "MM1"
    if num_servers >= 2:
        return "MMc"
    return "MM1"   # fallback
```

---

## 📉 Service-Rate Spike Detection

A sudden increase in μ may indicate:
- A second cashier opened → real increase, expected
- Tracker ID confusion → apparent rapid exits without real service

```python
MU_SPIKE_MULTIPLIER = 2.0   # Flag if μ jumps by 2× in one window

def detect_service_spike(current_mu: float, ema_mu: float) -> bool:
    return current_mu > ema_mu * MU_SPIKE_MULTIPLIER and current_mu > 0.1

def detect_service_degradation(current_mu: float, baseline_mu: float,
                                drop_fraction: float = 0.4) -> bool:
    """Service rate dropped 40% below baseline — possible cashier break."""
    return current_mu < baseline_mu * (1 - drop_fraction)
```

---

## 🕵️ Drift Detection & "Model Stale" Flag

### Why Drift Happens
- Lighting changes affect detection → apparent changes in λ/μ that aren't real
- Time of day changes queue behavior (M/M/1 assumptions drift)
- Long-running system without recalibration

### Drift Detection (CUSUM)
```python
class CUSUMDriftDetector:
    """
    Cumulative sum control chart for detecting parameter drift in λ or μ.
    Raises flag when cumulative deviation exceeds threshold.
    """
    def __init__(self, k: float = 0.5, h: float = 5.0):
        """
        k: allowance (half the expected shift size in std devs)
        h: decision threshold (5.0 is standard for 5-sigma detection)
        """
        self.k   = k
        self.h   = h
        self.S_pos = 0.0
        /* Lines 209-211 omitted */
        self.std   = None

    def update(self, value: float) -> bool:
        """Returns True if drift detected."""
        /* Lines 215-223 omitted */
        return self.S_pos > self.h or self.S_neg > self.h
```

### Model Stale Flag in Payload
```python
# Add to payload when drift detected or data window is old
"model_meta": {
    "model_type": "MM1",          # or "MMc", "MM_inf"
    "num_servers": 1,
    "window_seconds": 300,
    "observations_count": 8,
    "model_stale": True,          # ← True if drift detected OR last calibration > 15 min ago
    "stale_reason": "drift_detected",   # or "window_expired", "sparse_data"
    "last_calibrated_at": "2026-03-05T14:00:00Z"
}
```

---

## 🔃 Stable vs Unsteady Queue Semantics

```
STABLE queue:    λ < μ     → System drains over time, W is finite
NEAR SATURATION: λ ≈ μ     → W → very large; small fluctuations cause huge swings
UNSTEADY queue:  λ > μ     → System grows without bound; W = ∞ (model breaks down)

Classification:
  utilization ρ = λ / μ

  ρ < 0.70  → Stable, low utilization (comfortable)
  0.70 ≤ ρ < 0.90  → Stable, moderate utilization (normal busy)
  0.90 ≤ ρ < 1.00  → Stable but near saturation (WARN: small λ increase → crisis)
  ρ ≥ 1.00  → Unsteady (queue_stable = False, W reported as 999 sentinel)
```

```python
def classify_queue_stability(lambda_: float, mu: float) -> tuple[bool, str]:
    if mu <= 0:
        return False, "unsteady_zero_service"
    rho = lambda_ / mu
    if rho >= 1.0:
        return False, "unsteady_overflow"
    if rho >= 0.90:
        return True,  "near_saturation"
    if rho >= 0.70:
        return True,  "moderate"
    return True, "low_utilization"
```

---

## 🧪 Unit Tests for Uncertainty Math

```python
# tests/test_uncertainty.py
import pytest
from analysis.uncertainty import lambda_posterior_ci, classify_uncertainty
import math


def test_ci_contains_true_rate():
    # With 30 arrivals in 200s, true rate = 0.15 — CI should contain it
    mean, lo, hi = lambda_posterior_ci(30, 200)
    assert lo < 0.15 < hi


def test_sparse_data_forces_high_uncertainty():
    level = classify_uncertainty(arrivals=3, exits=2,
                                  ci_width_lambda=0.5, ci_width_mu=0.4,
                                  lambda_mean=0.1, mu_mean=0.15)
    assert level == "HIGH"


def test_mm1_wait_time_known_values():
    # λ=0.15, μ=0.20 → W = 0.15/(0.20-0.15) = 3.0s
    from analysis.queue_metrics import wait_time_mm1
    W = wait_time_mm1(lambda_=0.15, mu=0.20)
    assert abs(W - 3.0) < 0.01


def test_mm1_unstable_returns_sentinel():
    from analysis.queue_metrics import wait_time_mm1
    W = wait_time_mm1(lambda_=0.20, mu=0.15)
    assert W == 999.0 or math.isinf(W)
```

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*