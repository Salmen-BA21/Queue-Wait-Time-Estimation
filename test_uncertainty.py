"""
Unit tests for uncertainty quantification module.

Tests the Bayesian and variance-based uncertainty estimation methods.
"""

import unittest

import numpy as np

from src.uncertainty import (
    UncertaintyEstimate,
    classify_uncertainty_level,
    estimate_rate_uncertainty,
    estimate_uncertainty_from_detection_confidence,
    estimate_wait_time_uncertainty_from_variance,
    get_uncertainty_summary,
)


class TestRateUncertainty(unittest.TestCase):
    """Test Bayesian Gamma-based rate uncertainty estimation."""

    def test_zero_events(self):
        """When no events observed, rate should be zero with narrow bounds."""
        result = estimate_rate_uncertainty(0, 10.0)
        self.assertEqual(result.mean, 0.1)  # 0/10 = 0, but Gamma(1,10) mean = 1/10
        self.assertGreaterEqual(result.lower, 0.0)
        self.assertLessEqual(result.lower, result.mean)
        self.assertEqual(result.method, "bayesian_gamma")

    def test_positive_events(self):
        """With positive event count, interval should bound the estimate."""
        result = estimate_rate_uncertainty(5, 10.0)
        self.assertAlmostEqual(result.mean, 0.6, places=2)  # 6/10
        self.assertGreater(result.upper, result.mean)
        self.assertLess(result.lower, result.mean)
        self.assertGreaterEqual(result.lower, 0.0)

    def test_confidence_level(self):
        """Higher confidence level should give wider intervals."""
        result_90 = estimate_rate_uncertainty(5, 10.0, confidence=0.90)
        result_99 = estimate_rate_uncertainty(5, 10.0, confidence=0.99)
        width_90 = result_90.upper - result_90.lower
        width_99 = result_99.upper - result_99.lower
        self.assertLess(width_90, width_99)

    def test_invalid_window(self):
        """Zero or negative window should return zero estimate."""
        result = estimate_rate_uncertainty(5, 0)
        self.assertEqual(result.mean, 0.0)
        self.assertEqual(result.lower, 0.0)
        self.assertEqual(result.upper, 0.0)


class TestVarianceUncertainty(unittest.TestCase):
    """Test variance-based wait time uncertainty."""

    def test_insufficient_samples(self):
        """With fewer than min_samples, should return point estimate."""
        result = estimate_wait_time_uncertainty_from_variance([5.0, 5.1])
        self.assertEqual(result.mean, 5.05)
        self.assertEqual(result.lower, result.mean)
        self.assertEqual(result.upper, result.mean)

    def test_consistent_measurements(self):
        """Consistent measurements should give narrow interval."""
        waits = [5.0, 5.0, 5.0, 5.0, 5.0]
        result = estimate_wait_time_uncertainty_from_variance(waits)
        self.assertAlmostEqual(result.mean, 5.0, places=1)
        # Interval should be very tight for consistent data
        width = result.upper - result.lower
        self.assertLess(width, 0.1)

    def test_variable_measurements(self):
        """Variable measurements should give wider interval."""
        waits_tight = [5.0, 5.0, 5.0, 5.0, 5.0]
        waits_loose = [4.0, 5.0, 6.0, 4.5, 5.5]
        
        result_tight = estimate_wait_time_uncertainty_from_variance(waits_tight)
        result_loose = estimate_wait_time_uncertainty_from_variance(waits_loose)
        
        width_tight = result_tight.upper - result_tight.lower
        width_loose = result_loose.upper - result_loose.lower
        self.assertLess(width_tight, width_loose)


class TestConfidenceWeightedUncertainty(unittest.TestCase):
    """Test confidence-weighted uncertainty from detection scores."""

    def test_high_confidence(self):
        """High confidence detections should give narrow interval."""
        high_conf = [0.95, 0.96, 0.94, 0.95]
        result = estimate_uncertainty_from_detection_confidence(5.0, high_conf)
        width = result.upper - result.lower
        self.assertGreater(result.upper, result.mean)
        self.assertLess(result.lower, result.mean)

    def test_low_confidence(self):
        """Low confidence detections should give wider interval."""
        low_conf = [0.60, 0.65, 0.58, 0.62]
        result = estimate_uncertainty_from_detection_confidence(5.0, low_conf)
        width = result.upper - result.lower
        # Lower confidence should give wider intervals
        self.assertGreater(width, 5.0 * 0.5)  # At least 50% relative width

    def test_no_scores(self):
        """Empty score list should return point estimate."""
        result = estimate_uncertainty_from_detection_confidence(5.0, [])
        self.assertEqual(result.mean, 5.0)
        self.assertEqual(result.lower, 5.0)
        self.assertEqual(result.upper, 5.0)


class TestUncertaintyClassification(unittest.TestCase):
    """Test uncertainty level classification."""

    def test_low_uncertainty(self):
        """Narrow intervals should be classified as Low."""
        unc = UncertaintyEstimate(mean=5.0, lower=4.95, upper=5.05)
        level = classify_uncertainty_level(unc)
        self.assertEqual(level, "Low")

    def test_medium_uncertainty(self):
        """Medium-width intervals should be classified as Medium."""
        unc = UncertaintyEstimate(mean=5.0, lower=3.5, upper=6.5)  # 30% margin
        level = classify_uncertainty_level(unc)
        self.assertEqual(level, "Medium")

    def test_high_uncertainty(self):
        """Wide intervals should be classified as High."""
        unc = UncertaintyEstimate(mean=5.0, lower=2.5, upper=7.5)
        level = classify_uncertainty_level(unc)
        self.assertEqual(level, "High")


class TestUncertaintySummary(unittest.TestCase):
    """Test uncertainty summary string generation."""

    def test_summary_format(self):
        """Summary should be human-readable and include uncertainty level."""
        unc = UncertaintyEstimate(mean=5.2, lower=4.6, upper=5.8)
        summary = get_uncertainty_summary(unc)
        # Should contain value, margin, and level
        self.assertIn("5.2", summary)
        self.assertIn("0.6", summary)  # margin = (5.8 - 4.6) / 2
        self.assertIn("Low", summary)

    def test_summary_with_explicit_estimate(self):
        """Should use explicit point estimate if provided."""
        unc = UncertaintyEstimate(mean=5.0, lower=4.5, upper=5.5)
        summary = get_uncertainty_summary(unc, point_estimate=6.0)
        self.assertIn("6.0", summary)


class TestIntegration(unittest.TestCase):
    """Integration tests for uncertainty quantification workflow."""

    def test_full_workflow(self):
        """Test complete uncertainty estimation workflow."""
        # Simulate rate estimation
        rate_unc = estimate_rate_uncertainty(10, 20.0, confidence=0.95)
        self.assertIsNotNone(rate_unc)
        self.assertEqual(rate_unc.method, "bayesian_gamma")
        
        # Simulate wait time variance
        waits = [5.1, 4.9, 5.2, 5.0, 4.8]
        wait_unc = estimate_wait_time_uncertainty_from_variance(waits)
        self.assertIsNotNone(wait_unc)
        
        # Classify
        level = classify_uncertainty_level(wait_unc)
        self.assertIn(level, ["Low", "Medium", "High"])
        
        # Generate summary
        summary = get_uncertainty_summary(wait_unc)
        self.assertIsInstance(summary, str)
        self.assertIn("±", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
